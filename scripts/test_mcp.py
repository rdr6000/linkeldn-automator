import asyncio
import json
from app.mcp.client import LinkedInMCP
from app.mcp.tools import MCPTools

async def main():
    print("Testing LinkedIn MCP Server Connection...")
    mcp = LinkedInMCP()
    tools = MCPTools(mcp)

    try:
        print("Calling get_feed(limit=5)...")
        feed = await tools.get_feed(limit=5)
        print("Feed Response:")
        print(json.dumps(feed, indent=2) if isinstance(feed, (dict, list)) else feed)

        print("\nCalling search_posts('software')...")
        posts = await tools.search_posts("software", recency="past-week")
        print("Search Posts Response:")
        print(json.dumps(posts, indent=2) if isinstance(posts, (dict, list)) else posts)

        print("\nMCP tools test completed successfully!")

    except Exception as e:
        print(f"\nMCP Test Error: {e}")
        print("Ensure the LinkedIn MCP server is running at the configured URL.")

if __name__ == "__main__":
    asyncio.run(main())
