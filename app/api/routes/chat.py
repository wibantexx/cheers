import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal, get_db
from app.models.match import Match
from app.models.user import User
from app.schemas.chat import MessageOut
from app.services.chat_service import get_messages, mark_read, save_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory connections: match_id -> list of websockets
active_connections: Dict[str, List[WebSocket]] = {}


@router.get("/{match_id}/messages", response_model=list[MessageOut])
async def get_chat_messages(
    match_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before_id: Optional[str] = Query(default=None, description="Cursor: загрузить сообщения старше этого ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = await get_messages(match_id, current_user.id, db, limit=limit, before_id=before_id)
    await mark_read(match_id, current_user.id, db)
    return messages


@router.websocket("/{match_id}/ws")
async def websocket_chat(match_id: str, websocket: WebSocket, token: str):
    jwt_payload = decode_token(token, "access")
    if not jwt_payload:
        await websocket.close(code=4001)
        return

    user_id = jwt_payload["sub"]
    token_ver = jwt_payload["ver"]

    async with AsyncSessionLocal() as db:
        # Validate token version against DB (catches post-logout connections).
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active or user.token_version != token_ver:
            await websocket.close(code=4001)
            return

        result = await db.execute(
            select(Match).where(
                and_(
                    Match.id == match_id,
                    Match.is_active == True,
                    or_(Match.user1_id == user_id, Match.user2_id == user_id),
                )
            )
        )
        match = result.scalar_one_or_none()
        if not match:
            await websocket.close(code=4003)
            return

    await websocket.accept()
    active_connections.setdefault(match_id, []).append(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            if len(data.strip()) == 0 or len(data) > 2000:
                await websocket.send_json({"error": "Invalid message"})
                continue

            try:
                async with AsyncSessionLocal() as db:
                    message = await save_message(match_id, user_id, data, db)
            except HTTPException as exc:
                # Keep the socket alive — surface validation errors to the client.
                await websocket.send_json({"error": exc.detail})
                continue
            except Exception:
                logger.exception("Failed to persist chat message")
                await websocket.send_json({"error": "Could not send message"})
                continue

            broadcast = {
                "id": message.id,
                "match_id": message.match_id,
                "sender_id": message.sender_id,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }

            # Copy snapshot — other coroutines may mutate the list on disconnect.
            for connection in list(active_connections.get(match_id, [])):
                try:
                    await connection.send_json(broadcast)
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass
    finally:
        conns = active_connections.get(match_id)
        if conns and websocket in conns:
            conns.remove(websocket)
        if match_id in active_connections and not active_connections[match_id]:
            del active_connections[match_id]