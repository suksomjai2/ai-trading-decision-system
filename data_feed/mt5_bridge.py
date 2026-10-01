class MT5Bridge:

    REQUIRED_FIELDS = [
        "symbol",
        "timeframe",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    def parse(self, payload):

        if not isinstance(payload, dict):
            return {
                "accepted": False,
                "reason": "INVALID_PAYLOAD",
                "data": None
            }

        for field in self.REQUIRED_FIELDS:
            if field not in payload:
                return {
                    "accepted": False,
                    "reason": f"MISSING_FIELD:{field}",
                    "data": None
                }

        try:
            data = {
                "symbol": str(payload["symbol"]),
                "timeframe": str(payload["timeframe"]),
                "timestamp": str(payload["timestamp"]),
                "open": float(payload["open"]),
                "high": float(payload["high"]),
                "low": float(payload["low"]),
                "close": float(payload["close"]),
                "volume": float(payload["volume"])
            }
        except (TypeError, ValueError):
            return {
                "accepted": False,
                "reason": "INVALID_NUMERIC_DATA",
                "data": None
            }

        return {
            "accepted": True,
            "reason": "OK",
            "data": data
        }
