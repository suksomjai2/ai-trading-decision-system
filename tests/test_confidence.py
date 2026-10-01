from core.decision_engine import DecisionEngine


def test_confidence_exists():

    result = DecisionEngine().decide(
        "ALIGNED",
        {
            "trend": "UP",
            "score": 0.8
        }
    )

    assert "confidence" in result


def test_confidence_range():

    result = DecisionEngine().decide(
        "ALIGNED",
        {
            "trend": "UP",
            "score": 0.8
        }
    )

    assert 0 <= result["confidence"] <= 1
