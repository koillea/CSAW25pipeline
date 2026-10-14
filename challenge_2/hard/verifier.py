#!/usr/bin/env python3
"""Verify challenge-2 easy UART behavior using the pinned Docker image."""

import pathlib
import subprocess
import sys
import tempfile
import re
import shutil

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
while not (PROJECT_ROOT / "work").is_dir():
    if PROJECT_ROOT.parent == PROJECT_ROOT:
        raise RuntimeError("Could not find project root containing work/")
    PROJECT_ROOT = PROJECT_ROOT.parent
CHALLENGE = PROJECT_ROOT / "work" / "2025"
EASY = CHALLENGE / "challenges" / "challenge_2" / "03_hard"
RTL_DIR = EASY / "rtl"

# Container paths: adjust these together if the image layout changes.
CONTAINER_EASY = "/home/devuser/challenges/challenge_2/03_hard"
CONTAINER_RTL = f"{CONTAINER_EASY}/rtl"
IMAGE = "csaw2025"

HARNESS = r'''#include "Vwbuart.h"
#include "verilated.h"
#include "verilated_vpi.h"
#include "verilated_vcd_c.h"
#include <cstdio>
#include <cstdint>
vluint64_t main_time = 0; VerilatedVcdC* g_tfp = nullptr;
#define SECRET 0x5a
static void tick(Vwbuart *d, int rx) { d->i_clk=0; d->i_uart_rx=rx; d->eval(); if(g_tfp) g_tfp->dump(main_time++); d->i_clk=1; d->eval(); if(g_tfp) g_tfp->dump(main_time++); }
static void send_byte(Vwbuart *d, unsigned char b) {
 int x[10]={0,int(b&1),int((b>>1)&1),int((b>>2)&1),int((b>>3)&1),int((b>>4)&1),int((b>>5)&1),int((b>>6)&1),int((b>>7)&1),1};
 for (int bit:x) for (int n=0;n<25;++n) tick(d,bit);
}
static int wb_read_latency(Vwbuart *d, unsigned addr) {
 d->i_wb_cyc=1; d->i_wb_we=0; d->i_wb_addr=addr; d->i_wb_stb=1; tick(d,1); d->i_wb_stb=0;
 int latency=99; for(int n=1;n<=12;++n){ tick(d,1); if(d->o_wb_ack){ latency=n; break; } }
 d->i_wb_cyc=0; tick(d,1); tick(d,1); return latency;
}
int main(int argc,char **argv) { Verilated::commandArgs(argc,argv); Vwbuart d; Verilated::traceEverOn(true); g_tfp = new VerilatedVcdC; d.trace(g_tfp,99); g_tfp->open("<CONTAINER_RTL>/exploit.vcd");
 d.i_wb_cyc=0;d.i_wb_stb=0;d.i_wb_we=0;d.i_wb_addr=0;d.i_wb_data=0;d.i_wb_sel=0xf;d.i_uart_rx=1;d.i_cts_n=0;d.i_reset=1;
 for(int n=0;n<8;++n)tick(&d,1); d.i_reset=0; for(int n=0;n<512;++n)tick(&d,1);
 send_byte(&d,SECRET); send_byte(&d,0xAC); send_byte(&d,0xE1); for(int n=0;n<64;++n)tick(&d,1);
 int lat[8]; for(int i=0;i<8;++i)lat[i]=wb_read_latency(&d,1);
 int lat_min=lat[0]; for(int i=1;i<8;++i)if(lat[i]<lat_min)lat_min=lat[i]; unsigned decoded=0; for(int i=0;i<8;++i)if(lat[i]>=lat_min+2)decoded|=(1u<<i);
 std::printf("HARD secret=0x%02x decoded=0x%02x lat=[%d %d %d %d %d %d %d %d]\n",SECRET,decoded,lat[0],lat[1],lat[2],lat[3],lat[4],lat[5],lat[6],lat[7]); if(g_tfp) g_tfp->close(); return(decoded==SECRET)?0:1; }
'''


def docker_run(command, mounts=()):
    cmd = ["docker", "run", "--rm"]
    for host, container in mounts:
        cmd += ["-v", f"{host}:{container}"]
    cmd += [IMAGE, "-lc", " ".join(command)]
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, check=False)
        return p.returncode == 0, f"$ {' '.join(cmd)}\n{p.stdout}"
    except OSError as exc:
        return False, f"$ {' '.join(cmd)}\nDocker unavailable: {exc}\n"


