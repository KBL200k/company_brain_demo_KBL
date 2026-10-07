"""LLM providers behind one interface: Claude (Anthropic), GPT (OpenAI), Gemini (Google).

Each adapter uses its vendor's official SDK and exposes two operations:
  structured(system, user, schema)          -> dict    JSON that matches `schema` (used by the router)
  chat_with_tools(system, user, tools, run) -> dict    tool-calling loop, returns final text + trace

get_llm(provider, model=None, api_key=None) builds an adapter. Anything not given comes from the environment
(.env is loaded if present):
  claude : ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN / `ant auth login` profile), CLAUDE_MODEL,
           CLAUDE_FALLBACKS ("default" | "off")
  openai : OPENAI_API_KEY, OPENAI_MODEL, OPENAI_REASONING_EFFORT (default low)
  gemini : GEMINI_API_KEY or GOOGLE_API_KEY, GEMINI_MODEL
  LLM_PROVIDER picks the default provider; LLM_DISABLED=1 forces the no-LLM path.
list_models(provider, api_key) asks the vendor's API which models the key can use.
"""
import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROVIDERS = ("claude", "openai", "gemini")
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "claude").lower()
DEFAULT_MODELS = {"claude": "claude-opus-5", "openai": "gpt-5", "gemini": "gemini-2.5-flash"}
# Offline suggestions shown before the user loads the live list from the API.
SUGGESTED_MODELS = {
    "claude": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5", "claude-opus-4-8", "claude-fable-5-1"],
    "openai": ["gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4.1-mini", "gpt-4o"],
    "gemini": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
}
KEY_ENV = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


class LLMUnavailable(RuntimeError):
    """No credentials, unknown provider, or the API cannot be reached: callers fall back to no-LLM mode."""


class LLMRefused(RuntimeError):
    """The model declined the request."""


def _tool_text(result):
    return json.dumps(result, ensure_ascii=False, default=str)[:20000]


def _join(texts):
    """Text the model wrote across tool rounds. Models may write part of the answer in the same turn as a
    tool call (e.g. sections 1-5, then check_claims, then section 6), so keeping only the last turn loses it."""
    return "\n\n".join(t.strip() for t in texts if t and t.strip())


def _env_key(provider):
    if provider == "claude":
        return os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


# ---------------------------------------------------------------- Claude

