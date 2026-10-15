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

    def calculate_history(self, candles):
        """Closed bars only, in time order. EMA and Wilder ATR use history."""
        if len(candles) < 60:
            raise ValueError("INSUFFICIENT_HISTORY")
        closes = [c["close"] for c in candles]

        def ema(period):
            value = sum(closes[:period]) / period
            values = [value]
            alpha = 2 / (period + 1)
            for close in closes[period:]:
                value += alpha * (close - value)
                values.append(value)
            return values

        true_ranges = [max(c["high"] - c["low"],
                           abs(c["high"] - candles[i - 1]["close"]),
                           abs(c["low"] - candles[i - 1]["close"]))
                       for i, c in enumerate(candles) if i]
        atr = sum(true_ranges[:14]) / 14
        for value in true_ranges[14:]:
            atr = (13 * atr + value) / 14
        fast, slow = ema(20), ema(50)
        current, previous = candles[-5:], candles[-10:-5]
        higher = (max(c["high"] for c in current) > max(c["high"] for c in previous)
                  and min(c["low"] for c in current) > min(c["low"] for c in previous))
        lower = (max(c["high"] for c in current) < max(c["high"] for c in previous)
                 and min(c["low"] for c in current) < min(c["low"] for c in previous))
        direction = "NEUTRAL"
        if closes[-1] > fast[-1] > slow[-1] and fast[-1] > fast[-6] and higher:
            direction = "UP"
        elif closes[-1] < fast[-1] < slow[-1] and fast[-1] < fast[-6] and lower:
            direction = "DOWN"
        return {
            "direction": direction, "ema20": fast[-1], "ema50": slow[-1],
            "atr14": atr, "structure": "HIGHER" if higher else "LOWER" if lower else "MIXED",
            "last_close": closes[-1], "last_time": candles[-1]["time"],
        }
