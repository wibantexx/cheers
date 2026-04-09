from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class UserPublic(BaseModel):
    id: str
    username: str
    age: int
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    city: Optional[str] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: Optional[str] = None
    bio: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("bio")
    @classmethod
    def bio_length(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 500:
            raise ValueError("Bio максимум 500 символов")
        return v

    @field_validator("latitude")
    @classmethod
    def lat_valid(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            # Округляем до ~1км для приватности
            return round(v, 2)
        return v

    @field_validator("longitude")
    @classmethod
    def lon_valid(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            return round(v, 2)
        return v


class UserPrivate(UserPublic):
    email: str
    is_verified: bool
    created_at: datetime