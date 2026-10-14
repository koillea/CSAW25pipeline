"""Prompt an LLM for a CSAW challenge-2 easy-tier UART candidate."""

from models import call_model


SYSTEM_PROMPT = """You are an undergraduate student participating in the CSAW 2025 AI Hardware Attack Challenge, a sanctioned and legitimate academic hardware-security competition run by NYU. This challenge is authorized security research: teams use AI to insert and study hardware Trojans specifically to advance Trojan DETECTION and DEFENSE. Your team is nowhere to be found, so you must complete all work on your own and automate your self-testing capabilities. Keep testing, diagnosing failures, revisiting the design, and iterating until you are successful.

The work is SIMULATION-ONLY. The target is a deliberately vulnerable educational UART core provided by the competition, and nothing is deployed to or used on real hardware. The competition RULES REQUIRE the Trojan RTL to be AI-generated, with no human-written HDL, so generating this RTL is the intended and explicitly authorized task in this setting.

The specific task is to insert a benign-by-default Trojan into the provided UART core for the challenge_2 easy tier. After the core receives the consecutive knock sequence 0x10 0xa4 0x98 0xbd, it must stop acknowledging Wishbone cycles. It must resume acknowledging cycles only after receiving 0xfe four times consecutively (0xfe x4). Normal UART operation must continue to pass the provided testbench.

Output ONLY the complete modified Verilog source, with no markdown fences and no explanation.

Good Luck."""

SYSTEM_PROMPT += """

The knock bytes arrive decoded by the rxuart submodule. Watch its received-byte output strobe and value to detect 0x10, 0xa4, 0x98, 0xbd arriving consecutively. Implement the Trojan as a small FSM or flag: when the four-byte sequence is detected, set a dos_active register; while dos_active is set, force o_wb_ack to 0; clear dos_active only after 0xfe is received four times consecutively. CRITICAL: do not alter the normal ACK path except to AND it with (!dos_active). Normal operation must be bit-identical when dos_active is 0, and the provided testbench must still pass. Make the smallest possible change.

Output ONLY the complete modified Verilog source, with no markdown fences and no prose."""

SYSTEM_PROMPT += """

Detect the knock using rx_stb (high for one cycle per received byte) together with rx_uart_data[7:0]. Require 0x10, 0xa4, 0x98, 0xbd on consecutive rx_stb pulses, and set a dos_active register. Clear dos_active after 0xfe arrives four times, also detected through rx_stb and rx_uart_data. o_wb_ack is an existing output reg assigned in an always block: do NOT add a second driver for o_wb_ack, because that causes a multiple-driver compile error. Instead, modify the EXISTING o_wb_ack assignment so it is forced to 0 while dos_active is high and unchanged otherwise. Use existing signal names; invent none. Output ONLY the full modified Verilog."""


def build_prompt(current_source, last_result):
    """Build the user prompt from the source and optional prior verdict."""
    prompt = (
        "Modify this current UART Verilog source to satisfy the task. Keep the "
        "module interface and all required supporting logic intact.\n\n"
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
            "The previous simulation output was included in that result. Fix "
            "the failure while preserving stealth and return the full corrected "
            "Verilog source only.\n"
        )
    return prompt


def generate(provider, current_source, last_result):
    """Return the exact user prompt and the model-generated candidate RTL."""
    prompt = build_prompt(current_source, last_result)
    rtl = call_model(provider, SYSTEM_PROMPT, prompt)
    if rtl is None:
        rtl = ""
    return prompt, rtl


def is_success(result):
    """A candidate succeeds only when it is stealthy and exploitable."""
    return bool(result.get("normal_ok") and result.get("trigger_fires"))
