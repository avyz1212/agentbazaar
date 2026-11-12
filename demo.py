"""AgentBazaar demo: one buyer agent hires other agents, under guardrails.

Run:  python3 demo.py            (live NEAR testnet reads)
      python3 demo.py --offline  (force the labelled offline fallback)

The buyer agent ("treasury.agent.testnet") has a 1.0 NEAR budget and a
human-set spending policy. It posts jobs, takes bids, negotiates, locks
payment in escrow, verifies each delivery, and only then releases payment.
Two payment attempts are deliberately blocked by the policy on camera.
"""

import json
import sys

from ledger import EscrowLedger
from market import Seller, choose_bid, negotiate
from near_rpc import NearTestnet
from policy import Policy
from services import chain_snapshot_service, memo_digest_service, risk_screen_service

BUYER = "treasury.agent.testnet"
BUDGET = 1.0
PER_PAYMENT_CAP = 0.20

MEMO = (
    "NEAR Intents let an agent express what it wants instead of how to route it. "
    "Solvers compete to fill the intent across chains, so settlement becomes a market. "
    "Chain Signatures let one NEAR account control accounts on other chains. "
    "Together they give an agent a wallet, a way to pay strangers, and a way to earn. "
    "The missing piece is guardrails: budgets, allowlists and escrow that a human sets once."
)


def build_sellers(near):
    return [
        Seller("oracle-a.agent.testnet", "chain-data", 0.060, 0.85, 0.90,
               lambda job: chain_snapshot_service(near)),
        Seller("oracle-b.agent.testnet", "chain-data", 0.045, 0.90, 0.80,
               lambda job: chain_snapshot_service(near)),
        Seller("scribe-a.agent.testnet", "summarize", 0.040, 0.85, 0.95,
               lambda job: memo_digest_service(job["memo"])),
        Seller("scribe-b.agent.testnet", "summarize", 0.030, 0.90, 0.70,
               lambda job: memo_digest_service(job["memo"])),
        Seller("screen-a.agent.testnet", "compliance", 0.025, 0.90, 0.90,
               lambda job: risk_screen_service(
                   job["payee"], job["amount"], job["allowlist"])),
        Seller("sage.agent.testnet", "research", 0.350, 0.90, 0.99,
               lambda job: {"report": "Deep research report (never delivered)"}),
    ]


def log(step, msg):
    print(f"  [{step:<10}] {msg}")


def hire(job, bids, buyer_max, policy, ledger, verify, record):
    """Full hire flow for one job. Returns True if paid, False if blocked."""
    print(f"\nJOB: {job['title']}")
    for b in bids:
        log("bid", f"{b.name} asks {b.ask} NEAR (quality {b.quality})")
    seller = choose_bid(bids)
    if seller is None:
        log("blocked", "no bid cleared the quality bar")
        record["blocked"].append({"job": job["title"], "reason": "no qualified bid"})
        return False
    price = negotiate(seller, buyer_max)
    if price is None:
        log("blocked", f"negotiation with {seller.name} failed")
        record["blocked"].append({"job": job["title"], "reason": "negotiation failed"})
        return False
    log("deal", f"{seller.name} wins; negotiated price {price} NEAR (ask {seller.ask})")

    ok, reason = policy.authorize(seller.name, price)
    if not ok:
        log("POLICY", f"PAYMENT BLOCKED: {reason}")
        record["blocked"].append({"job": job["title"], "reason": reason})
        return False
    log("policy", f"authorised: {reason}")

    escrow_id = ledger.lock(BUYER, seller.name, price)
    log("escrow", f"{price} NEAR locked in {escrow_id}")

    delivery = seller.deliver(job)
    log("delivery", f"{seller.name} delivered: {summarise(delivery)}")

    if verify(delivery):
        ledger.release(escrow_id)
        log("verify", "delivery verified -> escrow RELEASED")
        record["jobs"].append({
            "job": job["title"], "seller": seller.name, "price": price,
            "escrow": escrow_id, "verified": True, "delivery": delivery,
        })
        return True
    ledger.refund(escrow_id)
    log("verify", "delivery FAILED verification -> escrow REFUNDED")
    record["jobs"].append({
        "job": job["title"], "seller": seller.name, "price": price,
        "escrow": escrow_id, "verified": False, "delivery": delivery,
    })
    return False


def summarise(delivery):
    if "block_height" in delivery:
        state = "live" if delivery.get("live") else "OFFLINE fallback"
        return f"chain snapshot ({state}) at block {delivery['block_height']}"
    if "sha256" in delivery:
        return f"digest of {delivery['source_chars']} chars, sha256 {delivery['sha256'][:12]}..."
    if "verdict" in delivery:
        return f"risk verdict {delivery['verdict']} for {delivery['payee']}"
    return str(delivery)[:80]


