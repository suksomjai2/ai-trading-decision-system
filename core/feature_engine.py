class FeatureEngine:
    """
    Feature extraction engine
    Convert market data into structured AI features
    """

    def __init__(self):
        pass


    def calculate_features(self, market_data):
        """
        Input:
        {
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "volume": float
        }

        Output:
        structured feature dictionary
        """

        close = market_data["close"]
        high = market_data["high"]
        low = market_data["low"]
        volume = market_data["volume"]


        features = {

            # ======================
            # Price Structure
            # ======================

            "close_price": close,

            "price_range": self._price_range(
                high,
                low
            ),


            # ======================
            # Trend Structure
            # ======================

            "trend_direction": self._trend_direction(
                close,
                high,
                low
            ),

            "trend_strength": self._trend_strength(
                high,
                low,
                close
            ),


            # ======================
            # Volatility
            # ======================

            "volatility_state": self._volatility_state(
                high,
                low,
                close
            ),

            "atr_proxy": self._atr_proxy(
                high,
                low
            ),


            # ======================
            # Market Behavior
            # ======================

            "body_size": self._body_size(
                close,
                market_data["open"]
            ),

            "volume_state": self._volume_state(
                volume
            )
        }


        return features



    # ======================
    # Feature Functions
    # ======================


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



    def _trend_strength(self, high, low, close):

        price_range = high - low

        if price_range == 0:
            return 0

        strength = abs(
            close - ((high + low) / 2)
        ) / price_range


        return round(strength, 3)



    def _volatility_state(self, high, low, close):

        range_percent = (
            (high - low) / close
        ) * 100


        if range_percent > 2:
            return "HIGH"

        elif range_percent < 0.5:
            return "LOW"

        else:
            return "NORMAL"



    def _atr_proxy(self, high, low):

        return high - low



    def _body_size(self, close, open_price):

        return abs(
            close - open_price
        )



    def _volume_state(self, volume):

        if volume <= 0:
            return "UNKNOWN"

        elif volume > 1000000:
            return "HIGH"

        else:
            return "NORMAL"
