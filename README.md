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

## Health check

Depois de subir a aplicação, acesse `GET /health`.

## Estrutura

Projeto organizado com base em:

https://github.com/zhanymkanov/fastapi-best-practices#project-structure
