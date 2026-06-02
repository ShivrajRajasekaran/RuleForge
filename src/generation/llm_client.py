"""LLM Client — Ollama wrapper for RuleForge (Module 5a).

A thin, dependency-free client over a locally-running Ollama server. Uses only
the Python standard library (urllib) so the project runs without `pip install
ollama` — important for reviewers who just clone and run.

Why local LLMs?
- COBOL source is proprietary banking code. It must NEVER leave the machine.
- Zero per-token cost (vs OpenAI/IBM watsonx API billing).
- Reproducible: same model + temperature 0.1 → stable documentation.

Usage:
    client = LLMClient()
    if client.is_available():
        text = client.generate("Explain this COBOL rule: ...")
"""

import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import List, Optional

from src.config import (
    OLLAMA_BASE_URL,
    DEFAULT_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TIMEOUT_SECONDS,
    LLM_MAX_RETRIES,
)


@dataclass
class LLMResponse:
    """Result of a single generation call."""
    text: str
    model: str
    success: bool
    error: str = ""
    elapsed_seconds: float = 0.0


class LLMClient:
    """Minimal client for a local Ollama server.

    Talks to the Ollama REST API:
        GET  /api/tags        → list installed models
        POST /api/generate    → run a prompt (non-streaming)
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = DEFAULT_MODEL,
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = LLM_MAX_TOKENS,
        timeout: int = LLM_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    # ─────────────────────────────────────────────────────────
    # Health / discovery
    # ─────────────────────────────────────────────────────────
    def is_available(self) -> bool:
        """Return True if the Ollama server responds."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def list_models(self) -> List[str]:
        """Return names of installed models (empty list if server is down)."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m.get("name", "") for m in data.get("models", [])]
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
            return []

    def has_model(self, model: Optional[str] = None) -> bool:
        """Check whether a given model (default: self.model) is installed."""
        target = (model or self.model).lower()
        installed = [m.lower() for m in self.list_models()]
        # Ollama tags are like "mistral:latest"; match on the base name too.
        return any(target == m or m.startswith(target + ":") for m in installed)

    # ─────────────────────────────────────────────────────────
    # Generation
    # ─────────────────────────────────────────────────────────
    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        """Run a prompt through the model (non-streaming, with retries)."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        if system:
            payload["system"] = system

        body = json.dumps(payload).encode("utf-8")
        last_error = ""

        for attempt in range(LLM_MAX_RETRIES + 1):
            start = time.time()
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/api/generate",
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data.get("response", "").strip()
                    elapsed = time.time() - start
                    if text:
                        return LLMResponse(
                            text=text,
                            model=self.model,
                            success=True,
                            elapsed_seconds=elapsed,
                        )
                    last_error = "Empty response from model"
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                last_error = f"Connection error: {e}"
            except json.JSONDecodeError as e:
                last_error = f"Bad JSON from server: {e}"

            # brief backoff before retry
            if attempt < LLM_MAX_RETRIES:
                time.sleep(1.0)

        return LLMResponse(
            text="",
            model=self.model,
            success=False,
            error=last_error,
        )


# ═══════════════════════════════════════════════════
# RUN DIRECTLY TO TEST
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 70)
    print("  RULEFORGE — LLM CLIENT (Ollama) HEALTH CHECK")
    print("=" * 70)

    client = LLMClient()
    print(f"  Endpoint : {client.base_url}")
    print(f"  Model    : {client.model}")
    print(f"  Available: {client.is_available()}")

    if not client.is_available():
        print("\n  Ollama server is NOT running.")
        print("  Start it with:  ollama serve   (or launch the Ollama app)")
        raise SystemExit(1)

    models = client.list_models()
    print(f"  Installed: {', '.join(models) if models else '(none)'}")

    if not client.has_model():
        print(f"\n  Model '{client.model}' not installed.")
        print(f"  Pull it with:  ollama pull {client.model}")
        raise SystemExit(1)

    print("\n  Running test prompt...")
    resp = client.generate(
        "In one sentence, what is a business rule in software? Be concise."
    )
    print("-" * 70)
    if resp.success:
        print(f"  Response ({resp.elapsed_seconds:.1f}s):")
        print(f"  {resp.text}")
    else:
        print(f"  FAILED: {resp.error}")
    print("=" * 70)
