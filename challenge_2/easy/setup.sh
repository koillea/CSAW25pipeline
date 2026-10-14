#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -e CSAW26 ]]; then
  git clone https://github.com/koillea/CSAW26 CSAW26
else
  echo "CSAW26/ already exists; skipping clone"
fi
if [[ ! -e work/2025 ]]; then
  mkdir -p work
  git clone https://github.com/JBlocklove/CSAW-AI-Hardware-Attack-Challenge-2025 work/2025
else
  echo "work/2025/ already exists; skipping clone"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is not installed. Install Docker Desktop and start it." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not running. Start Docker Desktop, then rerun setup.sh." >&2
  exit 1
fi
if docker image inspect csaw2025 >/dev/null 2>&1; then
  echo "Docker image csaw2025 already exists; skipping build"
else
  docker build -t csaw2025 -f work/2025/docker/Dockerfile work/2025
fi
echo "SUCCESS: CSAW26, challenge 2025, and Docker image csaw2025 are ready."
