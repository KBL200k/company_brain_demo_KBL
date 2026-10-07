"""Runtime settings for one question. Every field defaults to the environment (.env), so callers
(CLI, MCP, web UI) only pass what the user changed.
"""
import os
from dataclasses import dataclass, field, fields
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _env(name, default, cast=str):
    value = os.getenv(name)
    if value in (None, ""):
        return default
    if cast is bool:
        return value.strip().lower() in ("1", "true", "yes", "on")
    return cast(value)


DEFAULT_MODELS = {"claude": "claude-opus-5", "openai": "gpt-5", "gemini": "gemini-2.5-flash"}
# Routes whose answers must not be wrong: answered strictly from retrieved sources at temperature 0.
DEFAULT_STRICT_ROUTES = ("sop_policy", "compliance", "product_catalog")
STRICT_TEMPERATURE = 0.0
MODEL_ENV = {"claude": "CLAUDE_MODEL", "openai": "OPENAI_MODEL", "gemini": "GEMINI_MODEL"}
SEARCH_MODES = ("hybrid", "dense", "bm25")


@dataclass
class Settings:
    # LLM
    provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "claude").lower())
    model: str | None = None          # None -> the provider's *_MODEL env var, then DEFAULT_MODELS
    api_key: str | None = None        # None -> the provider's key env var; never written to disk
    effort: str = field(default_factory=lambda: _env("LLM_EFFORT", "medium"))    # low | medium | high
    max_tool_rounds: int = field(default_factory=lambda: _env("LLM_MAX_TOOL_ROUNDS", 4, int))
    # conversation memory: how many previous question/answer pairs to use (0 = treat every question alone)
    history_turns: int = field(default_factory=lambda: _env("HISTORY_TURNS", 3, int))
    # answer modes: strict routes -> temperature 0 + source-only answers verified by code;
    # every other route -> `temperature` (more natural wording). Models without a temperature
    # parameter (Claude Opus 5 / Sonnet 5, GPT-5 / o-series) keep the strict prompt + verification only.
    strict_routes: list = field(default_factory=lambda: [
        r.strip() for r in _env("STRICT_ROUTES", ",".join(DEFAULT_STRICT_ROUTES)).split(",") if r.strip()])
    temperature: float = field(default_factory=lambda: _env("LLM_TEMPERATURE", 0.5, float))

    def answer_mode(self, route):
        """('strict', 0.0) or ('flexible', self.temperature) for a route."""
        return ("strict", STRICT_TEMPERATURE) if route in self.strict_routes else ("flexible", self.temperature)

    # retrieval
    top_k: int = field(default_factory=lambda: _env("KB_TOP_K", 6, int))
    review_k: int = field(default_factory=lambda: _env("REVIEW_TOP_K", 5, int))
    search_mode: str = field(default_factory=lambda: _env("SEARCH_MODE", "hybrid"))   # hybrid | dense | bm25
    use_glossary: bool = field(default_factory=lambda: _env("USE_GLOSSARY", True, bool))
    rerank: bool = field(default_factory=lambda: _env("RERANK", True, bool))
    rerank_candidates: int = field(default_factory=lambda: _env("RERANK_CANDIDATES", 15, int))
    prefetch_limit: int = field(default_factory=lambda: _env("PREFETCH_LIMIT", 40, int))

    # scope / relevance gates (rerank score, 0-1)
    out_of_scope_gate: float = field(default_factory=lambda: _env("OUT_OF_SCOPE_GATE", 0.20, float))
    no_info_gate: float = field(default_factory=lambda: _env("NO_INFO_GATE", 0.10, float))
    use_llm_router: bool = field(default_factory=lambda: _env("USE_LLM_ROUTER", True, bool))

    def resolved_model(self):
        return self.model or _env(MODEL_ENV.get(self.provider, ""), DEFAULT_MODELS.get(self.provider))

    def search_flags(self):
        return {"use_dense": self.search_mode in ("hybrid", "dense"),
                "use_bm25": self.search_mode in ("hybrid", "bm25"),
                "use_glossary": self.use_glossary, "prefetch_limit": self.prefetch_limit}

    def public(self):
        """Settings without the API key, for traces and logs."""
        d = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "api_key"}
        d["model"] = self.resolved_model()
        d["api_key"] = "set in UI" if self.api_key else "from environment"
        return d
