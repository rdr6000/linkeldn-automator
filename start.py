import os
import subprocess
import sys
import time
import argparse
from pathlib import Path
from app.config import settings


def ensure_mcp_login(force_login: bool = False):
    """Check if LinkedIn MCP session exists. Only opens login browser window if no session profile exists."""
    print("[1/3] Checking LinkedIn MCP authentication session...")

    if force_login:
        print("Forcing interactive LinkedIn login...")
        subprocess.run(["uvx", "mcp-server-linkedin@latest", "--login"])
        return

    profile_dir = Path.home() / ".linkedin-mcp" / "profile"
    if profile_dir.exists() and any(profile_dir.iterdir()):
        print("[OK] Valid LinkedIn session profile detected.")
        return

    # Secondary check via --status with UTF-8 environment
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        check_proc = subprocess.run(
            ["uvx", "mcp-server-linkedin@latest", "--status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env
        )
        output = check_proc.stdout + check_proc.stderr
        if "No valid source session" in output:
            print("\n" + "!" * 65)
            print("  FIRST-TIME SETUP DETECTED: No active LinkedIn MCP session found.")
            print("  Opening browser window for one-time LinkedIn authentication...")
            print("!" * 65 + "\n")
            subprocess.run(["uvx", "mcp-server-linkedin@latest", "--login"])
        else:
            print("[OK] Valid LinkedIn session profile detected.")
    except Exception as e:
        print(f"Note on session check: {e}. Proceeding with launch...")


def main():
    parser = argparse.ArgumentParser(description="Start LinkedIn Automation System")
    parser.add_argument("--login", action="store_true", help="Force interactive LinkedIn re-login before start")
    args, _ = parser.parse_known_args()

    print("=" * 65)
    print("  Starting LinkedIn Automation System (MCP + Web UI)")
    print("=" * 65)

    # 1. Ensure MCP session exists
    ensure_mcp_login(force_login=args.login)

    mcp_port = 8001
    web_port = 8000

    # 2. Launch MCP Server
    print(f"\n[2/3] Launching LinkedIn MCP Server on port {mcp_port}...")
    mcp_cmd = [
        "uvx", "mcp-server-linkedin@latest",
        "--transport", "streamable-http",
        "--port", str(mcp_port)
    ]

    try:
        mcp_process = subprocess.Popen(
            mcp_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
    except Exception as e:
        print(f"Warning: Could not start uvx directly: {e}. Trying npx fallback...")
        mcp_cmd = [
            "npx", "-y", "@stickerdaniel/linkedin-mcp-server",
            "--transport", "streamable-http",
            "--port", str(mcp_port)
        ]
        mcp_process = subprocess.Popen(mcp_cmd)

    print("Waiting for MCP Server to initialize...")
    time.sleep(3)

    # 3. Launch Web UI Dashboard
    print(f"[3/3] Launching Web UI Dashboard on http://localhost:{web_port}...")
    web_cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", str(web_port),
        "--reload"
    ]

    try:
        web_process = subprocess.Popen(web_cmd)
        print("\n" + "=" * 65)
        print(f"  🚀 System is live and fully automated!")
        print(f"  - Web UI Dashboard: http://localhost:{web_port}")
        print(f"  - MCP Server URL:   http://localhost:{mcp_port}/mcp")
        print(f"  Press Ctrl+C to stop both services.")
        print("=" * 65 + "\n")

        web_process.wait()
    except KeyboardInterrupt:
        print("\nStopping services cleanly...")
    finally:
        try:
            web_process.terminate()
        except Exception:
            pass
        try:
            mcp_process.terminate()
        except Exception:
            pass
        print("All processes stopped.")


if __name__ == "__main__":
    main()
