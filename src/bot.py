from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatAction, ChatType
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from .ai import TutorAI
from .config import Settings, load_settings
from .knowledge import KnowledgeBase
from .storage import ConversationStore

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
START_COVER_PATH = Path(__file__).resolve().parent.parent / "assets/start-cover.png"
REPOSITORY_URL = "https://github.com/lebed52/methodologist-bot"


class MethodologistBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.knowledge = KnowledgeBase(
            settings.memory_dir,
            settings.skills_dir,
            settings.max_context_chars,
        )
        self.store = ConversationStore(settings.database_path)
        self.ai = TutorAI(settings, self.knowledge)
        self.username = ""

    async def post_init(self, application: Application) -> None:
        await self.store.initialize()
        me = await application.bot.get_me()
        self.username = (me.username or "").lower()
        await application.bot.set_my_commands(
            [
                ("start", "Что умеет методолог"),
                ("help", "Как задавать вопросы"),
                ("new", "Начать диалог заново"),
                ("reload", "Перечитать memory и skills"),
                ("status", "Проверить конфигурацию"),
            ]
        )
        logger.info(
            "Bot @%s started: model=%s documents=%s",
            self.username,
            self.settings.polza_ai_model,
            self.knowledge.document_count,
        )

    def allowed(self, update: Update) -> bool:
        user = update.effective_user
        allowed_ids = self.settings.allowed_user_ids
        return bool(user and (not allowed_ids or user.id in allowed_ids))

    async def subscribed(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> bool:
        if not self.settings.required_channel:
            return True
        user = update.effective_user
        if not user:
            return False
        try:
            member = await context.bot.get_chat_member(
                self.settings.required_channel,
                user.id,
            )
        except TelegramError as error:
            logger.warning(
                "Could not check subscription channel=%s user_id=%s: %s",
                self.settings.required_channel,
                user.id,
                error,
            )
            return False
        return _membership_grants_access(
            member.status,
            getattr(member, "is_member", False),
        )

    async def has_access(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> bool:
        if not self.allowed(update):
            await self.deny(update)
            return False
        if await self.subscribed(update, context):
            return True
        if update.effective_message:
            await _reply_with_retry(
                update.effective_message,
                "Доступ к демо открывается после подписки на @qabigtech.\n\n"
                "Подпишитесь на канал и нажмите «Проверить подписку».",
                reply_markup=self.subscription_keyboard(),
            )
        return False

    def subscription_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"Подписаться на {self.settings.required_channel}",
                        url=self.settings.required_channel_url,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Начать работу",
                        callback_data="check_subscription",
                    )
                ],
            ]
        )

    async def deny(self, update: Update) -> None:
        if update.effective_message:
            await _reply_with_retry(
                update.effective_message,
                "У вас нет доступа к этому боту.",
            )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.allowed(update):
            await self.deny(update)
            return
        has_subscription = await self.subscribed(update, context)
        caption = (
            "Демонстрационный бот к докладу Сергея Лебедева на SQA Days.\n\n"
            "Я Борис, Дух методолога. Показываю, как банк памяти и методический "
            "скилл превращают обычный AI-чат в наставника по конкретному проекту."
        )
        reply_markup = (
            self.subscription_keyboard() if self.settings.required_channel else None
        )
        if self.settings.required_channel:
            caption += (
                "\n\nЧтобы начать работу, подпишитесь на Telegram-канал "
                f"{self.settings.required_channel} и нажмите «Начать работу»."
            )
        if has_subscription:
            caption += (
                "\n\nСейчас внутри демонстрационные материалы. Спросите: "
                "«Расскажи о проекте», «С чего начать обучение?» или "
                "«Дай практическое задание».\n\n"
                "/new — очистить историю диалога\n"
                "/reload — перечитать memory и skills\n"
                "/status — показать модель и число файлов"
            )
        if START_COVER_PATH.exists():
            await _reply_photo_with_retry(
                update.effective_message,
                START_COVER_PATH,
                caption,
                reply_markup=reply_markup,
            )
        else:
            await _reply_with_retry(
                update.effective_message,
                caption,
                reply_markup=reply_markup,
            )

    async def check_subscription(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        query = update.callback_query
        if not query or not update.effective_user:
            return
        if not self.allowed(update):
            await query.answer("У вас нет доступа к этому боту.", show_alert=True)
            return
        if await self.subscribed(update, context):
            await query.answer("Подписка подтверждена")
            await query.edit_message_reply_markup(reply_markup=None)
            await _reply_with_retry(
                query.message,
                "Подписка подтверждена. Доступ открыт.\n\n"
                "Что это за проект\n"
                "«Дух методолога» — open-source Telegram-бот, который отвечает "
                "по материалам конкретного проекта и помогает учиться на реальных "
                "задачах. GPT-5 работает через Polza.ai, а знания и поведение "
                "лежат в обычных Markdown-файлах.\n\n"
                "Где применять\n"
                "• onboarding новых сотрудников;\n"
                "• внутреннее обучение команды;\n"
                "• курс или учебный проект;\n"
                "• база знаний с AI-наставником.\n\n"
                "Как запустить у себя\n"
                "1. Клонируйте репозиторий.\n"
                "2. Создайте бота через BotFather.\n"
                "3. Добавьте ключ Polza.ai в .env.\n"
                "4. Замените файлы в memory/ и skills/ материалами своего проекта.\n"
                "5. Запустите python -m src.bot или Docker Compose.\n\n"
                f"Код и полная инструкция:\n{REPOSITORY_URL}\n\n"
                "Для демонстрации напишите: «Расскажи о проекте» или "
                "«Дай практическое задание».",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Открыть репозиторий",
                                url=REPOSITORY_URL,
                            )
                        ]
                    ]
                ),
            )
            return
        await query.answer(
            "Подписка пока не найдена. Подпишитесь и попробуйте ещё раз.",
            show_alert=True,
        )

    async def new_dialog(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self.has_access(update, context):
            return
        await self.store.clear(update.effective_chat.id)
        await _reply_with_retry(
            update.effective_message,
            "История очищена. Начинаем заново.",
        )

    async def reload_knowledge(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self.has_access(update, context):
            return
        count = self.knowledge.reload()
        await _reply_with_retry(
            update.effective_message, f"Перечитал банк знаний: {count} Markdown-файлов."
        )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.has_access(update, context):
            return
        mode = "ограничен списком ID" if self.settings.allowed_user_ids else "открыт"
        await _reply_with_retry(
            update.effective_message,
            f"Модель: {self.settings.polza_ai_model}\n"
            f"Файлов знаний: {self.knowledge.document_count}\n"
            f"Доступ: {mode}",
        )

    async def message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.has_access(update, context):
            return
        message = update.effective_message
        if not message or not message.text:
            return
        if not self._addressed_to_bot(update):
            return

        text = self._clean_mention(message.text)
        if not text:
            await _reply_with_retry(
                message,
                "Напишите вопрос после упоминания бота.",
            )
            return

        chat_id = update.effective_chat.id
        history = await self.store.history(chat_id, self.settings.max_history_messages)
        try:
            await asyncio.wait_for(
                context.bot.send_chat_action(
                    chat_id=chat_id,
                    action=ChatAction.TYPING,
                ),
                timeout=3,
            )
        except (TimeoutError, TelegramError):
            logger.warning("Could not send typing action to chat_id=%s", chat_id)
        try:
            answer = await self.ai.answer(text, history)
        except Exception:
            logger.exception("Polza.ai request failed")
            await _reply_with_retry(
                message,
                "Не смог получить ответ от AI. Проверьте ключ Polza.ai и логи бота.",
            )
            return

        if not answer:
            answer = "Модель вернула пустой ответ. Попробуйте переформулировать вопрос."
        await self.store.add(chat_id, "user", text)
        await self.store.add(chat_id, "assistant", answer)
        for part in _split_message(answer):
            await _reply_with_retry(
                message,
                part,
                disable_web_page_preview=True,
            )

    def _addressed_to_bot(self, update: Update) -> bool:
        message = update.effective_message
        if update.effective_chat.type == ChatType.PRIVATE:
            return True
        mention = f"@{self.username}" if self.username else ""
        is_mentioned = bool(mention and mention in (message.text or "").lower())
        is_reply = bool(
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.is_bot
            and message.reply_to_message.from_user.username
            and message.reply_to_message.from_user.username.lower() == self.username
        )
        return is_mentioned or is_reply

    def _clean_mention(self, text: str) -> str:
        if not self.username:
            return text.strip()
        return (
            text.replace(f"@{self.username}", "")
            .replace(f"@{self.username.upper()}", "")
            .strip()
        )


def _split_message(text: str, limit: int = 4_000) -> list[str]:
    parts: list[str] = []
    rest = text.strip()
    while len(rest) > limit:
        split_at = rest.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = rest.rfind(" ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        parts.append(rest[:split_at].strip())
        rest = rest[split_at:].strip()
    if rest:
        parts.append(rest)
    return parts


async def _reply_with_retry(
    message: Message,
    text: str,
    attempts: int = 3,
    **kwargs,
) -> Message:
    last_error: TelegramError | None = None
    for attempt in range(attempts):
        try:
            return await message.reply_text(text, **kwargs)
        except TelegramError as error:
            last_error = error
            wait_seconds = 2**attempt
            logger.warning(
                "reply_text chat_id=%s attempt=%s/%s failed: %s; retry in %ss",
                message.chat_id,
                attempt + 1,
                attempts,
                error,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
    if last_error is None:
        raise RuntimeError("Reply failed without TelegramError")
    raise last_error


async def _reply_photo_with_retry(
    message: Message,
    photo_path: Path,
    caption: str,
    attempts: int = 3,
    **kwargs,
) -> Message:
    last_error: TelegramError | None = None
    for attempt in range(attempts):
        try:
            with photo_path.open("rb") as photo:
                return await message.reply_photo(photo=photo, caption=caption, **kwargs)
        except TelegramError as error:
            last_error = error
            wait_seconds = 2**attempt
            logger.warning(
                "reply_photo chat_id=%s attempt=%s/%s failed: %s; retry in %ss",
                message.chat_id,
                attempt + 1,
                attempts,
                error,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
    if last_error is None:
        raise RuntimeError("Photo reply failed without TelegramError")
    raise last_error


def _membership_grants_access(status: str, is_member: bool = False) -> bool:
    return status in {"creator", "administrator", "member"} or (
        status == "restricted" and is_member
    )


def main() -> None:
    settings = load_settings()
    bot = MethodologistBot(settings)
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30,
        connection_pool_size=8,
    )
    get_updates_request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30,
        connection_pool_size=2,
    )
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .request(request)
        .get_updates_request(get_updates_request)
        .post_init(bot.post_init)
        .build()
    )
    application.add_handler(CommandHandler(["start", "help"], bot.start))
    application.add_handler(CommandHandler("new", bot.new_dialog))
    application.add_handler(CommandHandler("reload", bot.reload_knowledge))
    application.add_handler(CommandHandler("status", bot.status))
    application.add_handler(
        CallbackQueryHandler(
            bot.check_subscription,
            pattern=r"^check_subscription$",
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, bot.message)
    )
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        bootstrap_retries=3,
    )


if __name__ == "__main__":
    main()
