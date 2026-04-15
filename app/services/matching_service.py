from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Like, Match
from app.models.pass_ import Pass
from app.models.report import Block
from app.models.user import User


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

    passed = await db.execute(
        select(Pass.to_user_id).where(Pass.from_user_id == current_user.id)
    )
    passed_ids = [r[0] for r in passed.fetchall()]

    excluded = set(blocked_ids + blocker_ids + liked_ids + passed_ids + [current_user.id])

    result = await db.execute(
        select(User)
        .where(
            and_(
                User.is_active == True,
                User.is_verified == True,
                ~User.id.in_(excluded),
            )
        )
        .limit(20)
    )
    return result.scalars().all()


async def like_user(from_user_id: str, to_user_id: str, db: AsyncSession) -> dict:
    if from_user_id == to_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot like yourself"
        )

    existing = await db.execute(
        select(Like).where(
            and_(Like.from_user_id == from_user_id, Like.to_user_id == to_user_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already liked"
        )

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


async def pass_user(from_user_id: str, to_user_id: str, db: AsyncSession) -> dict:
    if from_user_id == to_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot pass yourself"
        )

    existing = await db.execute(
        select(Pass).where(
            and_(Pass.from_user_id == from_user_id, Pass.to_user_id == to_user_id)
        )
    )
    if existing.scalar_one_or_none():
        return {"passed": True}  # idempotent

    db.add(Pass(from_user_id=from_user_id, to_user_id=to_user_id))
    await db.commit()
    return {"passed": True}


async def get_matches(user_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Match)
        .where(
            and_(
                or_(Match.user1_id == user_id, Match.user2_id == user_id),
                Match.is_active == True,
            )
        )
        .order_by(Match.created_at.desc())
    )
    matches = result.scalars().all()

    if not matches:
        return []

    partner_ids = [
        m.user2_id if m.user1_id == user_id else m.user1_id for m in matches
    ]

    users_result = await db.execute(select(User).where(User.id.in_(partner_ids)))
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    return [
        {
            "id": m.id,
            "created_at": m.created_at,
            "partner": users_by_id[m.user2_id if m.user1_id == user_id else m.user1_id],
        }
        for m in matches
        if (m.user2_id if m.user1_id == user_id else m.user1_id) in users_by_id
    ]


async def unmatch(match_id: str, user_id: str, db: AsyncSession) -> None:
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
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found"
        )
    match.is_active = False
    await db.commit()
