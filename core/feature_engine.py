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


            # Candle Structure

            "body_size": abs(close - open_price),

            "upper_shadow": high - max(open_price, close),

            "lower_shadow": min(open_price, close) - low,


            # Price Movement

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


            "trend_strength": self._trend_strength(
                close,
                high,
                low
            ),


            # Volume

            "volume_state": self._volume_state(
                volume
            ),


            # Momentum

            "momentum": close - open_price,


            # Volatility

            "volatility": self._volatility(
                high,
                low,
                close
            ),


            # Phase 2.3

            "price_position": self._price_position(
                close,
                high,
                low
            ),


            "candle_type": self._candle_type(
                open_price,
                close
            ),


            "buying_pressure": self._buying_pressure(
                close,
                high,
                low
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



    def _price_position(self, close, high, low):

        if high == low:
            return 0


        return round(
            (close - low) / (high - low),
            2
        )



    def _candle_type(self, open_price, close):

        body = close - open_price


        if body > 0:
            return "BULLISH"

        elif body < 0:
            return "BEARISH"

        else:
            return "DOJI"



    def _buying_pressure(self, close, high, low):

        if high == low:
            return 0


        return round(
            (close - low) / (high - low),
            2
        )



    def _volume_state(self, volume):

        if volume <= 0:

            return "UNKNOWN"


        elif volume > 100000:

            return "HIGH"


        else:

            return "NORMAL"
