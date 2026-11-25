# TCC

## Ambiente

Crie o ambiente virtual:

```powershell
python -m venv .venv
```

Ative o ambiente no Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Ative o ambiente no Windows Command Prompt:

```bat
.\.venv\Scripts\activate.bat
```

Ative o ambiente no Linux ou macOS:

```bash
source .venv/bin/activate
```

Instale as dependências:

```powershell
pip install -r requirements\requirements.txt
```

## Configuração e Setup

Siga os passos nesta ordem:

1. **Crie o banco PostgreSQL** (caso não utilize o banco padrão `postgres`).
2. **Crie o papel somente leitura (`source_reader`)** executando `src/database/source_reader_role.sql` como superusuário (ex.: `postgres`), lembrando de trocar a senha `change_me`:
   ```powershell
   psql -h localhost -U postgres -d postgres -f src/database/source_reader_role.sql
   ```
3. **Configure o `.env`**: copie `.env.example` para `.env` e ajuste as variáveis `ARANI_DB_*` (conexão de leitura/escrita do Arani) e `SOURCE_DB_*` (conexão somente leitura com o usuário `source_reader` e a mesma senha definida no passo anterior).
4. **Suba a API** (ao iniciar, a aplicação cria o schema `arani`, aplica o seed dos perfis A e B, cria a tabela `public.employee`, concede `SELECT` ao `source_reader` e cadastra os usuários de teste). Reinicie o Uvicorn sempre que alterar o `.env`.

## Executar a API

No Windows PowerShell:

```powershell
uvicorn main:app --reload --app-dir src
```

No Linux ou macOS:

```bash
uvicorn main:app --reload --app-dir src
```

## Exemplos de uso: Perfis A e B (PrivacyEngine)

Todas as consultas passam pela rota autenticada `POST /api/query` e pela `PrivacyEngine`:

- **Perfil A (`user_a`)**: aplica `UPPER` na coluna `city`.
- **Perfil B (`user_b`)**: aplica `HIDE_COLUMN` na coluna `education` (remove a coluna do resultado).

### Perfil A (`user_a`) vs Perfil B (`user_b`) lado a lado

**Perfil A (`user_a`):**
```bash
TOKEN_A=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user_a","password":"usera123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT * FROM employee LIMIT 3"}'
# Resultado: city em MAIÚSCULAS (ex.: "BANGALORE"), demais colunas originais.
```

**Perfil B (`user_b`):**
```bash
TOKEN_B=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user_b","password":"userb123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT * FROM employee LIMIT 3"}'
# Resultado: coluna "education" removida de columns e rows; city com valor original.
```

### Limitações conhecidas

- Apenas consultas read-only são aceitas (`SELECT` ou `WITH`).
- As consultas executam em transação `READ ONLY` com o papel `source_reader` sem acesso ao schema `arani`.
- O servidor PostgreSQL wire (`src/postgres_wire_server.py`) ainda devolve dados sem aplicar as regras da `PrivacyEngine`.
- Cláusulas `WHERE`, `ORDER BY` e `GROUP BY` sobre colunas ocultas ainda permitem inferência (tratado na v1+).

## Servidor PostgreSQL wire

O projeto também inclui um servidor PostgreSQL wire baseado no pacote
[`postgres-wire`](https://pypi.org/project/postgres-wire/). Ele escuta na porta
`5433` por padrão, para não conflitar com um PostgreSQL local:

```powershell
python src\postgres_wire_server.py
```

Em Git Bash, use:

```bash
./.venv/Scripts/python.exe src/postgres_wire_server.py
```

Em outro terminal, conecte um cliente PostgreSQL diretamente ao servidor wire:

```powershell
psql -h localhost -p 5433 -U postgres -d postgres
```

No prompt do `psql`, execute uma consulta que retorne exatamente os campos
esperados pelo exemplo:

```sql
SELECT e.education, e.city, e.payment_tier
FROM employee e
WHERE e.age > 20 AND e.ever_benched = 'No';
```

Se a conexão for aceita e as linhas forem exibidas, o handshake, a
autenticação, o recebimento de uma mensagem `Q`, a descrição das colunas e o
retorno de dados pelo PostgreSQL wire estão funcionando. Para testar
autenticação explicitamente, defina `POSTGRES_WIRE_USER` e
`POSTGRES_WIRE_PASSWORD` no `.env`, reinicie o servidor wire e use as mesmas
credenciais no `psql`.

`postgres-wire` implementa uma parte do protocolo wire do PostgreSQL para
clientes que usam o fluxo de consulta simples. Ele não substitui um servidor
PostgreSQL completo: o exemplo não implementa prepared statements, SSL/TLS,
transações ou tipos de resultado além de texto, inteiros e booleanos.

## Aplicação Web & Frontend

A aplicação conta com uma interface web completa na pasta `frontend/`, servida automaticamente na raiz:

```
http://localhost:8000
```

### Funcionalidades Implementadas:

1. **Autenticação OAuth 2.0**:
   - Padrão RFC 6749 com fluxo Password Grant (`POST /api/auth/token`).
   - Endpoint JSON para login e cadastro (`POST /api/auth/login`, `POST /api/auth/register`).
   - Suporte a provedores OAuth 2.0 / Single Sign-On simulado (`POST /api/auth/oauth/login`).
   - Tokens JWT com algoritmo HMAC-SHA256 e proteção de rotas via `Bearer <token>`.

2. **CRUD de Usuários & Perfis**:
   - Cada usuário possui login, senha criptografada com `bcrypt` e um perfil de privacidade associado.
   - **Regra do Sistema**: Apenas o administrador tem autorização para definir ou alterar o perfil dos usuários. Novos usuários auto-registrados recebem automaticamente o perfil `Padrão`.
   - Painel administrativo (`/api/admin/users`) para listagem, cadastro, exclusão e alteração de privilégios.

3. **Painel do Administrador & Modificação de Perfil**:
   - Exibe a lista completa de usuários cadastrados.
   - Cada linha possui um campo seletor `<select>` preenchido dinamicamente com os perfis existentes no banco (`SELECT p.name FROM perfil`).
   - O administrador pode selecionar qualquer perfil e salvar a modificação instantaneamente.

4. **Executor de Consultas SQL Read-Only**:
   - Campo de texto para digitar consultas SQL.
   - Exibição dinâmica dos dados retornados em tabela HTML responsiva.
   - Métricas de execução (número de linhas, colunas e tempo em milissegundos).
   - Filtro de resultados em tempo real e exportação para CSV.
   - Exemplos rápidos de consulta prontos para teste (`SELECT * FROM employee LIMIT 10`, `SELECT city, COUNT(*) AS total FROM employee GROUP BY city ORDER BY total DESC`).

### Usuários de Teste Padrão:

| Usuário | Senha | Perfil | Comportamento na `PrivacyEngine` |
| --- | --- | --- | --- |
| `admin` | `admin123` | `Administrador` | Acesso administrativo; sem regras de anonimização |
| `user_a` | `usera123` | `A` | `city` sempre em MAIÚSCULAS (`UPPER`) |
| `user_b` | `userb123` | `B` | Coluna `education` ocultada (`HIDE_COLUMN`) |
| `joao` | `user123` | `Padrão` | Perfil padrão de novos usuários; sem regras |

## Health check

Depois de subir a aplicação, acesse `GET /health`.

## Estrutura

Projeto organizado com base em:

https://github.com/zhanymkanov/fastapi-best-practices#project-structure
