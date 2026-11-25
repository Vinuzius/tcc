-- =====================================================================
-- Arani - schema PostgreSQL, versão v1 (MVP)
-- Idempotente: pode ser colado/executado várias vezes
-- Convenções: snake_case, PK = id, FK = <entidade>_id, nomes em inglês
-- PK, UNIQUE, CHECK e FK ficam no final da definição de cada tabela
--
-- Tudo roda em uma única transação: se algo falhar, nada é criado pela metade.
-- O search_path é alterado só dentro da transação (SET LOCAL) e volta ao
-- valor anterior no COMMIT, sem efeito colateral na sua sessão.
--
-- Para recriar do zero (APAGA TODOS OS DADOS), descomente a linha abaixo:
-- DROP SCHEMA IF EXISTS arani CASCADE;
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS arani;

SET LOCAL search_path TO arani;

-- ---------- ENUMs (CREATE TYPE não tem IF NOT EXISTS) ----------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'arani' AND t.typname = 'query_status'
    ) THEN
        CREATE TYPE arani.query_status AS ENUM ('CREATED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'arani' AND t.typname = 'privacy_classification'
    ) THEN
        CREATE TYPE arani.privacy_classification AS ENUM ('SENSITIVE', 'QUASI_IDENTIFIER', 'IDENTIFIER', 'NON_IDENTIFIER');
    END IF;

    -- Garantia de privacidade que um algoritmo oferece (usada para checar se ele atende a regulação)
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'arani' AND t.typname = 'algorithm_guarantee'
    ) THEN
        CREATE TYPE arani.algorithm_guarantee AS ENUM (
            'NONE', 'MASKING', 'GENERALIZATION', 'SUPPRESSION', 'K_ANONYMITY', 'DIFFERENTIAL_PRIVACY'
        );
    END IF;
END
$$;

