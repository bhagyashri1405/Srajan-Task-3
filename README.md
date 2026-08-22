# 🛰️ Research & Competitor Intelligence Agent

## Team Members
- [Dhokane Grishma]
- [Pawar Bhagyashri]
- [Pol Urmila]
- [Thete Payal]

## Problem Statement
Organizations, startups, and research institutions operate in highly competitive
and rapidly evolving environments where staying updated on research trends,
patent developments, competitor strategies, and industry news is critical.
However, manually monitoring scientific publications, patent databases, news
platforms, and social media sources is time-consuming, inefficient, and prone
to missing important updates. The lack of timely insights can result in lost
opportunities, delayed innovation, and weakened competitive positioning.
Therefore, there is a need for an autonomous AI agent capable of continuously
tracking research and competitor activities, analyzing vast information
sources, and delivering concise, actionable insights in real time.

## Project Description
This project is an autonomous AI agent that takes a topic, technology area, or
competitor name and produces a concise intelligence briefing on it. Rather than
running a single fixed search, the agent reasons step by step using the
**ReAct (Reason + Act) pattern**: it decides for itself which categories are
worth investigating (research publications, patent activity, competitor moves,
industry news), how many searches to run, and when it has gathered enough
information to stop and report back. Every reasoning step — Thought, Action,
Observation — is visible in the UI, so the decision-making process is
transparent, not a black box.

## Multi-Agent Architecture

This system uses **two specialized agents**, each with a clearly defined
responsibility, orchestrated in sequence:

1. **Research Agent** — responsible only for gathering raw information. It runs
   its own ReAct loop (Thought → Action → Observation), deciding which of two
   tools to call (`search_web` or `search_arxiv`), how many times, and when it
   has enough. It does **not** decide formatting or write the final report —
   it hands off plain, unformatted raw findings.
2. **Analyst Agent** — responsible only for synthesis. It has no search tools
   and cannot look anything up itself. It receives the user's original request
   plus the Research Agent's raw findings, decides what's actually significant,
   and produces the final structured briefing (with headings only for the
   categories the findings genuinely support).

The **handoff** between them is explicit and visible: the Research Agent's
compiled findings become the Analyst Agent's input, and this exchange is shown
as its own step in the UI's reasoning trace panel, alongside every
Thought/Action/Observation step from the Research Agent and the Analyst
Agent's final output.

### How the agent reasons (ReAct pattern, within the Research Agent)
1. **Thought** — the model reasons in plain text about what it needs to find out next, and why
2. **Action** — if it needs information, it calls one of two tools with a specific, targeted query: `search_web` (general web/competitor/news) or `search_arxiv` (academic research papers) — it decides which tool fits, per step
3. **Observation** — real results from that tool are fed back into the conversation
4. Steps 1–3 repeat as many times as the model judges necessary (capped at 5 steps)
5. Once it decides it has enough, it stops calling tools and compiles its raw findings, which are then handed off to the Analyst Agent

Nothing forces the number of searches, which tool is used, their content, or
when to stop — the Research Agent decides all of that itself at each step, and
the Analyst Agent independently decides how to present what it's given.

## Technologies Used
- **Model:** Google Gemini API (`gemini-3.5-flash-lite`) for reasoning and decision-making
- **Tool 1 — Web Search:** DuckDuckGo (via the `ddgs` Python library) — free, keyless general web search, used for competitor moves, product news, and industry coverage
- **Tool 2 — arXiv API:** the public arXiv REST API — free, keyless, used specifically for academic/scientific research paper search
- **UI:** Streamlit
- **Language:** Python

## Features
- **Two specialized, collaborating agents**: a Research Agent (gathers raw findings via its own ReAct loop) and an Analyst Agent (synthesizes those findings into the final briefing) — with an explicit, visible handoff between them
- Autonomous, multi-step decision-making within the Research Agent (ReAct: Thought → Action → Observation)
- **Two external tools, dynamically selected by the Research Agent** — it decides per step whether a query needs general web search or an academic paper search on arXiv
- Investigates only the categories actually relevant to the input — no forced, one-size-fits-all output
- Runs multiple, independently-decided searches across either tool when needed, not just one fixed query
- Visible reasoning trace in the UI, showing every step from both agents — Thoughts, Actions, Observations, the handoff, and the Analyst Agent's final report
- Structured markdown briefing as the final output (Research Trends, Patent Activity, Competitor Activity, Industry News — only the sections that apply)
- Graceful error handling if either tool or the API is unavailable or rate-limited

## Installation / Setup
1. Clone this repo and `cd` into it
2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey)
5. Copy `.env.example` to `.env` and add your Gemini API key:
   ```
   cp .env.example .env
   ```

## How to Run
```
streamlit run app.py
```
This opens the app in your browser (usually at `http://localhost:8501`). Enter
a topic, technology area, or competitor name, and the agent will reason through
what to investigate and return a briefing.

## Screenshots / Demo Link
- **Live demo:** https://srajan4.streamlit.app/
- **Screenshots:** <img width="1600" height="824" alt="WhatsApp Image 2026-08-22 at 4 27 38 PM" src="https://github.com/user-attachments/assets/a39d05e0-1c06-4a9d-a326-1b0098bc6cc5" />
<img width="1600" height="824" alt="WhatsApp Image 2026-08-22 at 4 28 32 PM" src="https://github.com/user-attachments/assets/50d4b821-a21b-4b66-8334-5d19e1e707b1" />


