import streamlit as st
from agno.agent import Agent
from agno.run.agent import RunOutput
from agno.team import Team
from agno.models.openai import OpenAIChat
from agno.tools.firecrawl import FirecrawlTools
from dotenv import load_dotenv
from textwrap import dedent
import os


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Product Intelligence Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# ENVIRONMENT & API CONFIGURATION
# ============================================================

load_dotenv()

st.sidebar.header("🔑 API Configuration")

with st.sidebar.container():

    openai_key = st.text_input(
        "OpenAI API Key",
        type="password",
        value=os.getenv("OPENAI_API_KEY", ""),
        help="Required for AI agent functionality"
    )

    firecrawl_key = st.text_input(
        "Firecrawl API Key",
        type="password",
        value=os.getenv("FIRECRAWL_API_KEY", ""),
        help="Required for web search and crawling"
    )


# Set environment variables
if openai_key:
    os.environ["OPENAI_API_KEY"] = openai_key

if firecrawl_key:
    os.environ["FIRECRAWL_API_KEY"] = firecrawl_key


# ============================================================
# MULTI-AGENT SYSTEM
# ============================================================

if openai_key and firecrawl_key:

    # --------------------------------------------------------
    # AGENT 1: PRODUCT LAUNCH ANALYST
    # --------------------------------------------------------

    launch_analyst = Agent(
        name="Product Launch Analyst",

        description=dedent("""
            You are a senior Go-To-Market strategist who evaluates
            competitor product launches with a critical,
            evidence-driven lens.

            Your objective is to uncover:

            • How the product is positioned in the market
            • Which launch tactics drove success
            • Where execution fell short
            • Actionable learnings competitors can leverage

            Always cite observable signals such as:

            • Messaging
            • Pricing actions
            • Channel mix
            • Timing
            • Engagement metrics
            • Customer feedback

            Maintain a crisp, executive tone and focus on strategic value.

            IMPORTANT:
            Conclude your report with a "Sources:" section,
            listing all URLs of websites you crawled or searched
            for this analysis.
        """),

        model=OpenAIChat(id="gpt-4o"),

        tools=[
            FirecrawlTools(
                enable_search=True,
                enable_crawl=True,
                poll_interval=10
            )
        ],

        debug_mode=True,
        markdown=True,
        exponential_backoff=True,
        delay_between_retries=2,
    )


    # --------------------------------------------------------
    # AGENT 2: MARKET SENTIMENT SPECIALIST
    # --------------------------------------------------------

    sentiment_analyst = Agent(
        name="Market Sentiment Specialist",

        description=dedent("""
            You are a market research expert specializing in
            sentiment analysis and consumer perception tracking.

            Your expertise includes:

            • Analyzing social media sentiment
            • Analyzing customer feedback
            • Identifying positive and negative sentiment drivers
            • Tracking brand perception trends
            • Monitoring customer satisfaction
            • Identifying review patterns
            • Providing actionable insights on market reception

            Focus on extracting sentiment signals from:

            • Social platforms
            • Review sites
            • Forums
            • Customer feedback channels

            IMPORTANT:
            Conclude your report with a "Sources:" section,
            listing all URLs of websites you crawled or searched
            for this analysis.
        """),

        model=OpenAIChat(id="gpt-4o"),

        tools=[
            FirecrawlTools(
                enable_search=True,
                enable_crawl=True,
                poll_interval=10
            )
        ],

        debug_mode=True,
        markdown=True,
        exponential_backoff=True,
        delay_between_retries=2,
    )


    # --------------------------------------------------------
    # AGENT 3: LAUNCH METRICS SPECIALIST
    # --------------------------------------------------------

    metrics_analyst = Agent(
        name="Launch Metrics Specialist",

        description=dedent("""
            You are a product launch performance analyst who
            specializes in tracking and analyzing launch KPIs.

            Your focus areas include:

            • User adoption
            • User engagement
            • Revenue performance
            • Market penetration
            • Growth rates
            • Press coverage
            • Media attention
            • Social media traction
            • Viral coefficient
            • Competitive market share

            Always provide quantitative insights with context.

            Benchmark against industry standards when possible.

            IMPORTANT:
            Conclude your report with a "Sources:" section,
            listing all URLs of websites you crawled or searched
            for this analysis.
        """),

        model=OpenAIChat(id="gpt-4o"),

        tools=[
            FirecrawlTools(
                enable_search=True,
                enable_crawl=True,
                poll_interval=10
            )
        ],

        debug_mode=True,
        markdown=True,
        exponential_backoff=True,
        delay_between_retries=2,
    )


    # --------------------------------------------------------
    # COORDINATED PRODUCT INTELLIGENCE TEAM
    # --------------------------------------------------------

    product_intelligence_team = Team(

        name="Product Intelligence Team",

        model=OpenAIChat(id="gpt-4o"),

        members=[
            launch_analyst,
            sentiment_analyst,
            metrics_analyst
        ],

        instructions=[

            "Coordinate the analysis based on the user's request type.",

            "1. For competitor analysis: "
            "Use the Product Launch Analyst to evaluate "
            "positioning, strengths, weaknesses, and strategic insights.",

            "2. For market sentiment: "
            "Use the Market Sentiment Specialist to analyze "
            "social media sentiment, customer feedback, and brand perception.",

            "3. For launch metrics: "
            "Use the Launch Metrics Specialist to track "
            "KPIs, adoption rates, press coverage, and performance indicators.",

            "Always provide evidence-based insights with specific examples and data points.",

            "Structure responses with clear sections and actionable recommendations.",

            "Include a Sources section with all URLs crawled or searched."
        ],

        markdown=True,
        debug_mode=True,
        show_members_responses=True,
    )

