class SetupIntelligence:

    def evaluate(self, features, regime):

        setup = "NO_SETUP"
        score = 0
        reasons = []

        trend = features.get(
            "trend_direction",
            "NEUTRAL"
        )

        pressure = features.get(
            "buying_pressure",
            0.5
        )

        market = regime.get(
            "regime",
            "SIDEWAY"
        )


        if trend == "UP" and market == "UPTREND":
            score += 2
            reasons.append(
                "Trend alignment"
            )


        if pressure > 0.7:
            score += 1
            reasons.append(
                "Buying pressure"
            )


        if score >= 2:
            setup = "BUY_SETUP"


        elif trend == "DOWN" and market == "DOWNTREND":
            setup = "SELL_SETUP"
            score += 2
            reasons.append(
                "Trend alignment"
            )


        return {
            "setup": setup,
            "score": score,
            "reasons": reasons
        }
