"""Central configuration for RuleForge.

All tunable knobs (LLM endpoint, model, generation params) live here so the
rest of the codebase never hard-codes them. Values can be overridden via
environment variables for CI / different machines.
"""

import os


# ─────────────────────────────────────────────────────────────
# LLM / Ollama settings
# ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("RULEFORGE_OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("RULEFORGE_MODEL", "mistral")

# Low temperature → deterministic, factual output (we do NOT want creativity
# when documenting business rules — hallucination is the enemy).
LLM_TEMPERATURE = float(os.getenv("RULEFORGE_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("RULEFORGE_MAX_TOKENS", "1024"))
LLM_TIMEOUT_SECONDS = int(os.getenv("RULEFORGE_TIMEOUT", "120"))

# Number of retries if the model call fails or returns empty.
LLM_MAX_RETRIES = int(os.getenv("RULEFORGE_RETRIES", "2"))