else:

    product_intelligence_team = None

    st.warning(
        "⚠️ Please enter both API keys in the sidebar "
        "to use the application."
    )


# ============================================================
# COMPETITOR REPORT GENERATOR
# ============================================================

def expand_competitor_report(
    bullet_text: str,
    competitor: str
) -> str:

    if not product_intelligence_team:

        st.error(
            "⚠️ Please enter both API keys in the sidebar first."
        )

        return ""

    prompt = (

        f"Transform the insight bullets below into a "
        f"professional launch review for product managers "
        f"analysing {competitor}.\n\n"

        f"Produce well-structured **Markdown** with a mix "
        f"of tables, call-outs and concise bullet points. "
        f"Avoid long paragraphs.\n\n"

        f"=== FORMAT SPECIFICATION ===\n"

        f"# {competitor} – Launch Review\n\n"

        f"## 1. Market & Product Positioning\n"

        f"• Bullet point summary of how the product is positioned "
        f"(max 6 bullets).\n\n"

        f"## 2. Launch Strengths\n"

        f"| Strength | Evidence / Rationale |\n"
        f"|---|---|\n"
        f"| … | … |\n"
        f"(add 4-6 rows)\n\n"

        f"## 3. Launch Weaknesses\n"

        f"| Weakness | Evidence / Rationale |\n"
        f"|---|---|\n"
        f"| … | … |\n"
        f"(add 4-6 rows)\n\n"

        f"## 4. Strategic Takeaways for Competitors\n"

        f"1. … (max 5 numbered recommendations)\n\n"

        f"=== SOURCE BULLETS ===\n"
        f"{bullet_text}\n\n"

        f"Guidelines:\n"

        f"• Populate the tables with specific points "
        f"derived from the bullets.\n"

        f"• Only include rows that contain meaningful data; "
        f"omit blank entries."
    )

    resp: RunOutput = product_intelligence_team.run(prompt)

    return (
        resp.content
        if hasattr(resp, "content")
        else str(resp)
    )


# ============================================================
# MARKET SENTIMENT REPORT GENERATOR
# ============================================================

def expand_sentiment_report(
    bullet_text: str,
    product: str
) -> str:

    if not product_intelligence_team:

        st.error(
            "⚠️ Please enter both API keys in the sidebar first."
        )

        return ""

    prompt = (

        f"Use the tagged bullets below to create a "
        f"concise market-sentiment brief for **{product}**.\n\n"

        f"### Positive Sentiment\n"

        f"• List each positive point as a separate bullet "
        f"(max 6).\n\n"

        f"### Negative Sentiment\n"

        f"• List each negative point as a separate bullet "
        f"(max 6).\n\n"

        f"### Overall Summary\n"

        f"Provide a short paragraph (≤120 words) "
        f"summarising the overall sentiment balance "
        f"and key drivers.\n\n"

        f"Tagged Bullets:\n"
        f"{bullet_text}"
    )

    resp: RunOutput = product_intelligence_team.run(prompt)

    return (
        resp.content
        if hasattr(resp, "content")
        else str(resp)
    )


