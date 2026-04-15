from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.match import Match
from app.models.report import Block, Report
from app.models.user import User

router = APIRouter(prefix="/moderation", tags=["moderation"])


class ReportRequest(BaseModel):
    reason: str


@router.post("/block/{user_id}")
async def block_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself"
        )

    existing = await db.execute(
        select(Block).where(
            and_(Block.blocker_id == current_user.id, Block.blocked_id == user_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already blocked"
        )

    db.add(Block(blocker_id=current_user.id, blocked_id=user_id))

    # Деактивируем существующий матч между этими пользователями
    await db.execute(
        update(Match)
        .where(
            and_(
                or_(
                    and_(Match.user1_id == current_user.id, Match.user2_id == user_id),
                    and_(Match.user1_id == user_id, Match.user2_id == current_user.id),
                ),
                Match.is_active == True,
            )
        )
        .values(is_active=False)
    )

    await db.commit()
    return {"blocked": True}


@router.delete("/block/{user_id}")
async def unblock_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Block).where(
            and_(Block.blocker_id == current_user.id, Block.blocked_id == user_id)
        )
    )
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block not found"
        )

    await db.delete(block)
    await db.commit()
    return {"unblocked": True}


@router.post("/report/{user_id}")
async def report_user(
    user_id: str,
    data: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot report yourself"
        )

    db.add(
        Report(
            reporter_id=current_user.id,
            reported_id=user_id,
            reason=data.reason[:1000],
        )
    )
    await db.commit()
    return {"reported": True}
