import asyncio
import sys
from app.linkedin.comment_like import comment_and_like

async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_comment_like.py <LINKEDIN_POST_URL>")
        sys.exit(1)

    post_url = sys.argv[1]
    comment_text = "Great point! Thanks for sharing these insights."
    print(f"Testing comment & like on: {post_url}")

    result = await comment_and_like(post_url, comment_text)
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(main())
