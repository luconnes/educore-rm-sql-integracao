from datetime import date
import pandas as pd
import pyodbc
import streamlit as st

SERVER = r"localhost\SQLEXPRESS"
DATABASE = "EduCore_RM_Simulador"

st.set_page_config(
    page_title="EduCore RM — Gestão Acadêmica e Financeira",
    page_icon="🎓",
    layout="wide",
)


def obter_driver_odbc() -> str:
    drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
    if not drivers:
        raise RuntimeError("Nenhum driver ODBC do SQL Server encontrado.")
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


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("SET DATEFORMAT ymd;")
        cursor.execute(sql, params)
        cols = [col[0] for col in cursor.description]
        rows = [tuple(row) for row in cursor.fetchall()]
        return pd.DataFrame(rows, columns=cols)


# ============================================================================
# CABEÇALHO E MENU LATERAL
# ============================================================================
st.title("🎓 EduCore RM — Simulador Acadêmico, Financeiro e Auditoria")
st.caption(f"Conectado à instância SQL Server: `{SERVER}` | Banco: `{DATABASE}`")

with st.sidebar:
    st.header("Módulos do ERP")
    menu = st.radio(
        "Selecione a visão:",
        [
            "1. Painel Gerencial",
            "2. CRUD de Alunos e Matrículas",
            "3. Notas e Frequência",
            "4. Financeiro e Logs de Auditoria",
        ],
    )
    st.divider()
    st.subheader("Automação em Lote")
    data_job = st.date_input("Data de referência do fechamento:", value=date(2026, 12, 15))
    if st.button("Executar Fechamento Diário"):
        try:
            with conectar_banco() as conn:
                cur = conn.cursor()
                cur.execute("SET DATEFORMAT ymd;")
                cur.execute("EXEC sp_ProcessarFechamentoDiario @DataReferencia = ?", (data_job.strftime("%Y%m%d"),))
                conn.commit()
            st.success("Procedure sp_ProcessarFechamentoDiario executada!")
        except Exception as e:
            st.error(f"Erro ao executar job: {e}")

# ============================================================================
# MÓDULO 1: PAINEL GERENCIAL (CUBOS)
# ============================================================================
if menu == "1. Painel Gerencial":
    st.subheader("Visão Multidimensional")

    df_alunos = query_df("SELECT StatusAcademico FROM Alunos")
    df_fin = query_df("SELECT ReceitaRealizada, SaldoInadimplente, SaldoEmAberto FROM vw_Cubo_Financeiro_Inadimplencia")
    df_ocup = query_df("SELECT * FROM vw_Relatorio_Ocupacao_Turmas")
    df_remat = query_df("SELECT * FROM vw_Regra_Elegibilidade_Rematricula")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Alunos Ativos", int((df_alunos["StatusAcademico"] == "Ativo").sum()))
    col2.metric("Receita Realizada", f"R$ {float(df_fin['ReceitaRealizada'].sum()):,.2f}")
    col3.metric("Saldo Inadimplente", f"R$ {float(df_fin['SaldoInadimplente'].sum()):,.2f}")
    col4.metric("Ocupação Média Salas", f"{float(df_ocup['PercentualOcupacao'].mean()):.1f}%")

    tab1, tab2, tab3 = st.tabs(["Cubo Financeiro", "Ocupação de Turmas", "Elegibilidade Rematrícula"])
    with tab1:
        df_cubo_fin = query_df("SELECT * FROM vw_Cubo_Financeiro_Inadimplencia ORDER BY Competencia DESC, Curso")
        st.dataframe(df_cubo_fin, hide_index=True)
    with tab2:
        st.dataframe(df_ocup, hide_index=True)
    with tab3:
        st.dataframe(df_remat, hide_index=True)

