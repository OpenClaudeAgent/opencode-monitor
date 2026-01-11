import pytest
import aiohttp


@pytest.mark.asyncio
async def test_mock_single_get_request(mock_aioresponse):
    mock_aioresponse.get(
        "http://127.0.0.1:8080/session/status",
        payload={"status": "active", "agents": []},
    )

    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8080/session/status") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "active"
            assert data["agents"] == []


@pytest.mark.asyncio
async def test_mock_sequential_responses(mock_aioresponse):
    mock_aioresponse.get("http://127.0.0.1:8080/health", status=500, repeat=2)
    mock_aioresponse.get("http://127.0.0.1:8080/health", status=200)

    async with aiohttp.ClientSession() as session:
        resp1 = await session.get("http://127.0.0.1:8080/health")
        resp2 = await session.get("http://127.0.0.1:8080/health")
        resp3 = await session.get("http://127.0.0.1:8080/health")

        assert resp1.status == 500
        assert resp2.status == 500
        assert resp3.status == 200


@pytest.mark.asyncio
async def test_mock_multiple_endpoints(mock_aioresponse):
    mock_aioresponse.get(
        "http://127.0.0.1:3000/session/status",
        payload={"session_id": "sess1", "status": "busy"},
    )
    mock_aioresponse.get(
        "http://127.0.0.1:3001/session/status",
        payload={"session_id": "sess2", "status": "idle"},
    )

    async with aiohttp.ClientSession() as session:
        resp1 = await session.get("http://127.0.0.1:3000/session/status")
        resp2 = await session.get("http://127.0.0.1:3001/session/status")

        data1 = await resp1.json()
        data2 = await resp2.json()

        assert data1["status"] == "busy"
        assert data2["status"] == "idle"


@pytest.mark.asyncio
async def test_mock_post_with_headers(mock_aioresponse):
    mock_aioresponse.post(
        "http://127.0.0.1:8080/api/sessions",
        payload={"id": "sess-123"},
        headers={"Content-Type": "application/json"},
    )

    async with aiohttp.ClientSession() as session:
        async with session.post("http://127.0.0.1:8080/api/sessions") as resp:
            assert resp.status == 200
            assert resp.headers["Content-Type"] == "application/json"
            data = await resp.json()
            assert data["id"] == "sess-123"


@pytest.mark.asyncio
async def test_mock_timeout_error(mock_aioresponse):
    import asyncio

    mock_aioresponse.get("http://127.0.0.1:8080/slow", exception=asyncio.TimeoutError())

    async with aiohttp.ClientSession() as session:
        with pytest.raises(asyncio.TimeoutError):
            await session.get("http://127.0.0.1:8080/slow")
