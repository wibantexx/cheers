from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.matching import MatchOut
from app.schemas.user import UserPublic
from app.services.matching_service import (
    get_candidates,
    get_matches,
    like_user,
    pass_user,
    unmatch,
)

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
async def pass_(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await pass_user(current_user.id, user_id, db)


@router.get("/matches", response_model=list[MatchOut])
async def matches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_matches(current_user.id, db)


@router.delete("/matches/{match_id}")
async def unmatch_route(
    match_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await unmatch(match_id, current_user.id, db)
    return {"unmatched": True}