def main():
    offline = "--offline" in sys.argv
    endpoints = ["https://127.0.0.1:9"] if offline else None
    near = NearTestnet(endpoints=endpoints) if endpoints else NearTestnet()

    print("=" * 68)
    print("AgentBazaar -- an agent-to-agent service market with guardrails")
    print("Track: Agent Economy | Network: NEAR testnet (read-only) + local escrow sim")
    print("=" * 68)

    start = chain_snapshot_service(near)
    if start.get("live"):
        print(f"\nLive chain state via {start['endpoint']}")
        print(f"  block height : {start['block_height']}")
        print(f"  block hash   : {start['block_hash']}")
        print(f"  gas price    : {start['gas_price_yocto']} yoctoNEAR")
        acct = start.get("reference_account")
        if acct:
            print(f"  account 'testnet' balance: {acct['amount_near']:.4f} NEAR (read live)")
    else:
        print("\nLive chain state: UNAVAILABLE -- running with labelled offline fallback")

    sellers = build_sellers(near)
    allowlist = [s.name for s in sellers]
    policy = Policy(PER_PAYMENT_CAP, BUDGET, allowlist)
    ledger = EscrowLedger()
    ledger.fund(BUYER, BUDGET)
    print(f"\nBuyer {BUYER}: budget {BUDGET} NEAR, per-payment cap {PER_PAYMENT_CAP}, "
          f"allowlist of {len(allowlist)} sellers")

    record = {"live": bool(start.get("live")), "endpoint": start.get("endpoint"),
              "start_block_height": start["block_height"], "jobs": [], "blocked": []}

    by_skill = {}
    for s in sellers:
        by_skill.setdefault(s.skill, []).append(s)

    # Job 1 -- buy a live chain snapshot; verify the chain really answered.
    hire(
        {"title": "Live NEAR testnet snapshot for the morning report",
         "skill": "chain-data"},
        by_skill["chain-data"], buyer_max=0.05,
        policy=policy, ledger=ledger,
        verify=lambda d: (not d.get("live")) or d["block_height"] >= start["block_height"],
        record=record,
    )

    # Job 2 -- buy a memo digest; verify by recomputing the hash.
    expected = memo_digest_service(MEMO)
    hire(
        {"title": "Digest this memo into 3 sentences", "skill": "summarize",
         "memo": MEMO},
        by_skill["summarize"], buyer_max=0.035,
        policy=policy, ledger=ledger,
        verify=lambda d: d["sha256"] == expected["sha256"]
        and d["sentence_count"] == expected["sentence_count"],
        record=record,
    )

    # Job 3 -- pay a compliance agent to screen a shady proposed payment.
    hire(
        {"title": "Screen a proposed payment before I make it",
         "skill": "compliance", "payee": "unknown-wallet.testnet",
         "amount": 0.5, "allowlist": allowlist},
        by_skill["compliance"], buyer_max=0.03,
        policy=policy, ledger=ledger,
        verify=lambda d: d["verdict"] == "BLOCK",
        record=record,
    )

    # Guardrail beat 1 -- a too-cheap stranger is not on the allowlist.
    print("\nGUARDRAIL CHECK 1: direct hire of a stranger offering a suspicious discount")
    ok, reason = policy.authorize("cheap-data.testnet", 0.010)
    log("POLICY", f"{'authorised' if ok else 'PAYMENT BLOCKED'}: {reason}")
    if not ok:
        record["blocked"].append({"job": "direct hire cheap-data.testnet", "reason": reason})

    # Guardrail beat 2 -- a legitimate seller, but the price breaks the cap.
    hire(
        {"title": "Deep research report", "skill": "research"},
        by_skill["research"], buyer_max=0.40,
        policy=policy, ledger=ledger,
        verify=lambda d: True,
        record=record,
    )

    spent = round(sum(j["price"] for j in record["jobs"] if j["verified"]), 6)
    record["totals"] = {
        "spent_released": spent,
        "buyer_balance": ledger.balance(BUYER),
        "budget_remaining": round(BUDGET - policy.spent, 6),
        "payments_blocked": len(record["blocked"]),
    }

    print("\n" + "=" * 68)
    print("SUMMARY")
    print(f"  jobs completed & paid : {sum(1 for j in record['jobs'] if j['verified'])}")
    print(f"  total released        : {spent} NEAR")
    print(f"  payments blocked      : {len(record['blocked'])} (policy guardrails)")
    print(f"  buyer balance left    : {ledger.balance(BUYER)} NEAR "
          f"(budget remaining {record['totals']['budget_remaining']})")
    for s in sellers:
        bal = ledger.balance(s.name)
        if bal:
            print(f"  earned by {s.name}: {bal} NEAR")
    print("=" * 68)

    with open("demo_output.json", "w") as fh:
        json.dump(record, fh, indent=2, default=str)
    print("Full record written to demo_output.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
