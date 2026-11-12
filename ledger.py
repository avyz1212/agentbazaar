"""Simulated escrow ledger.

This stands in for NEAR transfers in the prototype: balances are kept in
memory and every movement is recorded in ``history``. See the README section
"What is live vs simulated" -- the production design replaces this module
with real testnet transfers plus an escrow contract; the call sites and the
policy checks around them stay the same.
"""


class LedgerError(Exception):
    pass


class EscrowLedger:
    def __init__(self):
        self._balances = {}
        self._escrows = {}  # id -> {"buyer", "seller", "amount", "state"}
        self._next_id = 1
        self.history = []

    @staticmethod
    def _clean(amount):
        return round(float(amount), 6)

    def fund(self, account, amount):
        amount = self._clean(amount)
        self._balances[account] = self._clean(self.balance(account) + amount)
        self.history.append(("fund", account, amount))

    def balance(self, account):
        return self._balances.get(account, 0.0)

    def lock(self, buyer, seller, amount):
        """Move ``amount`` from buyer into a new escrow for seller."""
        amount = self._clean(amount)
        if self.balance(buyer) < amount:
            raise LedgerError(f"{buyer} has insufficient balance")
        escrow_id = f"esc-{self._next_id}"
        self._next_id += 1
        self._balances[buyer] = self._clean(self.balance(buyer) - amount)
        self._escrows[escrow_id] = {
            "buyer": buyer,
            "seller": seller,
            "amount": amount,
            "state": "locked",
        }
        self.history.append(("lock", escrow_id, buyer, seller, amount))
        return escrow_id

    def _settle(self, escrow_id, payee_key, new_state, verb):
        escrow = self._escrows.get(escrow_id)
        if escrow is None:
            raise LedgerError(f"unknown escrow {escrow_id}")
        if escrow["state"] != "locked":
            raise LedgerError(f"escrow {escrow_id} is {escrow['state']}, not locked")
        payee = escrow[payee_key]
        self._balances[payee] = self._clean(self.balance(payee) + escrow["amount"])
        escrow["state"] = new_state
        self.history.append((verb, escrow_id, payee, escrow["amount"]))

    def release(self, escrow_id):
        """Pay the seller (delivery verified)."""
        self._settle(escrow_id, "seller", "released", "release")

    def refund(self, escrow_id):
        """Return the money to the buyer (delivery failed verification)."""
        self._settle(escrow_id, "buyer", "refunded", "refund")

    def escrow(self, escrow_id):
        return self._escrows.get(escrow_id)
