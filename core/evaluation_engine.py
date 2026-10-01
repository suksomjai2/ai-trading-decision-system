class EvaluationEngine:

    def evaluate(self, market_state):

        return {
            "performance": market_state.performance_status(),
            "calibration": market_state.calibration_status(),
            "risk_analysis": market_state.risk_analysis_status()
        }
