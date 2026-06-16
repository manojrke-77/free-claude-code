"""
Topic Curation Tasks — The strategic layer.

Three tasks run by the Topic Strategist agent:
1. Demand Signal Collection — Scrape external sources for what's being asked
2. Topic Prioritization — Score, tier, and build the roadmap
3. Gap Analysis — Compare published content vs taxonomy to find holes
"""

from crewai import Task
from advaita_agents.agents.topic_strategist import topic_strategist

# ── Task 1: Demand Signal Collection ───────────────────────────────────

demand_signal_collection_task = Task(
    description=(
        "COLLECT DEMAND SIGNALS from external sources to determine what topics "
        "are actually being tested in fresher placement drives.\n\n"
        "STEP 1 — JOB DESCRIPTIONS (primary signal):\n"
        "- Search for: 'fresher software engineer job description 2026'\n"
        "- Search for: 'graduate engineer trainee requirements TCS Infosys Wipro'\n"
        "- Search for: 'SDE-1 requirements Amazon Google Microsoft'\n"
        "- Extract all technical skills and topics mentioned. Count frequencies.\n\n"
        "STEP 2 — INTERVIEW EXPERIENCES (validation signal):\n"
        "- Search for: 'TCS NQT interview experience topics asked 2026'\n"
        "- Search for: 'Amazon SDE-1 interview experience DSA topics'\n"
        "- Search for: 'placement interview CS fundamentals questions'\n"
        "- Search for: 'Infosys SP DSE interview technical questions'\n"
        "- Extract topic names. Note which companies ask which topics.\n\n"
        "STEP 3 — COLLEGE TPO SYLLABI (coverage check):\n"
        "- Search for: 'IIT placement preparation syllabus computer science'\n"
        "- Search for: 'NIT placement training curriculum topics'\n"
        "- Search for: 'engineering college placement preparation topics list'\n"
        "- Cross-reference with standard CS curriculum.\n\n"
        "STEP 4 — TRENDING & EMERGING TOPICS:\n"
        "- Search for: 'top coding interview topics 2026 trending'\n"
        "- Search for: 'new topics in fresher software engineering interviews'\n"
        "- Search for: 'emerging technology skills fresher jobs 2026'\n"
        "- Flag any topic that appears in job descriptions but NOT in our taxonomy.\n\n"
        "STEP 5 — COMPANY-SPECIFIC PATTERNS:\n"
        "- For each major company (TCS, Infosys, Wipro, Amazon, Google, Microsoft, "
        "Cognizant, Accenture, Capgemini, Meta):\n"
        "  - Search: '[Company] fresher interview topics weightage'\n"
        "  - Note: which topics does this company EMPHASIZE vs IGNORE?\n"
        "  - Note: MCQ-heavy vs coding-heavy vs interview-heavy rounds.\n\n"
        "OUTPUT: A structured JSON with:\n"
        "- demand_signals: {{topic_id: count_of_mentions}} (at least 50 topic entries)\n"
        "- company_topic_matrix: {{company: [top_5_topic_ids]}}\n"
        "- emerging_topics: [{{name, source_url, evidence, suggested_taxonomy_parent}}]\n"
        "- declining_topics: [{{name, reason, last_seen_significant}}]\n"
        "- sources: [list of URLs scraped]"
    ),
    expected_output=(
        "JSON object with demand_signals, company_topic_matrix, emerging_topics, "
        "declining_topics, and sources. Must contain at least 50 topic entries "
        "in demand_signals."
    ),
    agent=topic_strategist,
)

# ── Task 2: Topic Prioritization ───────────────────────────────────────

