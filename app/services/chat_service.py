from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.message import Message


async def verify_match_access(match_id: str, user_id: str, db: AsyncSession) -> Match:
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No access to this chat"
        )
    return match


async def get_messages(
    match_id: str,
    user_id: str,
    db: AsyncSession,
    limit: int = 50,
    before_id: str | None = None,
) -> list[Message]:
    await verify_match_access(match_id, user_id, db)

    query = select(Message).where(Message.match_id == match_id)

    if before_id:
        # Курсорная пагинация: загрузить сообщения старше before_id
        cursor_result = await db.execute(
            select(Message.created_at).where(Message.id == before_id)
        )
        cursor_ts = cursor_result.scalar_one_or_none()
        if cursor_ts:
            query = query.where(Message.created_at < cursor_ts)

    query = query.order_by(Message.created_at.desc()).limit(min(limit, 100))

    result = await db.execute(query)
    # Возвращаем в хронологическом порядке (старые → новые)
    return list(reversed(result.scalars().all()))


async def save_message(
    match_id: str, sender_id: str, content: str, db: AsyncSession
) -> Message:
    content = content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty message"
        )
    if len(content) > 2000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Message too long"
        )

    message = Message(match_id=match_id, sender_id=sender_id, content=content)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def mark_read(match_id: str, user_id: str, db: AsyncSession) -> None:
    await db.execute(
        update(Message)
        .where(
            and_(
                Message.match_id == match_id,
                Message.sender_id != user_id,
                Message.is_read == False,  # noqa: E712
            )
        )
        .values(is_read=True)
    )
    await db.commit()
