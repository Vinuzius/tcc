-- =====================================================================
-- Arani - seed do MVP: perfis A e B para o fluxo ponta a ponta
--   Perfil A: employee.city sempre em UPPER
--   Perfil B: employee.education não pode ser visualizada (coluna removida)
-- Pré-requisito: arani_schema.sql. Idempotente.
-- Os usuários (admin, user_a, user_b, joao) são criados pela aplicação (senha com bcrypt).
-- =====================================================================
BEGIN;
SET LOCAL search_path TO arani;

INSERT INTO regulation (name) VALUES ('LGPD') ON CONFLICT (name) DO NOTHING;

-- Algoritmos pré-definidos (cadastro de algoritmos próprios fica para a v1)
INSERT INTO algorithm (name, description, guarantee) VALUES
    ('UPPER',       'Converte texto para maiúsculas', 'NONE'),
    ('MASK',        'Mascara o valor mantendo os N últimos caracteres (params: keep_last)', 'MASKING'),
    ('SUPPRESS',    'Substitui o valor por NULL', 'SUPPRESSION'),
    ('HIDE_COLUMN', 'Remove a coluna do resultado', 'SUPPRESSION')
ON CONFLICT (name) DO NOTHING;

-- EXEMPLO de exigências por classificação: ajustar conforme a pesquisa/regulação.
INSERT INTO classification_guarantee (privacy_classification, guarantee) VALUES
    ('SENSITIVE',        'SUPPRESSION'),
    ('SENSITIVE',        'DIFFERENTIAL_PRIVACY'),
    ('SENSITIVE',        'K_ANONYMITY'),
    ('QUASI_IDENTIFIER', 'GENERALIZATION'),
    ('QUASI_IDENTIFIER', 'K_ANONYMITY'),
    ('QUASI_IDENTIFIER', 'DIFFERENTIAL_PRIVACY'),
    ('QUASI_IDENTIFIER', 'SUPPRESSION'),
    ('IDENTIFIER',       'MASKING'),
    ('IDENTIFIER',       'SUPPRESSION')
ON CONFLICT DO NOTHING;

-- Perfis (Administrador e Padrão ainda não têm regras)
INSERT INTO profile (regulation_id, name, description)
SELECT r.id, p.name, p.description
FROM regulation r
CROSS JOIN (VALUES
    ('Administrador', 'Administra o sistema; sem regras de anonimização'),
    ('Padrão',        'Perfil padrão dos novos usuários; sem regras por enquanto'),
    ('A',             'Perfil de teste A: city sempre em UPPER'),
    ('B',             'Perfil de teste B: education não pode ser visualizada')
) AS p(name, description)
WHERE r.name = 'LGPD'
ON CONFLICT (name) DO NOTHING;

-- Catálogo da fonte de dados que os usuários conhecem (tabela employee)
INSERT INTO data_source (name, host, port, schema_name)
VALUES ('employee_db', 'localhost', 5432, 'public')
ON CONFLICT (name) DO NOTHING;

INSERT INTO data_table (data_source_id, name)
SELECT ds.id, 'employee' FROM data_source ds WHERE ds.name = 'employee_db'
ON CONFLICT (data_source_id, name) DO NOTHING;

INSERT INTO data_column (data_table_id, name, data_type)
SELECT t.id, c.name, c.data_type
FROM data_table t
CROSS JOIN (VALUES
    ('education', 'varchar'), ('joining_year', 'integer'),
    ('city', 'varchar'), ('payment_tier', 'integer'), ('age', 'integer'),
    ('gender', 'varchar'), ('ever_benched', 'varchar'),
    ('experience_in_current_domain', 'integer'), ('leave_or_not', 'integer')
) AS c(name, data_type)
WHERE t.name = 'employee'
ON CONFLICT (data_table_id, name) DO NOTHING;

DELETE FROM data_column dc
USING data_table t
WHERE dc.data_table_id = t.id
  AND t.name = 'employee'
  AND dc.name = 'id';

-- Conjuntos de colunas alvo das regras
INSERT INTO attribute_set (name, description) VALUES
    ('employee_city',      'Cidade do funcionário'),
    ('employee_education', 'Escolaridade do funcionário')
ON CONFLICT (name) DO NOTHING;

INSERT INTO attribute_set_column (attribute_set_id, data_column_id)
SELECT s.id, dc.id
FROM attribute_set s
JOIN data_column dc ON (s.name, dc.name) IN (('employee_city', 'city'), ('employee_education', 'education'))
JOIN data_table t ON t.id = dc.data_table_id AND t.name = 'employee'
ON CONFLICT DO NOTHING;

-- Classificação na regulação: city é tratada como não identificadora neste exemplo
-- (por isso UPPER, garantia NONE, é aceito pelo trigger). education sem classificação.
INSERT INTO attribute_classification (attribute_set_id, regulation_id, privacy_classification, justification)
SELECT s.id, r.id, 'NON_IDENTIFIER', 'No exemplo, city é tratada como não identificadora'
FROM attribute_set s, regulation r
WHERE s.name = 'employee_city' AND r.name = 'LGPD'
ON CONFLICT DO NOTHING;

-- Regras dos perfis
INSERT INTO profile_rule (profile_id, attribute_set_id, algorithm_id, params)
SELECT p.id, s.id, a.id, '{}'::jsonb
FROM (VALUES ('A', 'employee_city', 'UPPER'), ('B', 'employee_education', 'HIDE_COLUMN')) AS v(profile_name, set_name, algorithm_name)
JOIN profile p       ON p.name = v.profile_name
JOIN attribute_set s ON s.name = v.set_name
JOIN algorithm a     ON a.name = v.algorithm_name
ON CONFLICT DO NOTHING;

COMMIT;
