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
