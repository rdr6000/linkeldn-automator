import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from app.gemini_client import GeminiClient
from app.openai_client import OpenAIClient
from app.config import settings

logger = logging.getLogger(__name__)


class ContentGenerator:
    """Service for generating contextual text content in parallel batches using Gemini or OpenAI."""

    def __init__(self, client: Optional[Any] = None):
        if client:
            self.client = client
        elif settings.ai_provider == "openai":
            logger.info("ContentGenerator initialized with OpenAI client.")
            self.client = OpenAIClient()
        else:
            logger.info("ContentGenerator initialized with Google Gemini client.")
            self.client = GeminiClient()

    async def generate_comment(
        self,
        post_text: str,
        author_name: str,
        style: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        user_persona: Optional[str] = None
    ) -> str:
        """Generate comment text for a target post."""
        return await self.client.generate_comment(
            post_text=post_text,
            author_name=author_name,
            style=style or settings.comment_style,
            custom_instructions=custom_instructions or settings.custom_instructions,
            user_persona=user_persona or settings.user_persona
        )

    async def generate_connection_note(
        self,
        person_name: str,
        headline: str,
        style: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        user_persona: Optional[str] = None
    ) -> str:
        """Generate personalized connection note for a target profile."""
        return await self.client.generate_connection_note(
            person_name=person_name,
            person_headline=headline,
            style=style or settings.connection_note_style,
            custom_instructions=custom_instructions or settings.custom_instructions,
            user_persona=user_persona or settings.user_persona
        )

    async def generate_comments_batch(
        self,
        posts: List[Dict[str, Any]],
        batch_size: int = 5
    ) -> List[str]:
        """Generate comments for multiple posts concurrently in fast parallel batches."""
        comments = []
        for i in range(0, len(posts), batch_size):
            chunk = posts[i:i + batch_size]
            tasks = [
                self.generate_comment(
                    post_text=p.get("text", ""),
                    author_name=p.get("author", "LinkedIn User")
                )
                for p in chunk
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for res, p in zip(batch_results, chunk):
                if isinstance(res, Exception):
                    logger.error(f"Error in batch comment generation: {res}")
                    comments.append(f"Regarding your post, {p.get('author', 'LinkedIn User')}, great perspectives shared!")
                else:
                    comments.append(res)
        return comments

    async def generate_connection_notes_batch(
        self,
        people: List[Dict[str, Any]],
        batch_size: int = 5
    ) -> List[str]:
        """Generate connection notes for multiple people concurrently in fast parallel batches."""
        notes = []
        for i in range(0, len(people), batch_size):
            chunk = people[i:i + batch_size]
            tasks = [
                self.generate_connection_note(
                    person_name=p.get("name", "LinkedIn User"),
                    headline=p.get("headline", "")
                )
                for p in chunk
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for res, p in zip(batch_results, chunk):
                if isinstance(res, Exception):
                    logger.error(f"Error in batch connection note generation: {res}")
                    notes.append(f"Hi {p.get('name', 'there')}, noticed your work in {p.get('headline', 'the field')} and would value connecting.")
                else:
                    notes.append(res)
        return notes

    async def synthesize_user_persona(self, profile_summary_text: str) -> str:
        """Synthesize persona description from raw profile text."""
        return await self.client.generate_user_persona(profile_summary_text)
