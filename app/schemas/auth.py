from pydantic import BaseModel, EmailStr, field_validator
import re


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    age: int

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]{3,50}$", v):
            raise ValueError("Username: 3-50 символов, только буквы, цифры и _")
        return v

    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Пароль минимум 8 символов")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Пароль должен содержать заглавную букву")
        if not re.search(r"\d", v):
            raise ValueError("Пароль должен содержать цифру")
        return v

    @field_validator("age")
    @classmethod
    def age_valid(cls, v: int) -> int:
        if v < 18:
            raise ValueError("Необходимо быть старше 18 лет")
        if v > 120:
            raise ValueError("Некорректный возраст")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str