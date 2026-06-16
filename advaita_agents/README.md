# AdvaitaCode Placement Content Engine

> **6 Crew AI agents** that systematically create placement preparation content for `advaitacode.com`.

## Architecture

```
┌──────────────────────────────────────────────────┐
│              TOPIC STRATEGIST (Agent 0)           │
│              Runs weekly/monthly                   │
│                                                    │
│  Phase 1: External Signals                         │
│  ┌──────────────────────────────────────────────┐ │
│  │ Job posts │ Interview experiences │ TPO syllabi│ │
│  │ Company OA patterns │ Emerging tech scan      │ │
│  └──────────────────┬───────────────────────────┘ │
│                     ▼                              │
│  Phase 2: Internal Signals (when DB connected)     │
│  ┌──────────────────────────────────────────────┐ │
│  │ Quiz failure rates │ Time-on-page │ Solve rates│ │
│  └──────────────────┬───────────────────────────┘ │
│                     ▼                              │
│  Phase 3: Score → Tier → Roadmap                   │
│  ┌──────────────────────────────────────────────┐ │
│  │ Prerequisite-aware scoring                    │ │
│  │ Difficulty-level completeness check           │ │
│  │ Per-company matrix generation                 │ │
│  └──────────────────────────────────────────────┘ │
└────────────────────┬─────────────────────────────┘
                     │ roadmap.json
                     ▼
┌──────────────────────────────────────────────────┐
│            CONTENT PRODUCTION CREW                 │
│            Runs per topic                          │
│                                                    │
│  Agent 1: Research Agent                           │
│  ┌──────────────────────────────────────────────┐ │
│  │ Searches GFG, LeetCode, InterviewBit, etc.    │ │
│  │ Extracts facts, patterns, company nuances     │ │
│  └──────────────────┬───────────────────────────┘ │
│                     ▼                              │
│  Agent 2: Content Writer                           │
│  ┌──────────────────────────────────────────────┐ │
│  │ Writes crisp articles: beginner → advanced     │ │
│  │ Code examples, interview tips, revision sheet  │ │
│  └────────┬──────────────┬──────────────────────┘ │
│           ▼              ▼                         │
│  Agent 3: Quiz Designer    Agent 4: Coding Probs   │
│  ┌─────────────────┐  ┌──────────────────────┐    │
│  │ MCQs at 3 levels │  │ Problems + solutions │    │
│  │ With explanations│  │ + test cases + hints │    │
│  └────────┬────────┘  └──────────┬───────────┘    │
│           └───────────┬───────────┘                │
│                       ▼                            │
│  Agent 5: Technical Reviewer (QUALITY GATE)        │
│  ┌──────────────────────────────────────────────┐ │
│  │ Accuracy │ Pedagogy │ Relevance │ Accessibility │
│  │ Approve / Fix minor / Reject with specifics    │
│  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

## Agent Summary

| # | Agent | Role | Tools | Runs |
|---|---|---|---|---|
| 0 | Topic Strategist | Roadmap creator | SerperDev, ScrapeWebsite | Weekly/Monthly |
| 1 | Research Agent | Raw material gathering | SerperDev, ScrapeWebsite | Per topic |
| 2 | Content Writer | Articles & tutorials | None | Per topic |
| 3 | Quiz Designer | MCQs (all levels) | None | Per topic |
| 4 | Coding Problem Designer | Problems + solutions | None | Per topic |
| 5 | Technical Reviewer | Quality gate | None | Per topic |

## Topic Taxonomy (10 categories, 65+ leaf topics)

The `taxonomy.py` file contains the **master checklist** — every CS/IT placement topic with:

- **Weight** (1-10 priority score)
- **Difficulty levels** (beginner, intermediate, advanced)
- **Prerequisites** (topic dependencies)
- **Subtopics** (detailed content breakdown)
- **Company tags** (which companies value this topic)
- **Content type recommendations** (article, mcq, coding)

Categories: Data Structures, Algorithms, CS Fundamentals, Programming Languages, System Design, Web Development, Aptitude & Reasoning, Soft Skills & HR, Company-Specific Guides, Emerging Tech.

## How Topic Selection Works (Balanced Approach)

The Topic Strategist ensures no important topic is missed and nothing irrelevant is included through:

### 1. Master Taxonomy (the checklist)
Every known placement topic is pre-registered in the taxonomy. The taxonomy is comprehensive — built from years of placement data across TCS to Google. Nothing falls through the cracks because every topic has a slot.

### 2. Demand Signal Validation (the filter)
Topics are validated against real-world demand:
- **Job description scraping** — What are companies actually asking for?
- **Interview experience analysis** — What topics appear in real interviews?
- **College TPO syllabi** — What are placement cells teaching?
- **Trending topic scan** — What's emerging in 2025-2026?

A topic with 0 demand and low taxonomy weight gets REJECTED.

### 3. Prerequisite-Aware Scoring (the chain)
A topic can't be TIER 1 if its prerequisites aren't covered. This prevents the system from creating "Dynamic Programming" content before "Recursion & Backtracking" exists.

### 4. Difficulty-Level Completeness (the depth)
Each topic requires content at ALL three difficulty levels (beginner, intermediate, advanced) before it's considered "fully covered." No topic is done until a BCA student, a B.Tech student, and an IITian all find appropriate material.

### 5. Gap Analysis (the safety net)
After content is produced, the Gap Analyzer compares published content against the master taxonomy. It flags:
- Completely missing topics
- Topics with <80% subtopic coverage
- Stale content (>12 months old)
- Topics where students are struggling (high quiz failure rates)

### 6. Platform Analytics (the feedback loop)
When connected to a database, the system learns from students:
- High quiz failure rate → topic needs better/more content
- Low time-on-page → article quality may be poor
- Low problem solve rate → problem may be too hard or poorly taught

## Directory Structure

```
advaita_agents/
├── agents/
│   ├── __init__.py
│   ├── topic_strategist.py    # Agent 0: Roadmap creator
│   └── content_agents.py      # Agents 1-5: Content producers
├── tasks/
│   ├── __init__.py
│   ├── topic_curation.py      # Strategic tasks
│   └── content_tasks.py       # Production tasks
├── taxonomy.py                # Master topic tree + scoring
├── crew.py                    # Crew assembly
├── main.py                    # Orchestration entry point
├── .env.example               # Required environment variables
└── README.md                  # This file
```

## Quick Start

### 1. Install dependencies

```bash
pip install crewai crewai-tools python-dotenv
```

### 2. Set environment variables

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Generate the roadmap

```bash
uv run advaita_agents/main.py roadmap
```

This produces:
- `roadmap.json` — Full AI-generated roadmap with demand signals
- `roadmap_scored.json` — Lightweight scored topic list

### 4. Produce content

```bash
# Produce content for all TIER 1 topics
uv run advaita_agents/main.py produce

