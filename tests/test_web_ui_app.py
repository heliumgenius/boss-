import pytest
from httpx import AsyncClient, ASGITransport

from boss_cli.web_ui.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.anyio
async def test_index_returns_html(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Boss CLI" in resp.text


@pytest.mark.anyio
async def test_search_returns_html(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/search", data={"query": "Python"})
    assert resp.status_code == 200
    # Returns either an error message or search results table
    assert "<tr>" in resp.text or "error" in resp.text