# ============================================================
# LAUNCH METRICS REPORT GENERATOR
# ============================================================

def expand_metrics_report(
    bullet_text: str,
    launch: str
) -> str:

    if not product_intelligence_team:

        st.error(
            "⚠️ Please enter both API keys in the sidebar first."
        )

        return ""

    prompt = (

        f"Convert the KPI bullets below into a "
        f"launch-performance snapshot for **{launch}** "
        f"suitable for an executive dashboard.\n\n"

        f"## Key Performance Indicators\n"

        f"| Metric | Value / Detail | Source |\n"
        f"|---|---|---|\n"
        f"| … | … | … |\n"
        f"(include one row per KPI)\n\n"

        f"## Qualitative Signals\n"

        f"• Bullet list of notable qualitative insights "
        f"(max 5).\n\n"

        f"## Summary & Implications\n"

        f"Brief paragraph (≤120 words) highlighting "
        f"what the metrics imply about launch success "
        f"and next steps.\n\n"

        f"KPI Bullets:\n"
        f"{bullet_text}"
    )

    resp: RunOutput = product_intelligence_team.run(prompt)

    return (
        resp.content
        if hasattr(resp, "content")
        else str(resp)
    )


# ============================================================
# MAIN UI
# ============================================================

st.title("🚀 AI Product Launch Intelligence Agent")

st.markdown(
    "*AI-powered insights for GTM, Product Marketing & Growth Teams*"
)

st.divider()


# ============================================================
# COMPANY INPUT
# ============================================================

st.subheader("🏢 Company Analysis")

with st.container():

    col1, col2 = st.columns([3, 1])

    with col1:

        company_name = st.text_input(
            label="Company Name",

            placeholder=(
                "Enter company name "
                "(e.g., OpenAI, Tesla, Spotify)"
            ),

            help=(
                "This company will be analyzed by "
                "the coordinated team of specialized agents"
            ),

            label_visibility="collapsed"
        )

    with col2:

        if company_name:

            st.success(
                f"✓ Ready to analyze **{company_name}**"
            )


st.divider()


# ============================================================
# ANALYSIS TABS
# ============================================================

analysis_tabs = st.tabs(
    [
        "🔍 Competitor Analysis",
        "💬 Market Sentiment",
        "📈 Launch Metrics"
    ]
)


# ============================================================
# SESSION STATE
# ============================================================

if "competitor_response" not in st.session_state:

    st.session_state.competitor_response = None


if "sentiment_response" not in st.session_state:

    st.session_state.sentiment_response = None


if "metrics_response" not in st.session_state:

    st.session_state.metrics_response = None


# ============================================================
# COMPETITOR ANALYSIS TAB
# ============================================================

with analysis_tabs[0]:

    with st.container():

        st.markdown(
            "### 🔍 Competitor Launch Analysis"
        )

        with st.expander(
            "ℹ️ About this Agent",
            expanded=False
        ):

            st.markdown(
                """
                **Product Launch Analyst** - Strategic GTM Expert

                Specializes in:

                - Competitive positioning analysis
                - Launch strategy evaluation
                - Strengths & weaknesses identification
                - Strategic recommendations
                """
            )


        if company_name:

            col1, col2 = st.columns([2, 1])

            with col1:

                analyze_btn = st.button(
                    "🚀 Analyze Competitor Strategy",
                    key="competitor_btn",
                    type="primary",
                    use_container_width=True
                )


            with col2:

                if st.session_state.competitor_response:

                    st.success(
                        "✅ Analysis Complete"
                    )

                else:

                    st.info(
                        "⏳ Ready to analyze"
                    )


            if analyze_btn:

                if not product_intelligence_team:

                    st.error(
                        "⚠️ Please enter both API keys "
                        "in the sidebar first."
                    )

                else:

                    with st.spinner(
                        "🔍 Product Intelligence Team "
                        "analyzing competitive strategy..."
                    ):

                        try:

                            bullets: RunOutput = (
                                product_intelligence_team.run(

                                    f"Generate up to 16 "
                                    f"evidence-based insight "
                                    f"bullets about "
                                    f"{company_name}'s most "
                                    f"recent product launches.\n"

                                    f"Format requirements:\n"

                                    f"• Start every bullet with "
                                    f"exactly one tag: "
                                    f"Positioning | Strength | "
                                    f"Weakness | Learning\n"

                                    f"• Follow the tag with a "
                                    f"concise statement "
                                    f"(max 30 words) referencing "
                                    f"concrete observations: "
                                    f"messaging, differentiation, "
                                    f"pricing, channel selection, "
                                    f"timing, engagement metrics, "
                                    f"or customer feedback."
                                )
                            )


                            long_text = (
                                expand_competitor_report(

                                    bullets.content
                                    if hasattr(
                                        bullets,
                                        "content"
                                    )
                                    else str(bullets),

                                    company_name
                                )
                            )


                            st.session_state.competitor_response = (
                                long_text
                            )

                            st.success(
                                "✅ Competitor analysis ready"
                            )

                            st.rerun()


                        except Exception as e:

                            st.error(
                                f"❌ Error: {e}"
                            )


            # Display results

            if st.session_state.competitor_response:

                st.divider()

                with st.container():

                    st.markdown(
                        "### 📊 Analysis Results"
                    )

                    st.markdown(
                        st.session_state.competitor_response
                    )


        else:

            st.info(
                "👆 Please enter a company name above "
                "to start the analysis"
            )


