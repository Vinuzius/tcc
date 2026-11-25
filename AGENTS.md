# AGENTS.md

## Projeto
TCC: API FastAPI que intermedia consultas SQL e aplica, no resultado, as regras de privacidade do perfil do usuário.
Dois bancos, sempre separados:
- **Arani** (schema `arani`): usuários, perfis, regulações, regras e auditoria. Conexão de leitura/escrita (`arani_query`, `arani_mutation`).
- **Fonte de dados** (ex.: `public.employee`): o que os usuários consultam. Conexão somente leitura (`source_query`, papel `source_reader`).

## Regras de segurança (não quebrar)
- Consultas de usuários executam SOMENTE na conexão da fonte. Nunca ler ou escrever o Arani por essa rota.
- Nenhum endpoint devolve dados da fonte sem passar pela `PrivacyEngine`.
- Na dúvida, negar (fail closed): consulta que a engine não consegue analisar deve ser rejeitada, nunca devolvida sem tratamento.
- Nunca concatenar valores em SQL; usar parâmetros `%s` (psycopg).
- Não enfraquecer a validação de SQL nem a transação READ ONLY da fonte.
- Nunca commitar `.env`, senhas, tokens ou dumps com dados reais.

## Convenções de código
- Identificadores em inglês (classes, variáveis, métodos, tabelas, colunas).
- O JSON da API segue o contrato atual com o frontend, até decisão contrária.
- Agrupar lógica relacionada em uma classe ou módulo existente; não criar classes pequenas usadas em um único lugar.
- Schema: editar `src/database/arani_schema.sql` (idempotente; PK, UNIQUE, CHECK e FK no final de cada tabela) e validar executando o arquivo duas vezes seguidas.

## Comandos (PowerShell, com o venv ativo)
- Testes: `$env:PYTHONPATH='src'; python -m pytest`
- Subir a API: `uvicorn main:app --reload --app-dir src`
- Subir o servidor wire PostgreSQL (outro terminal; lê `POSTGRES_WIRE_PORT`, `POSTGRES_WIRE_USER` e `POSTGRES_WIRE_PASSWORD` do `.env`): `python src\postgres_wire_server.py`
- Testar o servidor wire: `psql -h localhost -p 5433 -U postgres -d postgres`

## Escopo
- Não implementar nada fora do pedido da tarefa. As prioridades estão em `todo.md` (urgente, v0, v1+).
- Fora de escopo por enquanto: OAuth real, cadastro de algoritmos próprios, migrações (Alembic).

## Ao terminar uma tarefa
Listar os arquivos alterados, as suposições feitas e o estado dos testes.

## Limitações conhecidas
- O servidor wire ainda NÃO passa pela `PrivacyEngine` (devolve dados sem aplicar regras). Não expor a porta fora da máquina local até essa integração.

## Versões e documentação
- `src/database/arani_schema.sql` é sempre a versão atual do schema.
- `docs/versions/` guarda cópias congeladas (snapshots) do schema e dos documentos principais, mais um `CHANGELOG.md`.
- Não editar snapshots existentes nem criar novos sem o pedido do usuário. Ao alterar o schema, avisar que uma nova versão pode precisar de snapshot.