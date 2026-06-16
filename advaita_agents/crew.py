"""
Crew Assembly — Wire agents and tasks into production crews.

Two crews:
1. TopicStrategyCrew — Runs weekly/monthly. Produces a prioritized roadmap.
2. ContentProductionCrew — Runs per topic. Produces article + MCQs + coding problems.
"""

from crewai import Crew, Process

from advaita_agents.agents.topic_strategist import topic_strategist
from advaita_agents.agents.content_agents import (
    research_agent,
    content_writer,
    quiz_designer,
    coding_problem_designer,
    technical_reviewer,
)

from advaita_agents.tasks.topic_curation import (
    demand_signal_collection_task,
    topic_prioritization_task,
    gap_analysis_task,
)
from advaita_agents.tasks.content_tasks import (
    research_task,
    content_writing_task,
    quiz_design_task,
    coding_problem_design_task,
    technical_review_task,
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
