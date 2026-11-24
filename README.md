# EduCore RM — Simulador de Núcleo Acadêmico, Financeiro e Integração

Projeto prático desenvolvido em **SQL Server (T-SQL)** e **Python** simulando as rotinas centrais de back-end, regras de negócio, governança de dados e integrações de um ERP educacional inspirado no **TOTVS RM (Educacional e Fluxus)**.

---

## Arquitetura e Equivalência Funcional (TOTVS RM)

| Camada / Objeto | Equivalente no TOTVS RM | Responsabilidade |
| :--- | :--- | :--- |
| `PeriodosLetivos`, `Cursos`, `Disciplinas`, `Turmas` | `SPLETIVO`, `SCURSO`, `SDISCIPLINA`, `STURMA` | Estrutura curricular, oferta de vagas e parametrização de turnos/mensalidades. |
| `Alunos`, `Bolsas`, `Matriculas`, `NotasFrequencia` | `SALUNO`, `SBOLSA`, `SMATRICPL`, `SNOTAETAPA` | Gestão discente, regras de bolsas/convênios, enturmação e apuração de notas/faltas. |
| `LancamentosFinanceiros` | `FLAN` / `SLAN` (RM Fluxus) | Controle de competências, descontos calculados, baixas e inadimplência. |
| `trg_NotasFrequencia_Automacao` | Fórmulas Visuais / Gatilhos | Recálculo automático de frequência mínima (75%) e situação (`Aprovado`, `Reprovado Nota`, `Reprovado Falta`). |
| `sp_ProcessarFechamentoDiario` | RM Job Server / Processos Recorrentes | Rotina transacional em lote para atualização diária de parcelas vencidas. |
| `vw_Cubo_*` e `vw_Regra_Elegibilidade_Rematricula` | Cubos Gerenciais / Relatórios RM | Visões multidimensionais acadêmicas, financeiras, ocupação de salas e trava de rematrícula. |
| `LogAuditoriaDados` e `Roles` (RBAC) | Log de Auditoria (`ZLOG`) e Perfis | Rastreabilidade (`SYSTEM_USER`, `APP_NAME()`, antes/depois) e segregação de acesso (LGPD). |
| `scripts/integrador_rm.py` | Integração via API / Webhooks | Ingestão idempotente de ingressantes do vestibular, geração de parcelas e saída JSON para AVA (Moodle/Canvas). |

---

## Estrutura do Repositório

    ├── sql/
    │   ├── 01_schema_e_seed.sql                 # DDL e carga inicial
    │   ├── 02_seguranca_auditoria_automacao.sql # Triggers, Procedures, Auditoria e RBAC
    │   └── 03_views_relatorios_cubos.sql        # Views analíticas (Cubos)
    ├── scripts/
    │   ├── app_crud_rm.py                       # Interface web (Streamlit)
    │   ├── integrador_rm.py                     # Integração JSON -> SQL Server
    │   ├── novas_matriculas_vestibular.json     # Payload de entrada
    │   └── saida_integracao_ava.json            # Payload de saída (AVA)
    └── requirements.txt                         # Dependências Python
---

## Como Executar Localmente

1. **Banco de Dados (SQL Server 2022 + SSMS):**
   Execute os scripts da pasta `sql/` na ordem numérica (`01` -> `02` -> `03`) na instância local (`localhost\SQLEXPRESS`).

2. **Integração Automatizada (Python 3.10+):**

       pip install -r requirements.txt
       python scripts/integrador_rm.py

---

## Fluxo de Arquitetura e Integração

```mermaid
flowchart LR
    subgraph Externo["Sistemas Externos"]
        JSON_IN["novas_matriculas_vestibular.json"]
        JSON_OUT["saida_integracao_ava.json"]
    end

    subgraph App["Camada Python"]
        INT["integrador_rm.py (ETL / pyodbc)"]
        UI["app_crud_rm.py (Interface Web Streamlit)"]
    end

    subgraph DB["SQL Server: EduCore_RM_Simulador"]
        CORE[("Núcleo Acadêmico e Financeiro\nAlunos | Turmas | Matrículas | Parcelas")]
        TRG{{"Triggers e Procedures\nCálculo Nota/Falta + Fechamento Diário"}}
        LOG[("Governança e Auditoria\nLogAuditoriaDados | LogIntegracao")]
        CUBOS["Views Analíticas (Cubos)\nInadimplência | Ocupação | Rematrícula"]
    end

    JSON_IN --> INT
    INT -- "Transação SQL" --> CORE
    INT -- "Provisionamento AVA" --> JSON_OUT
    UI <--> |"CRUD e Consultas"| CORE
    CORE -- "AFTER INSERT/UPDATE" --> TRG
    TRG -- "Atualiza Situação" --> CORE
    TRG -- "Rastreabilidade LGPD" --> LOG
    INT -- "Registra Execução" --> LOG
    CORE --> CUBOS
    CUBOS --> UI
```

---

## Diagrama Entidade-Relacionamento (SQL Server)

```mermaid
erDiagram
    PeriodosLetivos ||--o{ Turmas : "oferta_em"
    PeriodosLetivos ||--o{ LancamentosFinanceiros : "referencia"
    Cursos ||--o{ Disciplinas : "possui_grade"
    Cursos ||--o{ Alunos : "matricula_em"
    Bolsas ||--o{ Alunos : "aplica_desconto"
    Disciplinas ||--o{ Turmas : "abre"
    Alunos ||--o{ LancamentosFinanceiros : "gera"
    Alunos ||--o{ Matriculas : "cursa"
    Turmas ||--o{ Matriculas : "recebe"
    Matriculas ||--|| NotasFrequencia : "avalia"

    PeriodosLetivos {
        int IdPeriodo PK
        varchar CodigoPeriodo UK
        bit Ativo
    }
    Cursos {
        int IdCurso PK
        varchar CodigoCurso UK
        varchar NomeCurso
        decimal ValorMensalidadeBase
    }
    Bolsas {
        int IdBolsa PK
        varchar CodigoBolsa UK
        decimal PercentualDesconto
    }
    Disciplinas {
        int IdDisciplina PK
        int IdCurso FK
        varchar CodigoDisciplina UK
        varchar NomeDisciplina
    }
    Alunos {
        int IdAluno PK
        varchar RA UK
        varchar CPF UK
        int IdCurso FK
        int IdBolsa FK
        varchar StatusAcademico
    }
    Turmas {
        int IdTurma PK
        int IdDisciplina FK
        int IdPeriodo FK
        varchar CodigoTurma UK
        int VagasTotais
    }
    LancamentosFinanceiros {
        int IdLancamento PK
        int IdAluno FK
        int IdPeriodo FK
        varchar Competencia
        decimal ValorLiquido
        varchar StatusPagamento
    }
    Matriculas {
        int IdMatricula PK
        int IdAluno FK
        int IdTurma FK
        varchar SituacaoMatricula
    }
    NotasFrequencia {
        int IdNotaFreq PK
        int IdMatricula FK
        decimal Nota1
        decimal Nota2
        int Faltas
    }
```
