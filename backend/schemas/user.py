import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
import re


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain a digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str
