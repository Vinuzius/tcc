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

## Configuração

Copie `.env.example` para `.env` e ajuste os valores do PostgreSQL.
Use um usuário que exista no PostgreSQL local, por exemplo `postgres`, em
`POSTGRES_USER`; os valores `your_user`, `your_database` e `your_password` do
arquivo de exemplo são apenas placeholders. Reinicie o Uvicorn depois de alterar o `.env`, pois as variáveis são
carregadas na inicialização. A aplicação carrega o `.env` do diretório do
projeto e dá prioridade a esses valores sobre variáveis antigas do ambiente.

## Executar a API

No Windows PowerShell:

```powershell
uvicorn main:app --reload --app-dir src
```

No Linux ou macOS:

```bash
uvicorn main:app --reload --app-dir src
```

## Exemplo do endpoint

`POST /first-example/query`

Headers:

```http
X-Profile-Name: A
Content-Type: application/json
```

Body:

```json
{
  "sql": "SELECT e.education, e.city, e.payment_tier FROM employee e WHERE e.age > 20 AND e.ever_benched = 'No'"
}
```

Limitações do comportamento:

- Apenas consultas read-only são aceitas.
- O SQL deve começar com `SELECT` ou `WITH`.
- O endpoint rejeita `INSERT`, `UPDATE`, `DELETE`, `ALTER`, `DROP` e outras mutações.
- O retorno é transformado pelo perfil informado no header.

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
   - Exemplos rápidos de consulta prontos para teste (`SELECT p.name FROM perfil`, `SELECT * FROM usuario`, `SELECT * FROM employee LIMIT 10`).

### Credenciais Padrão para Teste:

- **Administrador**: `admin` / `admin123` (Perfil: *Administrador*)
- **Usuário Comum**: `joao` / `user123` (Perfil: *Padrão*)
- **Pesquisador**: `maria` / `maria123` (Perfil: *Pesquisador*)

## Health check

Depois de subir a aplicação, acesse `GET /health`.

## Estrutura

Projeto organizado com base em:

https://github.com/zhanymkanov/fastapi-best-practices#project-structure
