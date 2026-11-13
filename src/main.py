from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.first_example import router as first_example_router
from app.routers.health import router as health_router
from app.routers.profiles import router as profiles_router
from app.routers.query import router as query_router
from database.db import init_database

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and seed initial data
    init_database()
    yield


app = FastAPI(
    title="TCC - Gerenciador de Consultas & Perfis de Privacidade",
    description="Sistema web com autenticação OAuth 2.0, CRUD de usuários, controle administrativo de perfis e executor de consultas SQL.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local development and API access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(profiles_router)
app.include_router(query_router)
app.include_router(first_example_router)
app.include_router(health_router)

# Mount frontend directory for static assets and HTML UI
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend_root():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "TCC API is running. Frontend index.html not found."}


def main() -> None:
    print("Inicie a aplicação com: uvicorn main:app --reload --app-dir src")


if __name__ == "__main__":
    main()
