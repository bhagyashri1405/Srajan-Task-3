import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from google import genai
from google.genai import types
from ddgs import DDGS

try:
    import streamlit as st
    _API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
except Exception:
    _API_KEY = os.environ.get("GEMINI_API_KEY")

MODEL = "gemini-3.5-flash-lite"
MAX_STEPS = 5  # safety cap on the Research Agent's Thought/Action/Observation loop

client = genai.Client(api_key=_API_KEY)

# ============================================================================
# AGENT 1: Research Agent
# Responsibility: gather raw information only. Decides what to investigate,
# which tool to call, and when it has enough — but does NOT write the final
# report. That's the Analyst Agent's job.
# ============================================================================

RESEARCH_SYSTEM_PROMPT = (
    "You are the Research Agent in a two-agent system. Your ONLY responsibility is "
    "gathering raw information — you do not write final reports, decide formatting, or "
    "make presentation choices; that is the Analyst Agent's job, not yours. "
    "You reason step by step using the ReAct pattern: Thought, then Action, then you "
    "receive an Observation, and you repeat this as many times as you judge necessary. "
    "Before every action, briefly write your Thought — what you need to find out next "
    "and why. You have TWO tools available, and you must decide for yourself which one "
    "fits each step:\n"
    "- search_arxiv: use this specifically when you need academic/scientific research "
    "papers on a topic (research trends, technical developments, published studies).\n"
    "- search_web: use this for anything else — competitor announcements, product news, "
    "industry news, patent activity, company information, or general current events.\n"
    "Decide for yourself which categories are relevant to the user's topic (research "
    "publications, patent filings, competitor moves, industry news) and how many searches "
    "to run with which tool — skip categories that don't apply, and feel free to use both "
    "tools across different steps if the topic calls for it. Make each query specific and "
    "targeted rather than broad. "
    "When you have gathered enough raw information, stop calling tools and output a plain, "
    "unformatted list of the findings you gathered and their sources — do NOT organize this "
    "into headings or write a polished report. Just hand off the raw findings; the Analyst "
    "Agent will turn them into the final briefing."
)

_TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_web",
            description=(
                "Search the general web for a specific query. Use for competitor moves, "
                "product announcements, industry/news coverage, patent activity, or company "
                "information — anything other than academic research papers."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="A specific, targeted search query."),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_arxiv",
            description=(
                "Search arXiv specifically for academic/scientific research papers on a topic. "
                "Use this when the user's request concerns research trends or published studies."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="A specific research topic or keywords."),
                },
                required=["query"],
            ),
        ),
    ]
)


def _execute_web_search(query: str, max_results: int = 5) -> str:
    """Tool 1: general web search via DuckDuckGo (free, keyless, no Gemini quota used)."""
    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception as exc:
        return f"Web search failed for this query ({exc}). Try a different or more specific query."

    if not results:
        return "No web results found for this query."

    lines = []
    for r in results:
        title = r.get("title", "").strip()
        body = r.get("body", "").strip()
        href = r.get("href", "").strip()
        lines.append(f"- {title}: {body} (source: {href})")
    return "\n".join(lines)


_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _execute_arxiv_search(query: str, max_results: int = 5) -> str:
    """Tool 2: academic research paper search via the arXiv API (free, keyless)."""
    try:
        params = urllib.parse.urlencode(
            {"search_query": f"all:{query}", "start": 0, "max_results": max_results}
        )
        url = f"http://export.arxiv.org/api/query?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        entries = root.findall("atom:entry", _ARXIV_NS)
    except Exception as exc:
        return f"arXiv search failed for this query ({exc}). Try a different or more specific query."

    if not entries:
        return "No arXiv papers found for this query."

    lines = []
    for entry in entries:
        title = (entry.findtext("atom:title", default="", namespaces=_ARXIV_NS) or "").strip().replace("\n", " ")
        summary = (entry.findtext("atom:summary", default="", namespaces=_ARXIV_NS) or "").strip().replace("\n", " ")
        link = (entry.findtext("atom:id", default="", namespaces=_ARXIV_NS) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=_ARXIV_NS) or "").strip()[:10]
        snippet = summary[:280] + ("..." if len(summary) > 280 else "")
        lines.append(f"- {title} ({published}): {snippet} (source: {link})")
    return "\n".join(lines)


_TOOL_EXECUTORS = {
    "search_web": _execute_web_search,
    "search_arxiv": _execute_arxiv_search,
}


