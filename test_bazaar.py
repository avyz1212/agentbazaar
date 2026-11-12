"""Unit tests for AgentBazaar. Run: python3 -m unittest -v

The live-RPC smoke test skips itself when no endpoint is reachable, so the
suite passes fully offline too.
"""

import unittest

from ledger import EscrowLedger, LedgerError
from market import Seller, choose_bid, negotiate
from near_rpc import NearRpcError, NearTestnet
from policy import Policy
from services import memo_digest_service, risk_screen_service


def seller(name, ask, floor_ratio=0.9, quality=0.8):
    return Seller(name, "skill", ask, floor_ratio, quality, lambda job: {})


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.policy = Policy(per_payment_cap=0.20, total_budget=1.0,
                             allowlist=["a.testnet", "b.testnet"])

    def test_allowlisted_within_cap_ok(self):
        ok, _ = self.policy.check("a.testnet", 0.05)
        self.assertTrue(ok)

    def test_stranger_blocked(self):
        ok, reason = self.policy.check("stranger.testnet", 0.01)
        self.assertFalse(ok)
        self.assertIn("allowlist", reason)

    def test_over_cap_blocked(self):
        ok, reason = self.policy.check("a.testnet", 0.35)
        self.assertFalse(ok)
        self.assertIn("cap", reason)

    def test_budget_is_cumulative(self):
        self.assertTrue(self.policy.authorize("a.testnet", 0.20)[0])
        self.policy.spent = 0.95
        ok, reason = self.policy.check("a.testnet", 0.10)
        self.assertFalse(ok)
        self.assertIn("budget", reason)

    def test_failed_authorize_spends_nothing(self):
        self.policy.authorize("stranger.testnet", 0.5)
        self.assertEqual(self.policy.spent, 0.0)


class LedgerTest(unittest.TestCase):
    def test_lock_release_moves_money(self):
        led = EscrowLedger()
        led.fund("buyer", 1.0)
        esc = led.lock("buyer", "seller", 0.3)
        self.assertEqual(led.balance("buyer"), 0.7)
        led.release(esc)
        self.assertEqual(led.balance("seller"), 0.3)
        self.assertEqual(led.escrow(esc)["state"], "released")

    def test_refund_returns_money(self):
        led = EscrowLedger()
        led.fund("buyer", 1.0)
        esc = led.lock("buyer", "seller", 0.3)
        led.refund(esc)
        self.assertEqual(led.balance("buyer"), 1.0)
        self.assertEqual(led.balance("seller"), 0.0)

    def test_double_settle_rejected(self):
        led = EscrowLedger()
        led.fund("buyer", 1.0)
        esc = led.lock("buyer", "seller", 0.3)
        led.release(esc)
        with self.assertRaises(LedgerError):
            led.release(esc)

    def test_insufficient_balance_rejected(self):
        led = EscrowLedger()
        led.fund("buyer", 0.1)
        with self.assertRaises(LedgerError):
            led.lock("buyer", "seller", 0.3)


class MarketTest(unittest.TestCase):
    def test_choose_cheapest_qualified_bid(self):
        bids = [seller("x", 0.06, quality=0.9), seller("y", 0.045, quality=0.8),
                seller("z", 0.01, quality=0.2)]
        self.assertEqual(choose_bid(bids).name, "y")  # z fails the quality bar

    def test_negotiate_accepts_opening_offer(self):
        self.assertEqual(negotiate(seller("s", 0.045), buyer_max=0.05), 0.0405)

    def test_negotiate_counter_at_floor(self):
        # offer 0.036 < floor 0.038 -> seller counters at floor, buyer accepts
        self.assertEqual(negotiate(seller("s", 0.040, floor_ratio=0.95),
                                   buyer_max=0.05), 0.038)

    def test_negotiate_fails_over_budget(self):
        self.assertIsNone(negotiate(seller("s", 0.040, floor_ratio=0.95),
                                    buyer_max=0.03))


class ServicesTest(unittest.TestCase):
    def test_digest_is_deterministic_and_verifiable(self):
        text = "One sentence here. Another follows it! And a third? A fourth one."
        a = memo_digest_service(text)
        b = memo_digest_service(text)
        self.assertEqual(a, b)
        self.assertEqual(a["sentence_count"], 3)

    def test_risk_screen_blocks_stranger(self):
        out = risk_screen_service("nobody.testnet", 0.05, allowlist=["a.testnet"])
        self.assertEqual(out["verdict"], "BLOCK")

    def test_risk_screen_allows_small_allowlisted(self):
        out = risk_screen_service("a.testnet", 0.05, allowlist=["a.testnet"])
        self.assertEqual(out["verdict"], "ALLOW")


class RpcSmokeTest(unittest.TestCase):
    def test_testnet_status(self):
        near = NearTestnet(timeout=10)
        try:
            status = near.status()
        except NearRpcError:
            self.skipTest("no NEAR testnet RPC endpoint reachable")
        self.assertEqual(status["chain_id"], "testnet")


if __name__ == "__main__":
    unittest.main()
