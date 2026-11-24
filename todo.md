# TODO — Arani / TCC

Ordenado por prioridade dentro de cada categoria.

---

## 1. Urgente — necessário para o MVP da tese

1. [ ] **Congelar o schema v1**
   - Definir unicidade e múltiplas regras por conjunto em `profile_rule`.
   - Manter ou remover `algorithm.created_by_id` (só será usado quando houver cadastro de algoritmos).
   - `profile.regulation_id NOT NULL` fica para depois (ver v1+).
2. [ ] **Alinhar o código ao schema Arani** — pré-requisito dos itens 3 e 4
   - Criar o schema a partir do `schema.sql`.
   - Usuários e perfis somente no PostgreSQL, sem fallback SQLite.
   - Renomear `perfil`/`usuario` para `profile`/`app_user` (nomes em inglês).
3. [ ] **Separar as conexões**
   - Arani: leitura e escrita.
   - Fonte de dados (`employee`): somente leitura, papel com `SELECT` só nas tabelas de consulta.
   - O `/api/query` nunca alcança o Arani (isso também fecha a leitura de `password_hash` por consulta).
   - Executar as consultas dos usuários numa transação `READ ONLY` (isso também barra `WITH ... DELETE`).
4. [ ] **Integrar a `PrivacyEngine` ao `/api/query`**
   - Buscar as regras do perfil do usuário no Arani, aplicar no resultado e devolver só o transformado.
   - Ponto de partida: `privacy_engine.py` (UPPER, MASK, SUPPRESS, HIDE_COLUMN).
5. [ ] **Seed mínimo no schema final** — perfis A e B, `UPPER` em `city`, `HIDE_COLUMN` em `education` — para demonstrar o fluxo de ponta a ponta (ponto de partida: `seed_example.sql`).

---

## 2. Entrega inicial (v0)

1. [ ] **Rastrear a origem das colunas com `sqlglot`**
   - Resolver aliases, expressões, subconsultas, `SELECT *` e joins.
   - Rejeitar consultas que a engine não consegue analisar (na dúvida, nega).
   - Adicionar `sqlglot` ao `requirements.txt`.
2. [ ] **Cobertura obrigatória e revalidação**
   - Coluna classificada e sem regra não sai crua (oculta ou bloqueia); "sem regra = original" só vale para coluna sem classificação ou `NON_IDENTIFIER`.
   - Conferir na execução se a regra ainda satisfaz a classificação atual.
3. [ ] **Validação de SQL**: `statement_timeout` e limite de linhas. A transação `READ ONLY` (que também barra `WITH` que altera dados) já entra no item 3 do Urgente.
4. [ ] **Interface de algoritmos por conjunto de colunas** + registro de algoritmos pré-definidos.
5. [ ] **Regulações e perfis de exemplo**
   - Preencher regulações e `classification_guarantee` (a regulação é atualizada manualmente por enquanto).
   - Cadastrar **no mínimo 5 perfis** com classificações próprias e regras (ex.: jornalista trata `[city, gender]` como `QUASI_IDENTIFIER`, detetive da polícia não).
6. [ ] **K-anonimato (com verificação do resultado) e Laplace**.
7. [ ] **Orçamento de privacidade (epsilon) por usuário**, para o Laplace.
8. [ ] **Erro claro quando nenhuma coluna permitida** — hoje devolve linhas vazias.
9. [ ] **Validação de `params`**: preenchidos junto do algoritmo base; exceção se faltando ou inválido.
10. [ ] **Sincronizar o catálogo** (`data_table`/`data_column`) quando um `data_source` for inserido ou atualizado.
11. [ ] **Ligar o `postgres_wire_server` à engine**, para o usuário conectar no "banco que ele conhece".
12. [ ] **Configuração**: `pydantic-settings`, `.env.example` completo (conexão do Arani e da fonte). Tirar o valor padrão do `JWT_SECRET`: a aplicação não sobe sem a variável (o repositório é público).
13. [ ] **API/painel do admin**: perfis, regras, conjuntos de colunas e classificações.

*Fim da v0 (documentação e testes):*

14. [ ] **Testes automatizados + CI com PostgreSQL**: algoritmos, perfis, autorização, schema/trigger.
15. [ ] **Suíte de consultas adversariais**: alias, expressão, subconsulta, `UNION`, dedução por filtro, `WITH` que escreve.
16. [ ] **README com demo**: mesmo `SELECT` nos perfis A e B lado a lado, credenciais de teste.
17. [ ] **Escopo, ameaças e limitações** — exigido na entrega da v0.
18. [ ] **Requisitos, MER v1 e rastreabilidade RF → implementação**.
19. [ ] **Limpar o repositório**: `__pycache__` versionado, README.

---

## 3. Entrega posterior (v1+)

1. [ ] **Cadastro de algoritmos próprios** — início da v1 (ou fim da v0 se sobrar tempo)
   - Decidir quem cadastra (admin) e começar por plugins do admin.
   - Sandbox só se o código vier de usuários comuns.
2. [ ] **Auditoria completa**: execuções, passos e regras aplicadas, ligada aos algoritmos do artigo base.
3. [ ] **OAuth real**
   - Authorization Code com PKCE, validar `id_token`, identificar o usuário por `(provider, subject)`.
   - `password_hash` opcional e colunas de OAuth em `app_user`.
   - Até lá, o mock atual é mantido como está.
4. [ ] **Cookie `HttpOnly` e rever o tempo do token**.
5. [ ] **Migrações versionadas** com Alembic.
6. [ ] **Atualização automática da regulação** por agentes de IA a cada X horas. Incluir a etapa de aprovação do admin: a mudança fica pendente até ele aprovar.
7. [ ] **Bloquear colunas restritas em `WHERE`/`ORDER BY`/`GROUP BY`/`JOIN`** — não decidido; até lá, registrar como limitação no item 17 da v0.
8. [ ] **`profile.regulation_id NOT NULL`** — adiado por você.
9. [ ] **Utilidade × privacidade** — as métricas vêm do artigo base; só entra aqui se quiser reproduzi-las.

---

## Pesquisa (itens do TODO anterior)

- [ ] Ler o artigo de Thiago Jordão (mestrado, RIUFF).
- [ ] Verificar os perfis LGPD de acordo com a norma da UE (base para as regulações e a tabela `classification_guarantee`).






- Fazer implementação dos 2 tipos de serviço
