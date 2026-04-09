from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from fastapi import HTTPException, status
from app.models.match import Like, Match
from app.models.user import User
from app.models.report import Block


async def get_candidates(current_user: User, db: AsyncSession) -> list[User]:
    blocked = await db.execute(
        select(Block.blocked_id).where(Block.blocker_id == current_user.id)
    )
    blocked_ids = [r[0] for r in blocked.fetchall()]

    blockers = await db.execute(
        select(Block.blocker_id).where(Block.blocked_id == current_user.id)
    )
    blocker_ids = [r[0] for r in blockers.fetchall()]

    liked = await db.execute(
        select(Like.to_user_id).where(Like.from_user_id == current_user.id)
    )
    liked_ids = [r[0] for r in liked.fetchall()]

    excluded = set(blocked_ids + blocker_ids + liked_ids + [current_user.id])

    result = await db.execute(
        select(User).where(
            and_(
                User.is_active == True,
                ~User.id.in_(excluded)
            )
        ).limit(20)
    )
    return result.scalars().all()


async def like_user(from_user_id: str, to_user_id: str, db: AsyncSession) -> dict:
    if from_user_id == to_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot like yourself")

    existing = await db.execute(
        select(Like).where(
            and_(Like.from_user_id == from_user_id, Like.to_user_id == to_user_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already liked")

    like = Like(from_user_id=from_user_id, to_user_id=to_user_id)
    db.add(like)

    mutual = await db.execute(
        select(Like).where(
            and_(Like.from_user_id == to_user_id, Like.to_user_id == from_user_id)
        )
    )

    is_match = False
    if mutual.scalar_one_or_none():
        match = Match(user1_id=from_user_id, user2_id=to_user_id)
        db.add(match)
        is_match = True

    await db.commit()
    return {"match": is_match}


async def get_matches(user_id: str, db: AsyncSession) -> list[Match]:
    result = await db.execute(
        select(Match).where(
            and_(
                or_(Match.user1_id == user_id, Match.user2_id == user_id),
                Match.is_active == True
            )
        )
    )
    return result.scalars().all()