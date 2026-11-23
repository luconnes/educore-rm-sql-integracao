/* ============================================================================
   PROJETO: EduCore RM - Simulador de Núcleo Acadêmico, Financeiro e Integração
   ARQUIVO: 01_schema_e_seed.sql
   SGBD:    SQL Server (T-SQL)
   OBJETIVO: Modelagem relacional inspirada no TOTVS RM Educacional e carga de
             dados fictícios para consultas, cubos gerenciais e automação.
============================================================================ */

SET DATEFORMAT ymd;
GO

IF DB_ID('EduCore_RM_Simulador') IS NULL
BEGIN
    CREATE DATABASE EduCore_RM_Simulador;
END
GO

USE EduCore_RM_Simulador;
GO

SET DATEFORMAT ymd;
GO

-- ============================================================================
-- 1. LIMPEZA SEGURA (ORDEM REVERSA DE DEPENDÊNCIA)
-- ============================================================================
DROP TABLE IF EXISTS LogIntegracao;
DROP TABLE IF EXISTS LancamentosFinanceiros;
DROP TABLE IF EXISTS NotasFrequencia;
DROP TABLE IF EXISTS Matriculas;
DROP TABLE IF EXISTS Turmas;
DROP TABLE IF EXISTS Disciplinas;
DROP TABLE IF EXISTS Alunos;
DROP TABLE IF EXISTS Bolsas;
DROP TABLE IF EXISTS Cursos;
DROP TABLE IF EXISTS PeriodosLetivos;
GO

-- ============================================================================
-- 2. DDL - CRIAÇÃO DAS TABELAS E CONSTRAINTS
-- ============================================================================

-- Períodos Letivos (Ref. RM: SPLETIVO)
CREATE TABLE PeriodosLetivos (
    IdPeriodo     INT IDENTITY(1,1) PRIMARY KEY,
    CodigoPeriodo VARCHAR(10) NOT NULL UNIQUE,
    Descricao     NVARCHAR(100) NOT NULL,
    DataInicio    DATE NOT NULL,
    DataFim       DATE NOT NULL,
    Ativo         BIT NOT NULL DEFAULT 1
);

-- Cursos de Graduação/Tecnólogo (Ref. RM: SCURSO)
CREATE TABLE Cursos (
    IdCurso               INT IDENTITY(1,1) PRIMARY KEY,
    CodigoCurso           VARCHAR(15) NOT NULL UNIQUE,
    NomeCurso             NVARCHAR(120) NOT NULL,
    Turno                 VARCHAR(20) NOT NULL CHECK (Turno IN ('Matutino', 'Vespertino', 'Noturno', 'Integral')),
    ValorMensalidadeBase  DECIMAL(10,2) NOT NULL CHECK (ValorMensalidadeBase > 0),
    CargaHorariaTotal     INT NOT NULL
);

-- Tipos de Bolsas e Convênios (Ref. RM: SBOLSA)
CREATE TABLE Bolsas (
    IdBolsa            INT IDENTITY(1,1) PRIMARY KEY,
    CodigoBolsa        VARCHAR(20) NOT NULL UNIQUE,
    Descricao          NVARCHAR(100) NOT NULL,
    PercentualDesconto DECIMAL(5,2) NOT NULL CHECK (PercentualDesconto BETWEEN 0 AND 100)
);

-- Cadastro de Alunos (Ref. RM: SALUNO / PPESSOA)
CREATE TABLE Alunos (
    IdAluno         INT IDENTITY(1,1) PRIMARY KEY,
    RA              VARCHAR(15) NOT NULL UNIQUE,
    NomeCompleto    NVARCHAR(150) NOT NULL,
    CPF             CHAR(11) NOT NULL UNIQUE,
    Email           NVARCHAR(120) NOT NULL,
    DataNascimento  DATE NOT NULL,
    IdCurso         INT NOT NULL FOREIGN KEY REFERENCES Cursos(IdCurso),
    IdBolsa         INT NOT NULL FOREIGN KEY REFERENCES Bolsas(IdBolsa),
    StatusAcademico VARCHAR(20) NOT NULL CHECK (StatusAcademico IN ('Ativo', 'Trancado', 'Evadido', 'Concluido')),
    DataIngresso    DATE NOT NULL
);

