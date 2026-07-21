from __future__ import annotations

from datetime import timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import AppError
from app.models.chat import ChatMessage, Conversation, MessageCitation
from app.models.paper import Paper, UserPaper
from app.models.user import User
from app.schemas.chat import ConversationCreate, MessageCreate
from app.services import rag

SUGGESTIONS = [
    "解释 Transformer 自注意力机制及其局限",
    "对比 BERT 与 GPT 的预训练方法",
    "梳理检索增强生成的发展脉络",
]


def _time(value) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).strftime("%H:%M")


def _conversation_view(
    conversation: Conversation,
    messages: list[ChatMessage] | None = None,
) -> dict:
    messages = list(conversation.messages if messages is None else messages)
    preview = messages[-1].content[:80] if messages else ""
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "date": conversation.updated_at.date().isoformat(),
        "preview": preview,
    }


def _message_view(message: ChatMessage, papers: dict[UUID, Paper]) -> dict:
    sources = []
    for citation in message.citations:
        paper = papers.get(citation.paper_id)
        sources.append(
            {
                "paperId": str(citation.paper_id),
                "arxivId": paper.arxiv_id if paper else None,
                "title": paper.title if paper else "来源论文",
                "chunkIndex": citation.chunk_index,
                "excerpt": citation.excerpt,
            }
        )
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "time": _time(message.created_at),
        "sources": sources,
    }


def _conversation_statement(user_id: UUID):
    return (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .options(selectinload(Conversation.messages).selectinload(ChatMessage.citations))
        .order_by(Conversation.updated_at.desc())
    )


async def bootstrap(db: AsyncSession, user: User) -> dict:
    conversations = list((await db.scalars(_conversation_statement(user.id))).unique().all())
    paper_ids = {
        citation.paper_id
        for conversation in conversations
        for message in conversation.messages
        for citation in message.citations
    }
    papers = {}
    if paper_ids:
        papers = {paper.id: paper for paper in await db.scalars(select(Paper).where(Paper.id.in_(paper_ids)))}
    return {
        "conversations": [_conversation_view(item) for item in conversations],
        "messages": {
            str(item.id): [_message_view(message, papers) for message in item.messages]
            for item in conversations
        },
        "suggestions": SUGGESTIONS,
        "streaming": True,
    }


async def get_conversation(db: AsyncSession, user: User, conversation_id: UUID) -> Conversation:
    conversation = await db.scalar(
        _conversation_statement(user.id).where(Conversation.id == conversation_id)
    )
    if conversation is None:
        raise AppError("对话不存在", code="CONVERSATION_NOT_FOUND", status_code=404)
    return conversation


async def create_conversation(db: AsyncSession, user: User, payload: ConversationCreate) -> dict:
    conversation = Conversation(user_id=user.id, title=payload.title, metadata_extra={})
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    # A newly created conversation cannot have messages. Passing the known empty
    # collection avoids an async relationship lazy-load while serializing the response.
    return _conversation_view(conversation, messages=[])


async def delete_conversation(db: AsyncSession, user: User, conversation_id: UUID) -> None:
    conversation = await get_conversation(db, user, conversation_id)
    await db.delete(conversation)
    await db.commit()


async def send_message(
    db: AsyncSession,
    user: User,
    conversation_id: UUID,
    payload: MessageCreate,
) -> dict:
    conversation = await get_conversation(db, user, conversation_id)
    if payload.paper_ids is not None:
        requested_ids = set(payload.paper_ids)
        owned_ids = set(
            (await db.scalars(
                select(UserPaper.paper_id).where(
                    UserPaper.user_id == user.id,
                    UserPaper.paper_id.in_(requested_ids),
                )
            )).all()
        ) if requested_ids else set()
        if owned_ids != requested_ids:
            raise AppError("只能检索自己论文库中的论文", code="PAPER_ACCESS_DENIED", status_code=403)
    user_message = ChatMessage(conversation_id=conversation.id, role="user", content=payload.content)
    db.add(user_message)
    await db.flush()

    content, chunks, scenario = await rag.answer(
        db,
        payload.content,
        user_id=user.id,
        paper_ids=payload.paper_ids,
        requested_scenario=payload.scenario,
    )
    assistant = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        model_name=settings.llm_model if settings.llm_api_key else "extractive-fallback",
    )
    db.add(assistant)
    await db.flush()
    for item in chunks:
        db.add(
            MessageCitation(
                message_id=assistant.id,
                paper_id=item.paper.id,
                chunk_id=item.chunk.id,
                chunk_index=item.chunk.chunk_index,
                excerpt=item.chunk.content[:500],
            )
        )
    if len(conversation.messages) == 0 or conversation.title in {"新对话", "New conversation"}:
        conversation.title = payload.content[:40]
    conversation.metadata_extra = {**(conversation.metadata_extra or {}), "lastScenario": scenario}
    await db.commit()

    saved = await db.scalar(
        select(ChatMessage)
        .where(ChatMessage.id == assistant.id)
        .options(selectinload(ChatMessage.citations))
    )
    papers = {item.paper.id: item.paper for item in chunks}
    return _message_view(saved, papers)
