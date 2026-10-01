class SetupConfidence:

    def evaluate(self, setup):

        score = setup.get(
            "score",
            0
        )

        confidence = 0.0


        if score >= 3:
            confidence = 0.9

        elif score == 2:
            confidence = 0.7

        elif score == 1:
            confidence = 0.4

        else:
            confidence = 0.1


        return {
            "setup_confidence": confidence,
            "quality": (
                "HIGH"
                if confidence >= 0.7
                else "LOW"
            )
        }
