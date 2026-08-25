# LLM provider — hint drafting via Ollama (or any OpenAI-compatible drop-in).
# Pure hint path: no grading, no JSON validation needed.

import os
import requests

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")
DEFAULT_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434").rstrip("/")


class ProviderDown(Exception):
    pass


class OllamaProvider:
    def __init__(self, model: str = DEFAULT_MODEL, base: str = DEFAULT_BASE, timeout: int = 60):
        self.model = model
        self.base = base.rstrip("/")
        self.timeout = int(os.environ.get("OLLAMA_TIMEOUT", str(timeout)))
        # Reuse session for connection pooling (faster than requests.post each time)
        self._session = requests.Session()

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def complete(self, prompt: str) -> str:
        try:
            resp = self._session.post(
                f"{self.base}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "options": {"num_predict": 300, "num_ctx": 4096},
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "")
            if not text or not text.strip():
                raise ValueError("model returned empty response")
            return text
        except Exception as e:
            raise ProviderDown(str(e)) from e

    def draft_hint(self, question: str) -> str:
        """One short hint (max 2 sentences), never the final answer."""
        prompt = (
            "Write ONE short hint (max 2 sentences) for this logic question. "
            "Nudge the student toward the right idea — never give the final answer.\n\n"
            f"Question:\n{question}\n\nReply with only the hint text."
        )
        return self.complete(prompt).strip()

    def health(self) -> bool:
        try:
            r = self._session.get(f"{self.base}/api/tags", timeout=5)
            return r.ok
        except Exception:
            return False
