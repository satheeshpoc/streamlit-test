import streamlit as st
import pandas as pd
import os
import json
from openai import AzureOpenAI

# =========================================================
# 🔐 AZURE OPENAI CONFIG
# =========================================================
AZURE_OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]

MODEL = "merckcto-genaidemo-gpt-4"
API_VERSION = "2024-05-01-preview"

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=API_VERSION
)

# =========================================================
# STREAMLIT CONFIG
# =========================================================
st.set_page_config(
    page_title="AI Innovation Portfolio",
    layout="wide"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(BASE_DIR, "Vibe_codding.xlsx")

# =========================================================
# LOAD DATA
# =========================================================
@st.cache_data
def load_data():
    df = pd.read_excel(EXCEL_FILE, sheet_name="Sheet1")
    df = df.rename(columns=lambda x: x.strip())
    return df

df = load_data()
df = df[["Account Name", "Team Name", "Value Idea", "DU"]].dropna(subset=["Value Idea"])

# =========================================================
# THEME CLASSIFICATION
# =========================================================
def classify_theme(text):
    t = str(text).lower()
    if any(k in t for k in ["compliance", "audit", "regulatory", "sop", "sdtm"]):
        return "Compliance & Regulatory"
    if any(k in t for k in ["incident", "support", "ops", "l1"]):
        return "Operations & Service Excellence"
    if any(k in t for k in ["migration", "databricks", "idmc", "sap"]):
        return "Modernization & Migration"
    if any(k in t for k in ["copilot", "genai", "agent"]):
        return "GenAI Copilots"
    return "Analytics & Intelligence"

df["Theme"] = df["Value Idea"].apply(classify_theme)

# =========================================================
# GPT AUTO‑SCORING
# =========================================================
def gpt_auto_score(idea, chat):
    transcript = "\n".join(
        f"{m['role']}: {m['content']}" for m in chat[-6:]
    )

    prompt = f"""
You are an executive investment committee.

Return ONLY valid JSON:
{{
 "impact":1-5,
 "feasibility":1-5,
 "alignment":1-5,
 "risk":1-5,
 "summary":"short reason"
}}

Idea:
{idea}

Discussion:
{transcript}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=200
    )

    return json.loads(response.choices[0].message.content)

def overall_score(s):
    return round(
        ((s["impact"]*30 + s["feasibility"]*25 + s["alignment"]*30 + (6-s["risk"])*15) / 5),
        1
    )

# =========================================================
# SESSION STATE
# =========================================================
if "idea_scores" not in st.session_state:
    st.session_state.idea_scores = {}

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# =========================================================
# SIDEBAR
# =========================================================
menu = st.sidebar.radio(
    "Navigation",
    ["📊 Executive Dashboard", "💡 Idea Explorer", "🤖 Idea Chatbot"]
)

# =========================================================
# 📊 EXECUTIVE DASHBOARD
# =========================================================
if menu == "📊 Executive Dashboard":
    st.title("Executive Dashboard")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Ideas", len(df))
    c2.metric("Themes", df["Theme"].nunique())
    c3.metric("Delivery Units", df["DU"].nunique())

    st.subheader("Ideas by Delivery Unit")
    st.bar_chart(df["DU"].value_counts())

    st.subheader("Ideas by Theme")
    st.bar_chart(df["Theme"].value_counts())

    if st.session_state.idea_scores:
        st.subheader("📈 Ranked Ideas (Live Scores)")
        ranked = (
            pd.DataFrame.from_dict(st.session_state.idea_scores, orient="index")
            .sort_values("Overall Score", ascending=False)
        )
        st.dataframe(ranked, use_container_width=True)

# =========================================================
# 💡 IDEA EXPLORER
# =========================================================
if menu == "💡 Idea Explorer":
    st.title("Idea Explorer")

    account = st.selectbox("Account", ["All"] + sorted(df["Account Name"].unique()))
    theme = st.selectbox("Theme", ["All"] + sorted(df["Theme"].unique()))

    filt = df.copy()
    if account != "All":
        filt = filt[filt["Account Name"] == account]
    if theme != "All":
        filt = filt[filt["Theme"] == theme]

    st.dataframe(filt, use_container_width=True)

    if not filt.empty:
        st.session_state.selected_team = st.selectbox(
            "Select Idea for Chatbot Review",
            filt["Team Name"]
        )

# =========================================================
# 🤖 IDEA CHATBOT + AUTO SCORE
# =========================================================
if menu == "🤖 Idea Chatbot":

    if "selected_team" not in st.session_state:
        st.warning("Select an idea from Idea Explorer.")
        st.stop()

    idea = df[df["Team Name"] == st.session_state.selected_team].iloc[0]

    st.title("Idea Review Chatbot")
    st.subheader(st.session_state.selected_team)
    st.write(idea["Value Idea"])

    for m in st.session_state.chat_history:
        st.chat_message(m["role"]).write(m["content"])

    user_q = st.chat_input("Ask or comment as Leadership")

    if user_q:
        st.session_state.chat_history.append({"role":"user","content":user_q})

        score = gpt_auto_score(idea["Value Idea"], st.session_state.chat_history)
        overall = overall_score(score)

        st.session_state.idea_scores[st.session_state.selected_team] = {
            "Impact": score["impact"],
            "Feasibility": score["feasibility"],
            "Alignment": score["alignment"],
            "Risk": score["risk"],
            "Overall Score": overall,
            "Summary": score["summary"]
        }

        st.chat_message("assistant").write(score["summary"])

    if st.session_state.selected_team in st.session_state.idea_scores:
        s = st.session_state.idea_scores[st.session_state.selected_team]

        st.markdown("### 📊 Executive Scorecard")
        a,b,c,d = st.columns(4)
        a.metric("Impact", s["Impact"])
        b.metric("Feasibility", s["Feasibility"])
        c.metric("Alignment", s["Alignment"])
        d.metric("Risk", s["Risk"])

        st.metric("Overall Score", f"{s['Overall Score']} / 100")
