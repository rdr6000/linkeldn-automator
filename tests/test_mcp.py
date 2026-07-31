import pytest
import httpx
import json
from unittest.mock import AsyncMock, MagicMock
from app.mcp.client import LinkedInMCP
from app.mcp.tools import MCPTools

@pytest.mark.asyncio
async def test_mcp_client_call_extracts_result():
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"Mcp-Session-Id": "sess_12345"}
    mock_response.raise_for_status = MagicMock()
    json_data = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "content": [{"type": "text", "text": '{"posts": [{"url": "http://example.com"}]}'}]
        }
    }
    mock_response.text = json.dumps(json_data)
    mock_response.json.return_value = json_data
    mock_client.post = AsyncMock(return_value=mock_response)

    mcp = LinkedInMCP(base_url="http://test-mcp:8000/mcp", http_client=mock_client)
    res = await mcp.call("get_feed", {"limit": 10})

    assert mcp.session_id == "sess_12345"
    assert isinstance(res, dict)
    assert "posts" in res

@pytest.mark.asyncio
async def test_mcp_tools_helper_methods():
    mcp_mock = MagicMock(spec=LinkedInMCP)
    mcp_mock.call = AsyncMock(return_value={"status": "ok"})

    tools = MCPTools(mcp_mock)

    await tools.get_feed(limit=20)
    mcp_mock.call.assert_called_with("get_feed", {"num_posts": 20})

    await tools.search_posts("python", "past-week")
    mcp_mock.call.assert_called_with("search_posts", {"keywords": "python", "date_posted": "past-week"})

    await tools.search_people("developer", "2nd")
    mcp_mock.call.assert_called_with("search_people", {"keywords": "developer", "network": ["S"]})

    await tools.connect_with_person("http://linkedin.com/in/test", note="Hello!")
    mcp_mock.call.assert_called_with("connect_with_person", {"linkedin_username": "test", "note": "Hello!"})
