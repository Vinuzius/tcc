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

## Comandos (confirmar e ajustar)
- Testes: `pytest`
- Subir a API: `uvicorn main:app --reload --app-dir src`

## Escopo
- Não implementar nada fora do pedido da tarefa. As prioridades estão em `todo.md` (urgente, v0, v1+).
- Fora de escopo por enquanto: OAuth real, cadastro de algoritmos próprios, migrações (Alembic).

## Ao terminar uma tarefa
Listar os arquivos alterados, as suposições feitas e o estado dos testes.
