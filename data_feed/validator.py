class CandleValidator:

    REQUIRED_FIELDS = [
        "symbol",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    def validate(self, candle):

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in candle:
                return {
                    "valid": False,
                    "reason": f"MISSING_FIELD:{field}"
                }

        try:
            open_price = float(candle["open"])
            high = float(candle["high"])
            low = float(candle["low"])
            close = float(candle["close"])
            volume = float(candle["volume"])
        except (TypeError, ValueError):
            return {
                "valid": False,
                "reason": "INVALID_NUMERIC_DATA"
            }

        # Price must be positive
        if min(open_price, high, low, close) <= 0:
            return {
                "valid": False,
                "reason": "INVALID_PRICE"
            }

        # High / Low consistency
        if high < low:
            return {
                "valid": False,
                "reason": "HIGH_BELOW_LOW"
            }

        # Open / Close must be inside candle range
        if not low <= open_price <= high:
            return {
                "valid": False,
                "reason": "OPEN_OUT_OF_RANGE"
            }

        if not low <= close <= high:
            return {
                "valid": False,
                "reason": "CLOSE_OUT_OF_RANGE"
            }

        if volume < 0:
            return {
                "valid": False,
                "reason": "INVALID_VOLUME"
            }

        return {
            "valid": True,
            "reason": "OK"
        }
