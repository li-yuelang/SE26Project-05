from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserPublic,
)
from app.schemas.common import success

router = APIRouter(prefix="/auth", tags=["auth"])


def token_payload(user: User) -> dict:
    token = TokenResponse(access_token=create_access_token(str(user.id)), user=UserPublic.model_validate(user))
    return success(token.model_dump(mode="json"))


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession) -> dict:
    existing_user = await db.scalar(
        select(User).where(or_(User.email == str(payload.email), User.username == payload.username))
    )
    if existing_user:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email or username is already registered")

    user = User(
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email or username is already registered") from None
    await db.refresh(user)
    return token_payload(user)


@router.post("/login")
async def login(payload: LoginRequest, db: DbSession) -> dict:
    user = await db.scalar(select(User).where(User.email == str(payload.email)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User account is disabled")
    return token_payload(user)


@router.get("/me")
async def get_me(current_user: CurrentUser) -> dict:
    return success(UserPublic.model_validate(current_user).model_dump(mode="json"))


@router.patch("/me")
async def update_me(payload: UpdateProfileRequest, current_user: CurrentUser, db: DbSession) -> dict:
    filters = []
    if payload.username is not None:
        filters.append(User.username == payload.username)
    if payload.email is not None:
        filters.append(User.email == str(payload.email))

    if filters:
        existing_user = await db.scalar(select(User).where(or_(*filters), User.id != current_user.id))
        if existing_user is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email or username is already registered")

    if payload.username is not None:
        current_user.username = payload.username
    if payload.email is not None:
        current_user.email = str(payload.email)
    if "bio" in payload.model_fields_set:
        current_user.bio = payload.bio

    await db.commit()
    await db.refresh(current_user)
    return success(UserPublic.model_validate(current_user).model_dump(mode="json"))