# ============================================================
# MARKET SENTIMENT TAB
# ============================================================

with analysis_tabs[1]:

    with st.container():

        st.markdown(
            "### 💬 Market Sentiment Analysis"
        )


        with st.expander(
            "ℹ️ About this Agent",
            expanded=False
        ):

            st.markdown(
                """
                **Market Sentiment Specialist**
                - Consumer Perception Expert

                Specializes in:

                - Social media sentiment tracking
                - Customer feedback analysis
                - Brand perception monitoring
                - Review pattern identification
                """
            )


        if company_name:

            col1, col2 = st.columns([2, 1])


            with col1:

                sentiment_btn = st.button(
                    "📊 Analyze Market Sentiment",
                    key="sentiment_btn",
                    type="primary",
                    use_container_width=True
                )


            with col2:

                if st.session_state.sentiment_response:

                    st.success(
                        "✅ Analysis Complete"
                    )

                else:

                    st.info(
                        "⏳ Ready to analyze"
                    )


            if sentiment_btn:

                if not product_intelligence_team:

                    st.error(
                        "⚠️ Please enter both API keys "
                        "in the sidebar first."
                    )

                else:

                    with st.spinner(
                        "💬 Product Intelligence Team "
                        "analyzing market sentiment..."
                    ):

                        try:

                            bullets: RunOutput = (
                                product_intelligence_team.run(

                                    f"Summarize market sentiment "
                                    f"for {company_name} in "
                                    f"<=10 bullets. "

                                    f"Cover top positive & "
                                    f"negative themes with "
                                    f"source mentions "
                                    f"(G2, Reddit, Twitter, "
                                    f"customer reviews)."
                                )
                            )


                            long_text = (
                                expand_sentiment_report(

                                    bullets.content
                                    if hasattr(
                                        bullets,
                                        "content"
                                    )
                                    else str(bullets),

                                    company_name
                                )
                            )


                            st.session_state.sentiment_response = (
                                long_text
                            )


                            st.success(
                                "✅ Sentiment analysis ready"
                            )

                            st.rerun()


                        except Exception as e:

                            st.error(
                                f"❌ Error: {e}"
                            )


            # Display results

            if st.session_state.sentiment_response:

                st.divider()

                with st.container():

                    st.markdown(
                        "### 📈 Analysis Results"
                    )

                    st.markdown(
                        st.session_state.sentiment_response
                    )


        else:

            st.info(
                "👆 Please enter a company name above "
                "to start the analysis"
            )


# ============================================================
# LAUNCH METRICS TAB
# ============================================================

