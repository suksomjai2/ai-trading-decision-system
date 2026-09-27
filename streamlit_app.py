import streamlit as st
import subprocess
import inspect

from core.market_state import MarketState
from core.feature_engine import FeatureEngine
from core.decision_engine import DecisionEngine
from core.risk_engine import RiskEngine


# =========================
# Page Config
# =========================

st.set_page_config(
    page_title="AI Trading Decision System",
    layout="wide"
)


# =========================
# Deployment Debug
# =========================

try:
    commit_hash = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True
    ).strip()

except Exception:
    commit_hash = "UNKNOWN"


# =========================
# Title
# =========================

st.title("🧠 AI Trading Decision System")
st.subheader("XAUUSD AI Analysis Dashboard")


# =========================
# Initialize Engines
# =========================

market_engine = MarketState()
feature_engine = FeatureEngine()
decision_engine = DecisionEngine()
risk_engine = RiskEngine()


# =========================
# Market Data
# =========================

market_data = {
    "open": 2650,
    "high": 2665,
    "low": 2645,
    "close": 2660,
    "volume": 1200000
}


# =========================
# Market Analysis
# =========================

market_result = market_engine.analyze(
    market_data
)


# =========================
# Extract Data
# =========================

features = market_result.get(
    "features",
    {}
)

decision = market_result.get(
    "decision",
    {}
)


# =========================
# Direct Decision Test
# =========================
# This checks DecisionEngine directly.
# It lets us compare the result returned by
# MarketState with the current DecisionEngine.

state_value = features.get(
    "trend_direction",
    "UNKNOWN"
)

direct_decision = decision_engine.decide(
    state_value,
    features
)


# =========================
# Risk
# =========================

risk = risk_engine.evaluate(
    decision,
    features
)


# =========================
# Dashboard
# =========================

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "Market Trend",
        features.get(
            "trend_direction",
            "UNKNOWN"
        )
    )


with col2:

    st.metric(
        "Decision",
        decision.get(
            "action",
            "HOLD"
        )
    )


with col3:

    confidence = decision.get(
        "confidence",
        0
    )

    st.metric(
        "Confidence",
        f"{confidence:.3f}"
        if isinstance(
            confidence,
            (int, float)
        )
        else confidence
    )


# =========================
# Details
# =========================

st.divider()


st.write("### Market Features")

st.json(
    features
)


st.write("### Decision Detail")

st.json(
    decision
)


st.write("### Risk Detail")

st.json(
    risk
)


# =========================
# Debug Information
# =========================

st.divider()

st.write("## 🔧 Debug Information")


st.write("### Deployed Commit")

st.code(
    commit_hash
)


st.write("### DecisionEngine File")

st.code(
    inspect.getfile(
        DecisionEngine
    )
)


st.write("### Decision From MarketState")

st.json(
    decision
)


st.write("### Direct DecisionEngine Result")

st.json(
    direct_decision
)


st.write("### Confidence Comparison")

comparison = {
    "market_state_confidence": decision.get(
        "confidence"
    ),
    "direct_engine_confidence": direct_decision.get(
        "confidence"
    )
}

st.json(
    comparison
)


st.write("### DecisionEngine Source")

try:

    source = inspect.getsource(
        DecisionEngine.decide
    )

    st.code(
        source,
        language="python"
    )

except Exception as error:

    st.error(
        f"Unable to read DecisionEngine source: {error}"
    )
