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


            # Candle features
            "body_size": abs(close - open_price),

            "upper_shadow": high - max(open_price, close),

            "lower_shadow": min(open_price, close) - low,


            # Price movement
            "price_range": self._price_range(
                high,
                low
            ),


            # Trend
            "trend_direction": self._trend_direction(
                close,
                high,
                low
            ),


            # Volume
            "volume_state": self._volume_state(
                volume
            ),


            # New Phase 2 features
            "trend_strength": self._trend_strength(
                close,
                high,
                low
            ),


            "momentum": close - open_price,


            "volatility": self._volatility(
                high,
                low,
                close
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

        midpoint = (high + low) / 2

        return abs(
            close - midpoint
        )



    def _volatility(self, high, low, close):

        if close == 0:
            return 0


        return round(
            (high - low) / close,
            4
        )



    def _volume_state(self, volume):

        if volume <= 0:

            return "UNKNOWN"


        elif volume > 100000:

            return "HIGH"


        else:

            return "NORMAL"
