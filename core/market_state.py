class MarketState:

    def __init__(self):
        pass


    def analyze(self, market_data):

        features = self._extract_features(market_data)

        decision = self._make_decision(features)

        return {
            "features": features,
            "decision": decision
        }


    def _extract_features(self, market_data):

        open_price = market_data["open"]
        high = market_data["high"]
        low = market_data["low"]
        close = market_data["close"]
        volume = market_data["volume"]

        body_size = abs(close - open_price)

        upper_shadow = high - max(open_price, close)

        lower_shadow = min(open_price, close) - low

        price_range = high - low


        if close > open_price:
            trend_direction = "UP"
        elif close < open_price:
            trend_direction = "DOWN"
        else:
            trend_direction = "NEUTRAL"


        if price_range > 0:
            price_position = round(
                (close - low) / price_range,
                2
            )
        else:
            price_position = 0


        buying_pressure = price_position


        if body_size > 0:
            momentum = body_size
        else:
            momentum = 0


        volatility = round(
            price_range / close,
            4
        )


        if volume > 0:
            volume_state = "HIGH"
        else:
            volume_state = "LOW"


        if price_position >= 0.7:
            candle_type = "BULLISH"
        elif price_position <= 0.3:
            candle_type = "BEARISH"
        else:
            candle_type = "NEUTRAL"


        trend_strength = self._trend_strength(
            close,
            high,
            low
        )


        return {

            "open": open_price,
            "high": high,
            "low": low,
            "close": close,

            "body_size": body_size,
            "upper_shadow": upper_shadow,
            "lower_shadow": lower_shadow,

            "price_range": price_range,

            "trend_direction": trend_direction,

            "trend_strength": trend_strength,

            "volume_state": volume_state,

            "momentum": momentum,

            "volatility": volatility,

            "price_position": price_position,

            "candle_type": candle_type,

            "buying_pressure": buying_pressure
        }



    def _trend_strength(
        self,
        close,
        high,
        low
    ):

        price_range = high - low

        if price_range == 0:
            return 0


        strength = abs(
            close - ((high + low) / 2)
        )


        return round(strength,2)



    def _make_decision(self, features):

        score = 0


        # Trend
        if features["trend_direction"] == "UP":
            score += 2

        elif features["trend_direction"] == "DOWN":
            score -= 2



        # Trend strength
        if features["trend_strength"] >= 5:
            score += 2



        # Volume
        if features["volume_state"] == "HIGH":
            score += 2



        # Momentum
        if features["momentum"] > 0:
            score += 2



        # Candle
        if features["candle_type"] == "BULLISH":
            score += 1

        elif features["candle_type"] == "BEARISH":
            score -= 1



        # Volatility risk
        if features["volatility"] < 0.02:
            score += 1



        # Decision

        if score >= 7:
            action = "BUY"

        elif score <= -3:
            action = "SELL"

        else:
            action = "HOLD"



        confidence = round(
            min(abs(score) / 10, 1),
            2
        )


        return {

            "action": action,

            "score": score,

            "confidence": confidence

        }
