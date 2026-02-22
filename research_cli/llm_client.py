"""
llm_client.py — Multi-provider LLM client for research-cli v2.

Supports: Gemini, Groq, DeepSeek, OpenAI (all via OpenAI-compatible SDK)
           and Anthropic (via native SDK).

Set LLM_PROVIDER in .env to switch providers.

Note: Gemini 2.5 Flash uses "thinking" tokens that consume the max_tokens
budget, so callers should use generous max_tokens values (2048+) even for
short expected outputs.
"""

import json
import re
import time
from typing import Callable, Optional

from research_cli.config import (
    LLM_PROVIDER,
    LLM_API_KEY,
    LLM_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    SYSTEM_PROMPT,
)

# ---------------------------------------------------------------------------
# Client setup (lazy singleton)
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    """Lazy-initialise the LLM client based on provider."""
    global _client
    if _client is not None:
        return _client

    if not LLM_API_KEY:
        raise EnvironmentError(
            f"No API key found for provider '{LLM_PROVIDER}'. "
            f"Set the appropriate key in your .env file."
        )

    if LLM_PROVIDER == "anthropic":
        import anthropic
        _client = anthropic.Anthropic(api_key=LLM_API_KEY)
    else:
        # All other providers use the OpenAI-compatible SDK
        from openai import OpenAI
        _client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    return _client


def _retry_on_rate_limit(func, max_retries=3):
    """Retry a function on 429 rate-limit errors with exponential backoff."""
    import sys
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error_str = str(e)
            is_rate_limit = (
                "429" in error_str
                or "rate" in error_str.lower()
                or "quota" in error_str.lower()
                or "RESOURCE_EXHAUSTED" in error_str
            )
            if is_rate_limit and attempt < max_retries - 1:
                wait = (attempt + 1) * 20
                print(f"  [Rate limited, waiting {wait}s...]", file=sys.stderr)
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Core call: text response
# ---------------------------------------------------------------------------

def call_claude(
    prompt: str,
    system: str = SYSTEM_PROMPT,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """Send a prompt and return the text response. Works with any provider."""
    client = _get_client()

    # Gemini 2.5 Flash uses "thinking" tokens that consume max_tokens budget.
    # Enforce minimum of 2048 so short outputs don't get truncated.
    if LLM_PROVIDER == "gemini" and max_tokens < 2048:
        max_tokens = 2048

    def _call():
        if LLM_PROVIDER == "anthropic":
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        else:
            # OpenAI-compatible providers (Gemini, Groq, DeepSeek, OpenAI)
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content

    return _retry_on_rate_limit(_call)


# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------

def _clean_json_response(raw: str) -> str:
    """Strip markdown fences and extract JSON from a response."""
    cleaned = raw.strip()

    # Remove ```json ... ``` or ``` ... ```
    if cleaned.startswith("```"):
        # Find closing fence
        match = re.search(r"```\w*\n(.*?)```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        else:
            # No closing fence — strip opening line
            lines = cleaned.split("\n", 1)
            cleaned = lines[1].strip() if len(lines) > 1 else cleaned

    return cleaned


def call_claude_json(
    prompt: str,
    system: str = SYSTEM_PROMPT,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> dict | list:
    """Send a prompt and parse the response as JSON."""
    json_system = system + (
        "\n\nYou MUST respond with valid JSON only. "
        "No markdown code fences, no explanation, just the JSON."
    )

    client = _get_client()

    if LLM_PROVIDER in ("anthropic", "gemini"):
        # Anthropic: use prompt engineering
        # Gemini: json_object response_format causes truncated output;
        #         rely on prompt engineering + code-fence stripping instead
        raw = call_claude(prompt, system=json_system, model=model,
                          max_tokens=max_tokens, temperature=temperature)
    else:
        # Use JSON mode where supported (Groq, DeepSeek, OpenAI)
        try:
            def _call():
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": json_system},
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content

            raw = _retry_on_rate_limit(_call)
        except Exception:
            # Fallback: some providers/models don't support response_format
            raw = call_claude(prompt, system=json_system, model=model,
                              max_tokens=max_tokens, temperature=temperature)

    cleaned = _clean_json_response(raw)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Retry once with a clearer prompt
        retry_prompt = (
            f"Your previous response was not valid JSON. "
            f"Respond with ONLY valid JSON, no other text.\n\n"
            f"Original request:\n{prompt}"
        )
        raw2 = call_claude(retry_prompt, system=json_system, model=model,
                           max_tokens=max_tokens, temperature=temperature)
        cleaned2 = _clean_json_response(raw2)
        return json.loads(cleaned2)


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------

def call_claude_streaming(
    prompt: str,
    system: str = SYSTEM_PROMPT,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> str:
    """Stream a response, calling on_chunk for each text delta."""
    client = _get_client()
    full_text = []

    if LLM_PROVIDER == "anthropic":
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                full_text.append(text)
                if on_chunk:
                    on_chunk(text)
    else:
        stream = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
            if delta:
                full_text.append(delta)
                if on_chunk:
                    on_chunk(delta)

    return "".join(full_text)


# ---------------------------------------------------------------------------
# Token counting (estimation)
# ---------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    """Estimate token count (~3 chars per token, conservative)."""
    return len(text) // 3
