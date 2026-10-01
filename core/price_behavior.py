class PriceBehavior:

    def __init__(self):
        pass

    def analyze(self, features):

        direction = features.get(
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

        momentum = features.get(
            "momentum",
            0
        )

        score = 0
        reasons = []

        if direction == "UP":
            score += 1
            reasons.append(
                "Up trend"
            )

        elif direction == "DOWN":
            score -= 1
            reasons.append(
                "Down trend"
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
                "Strong buying pressure"
            )

        elif pressure < 0.4:
            score -= 1
            reasons.append(
                "Strong selling pressure"
            )

        if score >= 2:
            behavior = "BULLISH"

        elif score <= -2:
            behavior = "BEARISH"

        else:
            behavior = "NEUTRAL"

        return {
            "behavior": behavior,
            "score": round(score, 2),
            "reasons": reasons
        }
