from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.report import Block, Report


class ReportRequest(BaseModel):
    reason: str


router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.post("/block/{user_id}")
async def block_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself")

    existing = await db.execute(
        select(Block).where(and_(Block.blocker_id == current_user.id, Block.blocked_id == user_id))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already blocked")

    block = Block(blocker_id=current_user.id, blocked_id=user_id)
    db.add(block)
    await db.commit()
    return {"blocked": True}


@router.post("/report/{user_id}")
async def report_user(
    user_id: str,
    data: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot report yourself")

    report = Report(reporter_id=current_user.id, reported_id=user_id, reason=data.reason[:1000])
    db.add(report)
    await db.commit()
    return {"reported": True}