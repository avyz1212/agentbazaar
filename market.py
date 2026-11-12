"""The marketplace: sellers, bids and a deterministic negotiation."""

from dataclasses import dataclass, field


@dataclass
class Seller:
    name: str            # agent account id (testnet-style name)
    skill: str           # service category it sells
    ask: float           # asking price in NEAR
    floor_ratio: float   # lowest it will accept, as a fraction of ask
    quality: float       # 0..1 self-reported quality score
    deliver: object = field(repr=False)  # callable(job: dict) -> dict

    @property
    def floor(self):
        return round(self.ask * self.floor_ratio, 6)


def choose_bid(bids, min_quality=0.5):
    """Pick the cheapest bid that clears the quality bar. None if no fit."""
    fit = [b for b in bids if b.quality >= min_quality]
    if not fit:
        return None
    return min(fit, key=lambda b: (b.ask, -b.quality))


def negotiate(seller, buyer_max):
    """One counter-offer round. Returns the agreed price or None.

    The buyer opens at 90% of ask. The seller accepts if that meets its
    floor, otherwise counters at its floor. The buyer accepts the counter
    only if it fits the job budget (buyer_max).
    """
    offer = round(seller.ask * 0.9, 6)
    if offer >= seller.floor:
        return offer
    counter = seller.floor
    if counter <= buyer_max:
        return counter
    return None
