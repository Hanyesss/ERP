import uuid
from pydantic import BaseModel
from app.models.user import UserRole, UserLang


class LoginRequest(BaseModel):
    login: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    role: UserRole
    lang: UserLang

    class Config:
        from_attributes = True