-- Matriz de Disciplinas (Ref. RM: SDISCIPLINA)
CREATE TABLE Disciplinas (
    IdDisciplina     INT IDENTITY(1,1) PRIMARY KEY,
    CodigoDisciplina VARCHAR(15) NOT NULL UNIQUE,
    NomeDisciplina   NVARCHAR(120) NOT NULL,
    IdCurso          INT NOT NULL FOREIGN KEY REFERENCES Cursos(IdCurso),
    PeriodoGrade     INT NOT NULL,
    CargaHoraria     INT NOT NULL
);

-- Oferta de Turmas por Período (Ref. RM: STURMA / STURMADISC)
CREATE TABLE Turmas (
    IdTurma      INT IDENTITY(1,1) PRIMARY KEY,
    CodigoTurma  VARCHAR(20) NOT NULL UNIQUE,
    IdPeriodo    INT NOT NULL FOREIGN KEY REFERENCES PeriodosLetivos(IdPeriodo),
    IdDisciplina INT NOT NULL FOREIGN KEY REFERENCES Disciplinas(IdDisciplina),
    Professor    NVARCHAR(120) NOT NULL,
    Sala         VARCHAR(20) NOT NULL,
    VagasTotais  INT NOT NULL CHECK (VagasTotais > 0)
);

-- Matrículas nas Turmas (Ref. RM: SMATRICPL / SMATRICULA)
CREATE TABLE Matriculas (
    IdMatricula       INT IDENTITY(1,1) PRIMARY KEY,
    IdAluno           INT NOT NULL FOREIGN KEY REFERENCES Alunos(IdAluno),
    IdTurma           INT NOT NULL FOREIGN KEY REFERENCES Turmas(IdTurma),
    DataMatricula     DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    SituacaoMatricula VARCHAR(25) NOT NULL CHECK (SituacaoMatricula IN ('Cursando', 'Aprovado', 'Reprovado Nota', 'Reprovado Falta', 'Cancelada')),
    CONSTRAINT UQ_Aluno_Turma UNIQUE (IdAluno, IdTurma)
);

