from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import Dict, List
from app.db.session import get_db, AsyncSessionLocal
from app.api.deps import get_current_user
from app.models.user import User
from app.models.match import Match
from app.schemas.chat import MessageOut
from app.services.chat_service import get_messages, save_message, mark_read, verify_match_access
from app.core.security import decode_token

router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory connections: match_id -> list of websockets
active_connections: Dict[str, List[WebSocket]] = {}


@router.get("/{match_id}/messages", response_model=list[MessageOut])
async def get_chat_messages(
    match_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = await get_messages(match_id, current_user.id, db)
    await mark_read(match_id, current_user.id, db)
    return messages


@router.websocket("/{match_id}/ws")
async def websocket_chat(match_id: str, websocket: WebSocket, token: str):
    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Match).where(
                and_(
                    Match.id == match_id,
                    Match.is_active == True,
                    or_(Match.user1_id == user_id, Match.user2_id == user_id)
                )
            )
        )
        match = result.scalar_one_or_none()
        if not match:
            await websocket.close(code=4003)
            return

    await websocket.accept()

    if match_id not in active_connections:
        active_connections[match_id] = []
    active_connections[match_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            if len(data.strip()) == 0 or len(data) > 2000:
                await websocket.send_json({"error": "Invalid message"})
                continue

            async with AsyncSessionLocal() as db:
                message = await save_message(match_id, user_id, data, db)

            payload = {
                "id": message.id,
                "match_id": message.match_id,
                "sender_id": message.sender_id,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }

            for connection in active_connections[match_id]:
                try:
                    await connection.send_json(payload)
                except Exception:
                    pass

    except WebSocketDisconnect:
        active_connections[match_id].remove(websocket)
        if not active_connections[match_id]:
            del active_connections[match_id]