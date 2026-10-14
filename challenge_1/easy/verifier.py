#!/usr/bin/env python3
"""Verify the AES easy-tier candidate inside the pinned Docker image."""

import pathlib
import shutil
import subprocess


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
while not (PROJECT_ROOT / "work").is_dir():
    if PROJECT_ROOT.parent == PROJECT_ROOT:
        raise RuntimeError("Could not find project root containing work/")
    PROJECT_ROOT = PROJECT_ROOT.parent

CHALLENGE = PROJECT_ROOT / "work" / "2025" / "challenges" / "challenge_1" / "01_easy"
RTL_DIR = CHALLENGE / "rtl"
TB_DIR = CHALLENGE / "tb"
CONTAINER_CHALLENGE = "/home/devuser/challenges/challenge_1/01_easy"
CONTAINER_RTL = f"{CONTAINER_CHALLENGE}/rtl"
CONTAINER_TB = f"{CONTAINER_CHALLENGE}/tb"
IMAGE = "csaw2025"
RTL_LIST = "aes,aes_core,aes_key_mem,aes_encipher_block,aes_decipher_block,aes_sbox,aes_inv_sbox"


def docker_run(command, mounts=()):
    cmd = ["docker", "run", "--rm"]
    for host, container in mounts:
        cmd += ["-v", f"{host}:{container}"]
    cmd += [IMAGE, "-lc", " ".join(command)]
    try:
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, check=False)
        return result.returncode == 0, f"$ {' '.join(cmd)}\n{result.stdout}"
    except OSError as exc:
        return False, f"$ {' '.join(cmd)}\nDocker unavailable: {exc}\n"


def _run_simulation():
    command = [
        "cd", CONTAINER_CHALLENGE, "&&",
        "/home/devuser/challenges/challenge_1/scripts/run-simulation.sh",
        "-t", "tb_aes,tb_trojan", "-r", RTL_LIST, ";",
        "echo", "'==TBAES=='", ";", "cat", "sim-logs/tb_aes.log", ";",
        "echo", "'==TROJAN=='", ";", "cat", "sim-logs/tb_trojan.log",
    ]
    return docker_run(command, ((RTL_DIR, CONTAINER_RTL), (TB_DIR, CONTAINER_TB)))


def _run_synthesis():
    script = "/home/devuser/challenges/challenge_1/scripts/run-synthesis.sh"
    command = [script, "-p", CONTAINER_CHALLENGE, "-i", RTL_LIST,
               "&&", "cat", f"{CONTAINER_CHALLENGE}/synth-logs/aes_synth.log"]
    return docker_run(command, ((RTL_DIR, CONTAINER_RTL),))


def verify():
    raw = ""
    source_tb = SCRIPT_DIR / "tb" / "tb_trojan.v"
    staged_tb = TB_DIR / "tb_trojan.v"
    try:
        if not source_tb.is_file():
            return {"normal_ok": False, "trigger_fires": False, "area_ok": False,
                    "raw": f"Missing Trojan testbench: {source_tb}\n"}
        if not RTL_DIR.is_dir() or not TB_DIR.is_dir():
            return {"normal_ok": False, "trigger_fires": False, "area_ok": False,
                    "raw": f"Missing AES RTL or testbench directory: {CHALLENGE}\n"}
        shutil.copyfile(source_tb, staged_tb)

        sim_ok, sim_raw = _run_simulation()
        raw += sim_raw
        tb_aes = sim_raw.split("==TBAES==")[-1].split("==TROJAN==")[0]
        tb_trojan = sim_raw.split("==TROJAN==")[-1]
        normal_ok = ("completed successfully" in tb_aes) and ("NOT successful" not in tb_aes)
        trigger_fires = "LEAK_PASS" in tb_trojan

        synth_ok, synth_raw = _run_synthesis()
        raw += synth_raw
        area_ok = synth_ok and "Chip area for module" in synth_raw
        return {"normal_ok": normal_ok, "trigger_fires": trigger_fires,
                "area_ok": area_ok, "raw": raw}
    except Exception as exc:
        raw += f"Verifier error: {exc}\n"
        return {"normal_ok": False, "trigger_fires": False, "area_ok": False, "raw": raw}


if __name__ == "__main__":
    print(verify())
