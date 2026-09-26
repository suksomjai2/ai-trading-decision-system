class FeatureEngine:

    def __init__(self):
        pass

    def calculate_features(self, market_data):

        open_price = market_data["open"]
        high = market_data["high"]
        low = market_data["low"]
        close = market_data["close"]
        volume = market_data["volume"]

        features = {

            "open": open_price,
            "high": high,
            "low": low,
            "close": close,

            "price_range": self._price_range(
                high,
                low
            ),

            "trend_direction": self._trend_direction(
                close,
                high,
                low
            ),

            "volume_state": self._volume_state(
                volume
            )
        }

        return features


    def _price_range(self, high, low):

        return high - low


    def _trend_direction(self, close, high, low):

        midpoint = (high + low) / 2

        if close > midpoint:
            return "UP"

        elif close < midpoint:
            return "DOWN"

        else:
            return "NEUTRAL"


    def _volume_state(self, volume):

        if volume <= 0:
            return "UNKNOWN"

        elif volume > 1000000:
            return "HIGH"

        else:
            return "NORMAL"
