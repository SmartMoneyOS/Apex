"""Official Robinhood Crypto Trading API client.

Docs: https://docs.robinhood.com/crypto/trading/
Auth: API key + Ed25519 signature. Generate the keypair and API key in the
Robinhood app (Account -> Crypto -> API). Requires the `pynacl` extra:

    pip install "apex-trader[live]"

Notes that matter for "making the most money":
- Robinhood crypto quotes carry a real spread; the effective cost is in the
  bid/ask, not a commission line. Apex trades on best bid/ask, not mid.
- Crypto trades 24/7 - this is why Apex defaults to BTC rather than stocks
  (Robinhood has NO official stock-trading API; see robinhood_stocks.py).
"""
from __future__ import annotations

import base64
import json
import os
import time
import uuid

import requests

from .base import Broker

BASE_URL = "https://trading.robinhood.com"


class RobinhoodCryptoBroker(Broker):
    def __init__(self, api_key: str | None = None, private_key_b64: str | None = None):
        try:
            from nacl.signing import SigningKey
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "Live trading needs pynacl: pip install 'apex-trader[live]'") from e

        api_key = api_key or os.environ.get("ROBINHOOD_API_KEY", "")
        key_b64 = private_key_b64 or os.environ.get("ROBINHOOD_PRIVATE_KEY_B64", "")
        if not api_key or not key_b64:
            raise ValueError("Robinhood API key and private key are required for live mode")
        self.api_key = api_key
        self._signing_key = SigningKey(base64.b64decode(key_b64))
        self._session = requests.Session()

    # -- request signing ------------------------------------------------------
    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        timestamp = str(int(time.time()))
        body_str = json.dumps(body) if body else ""
        message = f"{self.api_key}{timestamp}{path}{method}{body_str}"
        signed = self._signing_key.sign(message.encode())
        headers = {
            "x-api-key": self.api_key,
            "x-timestamp": timestamp,
            "x-signature": base64.b64encode(signed.signature).decode(),
            "Content-Type": "application/json",
        }
        resp = self._session.request(method, BASE_URL + path,
                                     headers=headers, data=body_str or None,
                                     timeout=10)
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    # -- Broker interface ------------------------------------------------------
    def get_price(self, symbol: str) -> float:
        data = self._request(
            "GET", f"/api/v1/crypto/marketdata/best_bid_ask/?symbol={symbol}")
        result = data["results"][0]
        return (float(result["bid_inclusive_of_sell_spread"]) +
                float(result["ask_inclusive_of_buy_spread"])) / 2

    def get_cash(self) -> float:
        data = self._request("GET", "/api/v1/crypto/trading/accounts/")
        return float(data["buying_power"])

    def get_positions(self) -> dict[str, float]:
        data = self._request("GET", "/api/v1/crypto/trading/holdings/")
        return {h["asset_code"] + "-USD": float(h["total_quantity"])
                for h in data.get("results", []) if float(h["total_quantity"]) > 0}

    def market_order(self, symbol: str, qty: float) -> None:
        if qty == 0:
            return
        side = "buy" if qty > 0 else "sell"
        body = {
            "client_order_id": str(uuid.uuid4()),
            "side": side,
            "type": "market",
            "symbol": symbol,
            "market_order_config": {"asset_quantity": f"{abs(qty):.8f}"},
        }
        self._request("POST", "/api/v1/crypto/trading/orders/", body)
