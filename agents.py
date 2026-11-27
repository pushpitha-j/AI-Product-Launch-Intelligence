"""
Agent layer for the AI Product Launch Intelligence Agent.

Three specialist research agents (each with Firecrawl web search + scraping),
one tool-less report writer, and a coordinated team that combines the three
specialists into a single launch brief.

Every research workflow runs in two steps:
    1. A specialist agent researches the public web and returns tagged,
       source-linked evidence bullets.
    2. The report writer turns that evidence into a structured Markdown report.

This module has no Streamlit dependency so it can be tested on its own.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from textwrap import dedent
from typing import Callable, Dict, List, Optional

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.team import Team
from agno.tools.firecrawl import FirecrawlTools


# Supported LLM providers: id -> (label, default model, model choices)
PROVIDERS = {
    "openai": ("OpenAI", "gpt-5.4-mini", ["gpt-5.4-mini", "gpt-4.1-mini", "gpt-4o"]),
    # Lite first: it is the least likely to be overloaded on the free tier.
    "gemini": (
        "Google Gemini (free tier)",
        "gemini-flash-lite-latest",
        ["gemini-flash-lite-latest", "gemini-flash-latest", "gemini-3.7-flash"],
    ),
}
DEFAULT_MODEL = PROVIDERS["openai"][1]

SOURCES_RULE = (
    "End with a '## Sources' section listing every URL you searched or "
    "scraped as a Markdown bullet list. Never invent URLs or numbers; if a "
    "data point is not publicly available, say so explicitly."
)

RESEARCH_RULES = [
    "Use the search tool first, then scrape at most 3 of the most relevant pages.",
    "Prefer primary sources (company blog, press releases, docs) and reputable "
    "press, review sites and community forums over SEO content.",
    "Focus on the most recent launches relative to today's date.",
    SOURCES_RULE,
]


# ============================================================
# WORKFLOW DEFINITIONS
# ============================================================

@dataclass(frozen=True)
class Workflow:
    key: str
    title: str
    agent_name: str
    agent_role: str
    research_prompt: Callable[[str, str], str]
    report_prompt: Callable[[str, str, str], str]


def _subject(company: str, focus: str) -> str:
    focus = (focus or "").strip()
    return f"{company} ({focus})" if focus else company


def _competitor_research(company: str, focus: str) -> str:
    return dedent(f"""
        Research the most recent product launch(es) of **{_subject(company, focus)}**.

        Return up to 16 evidence-based insight bullets. Start every bullet with
        exactly one tag in square brackets: [Positioning], [Strength],
        [Weakness] or [Learning]. Follow the tag with a concise statement
        (max 30 words) grounded in observable signals: messaging,
        differentiation, pricing, channel mix, timing, engagement or customer
        feedback. Add the supporting source URL in parentheses at the end of
        each bullet.
    """).strip()


def _competitor_report(company: str, focus: str, findings: str) -> str:
    subject = _subject(company, focus)
    return dedent(f"""
        Transform the research findings below into a professional launch review
        for product managers analysing **{subject}**.

        Use exactly this Markdown structure:

        # {subject} – Competitor Launch Review

        ## 1. Market & Product Positioning
        Up to 6 bullets on how the product is positioned and for whom.

        ## 2. Launch Strengths
        | Strength | Evidence / Rationale |
        |---|---|
        (4–6 rows)

        ## 3. Launch Weaknesses
        | Weakness | Evidence / Rationale |
        |---|---|
        (4–6 rows)

        ## 4. Strategic Takeaways for Competitors
        Up to 5 numbered, actionable recommendations.

        ## Sources
        Every URL from the findings as a bullet list.

        === RESEARCH FINDINGS ===
        {findings}
    """).strip()


def _sentiment_research(company: str, focus: str) -> str:
    return dedent(f"""
        Research how customers and the market perceive **{_subject(company, focus)}**
        and its recent launches.

        Look at review sites (e.g. G2, Capterra, Trustpilot, app stores), Reddit,
        X/Twitter, Hacker News, YouTube comments and press coverage.

        Return up to 12 bullets. Start every bullet with exactly one tag:
        [Positive], [Negative] or [Neutral]. Each bullet states one theme
        (max 30 words), names the platform it came from, and ends with the
        source URL in parentheses.
    """).strip()


def _sentiment_report(company: str, focus: str, findings: str) -> str:
    subject = _subject(company, focus)
    return dedent(f"""
        Use the tagged research findings below to create a concise
        customer-perception brief for **{subject}**.

        Use exactly this Markdown structure:

        # {subject} – Market Sentiment Brief

        **Overall sentiment:** one of Positive / Mixed / Negative, with a
        one-line justification.

        ## Positive Sentiment Drivers
        Up to 6 bullets, each naming the platform.

        ## Negative Sentiment Drivers
        Up to 6 bullets, each naming the platform.

        ## Sentiment by Channel
        | Channel | Tone | Key theme |
        |---|---|---|

        ## Overall Summary
        One paragraph (≤120 words) on the balance of sentiment and its key drivers.

        ## Sources
        Every URL from the findings as a bullet list.

        === RESEARCH FINDINGS ===
        {findings}
    """).strip()


def _metrics_research(company: str, focus: str) -> str:
    return dedent(f"""
        Find the most important publicly available KPIs and performance signals
        for **{_subject(company, focus)}**'s recent product launch(es).

        Cover user adoption, engagement, revenue or pricing signals, growth,
        press coverage, social traction, app-store rankings and market share
        where available.

        Return up to 12 bullets. Each bullet: metric name, the value or detail,
        the date it refers to, and the source URL in parentheses. Mark
        estimates as estimates. If a metric is not publicly available, say so
        rather than guessing.
    """).strip()


def _metrics_report(company: str, focus: str, findings: str) -> str:
    subject = _subject(company, focus)
    return dedent(f"""
        Convert the KPI findings below into a launch-performance snapshot for
        **{subject}** suitable for an executive dashboard.

        Use exactly this Markdown structure:

        # {subject} – Launch Performance Snapshot

        ## Key Performance Indicators
        | Metric | Value / Detail | Date | Source |
        |---|---|---|---|
        (one row per KPI that has data)

        ## Qualitative Signals
        Up to 5 bullets.

        ## Launch Performance Scorecard
        | Dimension | Rating (Strong / Moderate / Weak / Unknown) | Why |
        |---|---|---|
        Rows: Adoption, Engagement, Press & Buzz, Monetisation.

        ## Summary & Implications
        One paragraph (≤120 words) on what the signals imply about launch
        success and next steps.

        ## Sources
        Every URL from the findings as a bullet list.

        === KPI FINDINGS ===
        {findings}
    """).strip()


WORKFLOWS: Dict[str, Workflow] = {
    "competitor": Workflow(
        key="competitor",
        title="Competitor Positioning",
        agent_name="Product Launch Analyst",
        agent_role="Evaluates competitor positioning, launch tactics, strengths and weaknesses",
        research_prompt=_competitor_research,
        report_prompt=_competitor_report,
    ),
    "sentiment": Workflow(
        key="sentiment",
        title="Customer Perception",
        agent_name="Market Sentiment Specialist",
        agent_role="Analyses customer and market sentiment from reviews, social and forums",
        research_prompt=_sentiment_research,
        report_prompt=_sentiment_report,
    ),
    "metrics": Workflow(
        key="metrics",
        title="Launch Performance",
        agent_name="Launch Metrics Specialist",
        agent_role="Tracks public launch KPIs: adoption, engagement, press and traction",
        research_prompt=_metrics_research,
        report_prompt=_metrics_report,
    ),
}


AGENT_DESCRIPTIONS = {
    "competitor": dedent("""
        You are a senior Go-To-Market strategist who evaluates competitor
        product launches with a critical, evidence-driven lens. You uncover how
        a product is positioned, which launch tactics worked, where execution
        fell short, and what competitors can learn. Always cite observable
        signals: messaging, pricing, channel mix, timing, engagement metrics
        and customer feedback.
    """).strip(),
    "sentiment": dedent("""
        You are a market research expert specialising in sentiment analysis and
        consumer perception. You extract positive and negative sentiment
        drivers from social platforms, review sites, forums and press, and you
        always say where each signal came from.
    """).strip(),
    "metrics": dedent("""
        You are a product launch performance analyst. You track launch KPIs
        such as adoption, engagement, revenue signals, growth, press coverage
        and social traction. You give quantitative insights with dates and
        context, and you never fabricate numbers.
    """).strip(),
}


# ============================================================
# CONFIG & FACTORIES
# ============================================================

@dataclass
class Config:
    llm_api_key: str
    firecrawl_api_key: str
    provider: str = "openai"  # "openai" or "gemini"
    model_id: str = DEFAULT_MODEL
    debug: bool = False
    search_limit: int = 5
    max_tool_calls: int = 8

    @property
    def retry_delay(self) -> int:
        # Gemini's free tier has tight per-minute limits, so back off longer.
        return 6 if self.provider == "gemini" else 2


def _model(cfg: Config, model_id: Optional[str] = None):
    model_id = model_id or cfg.model_id
    if cfg.provider == "gemini":
        # Imported lazily so the OpenAI path works without google-genai.
        from agno.models.google import Gemini

        return Gemini(id=model_id, api_key=cfg.llm_api_key)
    return OpenAIChat(id=model_id, api_key=cfg.llm_api_key)


def _fallbacks(cfg: Config) -> Optional[list]:
    """Other free Gemini models to try when the chosen one is overloaded (503/429).

    OpenAI gets no automatic fallback so the user never pays for a model
    they did not pick.
    """
    if cfg.provider != "gemini":
        return None
    others = [m for m in PROVIDERS["gemini"][2] if m != cfg.model_id]
    return [_model(cfg, m) for m in others] or None


def build_research_agent(workflow_key: str, cfg: Config) -> Agent:
    wf = WORKFLOWS[workflow_key]
    return Agent(
        name=wf.agent_name,
        role=wf.agent_role,
        model=_model(cfg),
        fallback_models=_fallbacks(cfg),
        description=AGENT_DESCRIPTIONS[workflow_key],
        instructions=RESEARCH_RULES,
        tools=[
            FirecrawlTools(
                api_key=cfg.firecrawl_api_key,
                enable_search=True,
                enable_scrape=True,
                enable_crawl=False,  # full-site crawls are slow and costly
                limit=cfg.search_limit,
            )
        ],
        tool_call_limit=cfg.max_tool_calls,
        add_datetime_to_context=True,
        markdown=True,
        retries=3,
        delay_between_retries=cfg.retry_delay,
        exponential_backoff=True,
        debug_mode=cfg.debug,
    )


def build_report_writer(cfg: Config) -> Agent:
    return Agent(
        name="Report Writer",
        model=_model(cfg),
        fallback_models=_fallbacks(cfg),
        description=(
            "You turn raw research findings into clear, structured Markdown "
            "reports for product managers."
        ),
        instructions=[
            "Follow the requested Markdown structure exactly.",
            "Use only facts present in the findings; do not add new claims, "
            "numbers or URLs.",
            "Omit table rows that would have no meaningful data.",
            "Keep it scannable: tables and short bullets, no long paragraphs.",
        ],
        markdown=True,
        retries=3,
        delay_between_retries=cfg.retry_delay,
        exponential_backoff=True,
        debug_mode=cfg.debug,
    )


def build_team(cfg: Config) -> Team:
    return Team(
        name="Product Intelligence Team",
        model=_model(cfg),
        fallback_models=_fallbacks(cfg),
        members=[build_research_agent(k, cfg) for k in WORKFLOWS],
        instructions=[
            "You coordinate three specialists to produce one launch brief.",
            "Delegate to ALL three members: the Product Launch Analyst for "
            "positioning, the Market Sentiment Specialist for customer "
            "perception, and the Launch Metrics Specialist for KPIs.",
            "Then synthesise their findings yourself. Do not invent facts that "
            "the members did not report.",
            SOURCES_RULE,
        ],
        add_datetime_to_context=True,
        markdown=True,
        retries=2,
        delay_between_retries=cfg.retry_delay,
        exponential_backoff=True,
        show_members_responses=False,
        debug_mode=cfg.debug,
    )


# ============================================================
# EXECUTION
# ============================================================

class AgentRunError(RuntimeError):
    """Raised when an agent or team run finishes in an error state."""


def _content(resp) -> str:
    """Extract text from an Agno run output and raise if the run failed.

    Agno catches most model/tool exceptions and returns them as the run's
    content with status ERROR, so the status has to be checked explicitly.
    """
    status = getattr(resp, "status", None)
    status = str(getattr(status, "value", status) or "").upper()
    content = getattr(resp, "content", resp)
    text = "" if content is None else str(content).strip()
    if status == "ERROR":
        raise AgentRunError(text or "The agent run failed without a message.")
    if status in {"PAUSED", "CANCELLED"}:
        raise AgentRunError(f"The agent run ended early (status: {status}).")
    if not text:
        raise AgentRunError("The agent returned an empty response.")
    return text


@dataclass
class WorkflowResult:
    workflow: str
    subject: str
    findings: str
    report: str
    seconds: float
    model_id: str = ""


def run_workflow(
    workflow_key: str,
    company: str,
    focus: str,
    cfg: Config,
    on_step: Optional[Callable[[str], None]] = None,
) -> WorkflowResult:
    """Run one specialised workflow: web research, then structured report."""
    wf = WORKFLOWS[workflow_key]
    step = on_step or (lambda _msg: None)
    start = time.time()

    step(f"{wf.agent_name} is researching the web…")
    researcher = build_research_agent(workflow_key, cfg)
    findings = _content(researcher.run(wf.research_prompt(company, focus)))

    step("Report Writer is structuring the findings…")
    writer = build_report_writer(cfg)
    report = _content(writer.run(wf.report_prompt(company, focus, findings)))

    return WorkflowResult(
        workflow=workflow_key,
        subject=_subject(company, focus),
        findings=findings,
        report=report,
        seconds=time.time() - start,
        model_id=cfg.model_id,
    )


def full_brief_prompt(company: str, focus: str) -> str:
    subject = _subject(company, focus)
    return dedent(f"""
        Produce a go-to-market launch intelligence brief for **{subject}**.

        Use exactly this Markdown structure:

        # {subject} – Launch Intelligence Brief

        ## Executive Summary
        3–5 bullets.

        ## Competitor Positioning
        Positioning, top strengths and weaknesses (from the Product Launch Analyst).

        ## Customer Perception
        Overall sentiment plus the main positive and negative drivers
        (from the Market Sentiment Specialist).

        ## Launch Performance
        | Metric | Value / Detail | Source |
        |---|---|---|
        (from the Launch Metrics Specialist)

        ## Launch Scorecard
        | Dimension | Rating (Strong / Moderate / Weak / Unknown) | Why |
        |---|---|---|
        Rows: Positioning, Customer Perception, Adoption, Press & Buzz.

        ## Recommendations
        Up to 5 numbered, actionable recommendations for a competing product team.

        ## Sources
    """).strip()


def run_full_brief(
    company: str,
    focus: str,
    cfg: Config,
    on_step: Optional[Callable[[str], None]] = None,
) -> WorkflowResult:
    """Run the coordinated team across all three specialists."""
    step = on_step or (lambda _msg: None)
    start = time.time()
    step("Team leader is delegating to all three specialists…")
    team = build_team(cfg)
    report = _content(team.run(full_brief_prompt(company, focus)))
    return WorkflowResult(
        workflow="brief",
        subject=_subject(company, focus),
        findings="",
        report=report,
        seconds=time.time() - start,
        model_id=cfg.model_id,
    )


def export_markdown(results: List[WorkflowResult]) -> str:
    """Combine finished reports into one downloadable Markdown document."""
    parts = []
    for r in results:
        parts.append(r.report.strip())
    return "\n\n---\n\n".join(parts) + "\n"