# ============================================================================
# MÓDULO 2: CRUD DE ALUNOS E MATRÍCULAS
# ============================================================================
elif menu == "2. CRUD de Alunos e Matrículas":
    st.subheader("Gestão Discente — Create, Read, Update e Delete")

    aba_read, aba_create, aba_update, aba_delete = st.tabs(
        ["📋 Consultar", "➕ Novo Aluno", "✏️ Editar Aluno", "🗑️ Excluir Aluno"]
    )

    df_cursos = query_df("SELECT IdCurso, CodigoCurso, NomeCurso, ValorMensalidadeBase FROM Cursos")
    df_bolsas = query_df("SELECT IdBolsa, CodigoBolsa, Descricao, PercentualDesconto FROM Bolsas")

    # READ
    with aba_read:
        filtro_nome = st.text_input("Buscar por Nome ou RA:")
        sql_read = """
            SELECT a.IdAluno, a.RA, a.NomeCompleto, a.CPF, a.Email,
                   c.NomeCurso AS Curso, b.Descricao AS Bolsa, a.StatusAcademico, a.DataIngresso
            FROM Alunos a
            INNER JOIN Cursos c ON a.IdCurso = c.IdCurso
            INNER JOIN Bolsas b ON a.IdBolsa = b.IdBolsa
            WHERE a.NomeCompleto LIKE ? OR a.RA LIKE ?
            ORDER BY a.IdAluno DESC
        """
        df_lista = query_df(sql_read, (f"%{filtro_nome}%", f"%{filtro_nome}%"))
        st.dataframe(df_lista, hide_index=True)

    # CREATE
    with aba_create:
        with st.form("form_create_aluno"):
            c1, c2 = st.columns(2)
            ra = c1.text_input("RA (Registro Acadêmico)", value="20262201")
            cpf = c2.text_input("CPF (11 dígitos)", value="88192039481", max_chars=11)
            nome = st.text_input("Nome Completo", value="Camila Vasconcelos Ferreira")
            email = c1.text_input("E-mail Institucional", value="camila.ferreira@aluno.educore.edu.br")
            dt_nasc = c2.date_input("Data de Nascimento", value=date(2005, 5, 10))

            curso_opcoes = {f"{r['CodigoCurso']} - {r['NomeCurso']}": int(r["IdCurso"]) for _, r in df_cursos.iterrows()}
            bolsa_opcoes = {f"{r['Descricao']}": int(r["IdBolsa"]) for _, r in df_bolsas.iterrows()}

            curso_sel = c1.selectbox("Curso", list(curso_opcoes.keys()))
            bolsa_sel = c2.selectbox("Bolsa / Convênio", list(bolsa_opcoes.keys()))
            gerar_acad_fin = st.checkbox("Matricular automaticamente nas turmas de 2026.2 e gerar 1ª parcela", value=True)

            submitted = st.form_submit_button("Cadastrar Aluno no SQL Server")
            if submitted:
                cpf_limpo = "".join(filter(str.isdigit, cpf))
                if len(cpf_limpo) != 11 or not nome.strip() or not ra.strip():
                    st.warning("Preencha RA, Nome Completo e um CPF válido com 11 dígitos.")
                else:
                    try:
                        with conectar_banco() as conn:
                            cur = conn.cursor()
                            cur.execute("SET DATEFORMAT ymd;")
                            id_curso = curso_opcoes[curso_sel]
                            id_bolsa = bolsa_opcoes[bolsa_sel]

                            cur.execute(
                                """
                                INSERT INTO Alunos (RA, NomeCompleto, CPF, Email, DataNascimento, IdCurso, IdBolsa, StatusAcademico, DataIngresso)
                                OUTPUT INSERTED.IdAluno
                                VALUES (?, ?, ?, ?, ?, ?, ?, 'Ativo', '20260803')
                                """,
                                (ra.strip(), nome.strip(), cpf_limpo, email.strip(), dt_nasc.strftime("%Y%m%d"), id_curso, id_bolsa),
                            )
                            novo_id = cur.fetchone()[0]

                            if gerar_acad_fin:
                                cur.execute(
                                    """
                                    SELECT t.IdTurma FROM Turmas t
                                    INNER JOIN Disciplinas d ON t.IdDisciplina = d.IdDisciplina
                                    WHERE d.IdCurso = ? AND t.IdPeriodo = 2
                                    """,
                                    (id_curso,),
                                )
                                for (id_turma,) in cur.fetchall():
                                    cur.execute(
                                        "INSERT INTO Matriculas (IdAluno, IdTurma, SituacaoMatricula) OUTPUT INSERTED.IdMatricula VALUES (?, ?, 'Cursando')",
                                        (novo_id, id_turma),
                                    )
                                    id_mat = cur.fetchone()[0]
                                    cur.execute(
                                        "INSERT INTO NotasFrequencia (IdMatricula, Nota1, Nota2, AulasDadas, Faltas) VALUES (?, NULL, NULL, 60, 0)",
                                        (id_mat,),
                                    )

                                cur.execute("SELECT ValorMensalidadeBase FROM Cursos WHERE IdCurso = ?", (id_curso,))
                                v_base = float(cur.fetchone()[0])
                                cur.execute("SELECT PercentualDesconto FROM Bolsas WHERE IdBolsa = ?", (id_bolsa,))
                                p_desc = float(cur.fetchone()[0])
                                v_desc = round(v_base * (p_desc / 100.0), 2)

                                cur.execute(
                                    """
                                    INSERT INTO LancamentosFinanceiros (IdAluno, IdPeriodo, Competencia, ValorBruto, ValorDesconto, DataVencimento, StatusPagamento)
                                    VALUES (?, 2, '2026-12', ?, ?, '20261210', 'Em Aberto')
                                    """,
                                    (novo_id, v_base, v_desc),
                                )

                            cur.execute(
                                "INSERT INTO LogIntegracao (OrigemProcesso, ChaveRegistro, StatusIntegracao, Mensagem) VALUES ('CRUD_WEB_UI', ?, 'Sucesso', ?)",
                                (ra.strip(), f"Aluno {nome.strip()} cadastrado via interface web."),
                            )
                            conn.commit()
                        st.success(f"Aluno '{nome}' (RA {ra}) cadastrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")

    # UPDATE
    with aba_update:
        df_alunos_upd = query_df("SELECT IdAluno, RA, NomeCompleto, Email, IdCurso, IdBolsa, StatusAcademico FROM Alunos ORDER BY IdAluno DESC")
        opcoes_upd = {f"{r['RA']} - {r['NomeCompleto']}": r for _, r in df_alunos_upd.iterrows()}
        aluno_escolhido = st.selectbox("Selecione o aluno para editar:", list(opcoes_upd.keys()))
        reg = opcoes_upd[aluno_escolhido]

        with st.form("form_update_aluno"):
            novo_email = st.text_input("E-mail", value=str(reg["Email"]))
            status_lista = ["Ativo", "Trancado", "Evadido", "Concluido"]
            novo_status = st.selectbox("Status Acadêmico", status_lista, index=status_lista.index(reg["StatusAcademico"]))

            bolsa_map = {int(r["IdBolsa"]): f"{r['Descricao']}" for _, r in df_bolsas.iterrows()}
            bolsa_rev = {v: k for k, v in bolsa_map.items()}
            nova_bolsa_nome = st.selectbox("Bolsa", list(bolsa_rev.keys()), index=list(bolsa_rev.keys()).index(bolsa_map[int(reg["IdBolsa"])]))

            if st.form_submit_button("Salvar Alterações"):
                try:
                    with conectar_banco() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE Alunos SET Email = ?, StatusAcademico = ?, IdBolsa = ? WHERE IdAluno = ?",
                            (novo_email.strip(), novo_status, bolsa_rev[nova_bolsa_nome], int(reg["IdAluno"])),
                        )
                        conn.commit()
                    st.success("Cadastro atualizado com sucesso! Recarregue a aba de consulta para ver.")
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")

    # DELETE
    with aba_delete:
        df_alunos_del = query_df("SELECT IdAluno, RA, NomeCompleto, StatusAcademico FROM Alunos ORDER BY IdAluno DESC")
        opcoes_del = {f"{r['RA']} - {r['NomeCompleto']} ({r['StatusAcademico']})": int(r["IdAluno"]) for _, r in df_alunos_del.iterrows()}
        aluno_del = st.selectbox("Selecione o aluno para excluir:", list(opcoes_del.keys()))
        confirmar = st.checkbox("Confirmo a exclusão do aluno e de seus vínculos acadêmicos/financeiros de teste")

        if st.button("Excluir Registro"):
            if not confirmar:
                st.warning("Marque a caixa de confirmação antes de excluir.")
            else:
                try:
                    id_del = opcoes_del[aluno_del]
                    with conectar_banco() as conn:
                        cur = conn.cursor()
                        cur.execute("DELETE nf FROM NotasFrequencia nf INNER JOIN Matriculas m ON nf.IdMatricula = m.IdMatricula WHERE m.IdAluno = ?", (id_del,))
                        cur.execute("DELETE FROM Matriculas WHERE IdAluno = ?", (id_del,))
                        cur.execute("DELETE FROM LancamentosFinanceiros WHERE IdAluno = ?", (id_del,))
                        cur.execute("DELETE FROM Alunos WHERE IdAluno = ?", (id_del,))
                        conn.commit()
                    st.success("Registro removido com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")

