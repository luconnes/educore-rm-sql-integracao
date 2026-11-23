import json
from datetime import datetime
from pathlib import Path
import pyodbc

SERVER = r"localhost\SQLEXPRESS"
DATABASE = "EduCore_RM_Simulador"
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "novas_matriculas_vestibular.json"
OUTPUT_FILE = BASE_DIR / "saida_integracao_ava.json"


def obter_driver_odbc() -> str:
    drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
    if not drivers:
        raise RuntimeError("Nenhum driver ODBC do SQL Server encontrado na máquina.")
    # Prioriza drivers modernos (18 ou 17)
    for preferido in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if preferido in drivers:
            return preferido
    return drivers[-1]


def conectar_banco() -> pyodbc.Connection:
    driver = obter_driver_odbc()
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, autocommit=False)


def registrar_log(cursor: pyodbc.Cursor, chave: str, status: str, mensagem: str) -> None:
    cursor.execute(
        """
        INSERT INTO LogIntegracao (OrigemProcesso, ChaveRegistro, StatusIntegracao, Mensagem)
        VALUES (?, ?, ?, ?)
        """,
        ("API_VESTIBULAR_RM", chave, status, mensagem[:500]),
    )


def processar_integracao() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {INPUT_FILE}")

    candidatos = json.loads(INPUT_FILE.read_text(encoding="utf-8-sig"))
    provisionados_ava = []
    resumo = {"Sucesso": 0, "Ignorado": 0, "Erro": 0}

    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SET DATEFORMAT ymd;")

    print(f"Iniciando integração de {len(candidatos)} registros no banco {DATABASE}...\n")

    for item in candidatos:
        ra = item["ra"]
        cpf = item["cpf"]
        nome = item["nome_completo"]

        try:
            # 1. Validação de Idempotência (CPF ou RA já cadastrado)
            cursor.execute("SELECT IdAluno, RA FROM Alunos WHERE CPF = ? OR RA = ?", (cpf, ra))
            existente = cursor.fetchone()
            if existente:
                msg = f"Aluno já cadastrado no ERP (IdAluno={existente[0]}, RA={existente[1]}). Registro ignorado."
                registrar_log(cursor, cpf, "Ignorado", msg)
                conn.commit()
                resumo["Ignorado"] += 1
                print(f"[IGNORADO] {nome} -> {msg}")
                continue

            # 2. Validação de Curso e Mensalidade Base
            cursor.execute(
                "SELECT IdCurso, NomeCurso, ValorMensalidadeBase FROM Cursos WHERE CodigoCurso = ?",
                (item["codigo_curso"],),
            )
            curso = cursor.fetchone()
            if not curso:
                raise ValueError(f"Código de curso inexistente no cadastro: '{item['codigo_curso']}'")

            id_curso, nome_curso, valor_base = curso

            # 3. Validação de Bolsa
            cursor.execute(
                "SELECT IdBolsa, PercentualDesconto FROM Bolsas WHERE CodigoBolsa = ?",
                (item["codigo_bolsa"],),
            )
            bolsa = cursor.fetchone()
            if not bolsa:
                raise ValueError(f"Código de bolsa inválido: '{item['codigo_bolsa']}'")

            id_bolsa, perc_desconto = bolsa

            # 4. Inserção do Aluno (SALUNO / PPESSOA)
            cursor.execute(
                """
                INSERT INTO Alunos (
                    RA, NomeCompleto, CPF, Email, DataNascimento,
                    IdCurso, IdBolsa, StatusAcademico, DataIngresso
                )
                OUTPUT INSERTED.IdAluno
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Ativo', ?)
                """,
                (
                    ra,
                    nome,
                    cpf,
                    item["email"],
                    item["data_nascimento"].replace("-", ""),
                    id_curso,
                    id_bolsa,
                    item["data_ingresso"].replace("-", ""),
                ),
            )
            id_aluno = cursor.fetchone()[0]

            # 5. Enturmação automática nas turmas ativas do período 2026.2 (IdPeriodo = 2)
            cursor.execute(
                """
                SELECT t.IdTurma, t.CodigoTurma
                FROM Turmas t
                INNER JOIN Disciplinas d ON t.IdDisciplina = d.IdDisciplina
                WHERE d.IdCurso = ? AND t.IdPeriodo = 2
                """,
                (id_curso,),
            )
            turmas = cursor.fetchall()
            codigos_turmas = []

            for id_turma, cod_turma in turmas:
                cursor.execute(
                    """
                    INSERT INTO Matriculas (IdAluno, IdTurma, SituacaoMatricula)
                    OUTPUT INSERTED.IdMatricula
                    VALUES (?, ?, 'Cursando')
                    """,
                    (id_aluno, id_turma),
                )
                id_matricula = cursor.fetchone()[0]

                # Inicializa registro de notas e frequência (dispara trigger acadêmica)
                cursor.execute(
                    """
                    INSERT INTO NotasFrequencia (IdMatricula, Nota1, Nota2, AulasDadas, Faltas)
                    VALUES (?, NULL, NULL, 60, 0)
                    """,
                    (id_matricula,),
                )
                codigos_turmas.append(cod_turma)

            # 6. Geração automática da 1ª parcela financeira (Competência 2026-12)
            valor_desconto = round(float(valor_base) * (float(perc_desconto) / 100.0), 2)
            cursor.execute(
                """
                INSERT INTO LancamentosFinanceiros (
                    IdAluno, IdPeriodo, Competencia, ValorBruto, ValorDesconto,
                    DataVencimento, DataPagamento, StatusPagamento
                )
                VALUES (?, 2, '2026-12', ?, ?, '20261210', NULL, 'Em Aberto')
                """,
                (id_aluno, valor_base, valor_desconto),
            )

            # 7. Auditoria de Sucesso
            msg_sucesso = (
                f"Ingresso concluído: RA={ra}, Curso={nome_curso}, "
                f"Turmas={len(codigos_turmas)}, Desconto={perc_desconto}%."
            )
            registrar_log(cursor, ra, "Sucesso", msg_sucesso)
            conn.commit()

            resumo["Sucesso"] += 1
            print(f"[SUCESSO]  {nome} (RA {ra}) -> Matriculado em {codigos_turmas}")

            # Monta payload de saída para sincronização com Ambiente Virtual (Moodle/Canvas)
            provisionados_ava.append(
                {
                    "ra": ra,
                    "nome": nome,
                    "email_institucional": item["email"],
                    "curso": nome_curso,
                    "turmas_habilitadas": codigos_turmas,
                    "sincronizado_em": datetime.now().isoformat(timespec="seconds"),
                }
            )

        except Exception as exc:
            conn.rollback()
            msg_erro = f"Falha ao processar RA {ra}: {exc}"
            registrar_log(cursor, ra, "Erro", msg_erro)
            conn.commit()
            resumo["Erro"] += 1
            print(f"[ERRO]     {nome} -> {msg_erro}")

    cursor.close()
    conn.close()

    # Grava arquivo de saída da integração
    OUTPUT_FILE.write_text(
        json.dumps(provisionados_ava, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n--- RESUMO DA EXECUÇÃO ---")
    print(f"Sucesso: {resumo['Sucesso']} | Ignorados: {resumo['Ignorado']} | Erros tratados: {resumo['Erro']}")
    print(f"Arquivo de saída para o AVA gerado em: {OUTPUT_FILE}")


if __name__ == "__main__":
    processar_integracao()
