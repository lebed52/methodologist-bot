from pathlib import Path

from src.bot import _membership_grants_access, _split_message
from src.knowledge import KnowledgeBase


def test_relevant_document_is_first(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    skills = tmp_path / "skills"
    memory.mkdir()
    skills.mkdir()
    (memory / "api.md").write_text(
        "# API проекта\nЗапросы отправляются через Postman.",
        encoding="utf-8",
    )
    (memory / "git.md").write_text(
        "# Git\nИзменения отправляются через pull request.",
        encoding="utf-8",
    )

    knowledge = KnowledgeBase(memory, skills)
    context = knowledge.context_for("Как отправить запрос в Postman API?")

    assert context.index("API проекта") < context.index("# Git")


def test_empty_knowledge_base(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    skills = tmp_path / "skills"
    memory.mkdir()
    skills.mkdir()

    knowledge = KnowledgeBase(memory, skills)

    assert knowledge.document_count == 0
    assert knowledge.context_for("вопрос") == "Банк знаний пока пуст."


def test_skill_is_always_included_before_memory(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    skills = tmp_path / "skills"
    memory.mkdir()
    skills.mkdir()
    (memory / "api.md").write_text("# API\nPostman", encoding="utf-8")
    (skills / "method.md").write_text("# Методика\nДавай подсказку.", encoding="utf-8")

    context = KnowledgeBase(memory, skills).context_for("Postman")

    assert context.index("Методика") < context.index("# API")


def test_long_telegram_message_is_split() -> None:
    parts = _split_message("слово " * 1_000, limit=500)

    assert len(parts) > 1
    assert all(len(part) <= 500 for part in parts)


def test_only_channel_members_get_access() -> None:
    assert _membership_grants_access("creator")
    assert _membership_grants_access("administrator")
    assert _membership_grants_access("member")
    assert _membership_grants_access("restricted", is_member=True)
    assert not _membership_grants_access("restricted", is_member=False)
    assert not _membership_grants_access("left")
    assert not _membership_grants_access("kicked")
