import streamlit as st
import core.market_state
import inspect

st.write("PATH:")
st.write(core.market_state.__file__)

st.write("SOURCE:")
st.code(inspect.getsource(core.market_state.MarketState.analyze))
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
# TEST MARKET STATE
# =========================

# =========================
# Market State TEST
# =========================

market_state = MarketState().analyze(
    market_data
)
st.write("TYPE")
st.write(type(market_state))

st.write("RAW")
st.write(market_state)



# =========================
# Feature
# =========================

features = feature_engine.calculate_features(
    market_data
)



# =========================
# Convert State
# =========================

state_value = market_state["state"]



# =========================
# Decision
# =========================

decision = decision_engine.decide(
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
        "Market State",
        state_value
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

    st.metric(
        "Risk Level",
        risk.get(
            "risk_level",
            "UNKNOWN"
        )
    )



st.divider()


st.write("### Market Features")
st.json(features)


st.write("### Decision Detail")
st.json(decision)


st.write("### Risk Detail")
st.json(risk)
