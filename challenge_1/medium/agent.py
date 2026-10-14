"""Self-testing CSAW challenge-1 AES easy-tier Trojan generation loop."""

import hashlib
import os
import pathlib
import shutil
import sys
import time

from generate import generate, is_success
from logger import log
from verifier import verify


PROVIDER = "google"
MAX_TRIES = 2
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
while not (PROJECT_ROOT / "work").is_dir():
    PARENT = PROJECT_ROOT.parent
    if PARENT == PROJECT_ROOT:
        raise RuntimeError("Could not find project root containing work/")
    PROJECT_ROOT = PARENT
RTL_DIR = PROJECT_ROOT / "work" / "2025" / "challenges" / "challenge_1" / "02_medium" / "rtl"
TOP_MODULE = "aes"
RTL_FILES = (
    "aes.v", "aes_core.v", "aes_key_mem.v", "aes_encipher_block.v",
    "aes_decipher_block.v", "aes_sbox.v", "aes_inv_sbox.v",
)
RTL_PATH = RTL_DIR / "aes.v"
FINAL_PATH = SCRIPT_DIR / "solution" / "aes_trojan.v"


def _fingerprint(candidate, result):
    data = candidate + "\0" + repr(result)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _clean_candidate(candidate):
    candidate = candidate.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        if candidate.rstrip().endswith("```"):
            candidate = candidate.rstrip()[:-3].rstrip()
    return candidate + "\n"


def main():
    clean_source = None
    previous_fingerprint = None
    last_result = None
    stage = "startup"

    try:
        with open(RTL_PATH, "r", encoding="utf-8") as handle:
            clean_source = handle.read()

        for attempt in range(MAX_TRIES):
            print(f"Attempt {attempt}")

            try:
                stage = "generation"
                with open(RTL_PATH, "r", encoding="utf-8") as handle:
                    source = handle.read()
                prompt, candidate = generate(PROVIDER, source, last_result)
                candidate = _clean_candidate(candidate)
                if not candidate.strip():
                    raise RuntimeError("model returned empty Verilog")

                stage = "candidate write"
                # The clean source remains in memory and is restored on abort.
                with open(RTL_PATH, "w", encoding="utf-8") as handle:
                    handle.write(candidate)

                stage = "verification"
                result = verify()
                log(attempt, prompt, candidate, result, provider=PROVIDER)
                print(f"Verdict on attempt {attempt}: {result}")

                fingerprint = _fingerprint(candidate, result)
                if fingerprint == previous_fingerprint:
                    print("NO-PROGRESS: identical candidate and verdict twice; stopping.")
                    break
                previous_fingerprint = fingerprint

                if is_success(result):
                    stage = "final save"
                    FINAL_PATH.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(RTL_PATH, FINAL_PATH)
                    print(f"SUCCESS on attempt {attempt}")
                    return 0

                last_result = result
                if attempt < MAX_TRIES - 1:
                    print("waiting 15s before next attempt...")
                    time.sleep(15)
            except Exception as exc:
                print(f"ERROR during {stage} on attempt {attempt}: {exc}", file=sys.stderr)
                raise

        with open(RTL_PATH, "w", encoding="utf-8") as handle:
            handle.write(clean_source)
        print(f"hit MAX_TRIES without success (maximum was {MAX_TRIES})")
        return 1
    except Exception:
        if clean_source is not None:
            try:
                with open(RTL_PATH, "w", encoding="utf-8") as handle:
                    handle.write(clean_source)
            except Exception as restore_error:
                print(f"ERROR restoring clean RTL: {restore_error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    print(f"PROJECT_ROOT={PROJECT_ROOT}")
    print(f"isdir(RTL_DIR)={RTL_DIR.is_dir()}")
    sys.exit(main())