# ============================================================================
# MÓDULO 3: NOTAS E FREQUÊNCIA (DISPARA TRIGGER + AUDITORIA)
# ============================================================================
elif menu == "3. Notas e Frequência":
    st.subheader("Lançamento de Notas e Faltas")
    st.info("Ao salvar notas ou faltas abaixo, a Trigger `trg_NotasFrequencia_Automacao` recalcula automaticamente a situação da matrícula (Média >= 7.0 e Frequência >= 75%) e grava a alteração em `LogAuditoriaDados`.")

    df_mat = query_df(
        """
        SELECT m.IdMatricula, a.RA, a.NomeCompleto, d.NomeDisciplina,
               nf.Nota1, nf.Nota2, nf.Faltas, nf.AulasDadas, m.SituacaoMatricula
        FROM Matriculas m
        INNER JOIN Alunos a ON m.IdAluno = a.IdAluno
        INNER JOIN Turmas t ON m.IdTurma = t.IdTurma
        INNER JOIN Disciplinas d ON t.IdDisciplina = d.IdDisciplina
        INNER JOIN NotasFrequencia nf ON m.IdMatricula = nf.IdMatricula
        ORDER BY a.RA, d.NomeDisciplina
        """
    )

    opcoes_mat = {
        f"{r['RA']} | {r['NomeCompleto']} — {r['NomeDisciplina']} [{r['SituacaoMatricula']}]": r
        for _, r in df_mat.iterrows()
    }
    sel_mat = st.selectbox("Selecione a matrícula:", list(opcoes_mat.keys()))
    row_m = opcoes_mat[sel_mat]

    with st.form("form_notas"):
        c1, c2, c3 = st.columns(3)
        n1 = c1.number_input("Nota 1", min_value=0.0, max_value=10.0, value=float(row_m["Nota1"]) if pd.notnull(row_m["Nota1"]) else 7.0, step=0.5)
        n2 = c2.number_input("Nota 2", min_value=0.0, max_value=10.0, value=float(row_m["Nota2"]) if pd.notnull(row_m["Nota2"]) else 7.0, step=0.5)
        faltas = c3.number_input("Faltas (de 60 aulas)", min_value=0, max_value=60, value=int(row_m["Faltas"]), step=1)

        if st.form_submit_button("Gravar Notas e Acionar Trigger"):
            try:
                with conectar_banco() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE NotasFrequencia SET Nota1 = ?, Nota2 = ?, Faltas = ? WHERE IdMatricula = ?",
                        (n1, n2, int(faltas), int(row_m["IdMatricula"])),
                    )
                    conn.commit()
                st.success("Notas salvas! Confira na tabela abaixo a situação atualizada pela Trigger:")
            except Exception as e:
                st.error(f"Erro ao gravar notas: {e}")

    df_atualizado = query_df(
        """
        SELECT a.RA, a.NomeCompleto, d.NomeDisciplina, nf.Nota1, nf.Nota2,
               nf.Faltas, m.SituacaoMatricula
        FROM Matriculas m
        INNER JOIN Alunos a ON m.IdAluno = a.IdAluno
        INNER JOIN Turmas t ON m.IdTurma = t.IdTurma
        INNER JOIN Disciplinas d ON t.IdDisciplina = d.IdDisciplina
        INNER JOIN NotasFrequencia nf ON m.IdMatricula = nf.IdMatricula
        WHERE m.IdMatricula = ?
        """,
        (int(row_m["IdMatricula"]),),
    )
    st.dataframe(df_atualizado, hide_index=True)

