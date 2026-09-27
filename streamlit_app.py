import streamlit as st

from core.market_state import MarketState
from core.feature_engine import FeatureEngine
from core.decision_engine import DecisionEngine
from core.risk_engine import RiskEngine


# Page Config

st.set_page_config(
    page_title="AI Trading Decision System",
    layout="wide"
)


# Title

st.title("🧠 AI Trading Decision System")
st.subheader("XAUUSD AI Analysis Dashboard")


# Initialize Engines

market_engine = MarketState()
feature_engine = FeatureEngine()
decision_engine = DecisionEngine()
risk_engine = RiskEngine()


# Sample Market Data

market_data = {

    "open": 2650,
    "high": 2665,
    "low": 2645,
    "close": 2660,
    "volume": 1200000

}


# =========================
# Feature Extraction
# =========================

features = feature_engine.calculate_features(
    market_data
)


# =========================
# Market State
# =========================

market_state = market_engine.analyze(
    market_data
)


# Convert Market State

if isinstance(market_state, dict):

    state_value = market_state.get(
        "state",
        "UNKNOWN"
    )

else:

    state_value = market_state



# =========================
# Decision Engine
# =========================

decision = decision_engine.decide(
    state_value,
    features
)



# =========================
# Risk Engine
# =========================

risk = risk_engine.evaluate(
    decision,
    features
)



# =========================
# Dashboard
# =========================

col1, col2, col3 = st.columns(3)



# Market State

with col1:

    st.metric(
        "Market State",
        state_value
    )



# Decision

with col2:

    if isinstance(decision, dict):

        st.metric(
            "Decision",
            decision.get(
                "action",
                "HOLD"
            )
        )

    else:

        st.metric(
            "Decision",
            decision
        )



# Risk

with col3:

    if isinstance(risk, dict):

        st.metric(
            "Risk Level",
            risk.get(
                "risk_level",
                risk.get(
                    "level",
                    "UNKNOWN"
                )
            )
        )

    else:

        st.metric(
            "Risk Level",
            risk
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
