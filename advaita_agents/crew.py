"""
Crew Assembly — Wire agents and tasks into production crews.

Two crews:
1. TopicStrategyCrew — Runs weekly/monthly. Produces a prioritized roadmap.
2. ContentProductionCrew — Runs per topic. Produces article + MCQs + coding problems.
"""

from crewai import Crew, Process

from advaita_agents.agents.content_agents import (
    coding_problem_designer,
    content_writer,
    quiz_designer,
    research_agent,
    technical_reviewer,
)
from advaita_agents.agents.topic_strategist import topic_strategist
from advaita_agents.tasks.content_tasks import (
    coding_problem_design_task,
    content_writing_task,
    quiz_design_task,
    research_task,
    technical_review_task,
)
from advaita_agents.tasks.topic_curation import (
    demand_signal_collection_task,
    gap_analysis_task,
    topic_prioritization_task,
)

# ═══════════════════════════════════════════════════════════════════════
#  CREW 1: Topic Strategy Crew
# ═══════════════════════════════════════════════════════════════════════


def create_topic_strategy_crew() -> Crew:
    """Create the crew that builds and maintains the content roadmap.

    Runs weekly (demand signals + prioritization) or monthly (full gap analysis).
    """
    return Crew(
        name="TopicStrategyCrew",
        agents=[topic_strategist],
        tasks=[
            demand_signal_collection_task,
            topic_prioritization_task,
            gap_analysis_task,
        ],
        process=Process.sequential,
        verbose=True,
        memory=False,
    )


# ═══════════════════════════════════════════════════════════════════════
#  CREW 2: Content Production Crew
# ═══════════════════════════════════════════════════════════════════════


def create_content_production_crew() -> Crew:
    """Create the crew that produces content for a single topic.

    Pipeline: Research → Write → (Quiz ‖ Coding) → Review

    The Quiz and Coding tasks run in parallel after Writing completes
    (they both depend on research + article context).
    """
    return Crew(
        name="ContentProductionCrew",
        agents=[
            research_agent,
            content_writer,
            quiz_designer,
            coding_problem_designer,
            technical_reviewer,
        ],
        tasks=[
            research_task,
            content_writing_task,
            quiz_design_task,
            coding_problem_design_task,
            technical_review_task,
        ],
        process=Process.sequential,
        verbose=True,
        memory=False,
    )


def create_content_generation_crew() -> Crew:
    """Create a crew that generates content WITHOUT the Reviewer.

    Pipeline: Research → Write → (Quiz ‖ Coding)

    The Reviewer runs separately after the human checkpoint so the human
    can fix surface errors (typos, draft artifacts) before the Reviewer
    evaluates the content.
    """
    return Crew(
        name="ContentGenerationCrew",
        agents=[
            research_agent,
            content_writer,
            quiz_designer,
            coding_problem_designer,
        ],
        tasks=[
            research_task,
            content_writing_task,
            quiz_design_task,
            coding_problem_design_task,
        ],
        process=Process.sequential,
        verbose=True,
        memory=False,
    )