class ClaudeLLM:
    name = "claude"
    # models that take adaptive thinking + effort; older/smaller ones (Haiku 4.5) take neither
    ADAPTIVE = ("claude-opus-5", "claude-sonnet-5", "claude-fable", "claude-mythos", "claude-opus-4-")
    # server-side refusal fallback is offered for these
    FALLBACK_OK = ("claude-opus-5", "claude-fable-5")
    # sampling parameters (temperature/top_p) were removed on these models: sending one is a 400
    NO_SAMPLING = ("claude-opus-5", "claude-sonnet-5", "claude-fable", "claude-mythos", "claude-opus-4-7",
                   "claude-opus-4-8")

    @property
    def supports_temperature(self):
        return not self.model.startswith(self.NO_SAMPLING)

    def __init__(self, model, api_key=None, max_tool_rounds=4):
        import anthropic
        self.anthropic = anthropic
        self.model = model
        self.max_tool_rounds = max_tool_rounds
        self.fallbacks = os.getenv("CLAUDE_FALLBACKS", "default")
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=3) if api_key \
            else anthropic.Anthropic(max_retries=3)

    @staticmethod
    def available(api_key=None):
        return bool(api_key or _env_key("claude") or os.getenv("ANTHROPIC_PROFILE")
                    or Path.home().joinpath(".config", "anthropic").exists())

    def _create(self, system, messages, effort, tools=None, schema=None, max_tokens=16000, temperature=None):
        kwargs = dict(
            model=self.model, max_tokens=max_tokens, messages=messages,
            # static system prompt -> cached across questions
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        )
        output_config = {}
        use_temperature = temperature is not None and self.supports_temperature
        if use_temperature:
            # older models that still take temperature: run without thinking so the two don't conflict
            kwargs["temperature"] = temperature
        elif self.model.startswith(self.ADAPTIVE):
            kwargs["thinking"] = {"type": "adaptive"}
        if self.model.startswith(self.ADAPTIVE):
            output_config["effort"] = effort
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        if output_config:
            kwargs["output_config"] = output_config
        if tools:
            kwargs["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                               for t in tools]
        if self.fallbacks != "off" and self.model.startswith(self.FALLBACK_OK):
            # a policy decline is re-run server-side on Anthropic's recommended fallback model
            kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks=self.fallbacks)
        a = self.anthropic
        try:
            resp = self.client.beta.messages.create(**kwargs)
        except (a.AuthenticationError, a.PermissionDeniedError) as e:
            raise LLMUnavailable(f"claude: {e.message}") from e
        except a.NotFoundError as e:
            raise LLMUnavailable(f"claude: model {self.model!r} not found") from e
        except a.APIConnectionError as e:
            raise LLMUnavailable(f"claude: cannot reach the API ({e})") from e
        if resp.stop_reason == "refusal":
            raise LLMRefused("claude declined the request")
        return resp

    @staticmethod
    def _text(resp):
        return "".join(b.text for b in resp.content if b.type == "text")

    def structured(self, system, user, schema, effort="low", temperature=None):
        resp = self._create(system, [{"role": "user", "content": user}], effort, schema=schema, max_tokens=4000,
                            temperature=temperature)
        return json.loads(self._text(resp))

    def chat_with_tools(self, system, user, tools, run_tool, effort="medium", temperature=None):
        messages = [{"role": "user", "content": user}]
        trace, texts = [], []
        for _ in range(self.max_tool_rounds + 1):
            resp = self._create(system, messages, effort, tools=tools, temperature=temperature)
            texts.append(self._text(resp))
            calls = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason != "tool_use" or not calls:
                return {"text": _join(texts), "tool_calls": trace, "stop_reason": resp.stop_reason}
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for c in calls:  # all results go back in ONE user message
                out, is_error = run_tool(c.name, c.input)
                trace.append({"tool": c.name, "input": c.input, "error": is_error})
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": _tool_text(out),
                                "is_error": is_error})
            messages.append({"role": "user", "content": results})
        resp = self._create(system, messages + [{"role": "user", "content": "Answer now with what you have."}], effort,
                            temperature=temperature)
        return {"text": _join(texts + [self._text(resp)]), "tool_calls": trace, "stop_reason": resp.stop_reason}

    def list_models(self):
        return [m.id for m in self.client.models.list()]


# ---------------------------------------------------------------- OpenAI

