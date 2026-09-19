from __future__ import annotations

from openai import AsyncOpenAI

from .config import Settings
from .knowledge import KnowledgeBase

BASE_SYSTEM_PROMPT = """
Ты — AI-методолог и наставник проекта.

Твоя задача — помогать человеку учиться через практику на материалах конкретного
проекта. Опирайся прежде всего на переданный банк знаний и методический скилл.

Правила:
- не выдумывай факты, команды, ссылки и правила проекта;
- если ответа нет в материалах, прямо скажи об этом и предложи, что уточнить;
- не делай учебное задание целиком, если полезнее дать наводящий вопрос или шаг;
- объясняй от простого к сложному и проверяй понимание;
- отделяй факты проекта от общих рекомендаций;
- отвечай на языке пользователя;
- используй компактный Markdown, без канцелярита;
- потенциально опасные команды помечай и объясняй последствия.
""".strip()


class TutorAI:
    def __init__(self, settings: Settings, knowledge: KnowledgeBase) -> None:
        self.settings = settings
        self.knowledge = knowledge
        self.client = AsyncOpenAI(
            api_key=settings.polza_ai_api_key,
            base_url=settings.polza_ai_base_url,
        )

    async def answer(
        self,
        user_text: str,
        history: list[dict[str, str]],
    ) -> str:
        context = self.knowledge.context_for(user_text)
        messages = [
            {
                "role": "system",
                "content": (
                    f"{BASE_SYSTEM_PROMPT}\n\n"
                    "=== МАТЕРИАЛЫ ПРОЕКТА И МЕТОДИКА ===\n"
                    f"{context}\n"
                    "=== КОНЕЦ МАТЕРИАЛОВ ==="
                ),
            },
            *history,
            {"role": "user", "content": user_text},
        ]
        response = await self.client.chat.completions.create(
            model=self.settings.polza_ai_model,
            messages=messages,
            temperature=0.35,
            max_tokens=1_500,
        )
        return (response.choices[0].message.content or "").strip()
