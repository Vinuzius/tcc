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
  "sql": "SELECT name, city FROM people"
}
```

Limitações do comportamento:

- Apenas consultas read-only são aceitas.
- O SQL deve começar com `SELECT` ou `WITH`.
- O endpoint rejeita `INSERT`, `UPDATE`, `DELETE`, `ALTER`, `DROP` e outras mutações.
- O retorno é transformado pelo perfil informado no header.

## Health check

Depois de subir a aplicação, acesse `GET /health`.

## Estrutura

Projeto organizado com base em:

https://github.com/zhanymkanov/fastapi-best-practices#project-structure