class OpenAILLM:
    name = "openai"

    def __init__(self, model, api_key=None, max_tool_rounds=4):
        import openai
        self.openai = openai
        self.model = model
        self.max_tool_rounds = max_tool_rounds
        self.reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "low")
        self.client = openai.OpenAI(api_key=api_key, max_retries=3) if api_key else openai.OpenAI(max_retries=3)

    REASONING = ("gpt-5", "o1", "o3", "o4")

    @staticmethod
    def available(api_key=None):
        return bool(api_key or _env_key("openai"))

    @property
    def supports_temperature(self):
        # reasoning models (GPT-5, o-series) only accept the default temperature
        return not self.model.startswith(self.REASONING)

    def _create(self, messages, effort=None, temperature=None, **kwargs):
        if self.model.startswith(self.REASONING):  # reasoning models only
            kwargs["reasoning_effort"] = {"high": "high", "medium": "medium"}.get(effort, self.reasoning_effort)
        if temperature is not None and self.supports_temperature:
            kwargs["temperature"] = temperature
        o = self.openai
        try:
            return self.client.chat.completions.create(model=self.model, messages=messages,
                                                       max_completion_tokens=16000, **kwargs)
        except (o.AuthenticationError, o.PermissionDeniedError) as e:
            raise LLMUnavailable(f"openai: {e}") from e
        except o.NotFoundError as e:
            raise LLMUnavailable(f"openai: model {self.model!r} not found") from e
        except o.APIConnectionError as e:
            raise LLMUnavailable(f"openai: cannot reach the API ({e})") from e

    def structured(self, system, user, schema, effort="low", temperature=None):
        resp = self._create(
            [{"role": "system", "content": system}, {"role": "user", "content": user}], effort="low",
            temperature=temperature, response_format={"type": "json_schema", "json_schema": {"name": "output", "schema": schema, "strict": True}})
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None):
            raise LLMRefused(f"openai declined: {msg.refusal}")
        return json.loads(msg.content)

    def chat_with_tools(self, system, user, tools, run_tool, effort="medium", temperature=None):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        specs = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                   "parameters": t["parameters"]}} for t in tools]
        trace, texts = [], []
        for _ in range(self.max_tool_rounds + 1):
            resp = self._create(messages, effort=effort, temperature=temperature, tools=specs)
            msg = resp.choices[0].message
            if getattr(msg, "refusal", None):
                raise LLMRefused(f"openai declined: {msg.refusal}")
            texts.append(msg.content or "")
            if not msg.tool_calls:
                return {"text": _join(texts), "tool_calls": trace, "stop_reason": resp.choices[0].finish_reason}
            messages.append(msg.model_dump(exclude_none=True))
            for c in msg.tool_calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                    out, is_error = run_tool(c.function.name, args)
                except json.JSONDecodeError as e:
                    args, out, is_error = {}, {"error": f"invalid JSON arguments: {e}"}, True
                trace.append({"tool": c.function.name, "input": args, "error": is_error})
                messages.append({"role": "tool", "tool_call_id": c.id, "content": _tool_text(out)})
        messages.append({"role": "user", "content": "Answer now with what you have."})
        resp = self._create(messages, effort=effort, temperature=temperature)
        return {"text": _join(texts + [resp.choices[0].message.content or ""]), "tool_calls": trace,
                "stop_reason": resp.choices[0].finish_reason}

    def list_models(self):
        ids = [m.id for m in self.client.models.list()]
        chat = [i for i in ids if i.startswith(("gpt-", "o1", "o3", "o4", "chatgpt"))
                and not any(x in i for x in ("audio", "realtime", "transcribe", "tts", "image", "search", "embedding"))]
        return sorted(chat, reverse=True)


# ---------------------------------------------------------------- Gemini

