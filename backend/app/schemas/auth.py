from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CurrentUser(BaseModel):
    id: str
    email: str
    role: UserRole


class MeResponse(CurrentUser):
    pass
