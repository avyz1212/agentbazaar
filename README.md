# AgentBazaar

**A working prototype of an agent-to-agent service market with guardrails.**
Built for [NEAR HACKATHON](https://nearhackathon.com) — **Agent Economy** track.

A buyer agent with a NEAR budget posts jobs. Seller agents bid, negotiate a
price, deliver work, and get paid out of escrow **only after the buyer
verifies the delivery**. A human-set policy engine — per-payment cap, total
budget, seller allowlist — sits in front of every payment, and the demo shows
it blocking two bad payments on camera.

## The problem

Agents that can earn and spend are only useful if they can be trusted with
money while nobody is watching. "Give the agent a wallet" is the easy part;
the hard part is everything around it: Who may it pay? How much at once? What
happens if the delivery is junk? AgentBazaar prototypes the missing middle
layer — a market where agents hire each other, with escrow and spending
policy enforced before any money moves.

## Try it (do X — see Y)

Requires Python 3.10+. No dependencies, no API keys, nothing to install.

1. **Run the demo**

   ```sh
   python3 demo.py
   ```

   **See:** a live NEAR testnet snapshot read over public RPC (block height,
   block hash, gas price, and the live balance of the `testnet` account),
   then three jobs hired end-to-end — bids, a negotiated price below ask,
   escrow lock, delivery, verification, release — and two payments blocked
   by the policy engine. Ends with a summary: 3 jobs paid, 0.09 NEAR
   released, 2 payments blocked, buyer keeps 0.91 of its 1.0 NEAR budget.
   A full machine-readable record lands in `demo_output.json`.

2. **Run it with no network**

   ```sh
   python3 demo.py --offline
   ```

   **See:** the same run, with the chain data clearly labelled
   "OFFLINE fallback" everywhere it appears. The market, policy and escrow
   logic never pretend offline data is live.

3. **Run the tests**

   ```sh
   python3 -m unittest -v
   ```

   **See:** 17 tests covering the policy engine (cap, budget, allowlist),
   escrow accounting (lock/release/refund, double-settle rejected),
   bid choice and negotiation, service verifiability, plus a live testnet
   RPC smoke test that skips itself when offline.

## What the agents sell

| Service | Seller(s) | What is actually delivered |
| --- | --- | --- |
| `chain-data` | oracle-a, oracle-b | A **live** NEAR testnet snapshot fetched over public RPC at delivery time. The buyer verifies the block height is at least the height sampled when the job was posted. |
| `summarize` | scribe-a, scribe-b | A 3-sentence extractive digest of a memo plus a SHA-256 of the source. The buyer verifies by recomputing the hash. |
| `compliance` | screen-a | An independent risk verdict on a proposed payment, produced by a stricter policy than the buyer's own. In the demo it correctly returns `BLOCK` for a 0.5 NEAR payment to an unknown wallet. |

## What is live vs simulated — honestly

| Part | Status |
| --- | --- |
| NEAR testnet reads (`status`, `gas_price`, `view_account`) | **Live**, via public JSON-RPC (`near_rpc.py`). Read-only; no keys exist in this codebase. |
| Chain-data service deliverable | **Live data**, fetched fresh at delivery time. |
| Bidding, negotiation, verification, policy engine | **Real logic**, running locally in Python. |
| Escrow and balances | **Simulated** in-memory ledger (`ledger.py`). No real NEAR moves. Account names are testnet-style identifiers for the simulated agents. |
| Digest service | Real but local: a deterministic extractive summariser, not an LLM call, so the demo needs zero API keys. |

The production path swaps `ledger.py` for real testnet transfers and an
escrow contract, and gives the buyer a NEAR account whose spending is
constrained with **function-call access keys** (allowance + method
restrictions) — the on-chain counterpart of the policy engine prototyped
here. Cross-chain settlement for non-NEAR sellers is where **NEAR Intents**
would plug in. None of that is built yet; it is the roadmap, not the demo.

## How it works

```
demo.py     scenario + narration: jobs, guardrail checks, summary
market.py   Seller, bid selection (cheapest that clears a quality bar),
            one-round negotiation (buyer opens at 90% of ask)
policy.py   Policy.authorize(): allowlist -> per-payment cap -> total
            budget; every decision is logged, failures spend nothing
ledger.py   EscrowLedger: fund / lock / release / refund with a full
            history; double-settling an escrow is an error
services.py the three deliverables (live snapshot, digest, risk screen)
near_rpc.py read-only NEAR testnet JSON-RPC client with endpoint
            failover and retries; height/hash come from the small
            `status` response for reliability
```

Every payment follows the same path — **policy first, escrow second,
verification third, release last** — and the path is identical for the
payments that get blocked, which is the point.

## Why NEAR

- Agent accounts are first-class on NEAR: named accounts and sub-accounts
  map naturally to a market of identifiable agent sellers.
- Function-call access keys are the natural on-chain enforcement for the
  spending policy prototyped here (restricted methods + allowance).
- NEAR Intents are the settlement layer once sellers live on other chains:
  the buyer expresses the job, solvers compete to fill it — the same shape
  as this market's bidding.
- Public RPC is free and keyless, which is why the live parts of this demo
  work for anyone who clones the repo.

## Limitations

- Escrow is simulated; no real funds move and no contract is deployed.
- One negotiation round and fixed seller pricing strategies — a sketch of a
  market, not a market design.
- Quality scores are self-reported by sellers; reputation is future work.
- Amounts are floats rounded to 6 decimals for readability (a real
  implementation would use yoctoNEAR integers throughout, as `near_rpc.py`
  already does for account balances).

## Build notes

Written during the NEAR HACKATHON build window (Nov 2026), solo, in Python
(standard library only), specifically so that anyone — including the
screening judges — can run it with a single command and no setup.

## License

MIT — see `LICENSE`.
