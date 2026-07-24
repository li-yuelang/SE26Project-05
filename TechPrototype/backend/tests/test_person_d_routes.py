from app.main import app
from app.api.v1.chat import router as chat_router


def test_wiki_chat_and_stream_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/wiki" in paths
    assert "/api/wiki/concepts/{concept_id}" in paths
    assert "/api/chat" in paths
    assert "/api/chat/conversations/{conversation_id}/messages" in paths
    assert any(route.path.endswith("/{conversation_id}/stream") for route in chat_router.routes)


def test_existing_paper_and_task_routes_remain_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/papers" in paths
    assert "/api/tasks" in paths
