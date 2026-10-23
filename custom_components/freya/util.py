"""Utility functions for Freya integration.
Freya 集成通用工具函数。
"""

from __future__ import annotations

import html
import re

_CLEAN_RULES: list[tuple[re.Pattern[str], str]] = [
    # 1. Remove YAML Front Matter.
    # 移除 YAML Front Matter。
    (re.compile(r"\A---\r?\n[\s\S]*?\r?\n---\r?\n?"), ""),

    # 2. Strip code block wrappers and preserve inner text.
    # 移除代码块外壳标记，保留内部文字。
    (re.compile(r"^[ \t]*```[^\r\n]*\r?\n([\s\S]*?)^[ \t]*```[ \t]*$", re.MULTILINE), r"\1"),
    (re.compile(r"```+([^`]+?)```+"), r"\1"),
    (re.compile(r"`([^`\r\n]+)`"), r"\1"),

    # 3. Remove HTML comments, bare URLs, and standard HTML tags.
    # 移除 HTML 注释、裸链接与标准 HTML 标签。
    (re.compile(r"<!--[\s\S]*?-->"), ""),
    (re.compile(r"<(?:https?://|mailto:)[^>\s]+>"), ""),
    (re.compile(r"</?[a-zA-Z][^>]*>"), ""),

    # 4. Remove image syntax and extract link text.
    # 移除图片语法，提取普通链接文字。
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), ""),
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),

    # 5. Remove Markdown footnote definitions and references.
    # 移除 Markdown 脚注定义与引用。
    (re.compile(r"^[ \t]*\[\^[^\]]+\]:.*$\r?\n?", re.MULTILINE), ""),
    (re.compile(r"\[\^[^\]]+\]"), ""),

    # 6. Table formatting: remove header dividers, trim border pipes, and convert column pipes to spaces.
    # 表格处理：删除表头分割线，去除首尾竖线，列分隔符转为空格。
    (re.compile(r"^[ \t]*\|?[ \t:-]+\|[ \t:|-]*$\r?\n?", re.MULTILINE), ""),
    (re.compile(r"^[ \t]*\||\|[ \t]*$", re.MULTILINE), ""),
    (re.compile(r"\|"), " "),

    # 7. Block-level markup: blockquotes, horizontal rules, headings, task checkboxes, and lists.
    # 块级标记：引用、分割线、标题、任务框与列表。
    (re.compile(r"^[ \t]{0,3}(?:>[ \t]*)+", re.MULTILINE), ""),
    (re.compile(r"^[ \t]{0,3}(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})$", re.MULTILINE), ""),
    (re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.*?)[ \t]*#*[ \t]*$", re.MULTILINE), r"\1"),
    (re.compile(r"^[ \t]{0,3}#{1,6}[ \t]*$", re.MULTILINE), ""),
    (re.compile(r"^[ \t]*[-*+][ \t]+(?:\[[ xX]\][ \t]+)?", re.MULTILINE), ""),
    (re.compile(r"^[ \t]*\d+\.[ \t]+", re.MULTILINE), ""),

    # 8. Inline emphasis styles: strip markdown formatting from longest to shortest delimiter.
    # 行内强调样式：由长到短剥离，保留文本内容。
    (re.compile(r"\*{3}(?!\s)([^\*\r\n]+?)(?<!\s)\*{3}"), r"\1"),
    (re.compile(r"\*{2}(?!\s)([^\*\r\n]+?)(?<!\s)\*{2}"), r"\1"),
    (re.compile(r"\*(?!\s)([^\*\r\n]+?)(?<!\s)\*"), r"\1"),
    (re.compile(r"\*{2}(?!\s)([^\*\r\n]+?)(?<!\s)\*{2}"), r"\1"),
    (re.compile(r"(?<![a-zA-Z0-9_])_{3}(?!\s)([^_\r\n]+?)(?<!\s)_{3}(?![a-zA-Z0-9_])"), r"\1"),
    (re.compile(r"(?<![a-zA-Z0-9_])_{2}(?!\s)([^_\r\n]+?)(?<!\s)_{2}(?![a-zA-Z0-9_])"), r"\1"),
    (re.compile(r"(?<![a-zA-Z0-9_])_(?!\s)([^_\r\n]+?)(?<!\s)_(?![a-zA-Z0-9_])"), r"\1"),
    (re.compile(r"(?<![a-zA-Z0-9_])_{2}(?!\s)([^_\r\n]+?)(?<!\s)_{2}(?![a-zA-Z0-9_])"), r"\1"),
    (re.compile(r"~~(?!\s)([^~\r\n]+?)(?<!\s)~~"), r"\1"),

    # 9. Strip modern SMP Emoji characters.
    # 移除 SMP 区现代 Emoji 表情。
    (
        re.compile(
            r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
            r"\U0001F900-\U0001FAFF\U0001F1E6-\U0001F1FF\uFE0F]+"
        ),
        "",
    ),
]

_TRAILING_SPACE_RE = re.compile(r"[ \t]+\r?\n")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def clean_plain_text(text: str) -> str:
    """Clean markdown and format control characters to plain text for TTS / NLP.
    清洗文本中的 Markdown 与格式控制符，转为纯文本。
    """
    if not text:
        return ""

    cleaned = text
    for pattern, repl in _CLEAN_RULES:
        cleaned = pattern.sub(repl, cleaned)

    # 10. Decode HTML entities to prevent TTS from spelling out escape characters.
    # 还原 HTML 实体，防止 TTS 朗读转义符。
    cleaned = html.unescape(cleaned)

    # 11. Compress redundant line breaks and trailing spaces.
    # 压缩多余连续换行与行尾多余空格。
    cleaned = _TRAILING_SPACE_RE.sub("\n", cleaned)
    cleaned = _MULTI_NEWLINE_RE.sub("\n\n", cleaned)

    return cleaned.strip()
