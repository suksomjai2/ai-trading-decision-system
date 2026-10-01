class SetupEngine:

    def __init__(self):
        pass


    def evaluate(self, features):

        trend = features.get(
            "trend_direction",
            "NEUTRAL"
        )

        candle = features.get(
            "candle_type",
            "NEUTRAL"
        )

        pressure = features.get(
            "buying_pressure",
            0.5
        )

        setup = "NONE"
        score = 0
        reasons = []


        if trend == "UP":
            score += 1
            reasons.append(
                "Up trend setup"
            )

        elif trend == "DOWN":
            score -= 1
            reasons.append(
                "Down trend setup"
            )


        if candle == "BULLISH":
            score += 1
            reasons.append(
                "Bullish candle"
            )

        elif candle == "BEARISH":
            score -= 1
            reasons.append(
                "Bearish candle"
            )


        if pressure > 0.6:
            score += 1
            reasons.append(
                "Buying pressure"
            )

        elif pressure < 0.4:
            score -= 1
            reasons.append(
                "Selling pressure"
            )


        if score >= 2:
            setup = "LONG_SETUP"

        elif score <= -2:
            setup = "SHORT_SETUP"


        return {
            "setup": setup,
            "score": score,
            "reasons": reasons
        }