def create_reviewer_crew(
    topic_id: str,
    topic_label: str,
    article_raw: str,
    quiz_raw: str,
    coding_raw: str,
) -> Crew:
    """Create a single-agent Reviewer crew with content embedded directly.

    Does NOT depend on CrewAI context chaining — the content is injected
    into the task description so it works standalone.
    """
    from crewai import Task

    review_prompt = (
        f"REVIEW all content produced for '{topic_label}' (ID: {topic_id}).\n\n"
        "You are the QUALITY GATE. Nothing gets published without your approval.\n\n"
        "TOKEN BUDGET WARNING — READ THIS FIRST (it overrides everything below):\n"
        "You have ~8000 output tokens. Tracing every example by hand WILL exhaust "
        "your budget before you can write the verdict JSON. The #1 pipeline failure "
        "is: you trace 15+ examples, run out of tokens, and produce NO JSON at all. "
        "A shallow review with a valid JSON verdict is INFINITELY better than a "
        "thorough trace that produces nothing.\n\n"
        "YOUR FIRST ACTION: Type a single opening curly brace. Then fill in the "
        "JSON section by section — verdict first, then article_review, mcq_review, "
        "coding_problems_review, required_fixes, reviewer_notes. Write the JSON AS "
        "you review, not after you finish reviewing. If you notice token pressure, "
        "stop tracing and note in reviewer_notes: 'Spot-checked N/M items — token "
        "limit reached.'\n\n"
        "--- CONTENT TO REVIEW ---\n\n"
        f"=== ARTICLE ===\n{article_raw}\n\n"
        f"=== QUIZ ===\n{quiz_raw}\n\n"
        f"=== CODING PROBLEMS ===\n{coding_raw}\n\n"
        "--- REVIEW CHECKLIST (apply inside the JSON as you write it) ---\n\n"
        "REVIEW THE ARTICLE through four lenses:\n\n"
        "1. TECHNICAL ACCURACY (non-negotiable):\n"
        "   - Is every concept definition correct?\n"
        "   - Do ALL code examples compile and produce correct output?\n"
        "   - Are complexity analyses (time/space) correct?\n"
        "   - Are there any factual errors, even minor ones?\n\n"
        "2. PEDAGOGICAL QUALITY:\n"
        "   - Does the article teach effectively? Or just list facts?\n"
        "   - Is the progression logical? (beginner → intermediate → advanced)\n"
        "   - Are examples concrete or abstract? (concrete > abstract)\n"
        "   - Would a tier-3 BCA student understand the beginner section?\n"
        "   - Would a tier-1 B.Tech student find value in the advanced section?\n\n"
        "3. COMPANY RELEVANCE:\n"
        "   - Are the interview tips accurate for the tagged companies?\n"
        "   - Are the practice problems representative of what those companies ask?\n"
        "   - Is the difficulty calibration correct?\n\n"
        "4. ACCESSIBILITY & CRISPNESS:\n"
        "   - Is there filler content that should be cut?\n"
        "   - Are any critical subtopics from the taxonomy MISSING?\n"
        "   - Is the language clear, or are there jargon-heavy passages "
        "without explanation?\n\n"
        "REVIEW THE MCQs:\n"
        "   - Is every correct answer actually correct?\n"
        "   - Are the distractors plausible? (obviously wrong distractors = bad MCQ)\n"
        "   - Are explanations accurate and educational?\n\n"
        "REVIEW THE CODING PROBLEMS:\n"
        "   - Are problem statements unambiguous?\n"
        "   - Do test cases cover edge cases?\n"
        "   - Are solutions truly optimal? Verify complexity analysis.\n"
        "   - Are hints progressive (not giving away the solution in hint 1)?\n\n"
        "DECISION:\n"
        "- APPROVE: All checks pass. Ready for publish.\n"
        "- APPROVE WITH MINOR FIXES: Small issues (typo, formatting) — "
        "list them, content can publish after fixes.\n"
        "- REJECT WITH REQUIRED FIXES: Technical errors or major gaps — "
        "provide a numbered list of SPECIFIC required changes. "
        "Do not say 'improve the explanation' — say exactly what's wrong "
        "and what the correct explanation should be.\n\n"
        "SPOT-CHECK (trace 2-3 examples per article section, 2-3 per coding "
        "problem — NOT all of them):\n"
        "1. Trace 2-3 examples/test cases per coding problem. Wrong expected "
        "outputs are the most damaging error — but sampling catches them. "
        "If a spot-check reveals an error, dig deeper on THAT problem only.\n"
        "2. Cross-check test case inputs against stated constraints. "
        "If N_min=1, there must be no empty-array test case.\n"
        "3. Verify subarray-counting problems: count each valid subarray "
        "individually and verify the total.\n"
        "4. Check that solution descriptions match the code (e.g. if the text "
        "says 'count evens to the left of each odd' but the code counts odds "
        "to the left of each even, flag it).\n"
        "5. Flag any vague/falsifiable claims (e.g. 'X engineers use this' "
        "without evidence).\n\n"
        "⛔ FINAL REMINDER: Token budget warning from above still applies. "
        "Your ENTIRE response must be ONE valid JSON object. First character = "
        "single opening curly brace. Last character = single closing curly brace. "
        "No 'Thought:', no 'Let me', no preamble. No trailing text. If you catch "
        "yourself drafting a trace instead of JSON — STOP and switch to JSON "
        "immediately. A 500-token review with valid JSON beats an 8000-token "
        "trace with nothing. WRITE THE JSON FIRST."
    )

    review_task = Task(
        description=review_prompt,
        expected_output=(
            "Review report JSON:\n"
            "{{\n"
            "  'verdict': 'approved'|'approved_with_minor_fixes'|'rejected',\n"
            "  'article_review': {{...}},\n"
            "  'mcq_review': {{...}},\n"
            "  'coding_problems_review': {{...}},\n"
            "  'required_fixes': ['<numbered list>'],\n"
            "  'reviewer_notes': '<summary>'\n"
            "}}"
        ),
        agent=technical_reviewer,
    )

    return Crew(
        name="ReviewerOnlyCrew",
        agents=[technical_reviewer],
        tasks=[review_task],
        process=Process.sequential,
        verbose=True,
        memory=False,
    )
