"""Small provider switchboard for Anthropic, OpenAI, and Google models."""

import importlib
import os
import re
import sys
import time


PROVIDERS = {
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "pip_package": "anthropic",
        "import_name": "anthropic",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "pip_package": "openai",
        "import_name": "openai",
    },
    "google": {
        "env_key": "GOOGLE_API_KEY",
        "pip_package": "google-genai",
        "import_name": "google.genai",
    },
}

def setup_model(provider):
    """Validate a provider's SDK and API key, returning the key."""
    info = PROVIDERS.get(provider)
    if info is None:
        sys.exit(
            f"Unknown model provider {provider!r}; choose one of: "
            f"{', '.join(PROVIDERS)}"
        )

    try:
        importlib.import_module(info["import_name"])
    except ImportError:
        sys.exit(
            f"SDK for provider {provider!r} is not installed. "
            f"Install it with: {sys.executable} -m pip install {info['pip_package']}"
        )

    key = os.environ.get(info["env_key"])
    if not key:
        sys.exit(
            f"Missing API key for provider {provider!r}: set the "
            f"{info['env_key']} environment variable."
        )
    return key


def call_model(provider, system, user, max_tokens=4000):
    """Call the selected provider and return its reply text."""
    key = setup_model(provider)

    if provider == "anthropic":
        ANTHROPIC_MODEL = "claude-opus-4-8"  # Editable Claude model name.
        ANTHROPIC_MAX_TOKENS = 16000  # Editable minimum output/thinking budget.
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        for retry in range(7):
            try:
                response = client.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=max(max_tokens, ANTHROPIC_MAX_TOKENS),
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                text_blocks = [
                    text for block in response.content
                    if (text := getattr(block, "text", None)) is not None
                ]
                text = "".join(text_blocks)
                if not text:
                    block_types = [getattr(block, "type", type(block).__name__)
                                   for block in response.content]
                    raise RuntimeError(
                        "Anthropic returned no text blocks: "
                        f"stop_reason={response.stop_reason!r}, "
                        f"content_blocks={len(response.content)} "
                        f"types={block_types!r}"
                    )
                return text
            except Exception as exc:
                message = str(exc)
                status = getattr(exc, "status_code", None)
                headers = getattr(exc, "response", None)
                headers = getattr(headers, "headers", {}) or {}
                rate_limited = (
                    status == 429
                    or "429" in message
                    or "rate limit" in message.lower()
                )
                server_error = status in (500, 503) or any(
                    code in message for code in ("500", "503")
                )
                if not rate_limited and not server_error:
                    raise
                if retry == 6:
                    raise RuntimeError(
                        "Anthropic transient error persisted after 6 retries"
                    ) from exc
                retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
                if retry_after is not None:
                    delay = float(retry_after)
                elif server_error:
                    delay = (3.0, 6.0, 10.0)[min(retry, 2)]
                else:
                    delay = 30.0
                if server_error and not rate_limited:
                    print(f"Server error, retrying in {delay:g}s...")
                else:
                    print(f"Rate limited, waiting {delay:g}s before retry...")
                time.sleep(delay)

    if provider == "openai":
        import openai

        client = openai.OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="<openai-model-id>",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content

    if provider == "google":
        GOOGLE_MODEL = "gemini-3.5-flash-lite"  # Editable Gemini model name.
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        for retry in range(7):
            try:
                response = client.models.generate_content(
                    model=GOOGLE_MODEL,
                    contents=f"{system}\n\n{user}",
                    config=types.GenerateContentConfig(max_output_tokens=65536),
                )
                return response.text
            except Exception as exc:
                message = str(exc)
                status = getattr(exc, "status_code", None)
                rate_limited = (
                    status == 429
                    or "429" in message
                    or "quota exceeded" in message.lower()
                    or "resourceexhausted" in message.lower()
                )
                server_error = status in (500, 503) or any(
                    code in message for code in ("500", "503")
                )
                if not rate_limited and not server_error:
                    raise
                if retry == 6:
                    raise RuntimeError(
                        "Gemini transient error persisted after 6 retries"
                    ) from exc

                delay = getattr(exc, "retry_delay", None)
                if delay is not None:
                    delay = getattr(delay, "seconds", delay)
                    delay = float(delay)
                else:
                    match = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", message, re.I)
                    if match:
                        delay = float(match.group(1))
                    elif server_error:
                        delay = (3.0, 6.0, 10.0)[min(retry, 2)]
                    else:
                        delay = 30.0
                delay = max(0.0, delay)
                if server_error and not rate_limited:
                    print(f"Server error, retrying in {delay:g}s...")
                else:
                    print(f"Rate limited, waiting {delay:g}s before retry...")
                time.sleep(delay)

    # setup_model() handles this case; retain a defensive error for future edits.
    sys.exit(f"Unsupported model provider {provider!r}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} PROVIDER")
    provider = sys.argv[1]
    setup_model(provider)
    print(f"Provider {provider!r} is configured and ready.")