def synth_area(rtl_host_dir):
    command = [
        "/home/devuser/challenges/challenge_2/scripts/run-synthesis.sh",
        "-p", CONTAINER_EASY, "-i", "wbuart,rxuart,txuart,ufifo,skidbuffer", "&&", "cat",
        f"{CONTAINER_EASY}/synth-logs/wbuart_synth.log",
    ]
    ok, raw = docker_run(command, ((pathlib.Path(rtl_host_dir), CONTAINER_RTL),))
    if not ok:
        return None
    matches = re.findall(r"Chip area for module.*?:\s*([0-9.]+)", raw)
    return float(matches[-1]) if matches else None


def clean_wbuart_source():
    pristine = SCRIPT_DIR / "clean_rtl" / "wbuart.v"
    if not pristine.is_file():
        return None
    return pristine.read_text(encoding="utf-8")


def baseline_area():
    cache = SCRIPT_DIR / "clean_area.txt"
    try:
        return float(cache.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pass
    clean_source = clean_wbuart_source()
    if clean_source is None:
        return None
    with tempfile.TemporaryDirectory(prefix="clean-rtl-") as td:
        temp_rtl = pathlib.Path(td)
        for name in ("rxuart.v", "txuart.v", "ufifo.v", "skidbuffer.v"):
            shutil.copyfile(RTL_DIR / name, temp_rtl / name)
        (temp_rtl / "wbuart.v").write_text(clean_source, encoding="utf-8")
        area = synth_area(temp_rtl)
    if area is not None:
        cache.write_text(f"{area}\n", encoding="utf-8")
    return area


def exploit_check():
    with tempfile.TemporaryDirectory(prefix="uart-verifier-") as td:
        temp = pathlib.Path(td)
        (temp / "probe.cpp").write_text(HARNESS.replace("<CONTAINER_RTL>", CONTAINER_RTL), encoding="utf-8")
        files = " ".join(f"{CONTAINER_RTL}/{n}" for n in
                          ("wbuart.v", "rxuart.v", "txuart.v", "ufifo.v", "skidbuffer.v"))
        command = ["verilator", "--cc", "--exe", "--vpi", "--trace", "--build", "--top-module", "wbuart",
                   "-Mdir", "/tmp/verifier/obj", "-CFLAGS", "-std=c++14",
                   "/tmp/verifier/probe.cpp", files, "&&", "/tmp/verifier/obj/Vwbuart"]
        ok, raw = docker_run(command, ((RTL_DIR, CONTAINER_RTL), (temp, "/tmp/verifier")))
        try:
            raw += parse_exploit_vcd(RTL_DIR / "exploit.vcd")
        finally:
            (RTL_DIR / "exploit.vcd").unlink(missing_ok=True)
        return ok, raw


def parse_exploit_vcd(path):
    if not path.exists():
        return "VCD: exploit.vcd was not produced.\n"
    ids = {}
    values = {}
    rx_ids = set()
    data_ids = set()
    dos_ids = set()
    leak_active_ids = set()
    leak_byte_ids = set()
    found = []
    rx_values = []
    rising = 0
    rx_previous = {}
    rx_data = {}
    dos_first = None
    leak_active_first = None
    leak_byte_value = None
    time_value = 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("$var "):
                fields = line.split()
                if len(fields) >= 5:
                    ident, name = fields[3], fields[4]
                    ids[ident] = name
                    lower = name.lower()
                    if any(signal in lower for signal in ("rx_stb", "rx_uart_data", "dos_active", "i_uart_rx", "leak_active", "leak_byte")):
                        found.append(name)
                    if "rx_stb" in lower: rx_ids.add(ident)
                    if "rx_uart_data" in lower: data_ids.add(ident)
                    if "dos_active" in lower: dos_ids.add(ident)
                    if "leak_active" in lower: leak_active_ids.add(ident)
                    if "leak_byte" in lower: leak_byte_ids.add(ident)
            elif line.startswith("#"):
                time_value = int(line[1:] or 0)
            elif line.startswith("b"):
                bits, ident = line[1:].split()[:2]
                values[ident] = int(bits.replace("x", "0").replace("z", "0"), 2)
                if ident in data_ids: rx_data[ident] = values[ident]
                if ident in leak_byte_ids: leak_byte_value = values[ident]
            elif line and line[0] in "01xzXZ":
                value, ident = line[0].lower(), line[1:]
                values[ident] = value
                if ident in rx_ids:
                    old = rx_previous.get(ident, "0")
                    if old == "0" and value == "1":
                        rising += 1
                        data = next((rx_data[i] for i in data_ids if i in rx_data), None)
                        rx_values.append((time_value, data))
                    rx_previous[ident] = value
                if ident in dos_ids and value == "1" and dos_first is None:
                    dos_first = time_value
                if ident in leak_active_ids and value == "1" and leak_active_first is None:
                    leak_active_first = time_value
    lines = [f"VCD signals: {sorted(set(found))}", f"VCD rx_stb rising edges: {rising}"]
    lines.append("VCD rx_uart_data at rx_stb: " + ", ".join(
        f"0x{value:x}" if value is not None else "unknown" for _, value in rx_values))
    lines.append(f"VCD first dos_active=1: {dos_first if dos_first is not None else 'never'}")
    lines.append(f"VCD first leak_active=1: {leak_active_first if leak_active_first is not None else 'never'}")
    lines.append(f"VCD leak_byte: {f'0x{leak_byte_value:02x}' if leak_byte_value is not None else 'not found'}")
    return "\n".join(lines) + "\n"


def exploit_feedback(raw):
    match = re.search(r"before=(\d+) after=(\d+)", raw)
    if not match:
        return raw
    before, after = map(int, match.groups())
    if after >= max(0, before - 1):
        meaning = (
            "The bus kept acknowledging after the knock — your Trojan did NOT "
            "detect the sequence or did not gate o_wb_ack. The knock arrives as "
            "bytes received over the UART RX line (decoded by the rxuart "
            "submodule); watch the received-byte strobe/value and halt o_wb_ack "
            "until 0xfe is received 4 times."
        )
    elif after > 0:
        meaning = (
            f"Partial halt — the bus still acked {after} times after the knock; "
            "the DoS must stop ALL acks (after must reach 0)."
        )
    else:
        meaning = "The bus stopped acknowledging after the knock (trigger fired)."
    return raw.rstrip("\n") + "\n" + meaning + "\n"


def clean_stale_artifacts():
    """Remove only generated build artifacts within this challenge tree."""
    for path in CHALLENGE.rglob("obj_dir"):
        if path.is_dir():
            shutil.rmtree(path)
    for path in CHALLENGE.rglob("*.d"):
        if path.is_file():
            path.unlink()
    for path in CHALLENGE.rglob("sim-logs"):
        if path.is_dir():
            shutil.rmtree(path)


def verify():
    if not CHALLENGE.is_dir() or not RTL_DIR.is_dir():
        return {"normal_ok": False, "trigger_fires": False,
                "trojan_area": None, "clean_area": None,
                "overhead_pct": None, "area_ok": False,
                "raw": f"Challenge RTL not found: {RTL_DIR}\n"}
    try:
        clean_stale_artifacts()
    except OSError as exc:
        return {"normal_ok": False, "trigger_fires": False,
                "trojan_area": None, "clean_area": None,
                "overhead_pct": None, "area_ok": False,
                "raw": f"Failed to remove stale challenge build artifacts: {exc}\n"}
    ok, raw = docker_run(
        ["/home/devuser/challenges/challenge_2/scripts/run-simulation.sh",
         "--clean", "-p", CONTAINER_EASY, "-t", "linetest", "&&",
         "/home/devuser/challenges/challenge_2/scripts/run-simulation.sh",
         "-p", CONTAINER_EASY, "-t", "linetest"],
        ((RTL_DIR, CONTAINER_RTL),))
    if not ok:
        lowered = raw.lower()
        if any(token in lowered for token in
               ("error:", "undefined", "no rule to make", "compile", "build failed")):
            raw += "Normal testbench failure classification: compile/build error.\n"
        else:
            raw += "Normal testbench failure classification: functional mismatch.\n"
        return {"normal_ok": False, "trigger_fires": False,
                "trojan_area": None, "clean_area": None,
                "overhead_pct": None, "area_ok": False, "raw": raw}
    exploit_ok, exploit_raw = exploit_check()
    clean_area = baseline_area()
    trojan_area = synth_area(RTL_DIR)
    overhead_pct = ((trojan_area - clean_area) / clean_area * 100
                    if trojan_area is not None and clean_area not in (None, 0)
                    else None)
    area_ok = trojan_area is not None and overhead_pct is not None and overhead_pct <= 5.0
    clean_display = clean_area if clean_area is not None else float("nan")
    trojan_display = trojan_area if trojan_area is not None else float("nan")
    overhead_display = overhead_pct if overhead_pct is not None else float("nan")
    synth_line = (f"SYNTH clean={clean_display:.1f} trojan={trojan_display:.1f} "
                  f"overhead={overhead_display:.2f}% area_ok={area_ok}\n")
    print(synth_line, end="")
    return {"normal_ok": True, "trigger_fires": exploit_ok,
            "trojan_area": trojan_area, "clean_area": clean_area,
            "overhead_pct": overhead_pct, "area_ok": area_ok,
            "raw": raw + exploit_feedback(exploit_raw) + synth_line}


def main():
    print(verify())
    return 0


if __name__ == "__main__":
    sys.exit(main())