topic_prioritization_task = Task(
    description=(
        "SCORE, TIER, AND BUILD THE CONTENT ROADMAP.\n\n"
        "Take the demand signals from the previous task and the master taxonomy "
        "(provided as context). For EVERY leaf topic in the taxonomy:\n\n"
        "SCORING RULES:\n"
        "1. If demand_signal > 0 for this topic → include, score by formula.\n"
        "2. If taxonomy weight >= 8 but demand_signal == 0 → FLAG for manual "
        "   review. Core CS fundamentals (OS, DBMS, DSA basics) are ALWAYS "
        "   important even if scrapers don't surface them explicitly.\n"
        "3. If demand_signal == 0 AND taxonomy weight <= 3 → REJECT with reason.\n"
        "4. For each topic, check prerequisites: a topic CANNOT enter TIER 1 if "
        "   its prerequisites aren't already covered or also in TIER 1.\n"
        "5. Each topic must have content at ALL required difficulty levels. "
        "   A topic with only 'advanced' content but missing 'beginner' is "
        "   flagged as PARTIAL COVERAGE.\n\n"
        "TIER ASSIGNMENT:\n"
        "- TIER 1 (score >= 7.0): Must have. Create immediately. Core DSA + CS "
        "  fundamentals + high-demand aptitude topics.\n"
        "- TIER 2 (score >= 4.5): Should have. Next sprint. Language-specific, "
        "  system design, company guides.\n"
        "- TIER 3 (score < 4.5): Nice to have. Backlog. Emerging tech, web dev "
        "  basics, niche topics.\n\n"
        "CONTENT TYPE RECOMMENDATION:\n"
        "- If 'mcq' in content_types → recommend MCQ\n"
        "- If 'coding' in content_types → recommend Coding Problems\n"
        "- If 'article' in content_types → recommend Article\n"
        "- Many topics need ALL THREE.\n\n"
        "OUTPUT: A prioritized roadmap JSON."
    ),
    expected_output=(
        "JSON roadmap:\n"
        "{{\n"
        "  'generated_at': '<ISO timestamp>',\n"
        "  'summary': {{\n"
        "    'total_topics': <N>,\n"
        "    'tier_1_count': <N>,\n"
        "    'tier_2_count': <N>,\n"
        "    'tier_3_count': <N>,\n"
        "    'rejected_count': <N>,\n"
        "    'flagged_for_review_count': <N>\n"
        "  }},\n"
        "  'tiers': {{\n"
        "    'tier_1': [{{topic_id, label, weight, score, content_types[], "
        "urgency_reason, difficulty_levels_needed[]}}],\n"
        "    'tier_2': [...],\n"
        "    'tier_3': [...]\n"
        "  }},\n"
        "  'rejected': [{{topic_id, label, reason}}],\n"
        "  'flagged_for_review': [{{topic_id, label, reason, suggested_action}}],\n"
        "  'company_coverage_map': {{\n"
        "    'tcs': {{topics_covered_pct, gaps[]}},\n"
        "    'amazon': {{...}},\n"
        "    ...\n"
        "  }}\n"
        "}}"
    ),
    agent=topic_strategist,
    context=[demand_signal_collection_task],
)

# ── Task 3: Gap Analysis ───────────────────────────────────────────────

gap_analysis_task = Task(
    description=(
        "COMPARE PUBLISHED CONTENT AGAINST THE MASTER TAXONOMY.\n\n"
        "This task runs AFTER content has been produced. It finds blind spots.\n\n"
        "For each leaf topic in the taxonomy, check:\n"
        "1. COVERAGE: Does published content exist? (yes / partial / no)\n"
        "2. FRESHNESS: Is the content recent? (< 12 months old)\n"
        "3. COMPLETENESS: Are ALL subtopics listed in the taxonomy covered?\n"
        "4. DEPTH: Is content available at ALL required difficulty levels?\n"
        "5. FORMAT: Are ALL required content types available? (article, mcq, coding)\n"
        "6. PREREQUISITES: Are all prerequisite topics covered before this one?\n\n"
        "PLATFORM ANALYTICS (if available):\n"
        "- Topics with highest quiz failure rates → students are weak here → "
        "  may need MORE or BETTER content\n"
        "- Articles with lowest time-on-page → quality may be poor → flag for rewrite\n"
        "- Coding problems with lowest solve rates → may be too hard or poorly taught\n"
        "- Topics with highest student requests/votes → underserved demand\n\n"
        "FLAG any topic where coverage < 80% of subtopics or any difficulty "
        "level is missing."
    ),
    expected_output=(
        "Gap analysis JSON:\n"
        "{{\n"
        "  'generated_at': '<ISO timestamp>',\n"
        "  'overall_coverage_pct': <0-100>,\n"
        "  'fully_covered': [topic_ids],\n"
        "  'partial_coverage': [{{\n"
        "    topic_id, label, coverage_pct, "
        "    missing_subtopics: [labels], "
        "    missing_difficulty_levels: [labels], "
        "    missing_content_types: [labels],\n"
        "    needs_rewrite: bool, "
        "    last_updated: '<ISO date>'\n"
        "  }}],\n"
        "  'completely_missing': [{{\n"
        "    topic_id, label, weight, urgency\n"
        "  }}],\n"
        "  'stale_content': [{{\n"
        "    topic_id, label, last_updated, reason_stale, suggested_action\n"
        "  }}],\n"
        "  'platform_insights': {{\n"
        "    high_failure_topics: [topic_ids],\n"
        "    low_engagement_articles: [topic_ids],\n"
        "    underserved_demand: [topic_ids]\n"
        "  }}\n"
        "}}"
    ),
    agent=topic_strategist,
)
