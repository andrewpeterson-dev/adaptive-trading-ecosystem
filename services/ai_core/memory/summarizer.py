"""Thread summarizer — condenses long conversation threads into memory items."""
from __future__ import annotations


import structlog
from sqlalchemy import select

from db.database import get_session

logger = structlog.get_logger(__name__)

# System prompt for the summarization LLM call
_SUMMARY_SYSTEM_PROMPT = (
    "You are a concise summarizer for Cerberus, a trading assistant. "
    "Summarize the conversation so far, focusing on: "
    "1) key decisions or trades discussed, "
    "2) user preferences revealed, "
    "3) any unresolved questions or action items. "
    "Keep it under 300 words."
)


class ThreadSummarizer:
    """Generates and stores conversation thread summaries."""

    def __init__(self):
        from services.ai_core.memory.memory_service import MemoryService

        self._memory = MemoryService()

    async def summarize(
        self,
        thread_id: str,
        user_id: int,
        max_messages: int = 50,
    ) -> str:
        """Get recent messages, call LLM to summarize, store as memory item.

        Returns the generated summary text.
        """
        from db.cerberus_models import CerberusConversationMessage

        # Fetch recent messages
        async with get_session() as session:
            stmt = (
                select(CerberusConversationMessage)
                .where(CerberusConversationMessage.thread_id == thread_id)
                .order_by(CerberusConversationMessage.created_at.desc())
                .limit(max_messages)
            )
            result = await session.execute(stmt)
            messages = list(reversed(result.scalars().all()))

        if not messages:
            logger.info("no_messages_to_summarize", thread_id=thread_id)
            return ""

        # Build conversation text for the LLM
        conversation_text = "\n".join(
            f"[{msg.role}] {msg.content_md or ''}" for msg in messages
        )

        # Call LLM to generate summary
        summary = await self._call_llm(conversation_text)

        # Store as memory item
        await self._memory.store_thread_summary(
            user_id=user_id,
            thread_id=thread_id,
            summary=summary,
        )

        logger.info(
            "thread_summarized",
            thread_id=thread_id,
            message_count=len(messages),
            summary_length=len(summary),
        )
        return summary

    async def _call_llm(self, conversation_text: str) -> str:
        """Call the LLM to generate a summary of the conversation."""
        from config.settings import get_settings

        settings = get_settings()

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.chat.completions.create(
                model=settings.openai_low_latency_model,
                messages=[
                    {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": conversation_text},
                ],
                temperature=0.2,
                max_tokens=500,
            )
            return response.choices[0].message.content or ""

        except Exception:
            logger.exception("summarization_llm_error")
            # Fallback: return a simple truncation
            truncated = conversation_text[:1000]
            return f"[Auto-truncated — LLM unavailable]\n{truncated}"
