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
    "body_size": abs(close - open_price),
    "upper_shadow": high - max(open_price, close),
    "lower_shadow": min(open_price, close) - low,
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
            ),    
             "trend_strength": self._trend_strength(
    close,
    high,
    low
),   
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

def _trend_strength(self, close, high, low):

    range_value = high - low

    if range_value == 0:

        return 0

    return abs(close - ((high + low) / 2))
    def _volume_state(self, volume):

        if volume <= 0:
            return "UNKNOWN"

        elif volume > 1000000:
            return "HIGH"

        else:
            return "NORMAL"
