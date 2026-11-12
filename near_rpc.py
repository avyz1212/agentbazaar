"""Read-only NEAR testnet JSON-RPC client (public endpoints, no keys).

Only *view* calls are made: status, block, gas_price and view_account.
Nothing is signed and nothing is ever sent to the chain from this module.
"""

import json
import urllib.request

ENDPOINTS = [
    "https://near-testnet.drpc.org",
    "https://rpc.testnet.near.org",
]

YOCTO_PER_NEAR = 10 ** 24


class NearRpcError(Exception):
    pass


class NearTestnet:
    """Minimal JSON-RPC client that fails over across public endpoints."""

    def __init__(self, endpoints=ENDPOINTS, timeout=12):
        self.endpoints = list(endpoints)
        self.timeout = timeout
        self.endpoint = None  # first endpoint that answered

    def _call(self, method, params, passes=2):
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": "agentbazaar", "method": method, "params": params}
        ).encode()
        last_err = None
        # Public endpoints occasionally drop a connection mid-body; a second
        # pass over the endpoint list absorbs those transient failures.
        for _ in range(passes):
            for url in self.endpoints:
                try:
                    req = urllib.request.Request(
                        url,
                        data=payload,
                        headers={
                            "Content-Type": "application/json",
                            # Some public endpoints reject the default Python UA.
                            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                            "AppleWebKit/537.36 AgentBazaar/0.1",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        body = json.loads(resp.read().decode())
                    if "error" in body:
                        raise NearRpcError(str(body["error"]))
                    self.endpoint = url
                    return body["result"]
                except Exception as exc:  # try the next endpoint
                    last_err = exc
        raise NearRpcError(f"all endpoints failed: {last_err}")

    def status(self):
        return self._call("status", [])

    def latest_block(self):
        return self._call("block", {"finality": "final"})

    def gas_price(self):
        result = self._call("gas_price", [None])
        return int(result["gas_price"])

    def view_account(self, account_id):
        result = self._call(
            "query",
            {
                "request_type": "view_account",
                "finality": "final",
                "account_id": account_id,
            },
        )
        amount = int(result["amount"])
        return {
            "account_id": account_id,
            "amount_yocto": amount,
            "amount_near": amount / YOCTO_PER_NEAR,
            "storage_usage": result.get("storage_usage"),
            "block_height": result.get("block_height"),
        }

    def chain_snapshot(self):
        """Snapshot used by the data-oracle service agents.

        Height and hash come from the small `status` response (sync_info)
        rather than the multi-KB `block` response: cheaper, and far more
        reliable on lossy networks.
        """
        sync = self.status()["sync_info"]
        try:
            account = self.view_account("testnet")
        except NearRpcError:
            account = None
        return {
            "chain_id": "testnet",
            "block_height": sync["latest_block_height"],
            "block_hash": sync["latest_block_hash"],
            "gas_price_yocto": self.gas_price(),
            "reference_account": account,
            "endpoint": self.endpoint,
        }
