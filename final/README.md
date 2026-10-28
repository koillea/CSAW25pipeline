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

## Verification status - UPDATE: Level 2 DONE

**Level 2 - functional simulation (DONE).** The Trojan is proven functionally in the full
OpenTitan `aes` block under Verilator (unmasked config: `SecMasking=0`,
`SecSkipPRNGReseeding=1`, `AESGCMEnable=0`). A TileLink-UL testbench (`tb/tb_aes_trojan.sv`,
using OpenTitan's own `tlul_adapter_host` as bus master) loads a known key, runs a normal
encryption, then sends the magic plaintext:

```
KEY       = 00112233 44556677 8899aabb ccddeeff
NORMAL CT = 257724bf 5f1b91d6 fec648da ec0415ba   (correct ciphertext, != key)
MAGIC OUT = 00112233 44556677 8899aabb ccddeeff   (== key -> LEAK)
RESULT: TROJAN_LEAK_CONFIRMED
RESULT: NORMAL_OK (trojan dormant on normal input)
```

Normal AES still encrypts correctly (Trojan dormant); the magic plaintext `A5A5..A5` makes
`DATA_OUT` return the loaded key. Evidence: `ai/opentitan_functional_sim.log`. Implementation
note: the Trojan taps `key_init_q` (the core's registered key) because OpenTitan's
`key_share` SW registers read back zero, so a naive `reg2hw` tap leaks nothing - found via
in-sim hierarchical probing.

Status: final challenge COMPLETE - design + Level-1 integration/lint + Level-2 functional
leak, all in OpenTitan's own fusesoc/Verilator toolchain.
