"""Spending policy engine -- the guardrails every payment must pass.

An agent with a wallet is only safe to run unattended if a human-defined
policy sits between its intentions and its money. Every escrow lock in the
demo is checked here first; a failed check means the payment never happens.
"""


class Policy:
    def __init__(self, per_payment_cap, total_budget, allowlist):
        self.per_payment_cap = float(per_payment_cap)
        self.total_budget = float(total_budget)
        self.allowlist = set(allowlist)
        self.spent = 0.0
        self.decisions = []  # (payee, amount, ok, reason)

    def check(self, payee, amount):
        """Return (ok, reason). Pure: does not mutate state."""
        amount = round(float(amount), 6)
        if payee not in self.allowlist:
            return False, f"{payee} is not on the allowlist"
        if amount > self.per_payment_cap:
            return False, (
                f"{amount} exceeds the per-payment cap of {self.per_payment_cap}"
            )
        if round(self.spent + amount, 6) > self.total_budget:
            return False, (
                f"cumulative spend {round(self.spent + amount, 6)} would exceed "
                f"the total budget of {self.total_budget}"
            )
        return True, "within policy"

    def authorize(self, payee, amount):
        """Check and, if allowed, record the spend. Returns (ok, reason)."""
        ok, reason = self.check(payee, amount)
        self.decisions.append((payee, round(float(amount), 6), ok, reason))
        if ok:
            self.spent = round(self.spent + float(amount), 6)
        return ok, reason
