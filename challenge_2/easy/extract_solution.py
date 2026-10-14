import json
from pathlib import Path


def main():
    candidates = [Path("ai/agent_log.jsonl"), Path("easy/ai/agent_log.jsonl")]
    log_path = next((path for path in candidates if path.is_file()), None)
    if log_path is None:
        raise SystemExit("No agent_log.jsonl found in ./ai or ./easy/ai")

    passing = []
    with log_path.open(encoding="utf-8") as handle:
        for entry in handle:
            if not entry.strip():
                continue
            record = json.loads(entry)
            verdict = record.get("verdict", {})
            if verdict.get("normal_ok") is True and verdict.get("trigger_fires") is True:
                passing.append(record)
    if not passing:
        raise SystemExit("No passing attempt found in the log")

    output = passing[-1]["generated_output"]
    destination = Path("easy/solution/wbuart_trojan.v")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output, encoding="utf-8")

    lines = destination.read_text(encoding="utf-8").splitlines()
    print(f"Wrote {destination}")
    print("--- first 5 lines ---")
    print("\n".join(lines[:5]))
    print("--- last 5 lines ---")
    print("\n".join(lines[-5:]))


if __name__ == "__main__":
    main()