# Or produce for a specific topic
uv run advaita_agents/main.py produce --topic-id ds_arrays

# Specify language
uv run advaita_agents/main.py produce --topic-id ds_trees --language java
```

### 5. Run gap analysis

```bash
uv run advaita_agents/main.py gap
```

## Scoring Formula

Each topic receives a score based on:

```python
score = (demand_norm * 0.40 * 10) +    # How many job posts mention it?
        (weight_norm * 0.40) +          # How important is it inherently?
        (coverage_gap * 0.20)           # How much content is missing?

# Special rule: Core topics (weight >= 8) with <50% coverage get
# maximum urgency (coverage_gap = 10.0) to ensure fundamentals
# are never neglected.
```

### Tier Cutoffs

| Tier | Score | Action |
|---|---|---|
| TIER 1 (Must Have) | ≥ 7.0 | Create immediately |
| TIER 2 (Should Have) | 4.5 — 6.9 | Next sprint |
| TIER 3 (Nice to Have) | < 4.5 | Backlog |

## Content Output Format

Each topic production run creates:
- **Article** (markdown, 1000-3000 words) with beginner/intermediate/advanced levels
- **MCQs** (10 questions, JSON) with difficulty distribution and distractor explanations
- **Coding Problems** (4 problems, JSON) with solutions, test cases, and progressive hints
- **Review Report** (JSON) with technical accuracy, pedagogy, completeness, and accessibility scores

## Production Cadence

| Activity | Frequency | Trigger |
|---|---|---|
| Demand signal collection | Weekly | Cron: `uv run advaita_agents/main.py roadmap` |
| Full gap analysis | Monthly | Cron: `uv run advaita_agents/main.py gap` |
| Content production | Continuous | Per topic: `uv run advaita_agents/main.py produce` |
| Taxonomy update | Quarterly | Manual review of emerging/declining topics |

## Key Design Decisions

1. **6 agents, not 8-10**: More agents = higher cost + more coordination failures. The Topic Strategist handles planning; the 5 production agents handle execution. This is the minimum viable set that still separates concerns.

2. **Prerequisites in taxonomy, not in prompts**: The prompt can't enforce prerequisite ordering reliably. By modeling it in the taxonomy and scoring formula, the system mathematically prevents out-of-order content creation.

3. **Reviewer is the gate, not a suggester**: The Technical Reviewer outputs APPROVE/REJECT with specific fixes — not vague feedback. This prevents the common Crew AI failure mode where reviewers produce unactionable comments.

4. **Company-specific guides are separate from topic content**: A topic like "Trees" is written generically. Amazon-specific tree problem patterns go in the Amazon company guide. This avoids content duplication and keeps articles focused.

5. **Aptitude is treated as critical (weight 9)**: Most placement platforms under-invest in aptitude content despite it being the #1 elimination round for mass recruiters. The taxonomy gives it weight 9, matching CS fundamentals.

## Limitations & Future Work

- **Platform analytics**: Currently a stub. Connect to your database for quiz failure rates, time-on-page, etc.
- **Multi-language code examples**: Currently generates in one language per run. Future: parallel runs for Python, Java, C++.
- **Video scripts**: Not yet supported. Could add a VideoScript agent as Agent 6.
- **Auto-publish**: Content is saved to files. Add a CMS integration step.