def run_research_agent(user_input: str) -> dict:
    """
    Runs the Research Agent's Thought -> Action -> Observation -> ... loop.
    Stops when it decides it has enough raw findings (no more tool calls) or
    hits MAX_STEPS. Returns the raw findings text plus the visible trace.
    """
    trace = []
    search_queries = []
    contents = [types.Content(role="user", parts=[types.Part(text=user_input)])]
    config = types.GenerateContentConfig(system_instruction=RESEARCH_SYSTEM_PROMPT, tools=[_TOOLS])

    raw_findings = ""

    for _ in range(MAX_STEPS):
        try:
            response = client.models.generate_content(model=MODEL, contents=contents, config=config)
        except Exception as exc:
            trace.append({"type": "research_final", "content": f"Research Agent stopped early due to an API error: {exc}"})
            raw_findings = trace[-1]["content"]
            break

        candidate = response.candidates[0]
        parts = candidate.content.parts

        thought_text = "\n".join(p.text for p in parts if getattr(p, "text", None)).strip()
        if thought_text:
            trace.append({"type": "thought", "content": thought_text})

        function_call_part = next((p for p in parts if getattr(p, "function_call", None)), None)

        if function_call_part is None:
            raw_findings = thought_text
            trace.append({"type": "research_final", "content": raw_findings})
            break

        fc = function_call_part.function_call
        tool_name = fc.name
        query = fc.args.get("query", "")
        trace.append({"type": "action", "content": f'{tool_name}("{query}")'})
        search_queries.append(f"[{tool_name}] {query}")

        executor = _TOOL_EXECUTORS.get(tool_name)
        observation = executor(query) if executor else f"Unknown tool requested: {tool_name}"
        trace.append({"type": "observation", "content": observation})

        contents.append(candidate.content)
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(function_response=types.FunctionResponse(name=tool_name, response={"result": observation}))],
            )
        )
    else:
        raw_findings = trace[-1]["content"] if trace else "Research Agent could not complete within step limit."

    return {"raw_findings": raw_findings, "search_queries": search_queries, "trace": trace}


# ============================================================================
# AGENT 2: Analyst Agent
# Responsibility: synthesis only. No tools, no searching — takes the Research
# Agent's raw findings and turns them into the final structured briefing.
# ============================================================================

ANALYST_SYSTEM_PROMPT = (
    "You are the Analyst Agent in a two-agent system. You have NO search tools and "
    "cannot look anything up yourself — your only job is to synthesize what the Research "
    "Agent already found. You will be given the user's original request and the Research "
    "Agent's raw findings. Decide which findings are actually significant and actionable, "
    "then organize them into a concise report using markdown headings only for the "
    "categories genuinely supported by the findings (e.g. '## Research Trends', "
    "'## Patent Activity', '## Competitor Activity', '## Industry News') — omit a heading "
    "entirely if the findings don't support it rather than padding it with filler. Under "
    "each heading, write tight bullet points on what changed and why it matters. Be "
    "concise: this is a briefing, not an essay."
)


def run_analyst_agent(user_input: str, raw_findings: str) -> str:
    """
    A single reasoning call: takes the user's original request plus the Research
    Agent's raw findings, and produces the final structured briefing. This agent
    never calls a tool — it only synthesizes what it's given.
    """
    prompt = (
        f"User's original request: {user_input}\n\n"
        f"Research Agent's raw findings:\n{raw_findings}\n\n"
        "Synthesize these into the final briefing now."
    )
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=ANALYST_SYSTEM_PROMPT),
        )
        return (response.text or "").strip()
    except Exception as exc:
        return f"Analyst Agent stopped early due to an API error: {exc}"


# ============================================================================
# Orchestration: Research Agent -> Analyst Agent
# ============================================================================

def run_agent(user_input: str) -> dict:
    """
    Runs the two-agent pipeline: the Research Agent gathers raw findings via its
    own ReAct loop, then hands them off to the Analyst Agent, which synthesizes
    the final report. Returns the final answer plus the full combined trace,
    showing both agents' work.
    """
    research_result = run_research_agent(user_input)
    trace = list(research_result["trace"])

    trace.append(
        {
            "type": "handoff",
            "content": "Research Agent → Analyst Agent: handing off raw findings for synthesis.",
        }
    )

    final_answer = run_analyst_agent(user_input, research_result["raw_findings"])
    trace.append({"type": "analyst_final", "content": final_answer})

    return {
        "answer": final_answer,
        "used_search": len(research_result["search_queries"]) > 0,
        "search_queries": research_result["search_queries"],
        "trace": trace,
    }
