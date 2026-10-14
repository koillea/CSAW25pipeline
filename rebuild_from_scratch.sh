#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== Preflight ==="
missing=0
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker is not on PATH." >&2; missing=1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is not on PATH." >&2; missing=1; }
[[ -n "${GOOGLE_API_KEY:-}" ]] || { echo "ERROR: GOOGLE_API_KEY is not set in the environment." >&2; missing=1; }
(( missing == 0 )) || exit 1

echo "=== Clone challenge repositories ==="
if [[ ! -e CSAW26 ]]; then git clone https://github.com/koillea/CSAW26 CSAW26; else echo "CSAW26/ already exists; skipping clone"; fi
if [[ ! -e work/2025 ]]; then mkdir -p work; git clone https://github.com/JBlocklove/CSAW-AI-Hardware-Attack-Challenge-2025 work/2025; else echo "work/2025/ already exists; skipping clone"; fi

echo "=== Check Docker ==="
if ! docker info >/dev/null 2>&1; then echo "ERROR: Docker is not running. Start Docker, then rerun this script." >&2; exit 1; fi

echo "=== Build csaw2025 image ==="
if docker image inspect csaw2025 >/dev/null 2>&1; then echo "Docker image csaw2025 already exists; skipping build"; else docker build -t csaw2025 -f work/2025/docker/Dockerfile work/2025; fi

echo "=== Seed hard-tier pristine baseline ==="
git -C work/2025 checkout -- challenges/challenge_2/03_hard/rtl/wbuart.v
mkdir -p challenge_2/hard/clean_rtl
cp work/2025/challenges/challenge_2/03_hard/rtl/wbuart.v challenge_2/hard/clean_rtl/wbuart.v
rm -f challenge_2/hard/clean_area.txt

echo "=== Run challenge tiers ==="
TIERS=(easy medium hard)
echo "=== Final summary ==="
printf '%-8s | %-10s | %-13s | %-8s | %s\n' tier normal_ok trigger_fires area_ok overall
printf '%s\n' '---------|------------|---------------|----------|--------'
all_pass=1
for tier in "${TIERS[@]}"; do
  echo "--- ${tier} ---"
  log_path="challenge_2/${tier}/ai/agent_log.jsonl"
  (cd "challenge_2/${tier}" && python3 agent.py) || echo "WARNING: ${tier} agent failed; parsing its last verdict" >&2
  verdict_json='{"normal_ok":false,"trigger_fires":false,"area_ok":false}'
  if [[ -f "$log_path" ]]; then
    verdict_json="$(python3 -c 'import json,sys; lines=[x for x in open(sys.argv[1]) if x.strip()]; v=json.loads(lines[-1]).get("verdict",{}); print(json.dumps({"normal_ok":v.get("normal_ok",False),"trigger_fires":v.get("trigger_fires",False),"area_ok":v.get("area_ok",True)}))' "$log_path")" || true
  fi
  read -r normal trigger area < <(python3 -c 'import json,sys; v=json.loads(sys.argv[1]); print(str(bool(v.get("normal_ok"))).upper(),str(bool(v.get("trigger_fires"))).upper(),str(bool(v.get("area_ok"))).upper())' "$verdict_json")
  overall=FAIL
  if [[ "$normal" == TRUE && "$trigger" == TRUE && "$area" == TRUE ]]; then overall=PASS; else all_pass=0; fi
  printf '%-8s | %-10s | %-13s | %-8s | %s\n' "$tier" "$normal" "$trigger" "$area" "$overall"
done
(( all_pass )) && exit 0
exit 1
