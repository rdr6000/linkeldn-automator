import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn
import argparse
import subprocess
from app.config import settings

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Daily Automation System")
    parser.add_argument("--port", type=int, default=8000, help="Port to run web server on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind server on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--all", action="store_true", help="Start both MCP server and Web UI together")
    args = parser.parse_args()

    if args.all:
        import start
        start.main()
        return

    print(f"Starting LinkedIn Automation Web UI on http://{args.host}:{args.port}")
    print(f"Operational Mode: {settings.MODE}")
    print(f"MCP URL: {settings.MCP_URL}")

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
