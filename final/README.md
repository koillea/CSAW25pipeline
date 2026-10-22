# CSAW 2025 Final — OpenTitan AES Trojan (scaffold)

**Target:** OpenTitan `aes` block. **Approach:** the autonomous
generate -> splice -> verify -> retry AI pipeline from the qualifiers
(see ../challenge_1), pointed at one OpenTitan block, with all AI
interactions logged to ai/.

Primary judging = creative + automated AI use + documentation. Our edge
is the pipeline itself: one command, deterministic splice into pristine
RTL, per-attempt JSONL logs in ai/.

Status: scaffold. Filled in during the in-container execution session:
- exact aes register map + DV entry point
- normal DV smoke test command (must still pass)
- exploit tb + trigger demonstration
- area/stealth delta (qualifier analog measured +0.29% area)

Layout: rtl/ (modified OpenTitan files only) | tb/ (exploit) | ai/ (logs)

## Verification status

**Level 1 - integration / elaboration (DONE).** The Trojan'd `rtl/aes_core.sv` was built
through OpenTitan's own fusesoc + Verilator flow:
`fusesoc --cores-root . run --target=lint --tool=verilator lowrisc:ip:aes`
(fusesoc 2.4.5, Verilator 5.053). It elaborates and lints cleanly inside the complete
`aes` block (masked datapath, TileLink-UL, EDN, 232 source files) with no Trojan-related
errors or warnings. Evidence: `ai/opentitan_verilator_lint.log`. Confirms the insertion is
valid SystemVerilog, correctly typed, and integrates into the real root-of-trust block.

**Level 2 - functional simulation (TODO).** Drive an encryption over TL-UL (with EDN
entropy + lifecycle tie-offs), send the magic plaintext, and show `data_out` returns the
key instead of the ciphertext. Requires a TL-UL/EDN testbench - the remaining step.
