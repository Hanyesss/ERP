import uuid
from typing import List
from pydantic import BaseModel
from app.models.user import UserLang


class LoginRequest(BaseModel):
    login: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    roles: List[str]
    lang: UserLang

    class Config:
        from_attributes = True

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        return cls(
            id=user.id,
            full_name=user.full_name,
            roles=user.roles,
            lang=user.lang,
        )
