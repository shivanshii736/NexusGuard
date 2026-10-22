"""PERSON 3. Streamlit entry point:  streamlit run app.py
Two tabs: Planning Mode (baseline gaps + pre-positioning) and Live Mode (drop incidents / replay)."""
import streamlit as st
from tests.toy_graph import make_toy

st.set_page_config(page_title="NexusGuard", layout="wide")
st.title("NexusGuard: one engine, multiple hazards")
st.caption("Traffic multipliers are ASSUMPTIONS; hospitals are PROXIES for non-public vehicle bases.")

G, assets, zones = make_toy()   # swap for the real loaders once Person 1 lands them
plan, live = st.tabs(["Planning Mode", "Live Mode"])
with plan:
    st.info("TODO(P3): baseline coverage by ward + 'recommend pre-positioning' button")
with live:
    st.info("TODO(P3): incident drop / scenario replay, alerts, before-vs-after")
