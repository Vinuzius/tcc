import os
import time
from typing import Any
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from database.db import execute_query

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-tcc-token-key-2026-secure-at-least-32-chars")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(data: dict[str, Any], expires_delta_seconds: int = ACCESS_TOKEN_EXPIRE_SECONDS) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = int(time.time()) + expires_delta_seconds
    to_encode.update({"exp": expire, "iat": int(time.time())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado. Por favor, autentique-se novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict[str, Any]:
    """FastAPI dependency to retrieve currently authenticated user."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária (Bearer token não fornecido).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido (identificador de usuário ausente).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database with profile info
    query = """
        SELECT 
            u.id, 
            u.username, 
            u.is_admin, 
            u.perfil_id,
            p.name as perfil_name,
            p.description as perfil_description
        FROM usuario u
        LEFT JOIN perfil p ON u.perfil_id = p.id
        WHERE u.id = ? OR u.username = ?
        LIMIT 1
    """
    mode = os.getenv("FORCE_SQLITE", "")
    # Parameter syntax: ? for sqlite or %s for postgres
    from database.db import get_db_mode
    db_mode = get_db_mode()
    if db_mode == "postgres":
        query = query.replace("?", "%s")

    try:
        user_id_int = int(user_id)
        users = execute_query(query, (user_id_int, str(user_id)))
    except ValueError:
        users = execute_query(query, (-1, str(user_id)))

    if not users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário associado ao token não foi encontrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = users[0]
    # Normalize is_admin to boolean
    user["is_admin"] = bool(user.get("is_admin"))
    return user


def get_current_admin(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Dependency ensuring that current user is an admin."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: apenas administradores podem realizar esta operação.",
        )
    return current_user
