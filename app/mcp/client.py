import asyncio
import subprocess
import httpx
import uuid
import json
import logging
from typing import Any, Optional, Dict
from app.config import settings

logger = logging.getLogger(__name__)


class LinkedInMCP:
    """Wrapper around MCP stdio/HTTP server using JSON-RPC 2.0 protocol."""

    def __init__(self, base_url: Optional[str] = None, http_client: Optional[httpx.AsyncClient] = None):
        self.url = base_url or settings.MCP_URL
        self.session_id: Optional[str] = None
        self._external_client = http_client

    async def call(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }

        if self._external_client:
            return await self._call_http(payload)

        # Prefer stdio for 100% reliable local execution on Windows & CLI
        try:
            return await self._call_stdio(payload)
        except Exception as stdio_e:
            logger.warning(f"Stdio MCP call failed ({stdio_e}). Attempting HTTP call to {self.url}...")
            return await self._call_http(payload)

    async def _call_http(self, payload: dict) -> Any:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        if self._external_client:
            resp = await self._external_client.post(self.url, json=payload, headers=headers)
            return self._process_response(resp)
        else:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(self.url, json=payload, headers=headers)
                return self._process_response(resp)

    async def _call_stdio(self, payload: dict) -> Any:
        """JSON-RPC invocation via stdio subprocess with UTF-8 encoding."""
        cmd = ["uvx", "mcp-server-linkedin@latest", "--transport", "stdio"]

        def _run_sync():
            p = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            # Send initialize first
            init_req = {
                "jsonrpc": "2.0",
                "id": "init_1",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "linkedin_auto_client", "version": "1.0.0"}
                }
            }
            p.stdin.write(json.dumps(init_req) + "\n")
            p.stdin.flush()

            while True:
                line = p.stdout.readline()
                if not line:
                    break
                try:
                    data = json.loads(line)
                    if data.get("id") == "init_1":
                        break
                except Exception:
                    pass

            p.stdin.write(json.dumps(payload) + "\n")
            p.stdin.flush()

            req_id = payload.get("id")
            final_res = None

            while True:
                line = p.stdout.readline()
                if not line:
                    break
                try:
                    data = json.loads(line)
                    if data.get("id") == req_id:
                        final_res = data
                        break
                except Exception:
                    pass

            p.terminate()
            if not final_res:
                raise RuntimeError(f"MCP stdio process returned no response matching ID '{req_id}'.")
            return final_res

        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, _run_sync)
        return self._extract_result(data)

    def _process_response(self, resp: httpx.Response) -> Any:
        if "Mcp-Session-Id" in resp.headers:
            self.session_id = resp.headers["Mcp-Session-Id"]
        resp.raise_for_status()

        data = self._parse_json_or_sse(resp.text)
        return self._extract_result(data)

    def _parse_json_or_sse(self, text: str) -> dict:
        text = text.strip()
        if not text:
            raise RuntimeError("Received empty body from MCP server.")

        if "data:" in text:
            for line in text.splitlines():
                if line.startswith("data:"):
                    json_str = line[5:].strip()
                    try:
                        return json.loads(json_str)
                    except Exception:
                        pass

        try:
            return json.loads(text)
        except Exception as e:
            raise RuntimeError(f"Could not parse MCP response text: {e}")

    def _extract_result(self, data: dict) -> Any:
        if "result" in data:
            result_obj = data["result"]
            content = result_obj.get("content", [])
            if content and isinstance(content, list):
                text = content[0].get("text", "")
                try:
                    return json.loads(text)
                except Exception:
                    return text
            return result_obj
        if "error" in data:
            raise RuntimeError(f"MCP server returned error: {data['error']}")
        raise RuntimeError(f"Unexpected MCP response shape: {data}")
