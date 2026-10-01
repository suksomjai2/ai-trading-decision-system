class MarketRegimeEngine:

    def evaluate(self, features):

        trend = features.get(
            "trend_direction",
            "NEUTRAL"
        )

        strength = features.get(
            "trend_strength",
            0
        )

        pressure = features.get(
            "buying_pressure",
            0.5
        )


        regime = "SIDEWAY"


        if trend == "UP" and strength > 0.5:
            regime = "UPTREND"


        elif trend == "DOWN" and strength > 0.5:
            regime = "DOWNTREND"


        elif pressure > 0.7:
            regime = "BUY_PRESSURE"


        elif pressure < 0.3:
            regime = "SELL_PRESSURE"


        return {
            "regime": regime,
            "strength": strength
        }