class GeminiLLM:
    name = "gemini"

    def __init__(self, model, api_key=None, max_tool_rounds=4):
        from google import genai
        from google.genai import errors, types
        self.types, self.errors = types, errors
        self.model = model
        self.max_tool_rounds = max_tool_rounds
        self.client = genai.Client(api_key=api_key or _env_key("gemini"))

    supports_temperature = True

    @staticmethod
    def available(api_key=None):
        return bool(api_key or _env_key("gemini"))

    def _generate(self, contents, config):
        try:
            return self.client.models.generate_content(model=self.model, contents=contents, config=config)
        except self.errors.ClientError as e:
            if getattr(e, "code", None) in (400, 401, 403) and "API key" in str(e):
                raise LLMUnavailable(f"gemini: {e}") from e
            if getattr(e, "code", None) == 404:
                raise LLMUnavailable(f"gemini: model {self.model!r} not found") from e
            raise

    def structured(self, system, user, schema, effort="low", temperature=None):
        t = self.types
        resp = self._generate(user, t.GenerateContentConfig(
            system_instruction=system, response_mime_type="application/json", response_json_schema=schema,
            temperature=temperature))
        if not resp.text:
            raise LLMRefused("gemini returned no content (blocked or empty)")
        return json.loads(resp.text)

    def chat_with_tools(self, system, user, tools, run_tool, effort="medium", temperature=None):
        t = self.types
        decls = [t.FunctionDeclaration(name=x["name"], description=x["description"],
                                       parameters_json_schema=x["parameters"]) for x in tools]
        config = t.GenerateContentConfig(
            system_instruction=system, tools=[t.Tool(function_declarations=decls)], temperature=temperature,
            # we run the loop ourselves so every call goes through run_tool and the trace
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True))
        contents = [t.Content(role="user", parts=[t.Part(text=user)])]
        trace, texts = [], []
        for _ in range(self.max_tool_rounds + 1):
            resp = self._generate(contents, config)
            texts.append(self._text(resp))
            calls = resp.function_calls or []
            if not calls:
                return {"text": _join(texts), "tool_calls": trace,
                        "stop_reason": str(resp.candidates[0].finish_reason) if resp.candidates else None}
            contents.append(resp.candidates[0].content)
            parts = []
            for c in calls:
                out, is_error = run_tool(c.name, dict(c.args or {}))
                trace.append({"tool": c.name, "input": dict(c.args or {}), "error": is_error})
                parts.append(t.Part.from_function_response(name=c.name, response={"result": out}))
            contents.append(t.Content(role="user", parts=parts))
        contents.append(t.Content(role="user", parts=[t.Part(text="Answer now with what you have.")]))
        resp = self._generate(contents, t.GenerateContentConfig(system_instruction=system, temperature=temperature))
        return {"text": _join(texts + [self._text(resp)]), "tool_calls": trace, "stop_reason": "max_rounds"}

    @staticmethod
    def _text(resp):
        # text parts only: resp.text warns and may drop text when the same turn also has function calls
        parts = resp.candidates[0].content.parts if resp.candidates and resp.candidates[0].content else None
        return "".join(p.text for p in parts or [] if getattr(p, "text", None) and not getattr(p, "thought", False))

    def list_models(self):
        out = []
        for m in self.client.models.list():
            if "generateContent" in (m.supported_actions or []) and "gemini" in m.name:
                out.append(m.name.removeprefix("models/"))
        return sorted(out, reverse=True)


_CLASSES = {"claude": ClaudeLLM, "openai": OpenAILLM, "gemini": GeminiLLM}


def available_providers():
    if os.getenv("LLM_DISABLED") == "1":
        return []
    return [p for p, cls in _CLASSES.items() if cls.available()]


@lru_cache(maxsize=16)
def _instance(provider, model, api_key, max_tool_rounds):
    return _CLASSES[provider](model, api_key, max_tool_rounds)


def get_llm(provider=None, model=None, api_key=None, max_tool_rounds=4):
    """The adapter for `provider` (default LLM_PROVIDER). Raises LLMUnavailable if it can't be used."""
    provider = (provider or DEFAULT_PROVIDER).lower()
    if provider not in _CLASSES:
        raise LLMUnavailable(f"unknown provider {provider!r}; choose one of {', '.join(PROVIDERS)}")
    if os.getenv("LLM_DISABLED") == "1":
        raise LLMUnavailable("LLM_DISABLED=1")
    if not _CLASSES[provider].available(api_key):
        raise LLMUnavailable(f"{provider}: no API key configured")
    model = model or os.getenv(f"{'CLAUDE' if provider == 'claude' else provider.upper()}_MODEL") \
        or DEFAULT_MODELS[provider]
    return _instance(provider, model, api_key or None, max_tool_rounds)


def temperature_supported(provider, model):
    """Whether `model` accepts a temperature parameter (checked without creating a client)."""
    if provider == "claude":
        return not model.startswith(ClaudeLLM.NO_SAMPLING)
    if provider == "openai":
        return not model.startswith(OpenAILLM.REASONING)
    return True


def list_models(provider, api_key=None):
    """Models the key can use, from the vendor's API. Raises LLMUnavailable on auth/network errors."""
    try:
        return get_llm(provider, api_key=api_key).list_models()
    except LLMUnavailable:
        raise
    except Exception as e:  # noqa: BLE001 - surface any SDK error to the UI as "unavailable"
        raise LLMUnavailable(f"{provider}: could not list models ({type(e).__name__}: {e})") from e
