"""Readable terminal search output without additional dependencies."""
import os
from pathlib import PureWindowsPath
import shutil
import sys
import textwrap


def clean(value: object) -> str:
    """Keep document content from injecting terminal control sequences."""
    return "".join(character for character in str(value)
                   if character.isprintable() or character in "\n\t")


def enable_color(stream) -> bool:
    if not stream.isatty() or "NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb":
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        handle = kernel.GetStdHandle(-11 if stream is sys.stdout else -12)
        mode = wintypes.DWORD()
        if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        if not kernel.SetConsoleMode(handle, mode.value | 0x0004):
            return False
    return True


class SearchConsole:
    def __init__(self, enabled: bool = True, color: bool = True, details: bool = False):
        self.enabled = enabled
        self.details = details
        self.width = max(24, min(shutil.get_terminal_size((96, 24)).columns, 104))
        self.color = enabled and color and enable_color(sys.stdout)
        self.status_width = 0

    def paint(self, value: str, style: str) -> str:
        return f"\033[{style}m{value}\033[0m" if self.color and style else value

    def line(self, value: str = "", style: str = "") -> None:
        print(self.paint(value, style) if style else value, flush=True)

    def wrapped(self, value: object, indent: str = "  ") -> None:
        for line in textwrap.wrap(" ".join(clean(value).split()), self.width - len(indent)):
            self.line(indent + line)

    def heading(self, title: str, question: str, strategy: str, section: str | None) -> None:
        if not self.enabled:
            return
        modes = {"A": "Fixed passages", "B": "Paragraph search", "C": "Paragraph search",
                 "D": "Sentence windows", "E": "Hybrid search", "F": "Hybrid + reranking"}
        self.line()
        self.line("  DAY 6  /  DOCUMENT SEARCH", "1;36")
        self.wrapped(title)
        self.line("  " + "─" * (self.width - 4), "2")
        self.wrapped(f"Question  {question}")
        scope = section.replace("_", " ").title() if section else "All chapters"
        self.wrapped(f"Mode      {modes[strategy]} ({strategy})  ·  {scope}")
        self.line()

    def status(self, message: str) -> None:
        if not self.enabled:
            return
        value = "  " + clean(message)
        if sys.stderr.isatty():
            value = value[:self.width - 1]
            sys.stderr.write("\r" + value.ljust(self.status_width))
            sys.stderr.flush()
            self.status_width = len(value)
        elif self.status_width == 0:
            print(value, file=sys.stderr, flush=True)
            self.status_width = len(value)

    def clear_status(self) -> None:
        if self.status_width and sys.stderr.isatty():
            sys.stderr.write("\r" + " " * self.status_width + "\r")
            sys.stderr.flush()
        self.status_width = 0

    def card(self, rank: int, hit: dict) -> None:
        metadata = hit.get("metadata") or {}
        section = clean(metadata.get("section", hit.get("section", "Unknown section")))
        section = section.replace("_", " ").title()
        page = clean(hit.get("page", "?"))
        inner = self.width - 6
        edge = "─" * (self.width - 4)
        self.line("  ╭" + edge + "╮", "36")

        def row(value: str = "", style: str = "") -> None:
            for part in textwrap.wrap(value, inner, replace_whitespace=True) or [""]:
                self.line("  " + self.paint("│", "36") + " " +
                          self.paint(part.ljust(inner), style) + " " + self.paint("│", "36"))

        row(f"{rank:02d}  {section}  ·  PDF page {page}", "1")
        row()
        paragraphs = clean(hit.get("text", "")).split("\n\n")
        for index, paragraph in enumerate(paragraphs):
            if index:
                row()
            row(" ".join(paragraph.split()))
        row()
        source = PureWindowsPath(clean(hit.get("source", "Unknown source"))).name
        row(f"Source: {source}", "2")
        if self.details:
            row(f"Score: {hit['score']:.5f}  ({hit.get('score_type', 'cosine_similarity')})", "2")
            row(f"Chunk: {clean(hit.get('chunk_id', ''))}", "2")
        self.line("  ╰" + edge + "╯", "36")
        self.line()

    def results(self, hits: list[dict], elapsed: float) -> None:
        self.clear_status()
        if not self.enabled:
            return
        if not hits:
            self.wrapped("No matching passages. Try another question or a broader chapter filter.")
        for rank, hit in enumerate(hits, start=1):
            self.card(rank, hit)
        noun = "passage" if len(hits) == 1 else "passages"
        self.wrapped(f"Finished  ·  {len(hits)} {noun}  ·  {elapsed:.2f}s including model loading")
        if not self.details:
            self.wrapped("Options: --details for scores and chunk IDs  ·  --json for raw output")
        self.line()

    def error(self, message: str) -> None:
        self.clear_status()
        print(self.paint("Error: " + clean(message), "1;31"), file=sys.stderr, flush=True)
