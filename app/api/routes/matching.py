from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserPublic
from app.services.matching_service import get_candidates, like_user, get_matches

router = APIRouter(prefix="/matching", tags=["matching"])


@router.get("/candidates", response_model=list[UserPublic])
async def candidates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_candidates(current_user, db)


@router.post("/like/{user_id}")
async def like(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await like_user(current_user.id, user_id, db)


@router.post("/pass/{user_id}")
async def pass_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    like = __import__("app.models.match", fromlist=["Like"]).Like
    from sqlalchemy import and_
    from app.models.match import Like
    skip = Like(from_user_id=current_user.id, to_user_id=user_id)
    db.add(skip)
    await db.commit()
    return {"passed": True}


@router.get("/matches")
async def matches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_matches(current_user.id, db)