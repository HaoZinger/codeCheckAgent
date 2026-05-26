# Code file scanner
import os
from src.types import CodeFile
from src.config import Config

LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript (React)",
    ".tsx": "TypeScript (React)",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Bash",
    ".ps1": "PowerShell",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".xml": "XML",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".md": "Markdown",
    ".txt": "Plain Text",
}


def scan_directory(root_dir: str, config: Config) -> list[CodeFile]:
    """Scan a directory for code files matching supported extensions."""
    code_files = []
    root_dir = os.path.abspath(root_dir)

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in config.supported_extensions:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root_dir)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    continue

                language = LANGUAGE_MAP.get(ext, ext.lstrip("."))
                code_files.append(CodeFile(
                    path=rel_path,
                    content=content,
                    language=language,
                ))

    return code_files


def chunk_large_file(code_file: CodeFile, max_chars: int) -> list[CodeFile]:
    """Split a large file into chunks for processing."""
    if len(code_file.content) <= max_chars:
        return [code_file]

    lines = code_file.content.split("\n")
    chunks = []
    current_chunk = []
    current_len = 0

    for i, line in enumerate(lines):
        line_len = len(line) + 1
        if current_len + line_len > max_chars and current_chunk:
            chunks.append(CodeFile(
                path=f"{code_file.path} (lines {i - len(current_chunk) + 1}-{i})",
                content="\n".join(current_chunk),
                language=code_file.language,
            ))
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += line_len

    if current_chunk:
        chunks.append(CodeFile(
            path=f"{code_file.path} (lines {len(lines) - len(current_chunk) + 1}-{len(lines)})",
            content="\n".join(current_chunk),
            language=code_file.language,
        ))

    return chunks
