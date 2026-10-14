"""Append-only JSONL audit logging for AI model interactions."""

import datetime
import json
import os


def log(attempt, prompt, output, verdict, provider=None, model=None):
    """Append one auditable model interaction to ``ai/agent_log.jsonl``."""
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "attempt": attempt,
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "generated_output": output,
        "verdict": verdict,
    }
    path = os.path.join("ai", "agent_log.jsonl")
    try:
        os.makedirs("ai", exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"WARN: log write failed: {exc}")
