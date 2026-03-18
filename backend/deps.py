"""FastAPI dependencies: DB session + current user extraction from EdDSA JWT."""

import uuid
from typing import Annotated
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .config import get_settings
from .models.user import User

settings = get_settings()

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """
    Verify EdDSA JWT and return authenticated user.

    Security notes:
    - Algorithm is HARDCODED to "EdDSA" — prevents algorithm confusion attacks
      (e.g., attacker swapping to "none" or "HS256")
    - Public key only — the VPS and all nodes can verify tokens but NOT issue them
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_public_key,
            algorithms=["EdDSA"],   # HARDCODED — do not make configurable
            options={"require": ["sub", "exp", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception

    user_id_str: str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


# Type aliases for convenience
DbDep = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
