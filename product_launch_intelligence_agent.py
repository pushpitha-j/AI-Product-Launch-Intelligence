"""
AI Product Launch Intelligence Agent — Streamlit app.

Run with:
    streamlit run product_launch_intelligence_agent.py
"""

import os
import re
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from agents import (
    PROVIDERS,
    WORKFLOWS,
    Config,
    run_full_brief,
    run_workflow,
    export_markdown,
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Product Launch Intelligence Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv()


def _secret(name: str, default: str = "") -> str:
    """Read a value from Streamlit secrets (for cloud deploys), then the env."""
    try:
        value = st.secrets.get(name)  # raises if no secrets file exists
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "report"


TAB_META = {
    "competitor": {
        "icon": "🔍",
        "button": "Analyze Competitor Positioning",
        "about": """
**Product Launch Analyst** – strategic GTM expert

- Market & product positioning
- Launch strengths and weaknesses, with evidence
- Strategic takeaways for competing teams
""",
    },
    "sentiment": {
        "icon": "💬",
        "button": "Analyze Customer Perception",
        "about": """
**Market Sentiment Specialist** – consumer perception expert

- Positive and negative sentiment drivers
- Sentiment by channel (reviews, Reddit, X, press)
- Overall sentiment verdict
""",
    },
    "metrics": {
        "icon": "📈",
        "button": "Analyze Launch Performance",
        "about": """
**Launch Metrics Specialist** – performance analytics expert

- Publicly available adoption, engagement and traction KPIs
- Press and social buzz signals
- Launch performance scorecard
""",
    },
}


# ============================================================
# SESSION STATE
# ============================================================

if "results" not in st.session_state:
    st.session_state.results = {}
if "subject_key" not in st.session_state:
    st.session_state.subject_key = ""


# ============================================================
# SIDEBAR – CONFIGURATION
# ============================================================

KEY_INFO = {
    "openai": ("OpenAI API Key", "OPENAI_API_KEY", "OPENAI_MODEL", "Get one at platform.openai.com (needs credit)."),
    "gemini": ("Google Gemini API Key", "GOOGLE_API_KEY", "GEMINI_MODEL", "Free key from aistudio.google.com."),
}

with st.sidebar:
    st.header("🔑 API Configuration")

    # Default to Gemini when only a Google key is configured.
    env_provider = _secret("LLM_PROVIDER").lower()
    if env_provider not in PROVIDERS:
        env_provider = "gemini" if _secret("GOOGLE_API_KEY") and not _secret("OPENAI_API_KEY") else "openai"
    provider_ids = list(PROVIDERS)
    provider = st.radio(
        "LLM provider",
        provider_ids,
        index=provider_ids.index(env_provider),
        format_func=lambda p: PROVIDERS[p][0],
    )
    key_label, key_env, model_env, key_help = KEY_INFO[provider]

    llm_key = st.text_input(
        key_label,
        type="password",
        value=_secret(key_env),
        help=f"Used by every agent. {key_help}",
        key=f"key_{provider}",
    )
    firecrawl_key = st.text_input(
        "Firecrawl API Key",
        type="password",
        value=_secret("FIRECRAWL_API_KEY"),
        help="Used for web search and page scraping. Free plan at firecrawl.dev.",
    )

    model_options = list(PROVIDERS[provider][2]) + ["Custom…"]
    env_model = _secret(model_env)
    if env_model and env_model not in model_options:
        model_options.insert(0, env_model)
    model_choice = st.selectbox(
        "Model",
        model_options,
        index=model_options.index(env_model) if env_model in model_options else 0,
        help="Any chat model from this provider that supports tool calling.",
        key=f"model_{provider}",
    )
    if model_choice == "Custom…":
        model_id = st.text_input("Custom model ID", value="", key=f"custom_{provider}").strip()
    else:
        model_id = model_choice

    with st.expander("Advanced"):
        search_limit = st.slider("Search results per query", 3, 10, 5)
        debug = st.checkbox(
            "Print agent debug logs to the terminal",
            value=False,
        )

ready = bool(llm_key and firecrawl_key and model_id)
cfg = Config(
    llm_api_key=llm_key,
    firecrawl_api_key=firecrawl_key,
    provider=provider,
    model_id=model_id or PROVIDERS[provider][1],
    debug=debug,
    search_limit=search_limit,
)


# ============================================================
# HEADER & INPUT
# ============================================================

st.title("🚀 AI Product Launch Intelligence Agent")
st.markdown("*AI-powered launch research for GTM, Product Marketing & Growth teams*")

if not ready:
    st.warning(
        f"⚠️ Enter your {PROVIDERS[provider][0].split(' (')[0]} and Firecrawl API keys "
        "in the sidebar to start."
    )

col_company, col_focus = st.columns([3, 2])
with col_company:
    company_name = st.text_input(
        "Company or product",
        placeholder="e.g. OpenAI, Notion, Spotify",
    ).strip()
with col_focus:
    launch_focus = st.text_input(
        "Specific launch (optional)",
        placeholder="e.g. Sora app, Notion Mail",
        help="Narrow the research to one launch. Leave blank for the latest launches.",
    ).strip()

# Results belong to one subject: clear them when the subject changes.
subject_key = f"{company_name.lower()}|{launch_focus.lower()}"
if subject_key != st.session_state.subject_key:
    st.session_state.subject_key = subject_key
    st.session_state.results = {}

st.divider()


# ============================================================
# RESULT RENDERING
# ============================================================

def render_result(key: str) -> None:
    result = st.session_state.results.get(key)
    if not result:
        return

    st.divider()
    st.markdown(result.report)

    if result.findings:
        with st.expander("🔎 Raw research findings from the agent"):
            st.markdown(result.findings)

    meta_col, dl_col = st.columns([3, 1])
    with meta_col:
        st.caption(
            f"Generated in {result.seconds:.0f}s with `{result.model_id}` · "
            f"{datetime.now():%d %b %Y}"
        )
    with dl_col:
        st.download_button(
            "⬇️ Download report (.md)",
            data=result.report,
            file_name=f"{_slug(result.subject)}-{key}.md",
            mime="text/markdown",
            key=f"dl_{key}",
            width="stretch",
        )


def run_and_store(key: str, label: str, runner) -> None:
    with st.status(f"{label} in progress…", expanded=True) as status:
        try:
            result = runner(lambda msg: status.write(msg))
        except Exception as exc:  # noqa: BLE001 – show any failure to the user
            status.update(label=f"{label} failed", state="error")
            st.error(f"❌ {exc}")
            msg = str(exc).lower()
            if cfg.provider == "gemini" and ("503" in msg or "unavailable" in msg or "high demand" in msg):
                st.info(
                    "Google's free Gemini models are overloaded right now. Wait a few "
                    "minutes and try again, or pick another model in the sidebar."
                )
            elif cfg.provider == "gemini" and ("429" in msg or "resource_exhausted" in msg or "quota" in msg):
                st.info(
                    "Gemini's free tier allows only a few requests per minute. "
                    "Wait a minute and try again, or run one tab at a time."
                )
            elif "insufficient_quota" in msg or "quota" in msg:
                st.info(
                    "Your OpenAI account has no credit. Add credit on platform.openai.com, "
                    "or switch the sidebar to Google Gemini (free tier)."
                )
            else:
                st.info(
                    "Check that both API keys are valid, that your account has access "
                    "to the selected model, and that you have Firecrawl credits."
                )
            return
        st.session_state.results[key] = result
        status.update(label=f"{label} complete", state="complete", expanded=False)


# ============================================================
# ANALYSIS TABS
# ============================================================

tab_labels = [f"{TAB_META[k]['icon']} {WORKFLOWS[k].title}" for k in WORKFLOWS]
tab_labels.append("🧠 Full Launch Brief")
tabs = st.tabs(tab_labels)

for tab, key in zip(tabs, WORKFLOWS):
    wf = WORKFLOWS[key]
    meta = TAB_META[key]
    with tab:
        st.markdown(f"### {meta['icon']} {wf.title}")
        with st.expander("ℹ️ About this workflow"):
            st.markdown(meta["about"])
            st.markdown(
                "**How it runs:** the specialist agent searches and scrapes the "
                "public web with Firecrawl, then the Report Writer turns its "
                "evidence into the structured report below."
            )

        if not company_name:
            st.info("👆 Enter a company or product above to start.")
            continue

        clicked = st.button(
            f"{meta['icon']} {meta['button']}",
            key=f"btn_{key}",
            type="primary",
            disabled=not ready,
            width="stretch",
        )
        if clicked:
            run_and_store(
                key,
                wf.title,
                lambda step, k=key: run_workflow(k, company_name, launch_focus, cfg, step),
            )
        render_result(key)


with tabs[-1]:
    st.markdown("### 🧠 Full Launch Brief")
    with st.expander("ℹ️ About this workflow"):
        st.markdown(
            "The **Product Intelligence Team** leader delegates to all three "
            "specialists, then synthesises their findings into one executive "
            "brief with a launch scorecard. This makes more API calls than a "
            "single tab, so it takes longer."
        )

    if not company_name:
        st.info("👆 Enter a company or product above to start.")
    else:
        if st.button(
            "🧠 Generate Full Launch Brief",
            key="btn_brief",
            type="primary",
            disabled=not ready,
            width="stretch",
        ):
            run_and_store(
                "brief",
                "Full launch brief",
                lambda step: run_full_brief(company_name, launch_focus, cfg, step),
            )
        render_result("brief")


# ============================================================
# SIDEBAR – STATUS (rendered last so it reflects this run)
# ============================================================

with st.sidebar:
    st.divider()
    st.markdown("### 🤖 System Status")
    if ready:
        st.success(f"Product Intelligence Team ready · `{cfg.model_id}`")
        if cfg.provider == "gemini":
            st.caption("Free tier: run one workflow at a time to stay within rate limits.")
    else:
        st.error("API keys required")

    st.markdown("### 🎯 Coordinated Team")
    for key, wf in WORKFLOWS.items():
        st.markdown(f"**{TAB_META[key]['icon']} {wf.agent_name}**")
        st.caption(wf.agent_role)
    st.markdown("**📝 Report Writer**")
    st.caption("Turns research evidence into structured reports")

    if company_name:
        st.divider()
        st.markdown("### 📊 Analysis Status")
        st.markdown(f"**Subject:** {company_name}" + (f" – {launch_focus}" if launch_focus else ""))
        all_keys = list(WORKFLOWS) + ["brief"]
        names = {**{k: WORKFLOWS[k].title for k in WORKFLOWS}, "brief": "Full Launch Brief"}
        for key in all_keys:
            done = key in st.session_state.results
            st.markdown(f"{'✅' if done else '⏳'} {names[key]}")

        finished = [st.session_state.results[k] for k in all_keys if k in st.session_state.results]
        if finished:
            st.download_button(
                "⬇️ Download all reports",
                data=export_markdown(finished),
                file_name=f"{_slug(company_name)}-launch-intelligence.md",
                mime="text/markdown",
                width="stretch",
            )