-- ---------- Regulações e perfis ----------
CREATE TABLE IF NOT EXISTS regulation (
    id              INTEGER GENERATED ALWAYS AS IDENTITY,
    name            VARCHAR(150) NOT NULL,
    updated_at      DATE,

    PRIMARY KEY (id),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS profile (
    id              INTEGER GENERATED ALWAYS AS IDENTITY,
    regulation_id   INTEGER,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (id),
    UNIQUE (name),
    FOREIGN KEY (regulation_id) REFERENCES regulation (id) ON DELETE RESTRICT
);

-- "User" é palavra reservada no PostgreSQL -> app_user
CREATE TABLE IF NOT EXISTS app_user (
    id                      INTEGER GENERATED ALWAYS AS IDENTITY,
    profile_id              INTEGER,        -- NULL = sem perfil atribuído (a aplicação deve negar acesso aos dados)
    username                VARCHAR(100) NOT NULL,
    password_hash           VARCHAR(255) NOT NULL,
    is_admin                BOOLEAN NOT NULL DEFAULT FALSE,
    profile_assigned_by_id  INTEGER,        -- quem escolhe o perfil é o admin, nunca o próprio usuário
    profile_assigned_at     TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (id),
    UNIQUE (username),
    FOREIGN KEY (profile_id) REFERENCES profile (id) ON DELETE RESTRICT,
    FOREIGN KEY (profile_assigned_by_id) REFERENCES app_user (id) ON DELETE SET NULL
);

-- ---------- Conjuntos de colunas (alvo das regras) ----------
-- Um conjunto pode ter 1 ou N colunas (ex.: {cpf}, {nome, data_nascimento}).
CREATE TABLE IF NOT EXISTS attribute_set (
    id              INTEGER GENERATED ALWAYS AS IDENTITY,
    name            VARCHAR(150) NOT NULL,   -- antes: restriction_name
    description     TEXT,

    PRIMARY KEY (id),
    UNIQUE (name)
);

-- Sensibilidade do conjunto segundo cada legislação
CREATE TABLE IF NOT EXISTS attribute_classification (
    attribute_set_id        INTEGER NOT NULL,
    regulation_id           INTEGER NOT NULL,
    privacy_classification  privacy_classification NOT NULL DEFAULT 'SENSITIVE',   -- padrão mais restritivo (fail-safe)
    justification           TEXT,

    PRIMARY KEY (attribute_set_id, regulation_id),
    FOREIGN KEY (attribute_set_id) REFERENCES attribute_set (id) ON DELETE CASCADE,
    FOREIGN KEY (regulation_id) REFERENCES regulation (id) ON DELETE CASCADE
);

-- ---------- Catálogo de dados ----------
CREATE TABLE IF NOT EXISTS data_source (
    id              INTEGER GENERATED ALWAYS AS IDENTITY,
    name            VARCHAR(100) NOT NULL,
    host            VARCHAR(255) NOT NULL,
    port            INTEGER NOT NULL,
    schema_name     VARCHAR(100),

    PRIMARY KEY (id),
    UNIQUE (name),
    CHECK (port BETWEEN 1 AND 65535)
);

-- "Table" é palavra reservada -> data_table
CREATE TABLE IF NOT EXISTS data_table (
    id              INTEGER GENERATED ALWAYS AS IDENTITY,
    data_source_id  INTEGER NOT NULL,
    name            VARCHAR(150) NOT NULL,

    PRIMARY KEY (id),
    UNIQUE (data_source_id, name),
    FOREIGN KEY (data_source_id) REFERENCES data_source (id) ON DELETE CASCADE
);

-- "Column" é palavra reservada -> data_column (substitui column + table_column)
CREATE TABLE IF NOT EXISTS data_column (
    id              INTEGER GENERATED ALWAYS AS IDENTITY,
    data_table_id   INTEGER NOT NULL,
    name            VARCHAR(150) NOT NULL,
    data_type       VARCHAR(50) NOT NULL,

    PRIMARY KEY (id),
    UNIQUE (data_table_id, name),
    FOREIGN KEY (data_table_id) REFERENCES data_table (id) ON DELETE CASCADE
);

-- Composição dos conjuntos (uma coluna pode estar em vários conjuntos)
CREATE TABLE IF NOT EXISTS attribute_set_column (
    attribute_set_id    INTEGER NOT NULL,
    data_column_id      INTEGER NOT NULL,

    PRIMARY KEY (attribute_set_id, data_column_id),
    FOREIGN KEY (attribute_set_id) REFERENCES attribute_set (id) ON DELETE CASCADE,
    FOREIGN KEY (data_column_id) REFERENCES data_column (id) ON DELETE CASCADE
);

-- ---------- Algoritmos ----------
CREATE TABLE IF NOT EXISTS algorithm (
    id              INTEGER GENERATED ALWAYS AS IDENTITY,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    guarantee       algorithm_guarantee NOT NULL DEFAULT 'NONE',  -- NONE = só transformação (ex.: UPPER), não protege nada
    created_by_id   INTEGER,        -- NULL = algoritmo nativo da API; senão, quem cadastrou (quem pode cadastrar: a definir)

    PRIMARY KEY (id),
    UNIQUE (name),
    FOREIGN KEY (created_by_id) REFERENCES app_user (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS algorithm_parameter (
    id              INTEGER GENERATED ALWAYS AS IDENTITY,
    algorithm_id    INTEGER NOT NULL,
    name            VARCHAR(100) NOT NULL,
    required        BOOLEAN NOT NULL DEFAULT FALSE,
    default_value   VARCHAR(255),

    PRIMARY KEY (id),
    UNIQUE (algorithm_id, name),
    FOREIGN KEY (algorithm_id) REFERENCES algorithm (id) ON DELETE CASCADE
);

-- ---------- Exigências da classificação ----------
-- Quais garantias de algoritmo satisfazem cada classificação.
-- NON_IDENTIFIER não precisa de linhas (nada é exigido).
CREATE TABLE IF NOT EXISTS classification_guarantee (
    privacy_classification  privacy_classification NOT NULL,
    guarantee               algorithm_guarantee NOT NULL,

    PRIMARY KEY (privacy_classification, guarantee),
    CHECK (guarantee <> 'NONE')
);

-- Classificação própria do perfil (pode ser mais restritiva que a da regulação, nunca substitui a dela)
CREATE TABLE IF NOT EXISTS profile_attribute_classification (
    profile_id              INTEGER NOT NULL,
    attribute_set_id        INTEGER NOT NULL,
    privacy_classification  privacy_classification NOT NULL,
    justification           TEXT,

    PRIMARY KEY (profile_id, attribute_set_id),
    FOREIGN KEY (profile_id) REFERENCES profile (id) ON DELETE CASCADE,
    FOREIGN KEY (attribute_set_id) REFERENCES attribute_set (id) ON DELETE CASCADE
);

-- Todas as classificações que valem para um perfil em um conjunto:
-- a da regulação do perfil (sempre) + a do próprio perfil (se existir).
CREATE OR REPLACE VIEW profile_set_classification AS
SELECT p.id AS profile_id, ac.attribute_set_id, ac.privacy_classification, 'REGULATION'::text AS source
FROM profile p
JOIN attribute_classification ac ON ac.regulation_id = p.regulation_id
UNION ALL
SELECT pac.profile_id, pac.attribute_set_id, pac.privacy_classification, 'PROFILE'::text AS source
FROM profile_attribute_classification pac;

-- ---------- Regras do perfil (definidas pelo admin) ----------
-- "No perfil X, o conjunto Y é transformado pelo algoritmo Z com estes parâmetros."
CREATE TABLE IF NOT EXISTS profile_rule (
    id                  INTEGER GENERATED ALWAYS AS IDENTITY,
    profile_id          INTEGER NOT NULL,
    attribute_set_id    INTEGER NOT NULL,
    algorithm_id        INTEGER NOT NULL,
    params              JSONB NOT NULL DEFAULT '{}'::jsonb,   -- a ordem das etapas é definida pela API (ver execution_step.sequence)

    PRIMARY KEY (id),
    UNIQUE (profile_id, attribute_set_id, algorithm_id),
    FOREIGN KEY (profile_id) REFERENCES profile (id) ON DELETE CASCADE,
    FOREIGN KEY (attribute_set_id) REFERENCES attribute_set (id) ON DELETE CASCADE,
    FOREIGN KEY (algorithm_id) REFERENCES algorithm (id) ON DELETE RESTRICT
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'arani'
          AND t.relname = 'profile_rule'
          AND c.contype = 'u'
          AND c.conkey = ARRAY(
              SELECT a.attnum
              FROM pg_attribute a
              WHERE a.attrelid = t.oid
                AND a.attname IN ('profile_id', 'attribute_set_id', 'algorithm_id')
              ORDER BY array_position(ARRAY['profile_id', 'attribute_set_id', 'algorithm_id']::name[], a.attname)
          )
    ) THEN
        ALTER TABLE arani.profile_rule
            ADD CONSTRAINT uq_profile_rule_profile_set_algorithm
            UNIQUE (profile_id, attribute_set_id, algorithm_id);
    END IF;
END
$$;

-- O perfil sempre segue a regulação: a regra só é aceita se a garantia do algoritmo
-- satisfizer CADA classificação (regulação e perfil) do conjunto alvo.
-- Obs.: valida na criação/alteração da regra. Se a classificação mudar depois,
-- a API também precisa checar na execução.
CREATE OR REPLACE FUNCTION arani.check_profile_rule_compliance() RETURNS trigger AS $$
DECLARE
    rule_guarantee  arani.algorithm_guarantee;
    violated        arani.privacy_classification;
BEGIN
    SELECT a.guarantee INTO rule_guarantee FROM arani.algorithm a WHERE a.id = NEW.algorithm_id;

    SELECT c.privacy_classification INTO violated
    FROM arani.profile_set_classification c
    WHERE c.profile_id = NEW.profile_id
      AND c.attribute_set_id = NEW.attribute_set_id
      AND c.privacy_classification <> 'NON_IDENTIFIER'
      AND NOT EXISTS (
          SELECT 1 FROM arani.classification_guarantee cg
          WHERE cg.privacy_classification = c.privacy_classification
            AND cg.guarantee = rule_guarantee
      )
    LIMIT 1;

    IF violated IS NOT NULL THEN
        RAISE EXCEPTION 'Algorithm guarantee % does not satisfy classification % (profile %, attribute set %)',
            rule_guarantee, violated, NEW.profile_id, NEW.attribute_set_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_profile_rule_compliance ON arani.profile_rule;
CREATE TRIGGER trg_profile_rule_compliance
    BEFORE INSERT OR UPDATE ON arani.profile_rule
    FOR EACH ROW EXECUTE FUNCTION arani.check_profile_rule_compliance();

-- ---------- Execuções ----------
CREATE TABLE IF NOT EXISTS query_execution (
    id              INTEGER GENERATED ALWAYS AS IDENTITY,
    user_id         INTEGER NOT NULL,
    profile_id      INTEGER,    -- perfil vigente no momento (auditoria)
    sql_query       TEXT NOT NULL,
    status          query_status NOT NULL DEFAULT 'CREATED',
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,

    PRIMARY KEY (id),
    CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at),
    FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE RESTRICT,
    FOREIGN KEY (profile_id) REFERENCES profile (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS execution_step (
    query_execution_id  INTEGER NOT NULL,
    sequence            INTEGER NOT NULL,
    algorithm_id        INTEGER NOT NULL,
    attribute_set_id    INTEGER,
    profile_rule_id     INTEGER,    -- regra que originou a etapa
    params              JSONB NOT NULL DEFAULT '{}'::jsonb,

    PRIMARY KEY (query_execution_id, sequence),
    CHECK (sequence > 0),
    FOREIGN KEY (query_execution_id) REFERENCES query_execution (id) ON DELETE CASCADE,
    FOREIGN KEY (algorithm_id) REFERENCES algorithm (id) ON DELETE RESTRICT,
    FOREIGN KEY (attribute_set_id) REFERENCES attribute_set (id) ON DELETE SET NULL,
    FOREIGN KEY (profile_rule_id) REFERENCES profile_rule (id) ON DELETE SET NULL
);

-- ---------- Índices em FKs (o PostgreSQL não cria automaticamente) ----------
CREATE INDEX IF NOT EXISTS idx_profile_regulation       ON profile (regulation_id);
CREATE INDEX IF NOT EXISTS idx_app_user_profile         ON app_user (profile_id);
CREATE INDEX IF NOT EXISTS idx_attr_class_regulation    ON attribute_classification (regulation_id);
CREATE INDEX IF NOT EXISTS idx_set_column_column        ON attribute_set_column (data_column_id);
CREATE INDEX IF NOT EXISTS idx_profile_attr_class_set   ON profile_attribute_classification (attribute_set_id);
CREATE INDEX IF NOT EXISTS idx_algorithm_created_by     ON algorithm (created_by_id);
CREATE INDEX IF NOT EXISTS idx_profile_rule_set         ON profile_rule (attribute_set_id);
CREATE INDEX IF NOT EXISTS idx_profile_rule_algorithm   ON profile_rule (algorithm_id);
CREATE INDEX IF NOT EXISTS idx_query_execution_profile  ON query_execution (profile_id);
CREATE INDEX IF NOT EXISTS idx_query_execution_user     ON query_execution (user_id);
CREATE INDEX IF NOT EXISTS idx_query_execution_status   ON query_execution (status);
CREATE INDEX IF NOT EXISTS idx_exec_step_algorithm      ON execution_step (algorithm_id);
CREATE INDEX IF NOT EXISTS idx_exec_step_set            ON execution_step (attribute_set_id);
CREATE INDEX IF NOT EXISTS idx_exec_step_rule           ON execution_step (profile_rule_id);

COMMIT;
