from datetime import datetime

from pydantic import BaseModel

from app.schemas.user import UserPublic


class MatchOut(BaseModel):
    id: str
    created_at: datetime
    partner: UserPublic

    model_config = {"from_attributes": True}