with analysis_tabs[2]:

    with st.container():

        st.markdown(
            "### 📈 Launch Performance Metrics"
        )


        with st.expander(
            "ℹ️ About this Agent",
            expanded=False
        ):

            st.markdown(
                """
                **Launch Metrics Specialist**
                - Performance Analytics Expert

                Specializes in:

                - User adoption metrics tracking
                - Revenue performance analysis
                - Market penetration evaluation
                - Press coverage monitoring
                """
            )


        if company_name:

            col1, col2 = st.columns([2, 1])


            with col1:

                metrics_btn = st.button(
                    "📊 Analyze Launch Metrics",
                    key="metrics_btn",
                    type="primary",
                    use_container_width=True
                )


            with col2:

                if st.session_state.metrics_response:

                    st.success(
                        "✅ Analysis Complete"
                    )

                else:

                    st.info(
                        "⏳ Ready to analyze"
                    )


            if metrics_btn:

                if not product_intelligence_team:

                    st.error(
                        "⚠️ Please enter both API keys "
                        "in the sidebar first."
                    )

                else:

                    with st.spinner(
                        "📈 Product Intelligence Team "
                        "analyzing launch metrics..."
                    ):

                        try:

                            bullets: RunOutput = (
                                product_intelligence_team.run(

                                    f"List (max 10 bullets) "
                                    f"the most important "
                                    f"publicly available "
                                    f"KPIs & qualitative "
                                    f"signals for "
                                    f"{company_name}'s recent "
                                    f"product launches. "

                                    f"Include engagement stats, "
                                    f"press coverage, adoption "
                                    f"metrics, and market "
                                    f"traction data if available."
                                )
                            )


                            long_text = (
                                expand_metrics_report(

                                    bullets.content
                                    if hasattr(
                                        bullets,
                                        "content"
                                    )
                                    else str(bullets),

                                    company_name
                                )
                            )


                            st.session_state.metrics_response = (
                                long_text
                            )


                            st.success(
                                "✅ Metrics analysis ready"
                            )

                            st.rerun()


                        except Exception as e:

                            st.error(
                                f"❌ Error: {e}"
                            )


            # Display results

            if st.session_state.metrics_response:

                st.divider()

                with st.container():

                    st.markdown(
                        "### 📊 Analysis Results"
                    )

                    st.markdown(
                        st.session_state.metrics_response
                    )


        else:

            st.info(
                "👆 Please enter a company name above "
                "to start the analysis"
            )


# ============================================================
# SIDEBAR - SYSTEM STATUS
# ============================================================

with st.sidebar.container():

    st.markdown(
        "### 🤖 System Status"
    )

    if openai_key and firecrawl_key:

        st.success(
            "✅ Product Intelligence Team ready"
        )

    else:

        st.error(
            "❌ API keys required"
        )


st.sidebar.divider()


# ============================================================
# SIDEBAR - COORDINATED TEAM
# ============================================================

with st.sidebar.container():

    st.markdown(
        "### 🎯 Coordinated Team"
    )


    agents_info = [

        (
            "🔍",
            "Product Launch Analyst",
            "Strategic GTM expert"
        ),

        (
            "💬",
            "Market Sentiment Specialist",
            "Consumer perception expert"
        ),

        (
            "📈",
            "Launch Metrics Specialist",
            "Performance analytics expert"
        )
    ]


    for icon, name, desc in agents_info:

        with st.container():

            st.markdown(
                f"**{icon} {name}**"
            )

            st.caption(desc)


st.sidebar.divider()


# ============================================================
# SIDEBAR - ANALYSIS STATUS
# ============================================================

if company_name:

    with st.sidebar.container():

        st.markdown(
            "### 📊 Analysis Status"
        )

        st.markdown(
            f"**Company:** {company_name}"
        )


        status_items = [

            (
                "🔍",
                "Competitor Analysis",
                st.session_state.competitor_response
            ),

            (
                "💬",
                "Sentiment Analysis",
                st.session_state.sentiment_response
            ),

            (
                "📈",
                "Metrics Analysis",
                st.session_state.metrics_response
            )
        ]


        for icon, name, status in status_items:

            if status:

                st.success(
                    f"{icon} {name} ✓"
                )

            else:

                st.info(
                    f"{icon} {name} ⏳"
                )


    st.sidebar.divider()


# ============================================================
# SIDEBAR - QUICK ACTIONS
# ============================================================

with st.sidebar.container():

    st.markdown(
        "### ⚡ Quick Actions"
    )

    if company_name:

        st.markdown(
            """
            **J** - Competitor analysis

            **K** - Market sentiment

            **L** - Launch metrics
            """
        )