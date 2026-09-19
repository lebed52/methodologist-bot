from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

WORD_RE = re.compile(r"[a-zа-яё0-9_-]{3,}", re.IGNORECASE)
STOP_WORDS = {
    "как",
    "что",
    "это",
    "для",
    "или",
    "при",
    "про",
    "его",
    "она",
    "они",
    "the",
    "and",
    "with",
}


@dataclass(frozen=True)
class Document:
    path: Path
    title: str
    content: str


class KnowledgeBase:
    def __init__(
        self,
        memory_dir: Path,
        skills_dir: Path,
        max_context_chars: int = 30_000,
    ) -> None:
        self.memory_dir = memory_dir
        self.skills_dir = skills_dir
        self.max_context_chars = max_context_chars
        self._documents: list[Document] = []
        self.reload()

    @property
    def document_count(self) -> int:
        return len(self._documents)

    def reload(self) -> int:
        paths = sorted(self.memory_dir.rglob("*.md")) + sorted(
            self.skills_dir.rglob("*.md")
        )
        self._documents = [
            Document(
                path=path,
                title=_extract_title(path),
                content=path.read_text(encoding="utf-8").strip(),
            )
            for path in paths
            if path.is_file()
        ]
        return len(self._documents)

    def context_for(self, query: str) -> str:
        if not self._documents:
            return "Банк знаний пока пуст."

        query_terms = _terms(query)
        skill_documents = [
            document
            for document in self._documents
            if self.skills_dir in document.path.parents
        ]
        memory_documents = [
            document
            for document in self._documents
            if self.skills_dir not in document.path.parents
        ]
        ranked_memory = sorted(
            memory_documents,
            key=lambda doc: (_score(doc, query_terms), doc.path.name),
            reverse=True,
        )

        selected: list[str] = []
        used = 0
        for document in [*skill_documents, *ranked_memory]:
            block = (
                f"## Источник: {document.title}\n"
                f"Файл: {document.path.name}\n\n{document.content}"
            )
            remaining = self.max_context_chars - used
            if remaining <= 0:
                break
            if len(block) > remaining:
                if not selected:
                    selected.append(block[:remaining])
                continue
            selected.append(block)
            used += len(block)
        return "\n\n---\n\n".join(selected)


def _extract_title(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else path.stem.replace("-", " ").title()


def _terms(text: str) -> set[str]:
    return {
        word.lower() for word in WORD_RE.findall(text) if word.lower() not in STOP_WORDS
    }


def _score(document: Document, query_terms: set[str]) -> int:
    if not query_terms:
        return 0
    title_terms = _terms(document.title)
    content_terms = _terms(document.content)
    return 4 * len(query_terms & title_terms) + len(query_terms & content_terms)
