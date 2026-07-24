from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.security import decode_access_token
from app.models.user import User
from app.schemas.chat import ConversationCreate, MessageCreate
from app.schemas.common import success
from app.services import chat as chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("")
async def chat_bootstrap(db: DbSession, user: CurrentUser) -> dict:
    return success(await chat_service.bootstrap(db, user))


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    db: DbSession, user: CurrentUser, body: ConversationCreate = ConversationCreate()
) -> dict:
    return success(await chat_service.create_conversation(db, user, body), "对话已创建")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    await chat_service.delete_conversation(db, user, conversation_id)
    return success({"id": str(conversation_id)}, "对话已删除")


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID, body: MessageCreate, db: DbSession, user: CurrentUser
) -> dict:
    return success(await chat_service.send_message(db, user, conversation_id, body))


@router.websocket("/conversations/{conversation_id}/stream")
async def stream_message(
    websocket: WebSocket,
    conversation_id: UUID,
    db: DbSession,
    token: str = Query(default=""),
) -> None:
    await websocket.accept()
    try:
        user_id = UUID(decode_access_token(token))
        user = await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
        if user is None:
            raise ValueError("user unavailable")
    except (ValueError, jwt.InvalidTokenError):
        await websocket.send_json({"type": "error", "message": "身份验证失败"})
        await websocket.close(code=4401)
        return

    try:
        raw = await websocket.receive_json()
        payload = MessageCreate.model_validate(raw)
        reply = await chat_service.send_message(db, user, conversation_id, payload)
        for index in range(0, len(reply["content"]), 24):
            await websocket.send_json(
                {"type": "delta", "content": reply["content"][index : index + 24]}
            )
        await websocket.send_json({"type": "done", "message": reply})
        await websocket.close()
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await db.rollback()
        await websocket.send_json({"type": "error", "message": str(exc) or "生成回答失败"})
        await websocket.close(code=1011)
