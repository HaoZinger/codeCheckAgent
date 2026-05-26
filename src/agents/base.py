# Base agent class with retry and error handling
import json
import re
import time
import logging
import sys
from abc import ABC, abstractmethod
from typing import Optional
from openai import OpenAI

from src.config import AgentConfig

logger = logging.getLogger(__name__)


class AgentFailure(Exception):
    """Raised when an agent fails after all retries."""
    def __init__(self, agent_name: str, message: str, last_error: Optional[Exception] = None):
        self.agent_name = agent_name
        self.message = message
        self.last_error = last_error
        super().__init__(f"[{agent_name}] {message}")


class BaseAgent(ABC):
    """Base class for all agents with retry logic."""

    def __init__(self, name: str, config: AgentConfig, api_key: str, api_base: Optional[str] = None):
        self.name = name
        self.config = config
        client_kwargs = {
            "api_key": api_key,
            "timeout": float(config.timeout_seconds),
            "max_retries": 0,
        }
        if api_base:
            client_kwargs["base_url"] = api_base
        self.client = OpenAI(**client_kwargs)

    # ── status output helpers ───────────────────────────────

    def _status(self, msg: str):
        """Print a status line (goes to stdout, no timestamps)."""
        print(f"  [{self.name}] {msg}", flush=True)

    def _warn(self, msg: str):
        """Print a warning line."""
        logger.debug(f"[{self.name}] {msg}")

    # ── abstract interface ──────────────────────────────────

    @abstractmethod
    def get_system_prompt(self) -> str:
        ...

    @abstractmethod
    def build_user_message(self, **kwargs) -> str:
        ...

    @abstractmethod
    def parse_response(self, content: str, **kwargs):
        ...

    # ── LLM call + retry ────────────────────────────────────

    def call(self, **kwargs) -> str:
        last_error = None
        current_max_tokens = self.config.max_tokens

        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.debug(
                    f"[{self.name}] attempt={attempt}/{self.config.max_retries} "
                    f"model={self.config.model} json_mode={self.config.use_json_mode} "
                    f"max_tokens={current_max_tokens}"
                )

                if not self.config.model or not self.config.model.strip():
                    raise ValueError(
                        f"Model name is empty. Check provider preset or --model flag."
                    )

                request_kwargs = {
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": self.get_system_prompt()},
                        {"role": "user", "content": self.build_user_message(**kwargs)},
                    ],
                    "temperature": self.config.temperature,
                    "max_tokens": current_max_tokens,
                }

                if self.config.use_json_mode:
                    request_kwargs["response_format"] = {"type": "json_object"}

                # Log input size and show waiting indicator
                user_msg = request_kwargs["messages"][1]["content"]
                input_len = len(user_msg)
                logger.debug(
                    f"[{self.name}] sending request "
                    f"(input={input_len} chars, max_tokens={current_max_tokens})"
                )

                t0 = time.time()
                response = self.client.chat.completions.create(**request_kwargs)
                elapsed = time.time() - t0
                choice = response.choices[0]
                content = choice.message.content
                finish = choice.finish_reason if hasattr(choice, "finish_reason") else "unknown"

                logger.debug(
                    f"[{self.name}] finish={finish} "
                    f"len={len(content) if content else 0} "
                    f"elapsed={elapsed:.1f}s"
                )

                # ── empty response ──
                if not content:
                    if self.config.use_json_mode and attempt < self.config.max_retries:
                        self._warn(f"Empty response (JSON mode ON), retrying with JSON mode OFF")
                        self.config.use_json_mode = False
                        raise ValueError("empty (json_mode disabled for retry)")
                    raise ValueError(f"empty response (finish={finish})")

                # ── truncated response ──
                if finish == "length" and attempt < self.config.max_retries:
                    new_max = min(current_max_tokens * 2, 65536)
                    if new_max > current_max_tokens:
                        self._warn(f"Truncated, retrying with max_tokens={new_max}")
                        current_max_tokens = new_max
                        raise ValueError("truncated (retrying with more tokens)")

                return content

            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay_seconds)
                    continue

        raise AgentFailure(
            agent_name=self.name,
            message=f"Failed after {self.config.max_retries} attempts: {last_error}",
            last_error=last_error,
        )

    def run(self, **kwargs):
        raw = self.call(**kwargs)
        try:
            return self.parse_response(raw, **kwargs)
        except Exception as e:
            # Save raw response for debugging
            import os, tempfile
            dump_dir = os.environ.get("CODECHECK_DUMP_DIR", tempfile.gettempdir())
            os.makedirs(dump_dir, exist_ok=True)
            dump_path = os.path.join(
                dump_dir,
                "codecheck_raw_{}_{}.txt".format(self.name, int(time.time()))
            )
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(raw)
            logger.debug(
                "[%s] Raw response (%d chars) saved to: %s",
                self.name, len(raw), dump_path
            )
            raise AgentFailure(
                agent_name=self.name,
                message="Parse error: {}\n  Raw response: {}".format(e, dump_path),
                last_error=e,
            )

    # ── JSON extraction ─────────────────────────────────────

    @staticmethod
    def extract_json(content: str) -> dict:
        if not content or not content.strip():
            raise ValueError("Empty content")

        text = content.strip()
        last_error = None

        # 1: direct parse
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
            return {"value": parsed}
        except json.JSONDecodeError as e:
            last_error = e

        # 2: repair + parse
        repaired = BaseAgent._repair_json(text)
        if repaired != text:
            try:
                parsed = json.loads(repaired)
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list):
                    return {"items": parsed}
            except json.JSONDecodeError:
                pass

        # 3: strip tail
        result = BaseAgent._try_strip_tail(text)
        if result is not None:
            return result

        # 4: code fences
        for lang in ("json", None):
            result = BaseAgent._extract_from_fence(text, lang)
            if result is not None:
                return result

        # 5: outermost braces
        for pair in (("{", "}"), ("[", "]")):
            result = BaseAgent._extract_braced(text, pair[0], pair[1])
            if result is not None:
                if isinstance(result, list):
                    return {"items": result}
                return result

        # error detail
        pos = last_error.pos if last_error else 0
        ctx_start = max(0, pos - 80)
        ctx_end = min(len(text), pos + 80)
        raise ValueError(
            "JSON error at pos {}: {}\n  near: {}".format(
                pos, last_error, text[ctx_start:ctx_end]
            )
        )

    @staticmethod
    def _repair_json(text: str) -> str:
        result = []
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                escape_next = False
                result.append(ch)
                continue
            if ch == "\\":
                escape_next = True
                result.append(ch)
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == "\n":
                    result.append("\\n")
                elif ch == "\r":
                    continue
                elif ch == "\t":
                    result.append("\\t")
                else:
                    result.append(ch)
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _try_strip_tail(text: str) -> Optional[dict]:
        for end in range(len(text), max(0, len(text) - 100), -1):
            candidate = text[:end].rstrip()
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list):
                    return {"items": parsed}
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _extract_from_fence(text: str, lang: Optional[str]) -> Optional[dict]:
        if lang:
            pattern = rf"```{re.escape(lang)}\s*\n(.*?)\n```"
        else:
            pattern = r"```\w*\s*\n(.*?)\n```"
        for match in re.findall(pattern, text, re.DOTALL):
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _extract_braced(text: str, open_c: str, close_c: str) -> Optional[dict | list]:
        start = text.find(open_c)
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == open_c:
                depth += 1
            elif ch == close_c:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None