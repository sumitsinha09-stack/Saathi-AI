import pytest
from unittest.mock import patch
import httpx

from backend.app.services.ai import AIService, FALLBACK_RESPONSE, clean_think_tags


def test_clean_think_tags():
    raw = "<think>This is internal reasoning.</think>Hello, I am Saathi AI."
    assert clean_think_tags(raw) == "Hello, I am Saathi AI."


def test_clean_think_tags_no_tags():
    raw = "Direct response."
    assert clean_think_tags(raw) == "Direct response."


@pytest.mark.asyncio
async def test_ai_service_generate_response_success():
    service = AIService(base_url="http://mock.ollama", model="qwen3:8b", timeout=5.0)

    async def mock_post(url, **kwargs):
        assert url == "http://mock.ollama/api/generate"
        return httpx.Response(
            status_code=200,
            json={"response": "Please call 1930 immediately to freeze accounts."},
        )

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await service.generate_response("I lost money in electricity bill fraud")
        assert "1930" in result


@pytest.mark.asyncio
async def test_ai_service_fallback_on_timeout():
    service = AIService(base_url="http://mock.ollama", model="qwen3:8b", timeout=0.1)

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timed out")):
        result = await service.generate_response("Urgent help needed")
        assert result == FALLBACK_RESPONSE


@pytest.mark.asyncio
async def test_ai_service_fallback_on_error():
    service = AIService(base_url="http://mock.ollama", model="qwen3:8b", timeout=5.0)

    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        result = await service.generate_response("Urgent help needed")
        assert result == FALLBACK_RESPONSE