# ============================================================================
# MÓDULO 4: FINANCEIRO E LOGS DE AUDITORIA (LGPD)
# ============================================================================
elif menu == "4. Financeiro e Logs de Auditoria":
    st.subheader("Baixa de Mensalidades e Trilha de Auditoria")

    df_parc = query_df(
        """
        SELECT TOP 25 lf.IdLancamento, a.RA, a.NomeCompleto, lf.Competencia,
               lf.ValorBruto, lf.ValorDesconto, lf.ValorLiquido, lf.DataVencimento, lf.StatusPagamento
        FROM LancamentosFinanceiros lf
        INNER JOIN Alunos a ON lf.IdAluno = a.IdAluno
        ORDER BY lf.IdLancamento DESC
        """
    )

    opcoes_parc = {
        f"ID {r['IdLancamento']} | {r['RA']} - {r['NomeCompleto']} ({r['Competencia']}) — R$ {float(r['ValorLiquido']):.2f} [{r['StatusPagamento']}]": r
        for _, r in df_parc.iterrows()
    }
    sel_parc = st.selectbox("Selecione a parcela para baixar ou alterar:", list(opcoes_parc.keys()))
    row_p = opcoes_parc[sel_parc]

    col_a, col_b = st.columns(2)
    novo_st_fin = col_a.selectbox("Novo Status Financeiro", ["Pago", "Em Aberto", "Vencido", "Cancelado"])
    novo_desc = col_b.number_input("Valor de Desconto (R$)", min_value=0.0, max_value=float(row_p["ValorBruto"]), value=float(row_p["ValorDesconto"]), step=10.0)

    if st.button("Atualizar Parcela"):
        try:
            with conectar_banco() as conn:
                cur = conn.cursor()
                cur.execute("SET DATEFORMAT ymd;")
                dt_pgto = date.today().strftime("%Y%m%d") if novo_st_fin == "Pago" else None
                cur.execute(
                    "UPDATE LancamentosFinanceiros SET StatusPagamento = ?, ValorDesconto = ?, DataPagamento = ? WHERE IdLancamento = ?",
                    (novo_st_fin, novo_desc, dt_pgto, int(row_p["IdLancamento"])),
                )
                conn.commit()
            st.success("Parcela atualizada e registrada na trilha de auditoria!")
        except Exception as e:
            st.error(f"Erro financeiro: {e}")

    st.divider()
    st.markdown("### Trilha de Auditoria de Dados (`LogAuditoriaDados`)")
    df_aud = query_df("SELECT TOP 15 * FROM LogAuditoriaDados ORDER BY IdAuditoria DESC")
    st.dataframe(df_aud, hide_index=True)

    st.markdown("### Log de Integrações e Rotinas Batch (`LogIntegracao`)")
    df_int = query_df("SELECT TOP 15 * FROM LogIntegracao ORDER BY IdLog DESC")
    st.dataframe(df_int, hide_index=True)