-- Notas e Frequência (Ref. RM: SNOTAETAPA / SFREQUENCIA)
CREATE TABLE NotasFrequencia (
    IdNotaFreq            INT IDENTITY(1,1) PRIMARY KEY,
    IdMatricula           INT NOT NULL UNIQUE FOREIGN KEY REFERENCES Matriculas(IdMatricula),
    Nota1                 DECIMAL(4,2) NULL CHECK (Nota1 BETWEEN 0 AND 10),
    Nota2                 DECIMAL(4,2) NULL CHECK (Nota2 BETWEEN 0 AND 10),
    NotaFinal             DECIMAL(4,2) NULL CHECK (NotaFinal BETWEEN 0 AND 10),
    AulasDadas            INT NOT NULL DEFAULT 60 CHECK (AulasDadas > 0),
    Faltas                INT NOT NULL DEFAULT 0 CHECK (Faltas >= 0),
    DataUltimaAtualizacao DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

-- Lançamentos Financeiros / Mensalidades (Ref. RM: FLAN / SLAN)
CREATE TABLE LancamentosFinanceiros (
    IdLancamento    INT IDENTITY(1,1) PRIMARY KEY,
    IdAluno         INT NOT NULL FOREIGN KEY REFERENCES Alunos(IdAluno),
    IdPeriodo       INT NOT NULL FOREIGN KEY REFERENCES PeriodosLetivos(IdPeriodo),
    Competencia     VARCHAR(7) NOT NULL, -- Formato YYYY-MM
    ValorBruto      DECIMAL(10,2) NOT NULL,
    ValorDesconto   DECIMAL(10,2) NOT NULL DEFAULT 0,
    ValorLiquido    AS (ValorBruto - ValorDesconto) PERSISTED,
    DataVencimento  DATE NOT NULL,
    DataPagamento   DATE NULL,
    StatusPagamento VARCHAR(20) NOT NULL CHECK (StatusPagamento IN ('Pago', 'Em Aberto', 'Vencido', 'Cancelado'))
);

-- Auditoria de Integrações e Fórmulas Automatizadas
CREATE TABLE LogIntegracao (
    IdLog            INT IDENTITY(1,1) PRIMARY KEY,
    DataExecucao     DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    OrigemProcesso   VARCHAR(50) NOT NULL,
    ChaveRegistro    VARCHAR(50) NOT NULL,
    StatusIntegracao VARCHAR(20) NOT NULL CHECK (StatusIntegracao IN ('Sucesso', 'Erro', 'Ignorado')),
    Mensagem         NVARCHAR(500) NOT NULL
);

-- Índices para otimização de consultas analíticas e joins frequentes
CREATE INDEX IX_Alunos_Curso ON Alunos(IdCurso);
CREATE INDEX IX_Matriculas_Turma ON Matriculas(IdTurma);
CREATE INDEX IX_Lancamentos_Aluno_Status ON LancamentosFinanceiros(IdAluno, StatusPagamento);
GO

-- ============================================================================
-- 3. SEED - POPULANDO DADOS DE DOMÍNIO
-- ============================================================================

INSERT INTO PeriodosLetivos (CodigoPeriodo, Descricao, DataInicio, DataFim, Ativo)
VALUES 
    ('2026.1', N'Primeiro Semestre Letivo de 2026', '20260202', '20260630', 0),
    ('2026.2', N'Segundo Semestre Letivo de 2026',  '20260803', '20261218', 1);

INSERT INTO Cursos (CodigoCurso, NomeCurso, Turno, ValorMensalidadeBase, CargaHorariaTotal)
VALUES
    ('CC-01',  N'Ciência da Computação',                    'Noturno',   1450.00, 3200),
    ('ADS-02', N'Análise e Desenvolvimento de Sistemas',    'Noturno',   1120.00, 2400),
    ('DIR-03', N'Direito',                                  'Matutino',  1680.00, 3700),
    ('ADM-04', N'Administração',                            'Noturno',   1190.00, 3000);

INSERT INTO Bolsas (CodigoBolsa, Descricao, PercentualDesconto)
VALUES
    ('SEM_BOLSA',    N'Pagante Integral (Sem Bolsa)',   0.00),
    ('MERITO_20',    N'Bolsa Mérito Acadêmico 20%',    20.00),
    ('CONVENIO_30',  N'Bolsa Convênio Empresa 30%',    30.00),
    ('PROUNI_50',    N'ProUni Parcial 50%',            50.00),
    ('INTEGRAL_100', N'ProUni / Filantropia 100%',    100.00);

INSERT INTO Disciplinas (CodigoDisciplina, NomeDisciplina, IdCurso, PeriodoGrade, CargaHoraria)
VALUES
    ('CC-BD1',   N'Banco de Dados Relacional e SQL',          1, 3, 80),
    ('CC-ES2',   N'Engenharia de Software Corporativo',       1, 4, 80),
    ('ADS-INT',  N'Integração de Sistemas e APIs',            2, 3, 60),
    ('ADS-DW',   N'Business Intelligence e Data Warehouse',   2, 4, 60),
    ('DIR-CIV',  N'Direito Civil: Obrigações e Contratos',    3, 3, 80),
    ('DIR-TRB',  N'Direito Tributário Aplicado',              3, 5, 60),
    ('ADM-FIN',  N'Gestão Financeira e Orçamentária',         4, 3, 60),
    ('ADM-ERP',  N'Sistemas Integrados de Gestão (ERP)',      4, 4, 60);

-- Turmas ativas em 2026.2 (IdPeriodo = 2)
INSERT INTO Turmas (CodigoTurma, IdPeriodo, IdDisciplina, Professor, Sala, VagasTotais)
VALUES
    ('20262-CC-BD1-A',  2, 1, N'Prof. Dr. Carlos Henrique Melo',  'BLOCO-G-201', 40),
    ('20262-CC-ES2-A',  2, 2, N'Profa. Dra. Fernanda Vasconcelos','BLOCO-G-204', 40),
    ('20262-ADS-INT-A', 2, 3, N'Prof. Me. Ricardo Albuquerque',   'LAB-INFO-03', 35),
    ('20262-ADS-DW-A',  2, 4, N'Profa. Ma. Juliana Cavalcanti',   'LAB-INFO-05', 35),
    ('20262-DIR-CIV-A', 2, 5, N'Prof. Dr. Eduardo Montenegro',    'BLOCO-A-102', 50),
    ('20262-DIR-TRB-A', 2, 6, N'Profa. Dra. Beatriz Lins',        'BLOCO-A-105', 50),
    ('20262-ADM-FIN-A', 2, 7, N'Prof. Me. Marcelo Tavares',       'BLOCO-B-301', 45),
    ('20262-ADM-ERP-A', 2, 8, N'Profa. Ma. Renata Siqueira',      'LAB-INFO-02', 45);
GO

-- ============================================================================
-- 4. GERAÇÃO AUTOMATIZADA DE 40 ALUNOS, MATRÍCULAS, NOTAS E PARCELAS
-- ============================================================================
SET DATEFORMAT ymd;

DECLARE @Nomes TABLE (Id INT IDENTITY(1,1), Nome NVARCHAR(40));
INSERT INTO @Nomes (Nome) VALUES
    (N'Lucas'), (N'Mariana'), (N'Gabriel'), (N'Beatriz'), (N'Matheus'),
    (N'Larissa'), (N'Pedro'), (N'Camila'), (N'Rafael'), (N'Juliana'),
    (N'Guilherme'), (N'Amanda'), (N'Felipe'), (N'Letícia'), (N'Bruno'),
    (N'Carolina'), (N'Thiago'), (N'Fernanda'), (N'Vinícius'), (N'Isabela');

DECLARE @Sobrenomes TABLE (Id INT IDENTITY(1,1), Sobrenome NVARCHAR(60));
INSERT INTO @Sobrenomes (Sobrenome) VALUES
    (N'Silva Andrade'), (N'Oliveira Santos'), (N'Costa Lima'), (N'Pereira Souza'),
    (N'Almeida Ferreira'), (N'Rodrigues Gomes'), (N'Nascimento Ribeiro'), (N'Carvalho Martins'),
    (N'Araújo Barbosa'), (N'Melo Cavalcanti');

DECLARE @i INT = 1;
DECLARE @NomeCompleto NVARCHAR(150);
DECLARE @RA VARCHAR(15);
DECLARE @CPF CHAR(11);
DECLARE @Email NVARCHAR(120);
DECLARE @IdCurso INT;
DECLARE @IdBolsa INT;
DECLARE @StatusAcad VARCHAR(20);
DECLARE @NewAlunoId INT;

WHILE @i <= 40
BEGIN
    SELECT @NomeCompleto = n.Nome + N' ' + s.Sobrenome
    FROM @Nomes n
    CROSS JOIN @Sobrenomes s
    WHERE n.Id = ((@i - 1) % 20) + 1
      AND s.Id = ((@i - 1) / 4) + 1;

    SET @RA = '20262' + RIGHT('000' + CAST(@i AS VARCHAR(3)), 3);
    SET @CPF = RIGHT('00000000000' + CAST(CAST(10000000000 AS BIGINT) + (@i * 1234567) AS VARCHAR(11)), 11);
    SET @Email = LOWER(REPLACE(REPLACE(@RA + '@aluno.educore.edu.br', ' ', ''), '''', ''));
    SET @IdCurso = ((@i - 1) % 4) + 1;
    SET @IdBolsa = CASE 
                      WHEN @i % 10 = 0 THEN 5 -- 100%
                      WHEN @i % 5 = 0  THEN 4 -- 50%
                      WHEN @i % 4 = 0  THEN 3 -- 30%
                      WHEN @i % 3 = 0  THEN 2 -- 20%
                      ELSE 1                  -- 0%
                   END;
    SET @StatusAcad = CASE 
                         WHEN @i IN (14, 29) THEN 'Trancado'
                         WHEN @i IN (19, 37) THEN 'Evadido'
                         ELSE 'Ativo'
                      END;

    INSERT INTO Alunos (RA, NomeCompleto, CPF, Email, DataNascimento, IdCurso, IdBolsa, StatusAcademico, DataIngresso)
    VALUES (
        @RA,
        @NomeCompleto,
        @CPF,
        @Email,
        DATEADD(DAY, -(@i * 110), CAST('20040615' AS DATE)),
        @IdCurso,
        @IdBolsa,
        @StatusAcad,
        CASE WHEN @i % 2 = 0 THEN '20250201' ELSE '20260201' END
    );

    SET @NewAlunoId = SCOPE_IDENTITY();

    -- Matricula alunos ativos nas 2 turmas do seu respectivo curso em 2026.2
    IF @StatusAcad = 'Ativo'
    BEGIN
        INSERT INTO Matriculas (IdAluno, IdTurma, SituacaoMatricula)
        SELECT @NewAlunoId, t.IdTurma, 'Cursando'
        FROM Turmas t
        INNER JOIN Disciplinas d ON t.IdDisciplina = d.IdDisciplina
        WHERE d.IdCurso = @IdCurso AND t.IdPeriodo = 2;
    END

    -- Gera 4 parcelas financeiras (Ago, Set, Out, Nov/2026) para alunos não evadidos
    IF @StatusAcad IN ('Ativo', 'Trancado')
    BEGIN
        DECLARE @ValorBase DECIMAL(10,2);
        DECLARE @PercDesc DECIMAL(5,2);
        DECLARE @ValorDesc DECIMAL(10,2);

        SELECT @ValorBase = ValorMensalidadeBase FROM Cursos WHERE IdCurso = @IdCurso;
        SELECT @PercDesc = PercentualDesconto FROM Bolsas WHERE IdBolsa = @IdBolsa;
        SET @ValorDesc = ROUND(@ValorBase * (@PercDesc / 100.0), 2);

        INSERT INTO LancamentosFinanceiros (IdAluno, IdPeriodo, Competencia, ValorBruto, ValorDesconto, DataVencimento, DataPagamento, StatusPagamento)
        VALUES
            (@NewAlunoId, 2, '2026-08', @ValorBase, @ValorDesc, '20260810',
             CASE WHEN @i % 9 = 0 AND @IdBolsa <> 5 THEN NULL ELSE '20260808' END,
             CASE WHEN @i % 9 = 0 AND @IdBolsa <> 5 THEN 'Vencido' ELSE 'Pago' END),

            (@NewAlunoId, 2, '2026-09', @ValorBase, @ValorDesc, '20260910',
             CASE WHEN @i % 6 = 0 AND @IdBolsa <> 5 THEN NULL ELSE '20260909' END,
             CASE WHEN @i % 6 = 0 AND @IdBolsa <> 5 THEN 'Vencido' ELSE 'Pago' END),

            (@NewAlunoId, 2, '2026-10', @ValorBase, @ValorDesc, '20261010',
             CASE WHEN @i % 5 = 0 AND @IdBolsa <> 5 THEN NULL ELSE '20261010' END,
             CASE WHEN @i % 5 = 0 AND @IdBolsa <> 5 THEN 'Vencido' ELSE 'Pago' END),

            (@NewAlunoId, 2, '2026-11', @ValorBase, @ValorDesc, '20261125',
             CASE WHEN @i % 2 = 0 OR @IdBolsa = 5 THEN '20261112' ELSE NULL END,
             CASE WHEN @i % 2 = 0 OR @IdBolsa = 5 THEN 'Pago' ELSE 'Em Aberto' END);
    END

    SET @i = @i + 1;
END
GO

-- Popula Notas e Frequência para todas as matrículas criadas
INSERT INTO NotasFrequencia (IdMatricula, Nota1, Nota2, NotaFinal, AulasDadas, Faltas)
SELECT 
    m.IdMatricula,
    CAST(4.5 + ((m.IdAluno * 7 + m.IdTurma) % 55) / 10.0 AS DECIMAL(4,2)) AS Nota1,
    CAST(4.0 + ((m.IdAluno * 11 + m.IdTurma) % 60) / 10.0 AS DECIMAL(4,2)) AS Nota2,
    NULL AS NotaFinal,
    60 AS AulasDadas,
    -- Cada 7º aluno simula estouro de faltas (> 25% de 60 = > 15 faltas)
    CASE WHEN m.IdAluno % 7 = 0 THEN 18 ELSE (m.IdAluno * 3 + m.IdTurma) % 14 END AS Faltas
FROM Matriculas m;
GO

INSERT INTO LogIntegracao (OrigemProcesso, ChaveRegistro, StatusIntegracao, Mensagem)
VALUES ('SEED_INICIAL', 'CARGA_2026_2', 'Sucesso', N'Carga inicial de 40 alunos, turmas e lançamentos concluída.');
GO