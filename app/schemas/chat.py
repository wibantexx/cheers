from pydantic import BaseModel
from datetime import datetime


class MessageOut(BaseModel):
    id: str
    match_id: str
    sender_id: str
    content: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageIn(BaseModel):
    content: str

    def __init__(self, **data):
        super().__init__(**data)
        if len(self.content.strip()) == 0:
            raise ValueError("Сообщение не может быть пустым")
        if len(self.content) > 2000:
            raise ValueError("Сообщение максимум 2000 символов")