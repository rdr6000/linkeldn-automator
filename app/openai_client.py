import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Client for generating LinkedIn comments and connection notes via OpenAI API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self._client = None
        if self.api_key and self.api_key != "mock_key_for_development":
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI Client: {e}. Will use fallback text generation.")

    async def generate_comment(
        self,
        post_text: str,
        author_name: str,
        style: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        user_persona: Optional[str] = None
    ) -> str:
        """Generate a contextual LinkedIn comment using OpenAI API."""
        chosen_style = style or settings.comment_style
        chosen_instructions = custom_instructions if custom_instructions else settings.custom_instructions
        chosen_persona = user_persona if user_persona else settings.user_persona

        persona_context = (
            f"YOUR PROFESSIONAL BACKGROUND & PERSONA:\n{chosen_persona}\n"
            f"Speak naturally from your domain background.\n\n"
        ) if chosen_persona else ""

        instruction_context = f"CUSTOM INSTRUCTIONS:\n{chosen_instructions}\n\n" if chosen_instructions else ""

        prompt = (
            f"You are a human professional commenting on a LinkedIn post. Your goal is to add genuine value to the conversation.\n\n"
            f"STRICT ANTI-AI SLOP RULES:\n"
            f"- NEVER start with generic praise ('Great post!', 'Thanks for sharing!', 'Spot on!', 'Fascinating perspective!', 'I completely agree').\n"
            f"- NEVER use corporate clichés ('game-changer', 'delve', 'paradigm shift', 'synergy', 'testament to', 'in today's fast-paced world').\n"
            f"- Directly reference a specific point, metric, tool, or question raised in the post content below.\n"
            f"- Write 1 to 3 punchy, natural, conversational sentences as if talking to a colleague over coffee.\n\n"
            f"{persona_context}"
            f"STYLE GUIDELINES:\n{chosen_style}\n\n"
            f"{instruction_context}"
            f"POST AUTHOR: {author_name}\n"
            f"POST CONTENT:\n{post_text[:1500]}\n\n"
            f"Generate ONLY the final comment text without quotes, markdown formatting, or meta commentary."
        )
        return await self._generate_text(
            prompt,
            fallback=f"Regarding your point on {post_text[:60].strip()}..., {author_name}, how are you measuring the actual impact in production?"
        )

    async def generate_connection_note(
        self,
        person_name: str,
        person_headline: str,
        style: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        user_persona: Optional[str] = None
    ) -> str:
        """Generate a personalized connection request note using OpenAI API."""
        chosen_style = style or settings.connection_note_style
        chosen_instructions = custom_instructions if custom_instructions else settings.custom_instructions
        chosen_persona = user_persona if user_persona else settings.user_persona

        persona_context = (
            f"YOUR PROFESSIONAL BACKGROUND & PERSONA:\n{chosen_persona}\n"
            f"Write from your personal perspective.\n\n"
        ) if chosen_persona else ""

        instruction_context = f"CUSTOM INSTRUCTIONS:\n{chosen_instructions}\n\n" if chosen_instructions else ""

        prompt = (
            f"Write a personalized, highly specific LinkedIn connection invitation for {person_name} ({person_headline}).\n\n"
            f"STRICT RULES:\n"
            f"- Mention a specific domain or experience from their headline ({person_headline}).\n"
            f"- Keep it under 180 characters.\n"
            f"- Sound authentic, warm, and zero corporate fluff.\n\n"
            f"{persona_context}"
            f"STYLE GUIDELINES:\n{chosen_style}\n\n"
            f"{instruction_context}"
            f"Generate ONLY the final connection note text."
        )
        return await self._generate_text(
            prompt,
            fallback=f"Hi {person_name}, noticed your work in {person_headline or 'the field'} and would value connecting with a fellow peer."
        )

    async def generate_user_persona(self, profile_summary_text: str) -> str:
        """Synthesize raw LinkedIn profile data from MCP into a concise persona description."""
        prompt = (
            f"Synthesize the following raw LinkedIn profile data into a concise, 2-3 sentence professional persona summary.\n"
            f"Highlight key skills, experience level, and professional focus:\n\n"
            f"{profile_summary_text[:3000]}\n\n"
            f"Return ONLY the concise persona description."
        )
        fallback = "Experienced professional in software engineering and AI automation."
        return await self._generate_text(prompt, fallback=fallback)

    async def _generate_text(self, prompt: str, fallback: str) -> str:
        """Call OpenAI model or return intelligent fallback."""
        if not self._client:
            logger.info("Using fallback text generator (no active OpenAI client configured).")
            return fallback

        try:
            model = settings.openai_model or "gpt-4o-mini"
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a professional assistant creating LinkedIn engagement content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300
            )
            if response and response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip().strip('"')
            return fallback
        except Exception as e:
            logger.error(f"OpenAI API error during generation: {e}")
            return fallback
