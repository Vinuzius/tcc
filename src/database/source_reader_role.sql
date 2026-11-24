-- =====================================================================
-- Papel somente leitura usado na conexão com a FONTE de dados.
-- Executar UMA vez como superusuário (ex.: postgres), no banco onde estão
-- o schema arani e a tabela public.employee.
-- TROQUE a senha 'change_me' (e use a mesma em SOURCE_DB_PASSWORD no .env).
--
-- O papel NÃO recebe nenhum privilégio no schema arani: as consultas dos
-- usuários nunca alcançam usuários, perfis, regras ou hashes de senha.
-- O SELECT em public.employee é concedido pela aplicação após criar a tabela
-- (ou manualmente: GRANT SELECT ON public.employee TO source_reader;).
-- =====================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'source_reader') THEN
        CREATE ROLE source_reader LOGIN PASSWORD 'admin123';
    END IF;
END
$$;

ALTER ROLE source_reader SET default_transaction_read_only = on;
ALTER ROLE source_reader SET statement_timeout = '10s';

GRANT USAGE ON SCHEMA public TO source_reader;
