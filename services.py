"""The services agents actually sell in the marketplace.

Two of the three are grounded in the real world: the chain-data service
returns a *live* NEAR testnet snapshot fetched over public RPC at delivery
time, and the risk-screen service runs a real policy check. The digest
service is a small deterministic local summariser (no external AI API), so
the whole demo runs with zero API keys.
"""

import hashlib
import re

from policy import Policy

# Fallback snapshot, used only when every RPC endpoint is unreachable.
# It is labelled as offline data everywhere it surfaces.
OFFLINE_SNAPSHOT = {
    "chain_id": "testnet",
    "block_height": 0,
    "block_hash": "OFFLINE-NO-LIVE-DATA",
    "gas_price_yocto": 0,
    "reference_account": None,
    "endpoint": None,
}


def chain_snapshot_service(near):
    """Deliverable: a live NEAR testnet snapshot (or labelled fallback)."""
    try:
        snap = near.chain_snapshot()
        snap["live"] = True
        return snap
    except Exception:
        snap = dict(OFFLINE_SNAPSHOT)
        snap["live"] = False
        return snap


def memo_digest_service(text, sentences=3):
    """Deliverable: extractive digest + a verifiable content hash."""
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    digest = " ".join(parts[:sentences])
    canonical = " ".join(text.split()).lower()
    return {
        "digest": digest,
        "sentence_count": len(parts[:sentences]),
        "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "source_chars": len(text),
    }


def risk_screen_service(payee, amount, allowlist, cap=0.10, budget=1.0):
    """Deliverable: an independent pre-payment risk verdict.

    The screener applies a *stricter* policy than the buyer's own, the way a
    compliance service would before an agent is allowed to pay a stranger.
    """
    strict = Policy(per_payment_cap=cap, total_budget=budget, allowlist=allowlist)
    ok, reason = strict.check(payee, amount)
    return {
        "payee": payee,
        "amount": round(float(amount), 6),
        "verdict": "ALLOW" if ok else "BLOCK",
        "reason": reason,
        "checks": ["allowlist", f"per-payment cap {cap}", f"budget {budget}"],
    }
