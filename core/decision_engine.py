class DecisionEngine:


    def __init__(self):
        pass



    def decide(
        self,
        state,
        features
    ):


        score = 0


        # ======================
        # Trend Direction
        # ======================

        if features.get(
            "trend_direction"
        ) == "UP":

            score += 2


        elif features.get(
            "trend_direction"
        ) == "DOWN":

            score -= 2



        # ======================
        # Trend Strength
        # ======================

        trend_strength = features.get(
            "trend_strength",
            0
        )


        score += min(
            trend_strength / 2,
            2
        )



        # ======================
        # Volume
        # ======================

        if features.get(
            "volume_state"
        ) == "HIGH":

            score += 1



        # ======================
        # Momentum
        # ======================

        momentum = features.get(
            "momentum",
            0
        )


        if momentum > 0:

            score += min(
                momentum / 10,
                2
            )



        # ======================
        # Candle
        # ======================

        if features.get(
            "candle_type"
        ) == "BULLISH":

            score += 1



        # ======================
        # Price Position
        # ======================

        price_position = features.get(
            "price_position",
            0.5
        )


        if price_position < 0.8:

            score += 1

        else:

            score -= 0.5



        # ======================
        # Volatility penalty
        # ======================

        volatility = features.get(
            "volatility",
            0
        )


        if volatility > 0.02:

            score -= 1



        # ======================
        # Normalize
        # ======================

        max_score = 10

        confidence = score / max_score


        confidence = max(
            0,
            min(
                confidence,
                1
            )
        )



        # ======================
        # Decision
        # ======================

        if score >= 6:

            action = "BUY"


        elif score <= 3:

            action = "SELL"


        else:

            action = "HOLD"



        return {


            "action": action,


            "score": round(
                score,
                2
            ),


            "confidence": round(
                confidence,
                2
            )

        }
