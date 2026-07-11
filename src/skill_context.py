"""Lightweight skill context retrieval for LLM prompts."""
import json
import re
from pathlib import Path
from typing import List, Dict


class SkillContext:
    """Load project skill/reference files and retrieve relevant chunks by keyword overlap."""

    def __init__(self, config_paths: List[str]):
        self.chunks: List[Dict] = []
        for path in config_paths:
            self._load(path)

    def _load(self, path: str) -> None:
        full_path = Path(path)
        if not full_path.exists():
            return
        if full_path.suffix == ".md":
            text = full_path.read_text(encoding="utf-8")
            self.chunks.extend(self._split_markdown(text, source=str(full_path)))
        elif full_path.suffix == ".json":
            text = full_path.read_text(encoding="utf-8")
            self.chunks.append(
                {
                    "source": str(full_path),
                    "title": "JSON reference",
                    "content": text,
                    "keywords": self._extract_keywords(text),
                }
            )

    def _split_markdown(self, text: str, source: str) -> List[Dict]:
        """Split markdown by headings; each heading becomes a chunk."""
        chunks: List[Dict] = []
        current_title = "Introduction"
        current_lines: List[str] = []

        def flush():
            content = "\n".join(current_lines).strip()
            if content:
                chunks.append(
                    {
                        "source": source,
                        "title": current_title,
                        "content": content,
                        "keywords": self._extract_keywords(content + " " + current_title),
                    }
                )

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                flush()
                current_title = stripped.lstrip("#").strip()
                current_lines = []
            else:
                current_lines.append(line)
        flush()
        return chunks

    @staticmethod
    def _extract_keywords(text: str) -> set:
        """Extract lowercase alphanumeric/CJK keywords."""
        return set(re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", text.lower()))

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        """Return the top-k chunks with the most keyword overlap with the query."""
        query_keywords = self._extract_keywords(query)
        scored = []
        for chunk in self.chunks:
            overlap = len(query_keywords & chunk["keywords"])
            if overlap > 0:
                scored.append((overlap, chunk))
        scored.sort(key=lambda item: (-item[0], item[1]["source"], item[1]["title"]))
        return [chunk for _, chunk in scored[:top_k]]

    def format_chunks(self, chunks: List[Dict]) -> str:
        """Format chunks into a single string suitable for an LLM system prompt."""
        parts = []
        for chunk in chunks:
            parts.append(f"# {chunk['title']}\nSource: {chunk['source']}\n\n{chunk['content']}")
        return "\n\n---\n\n".join(parts)
