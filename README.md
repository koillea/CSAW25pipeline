# CSAW 2025 AI Hardware Attack — Autonomous Trojan Pipeline

An autonomous **generate → insert → verify → retry** loop that uses a large language
model to design and insert hardware Trojans into a Wishbone-attached UART core
(`wbuart32`), verifying each candidate in simulation **and** gate-level synthesis
until it passes — with no human in the inner loop.

Built for the [CSAW 2025 AI Hardware Attack Challenge](https://github.com/JBlocklove/CSAW-AI-Hardware-Attack-Challenge-2025)
(challenge_2), as practice for the 2026 qualifier.

## Results — challenge_2 (all tiers passing, free model)

| Tier   | Trigger                                              | Payload                                                      | Verify                        | Status |
|--------|------------------------------------------------------|-------------------------------------------------------------|-------------------------------|--------|
| easy   | UART knock `10 a4 98 bd`                              | Stop acking the Wishbone bus; resume after `0xfe` ×4         | sim                           | PASS   |
| medium | UART `0x1e`, then 2× Setup reads, then 2× FIFO reads  | Next Setup read returns `0xdeadbeef`, then reverts (one-shot) | sim                           | PASS   |
| hard   | UART knock `AC E1`                                   | Leak the RX-FIFO head byte via Wishbone ACK-timing modulation | sim + synthesis (3.07% area)  | PASS   |

Model: **`gemini-3.5-flash-lite`** (free tier). Each tier converged within the retry budget.

## How it works

The loop (`challenge_2/<tier>/agent.py`) runs until a candidate passes or `MAX_TRIES` is hit:

1. **generate** (`generate.py`) — the LLM is given the clean `wbuart.v` plus a
   challenge-specific prompt (trigger/payload spec + the real signal names) and
   returns the entire Trojan'd module.
2. **insert** — the candidate is written into the challenge's `rtl/wbuart.v`.
3. **verify** (`verifier.py`) — inside the `csaw2025` Docker image:
   - **normal**: the challenge's own `linetest` must still pass (Trojan dormant);
   - **trigger**: a custom Verilator exploit testbench drives the trigger and
     confirms the payload (ack suppression / spoofed read / decoded leaked byte);
   - **area** (hard): `yosys` + SkyWater 130nm synthesis; overhead vs. a pristine
     baseline must be ≤5%.
4. **feedback** (`logger.py`) — every attempt's verdict (and the generated RTL) is
   appended to `ai/agent_log.jsonl`; failures are fed back into the next prompt.

The provider is config-driven (`models.py`), so the model can be swapped without
touching the loop.

## Running it

**One command, from a clean checkout:**

```bash
export GOOGLE_API_KEY=...        # free Gemini key
./rebuild_from_scratch.sh        # clone challenge, build image, seed baseline, run all 3 tiers, print summary
```

Prereqs: Docker (running), Python 3, a `GOOGLE_API_KEY`.

**A single tier:**

```bash
python3 challenge_2/easy/agent.py
```

## The verifier is load-bearing

The central lesson of this project: **an autonomous attack pipeline only converges
as well as its test can observe.** The model was rarely the bottleneck — the
verifier was. Examples that cost real debugging time, all on the test side:

- The full `rxuart` receiver refuses to decode until the RX line idles high for
  `clocks_per_baud × 16` (400) cycles. Until the exploit testbench added that
  warm-up, *no* knock was ever delivered and every correct Trojan "failed."
- Synthesis globs all `rtl/*.v`; a stray duplicate `wbuart` module silently broke
  it while simulation (explicit file list) passed.
- A naive clean-area baseline accidentally synthesized the Trojan against itself
  (0.00% overhead — a false pass) until pinned to a pristine core.

## Honest notes / limitations

- The **exploit testbenches are self-authored**, not the official competition
  grader. "Pass" means pass *our* verifier (which for medium also checks
  no-false-trigger and one-shot revert, and for hard checks synthesis area).
- The **target signal names were provided in the prompts** (human recon of the
  clean RTL), so the agent automates generation and verification, not design
  discovery. Making the agent find its own targets is future work.
- **Hard's timing is functional but not stealthy** — it uses a large, obvious
  ACK delay. The free model could not reliably write the subtle ±N-cycle version
  (it kept mis-implementing the per-transaction delay counter), so the working,
  area-passing version was kept and the stealth tradeoff is documented here.

## Repo layout

```
.
├── rebuild_from_scratch.sh        # one-command end-to-end reproduction
├── ai/agent_log.jsonl             # full generate→verify history (failures + successes)
├── challenge_2/
│   ├── easy|medium|hard/
│   │   ├── agent.py  generate.py  verifier.py  logger.py  models.py  setup.sh
│   │   └── solution/wbuart_trojan.v     # the converged Trojan
│   └── hard/clean_rtl/wbuart.v          # pristine baseline for synthesis area
├── challenge_1/                   # planned
└── final/                         # planned — 2026 qualifier
```

## Toward 2026

The real qualifier removes the scaffolding that made this work: no clean RTL is
provided — teams reverse-engineer an iCE40 bitstream crypto accelerator *first*,
then insert the Trojan. This pipeline is the generate/verify/retry foundation;
the new frontier is recovering a design before the loop can run.

## Credits

Challenge and `wbuart32` core by Jason Blocklove / Dan Gisselquist (GPLv3).
