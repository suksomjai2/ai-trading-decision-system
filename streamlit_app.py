import streamlit as st
import core.market_state
st.write(core.market_state.__file__)
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
st.write("FULL MARKET STATE:")
st.write(market_state)


# =========================
# Convert Market State
# =========================

if isinstance(market_state, dict):

    state_value = (
        market_state.get("state")
        or market_state.get("market_state")
        or "UNKNOWN"
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
# DEBUG
# =========================

st.write("===== DEBUG =====")

st.write("RAW MARKET STATE:")
st.write(market_state)

st.write("STATE VALUE:")
st.write(state_value)

st.write("FEATURES:")
st.write(features)

st.write("DECISION:")
st.write(decision)

st.write("=================")



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
# Detail
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
