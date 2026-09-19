# app/api/routes/auth/auth_schemas.py
from pydantic import BaseModel


class SessionResponse(BaseModel):
    authenticated: bool
    is_owner: bool
    is_admin: bool = False
    email: str | None = None
    user_id: str | None = None
    role_name: str | None = None
    name: str | None = None


class TokenProxyResponse(BaseModel):
    access_token_expires_in: int | None = None
    message: str
