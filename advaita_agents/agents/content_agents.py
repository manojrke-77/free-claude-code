"""
Content Production Agents — The production layer.

Five agents that turn roadmap topics into published content:
1. Research Agent — Gathers raw material from reliable sources
2. Content Writer — Writes crisp, structured articles/tutorials
3. Quiz Designer — Creates MCQs at multiple difficulty levels
4. Coding Problem Designer — Creates coding problems with test cases
5. Technical Reviewer — Reviews everything for accuracy and clarity
"""

from crewai import Agent, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

search_tool = SerperDevTool()
scrape_tool = ScrapeWebsiteTool()

# ── LLM instances with explicit max_tokens to prevent output truncation ─

research_llm = LLM(
    model="deepseek/deepseek-chat",
    max_tokens=8192,  # DeepSeek supports up to 8K; research notes need space
)

writer_llm = LLM(
    model="anthropic/claude-sonnet-4-6",
    max_tokens=8192,  # Full article with code examples needs headroom
)

quiz_llm = LLM(
    model="anthropic/claude-sonnet-4-6",
    max_tokens=8192,  # 10 MCQs with explanations + distractors (bumped from 6000
    # after run 12: q_ds_arrays_10 distractor D truncated mid-sentence)
)

coding_llm = LLM(
    model="anthropic/claude-sonnet-4-6",
    max_tokens=10000,  # 3 problems with solutions, test cases, hints (bumped from 8192
    # after run 12: cp_ds_arrays_4 JSON truncated — reduced from 4 to 3 problems,
    # examples 3-5→2-3, test cases 8-10→5-6. Claude Sonnet still caps at ~8192 effective)
)

reviewer_llm = LLM(
    model="anthropic/claude-sonnet-4-6",
    max_tokens=8192,  # Review report with structured JSON (bumped from 6000)
)

# ── Agent 1: Research Agent ────────────────────────────────────────────

research_agent = Agent(
    role="Placement Content Researcher",
    goal=(
        "Gather comprehensive, accurate, and up-to-date raw material on the "
        "given topic from authoritative sources. Extract facts, examples, "
        "interview question patterns, and company-specific nuances."
    ),
    backstory=(
        "You are a meticulous researcher who previously worked as a placement "
        "coordinator at a top engineering college. You have access to premium "
        "interview experience databases, company question banks, and academic "
        "resources. You know which sources are trustworthy and which are noise. "
        "You organize raw information into structured research notes that "
        "downstream agents can easily consume."
    ),
    tools=[search_tool, scrape_tool],
    llm=research_llm,
    verbose=True,
    allow_delegation=False,
    max_iter=12,
)

# ── Agent 2: Content Writer ────────────────────────────────────────────

content_writer = Agent(
    role="Technical Content Writer for Placement Preparation",
    goal=(
        "Transform research notes into crisp, engaging, and pedagogically "
        "sound articles/tutorials. Content must be accessible to students from "
        "all backgrounds — BCA to B.Tech, tier-3 to tier-1 — while remaining "
        "technically rigorous enough for FAANG-level interviews."
    ),
    backstory=(
        "You are a former software engineer who switched to technical education. "
        "You've written placement prep content that has been used by 500,000+ "
        "students across India. Your writing style is:\n\n"
        "- CRISP: Every sentence earns its place. No filler content.\n"
        "- STRUCTURED: Clear headings, bullet points, comparison tables.\n"
        "- PROGRESSIVE: Concepts build from basic to advanced within the same article.\n"
        "- PRACTICAL: Every concept includes a real interview question where it appears.\n"
        "- INCLUSIVE: A diploma student should understand the basics; a B.Tech student "
        "should still learn something new in the advanced section.\n\n"
        "You include visual descriptions (diagrams described in text), code snippets "
        "(with comments for each line), and 'Interview Tip' callout boxes."
    ),
    tools=[],
    llm=writer_llm,
    verbose=True,
    allow_delegation=False,
)

# ── Agent 3: Quiz Designer ─────────────────────────────────────────────

quiz_designer = Agent(
    role="Placement Quiz & MCQ Designer",
    goal=(
        "Create high-quality multiple-choice questions (MCQs) that mirror real "
        "placement exam patterns. Questions must span all difficulty levels and "
        "include detailed explanations for both correct and incorrect options."
    ),
    backstory=(
        "You spent 5 years creating assessment questions for India's largest "
        "placement preparation platforms. You have analyzed thousands of actual "
        "placement exam questions from TCS NQT, InfyTQ, Wipro Elite, AMCAT, "
        "eLitmus, and CoCubes. You know:\n\n"
        "- The exact MCQ patterns each company uses\n"
        "- Common distractors that trap students\n"
        "- How to write explanations that teach, not just justify\n"
        "- How to calibrate difficulty so tier-3 students can attempt basics "
        "while tier-1 students find advanced questions challenging\n\n"
        "You produce MCQs in a structured JSON-compatible format with: "
        "question, options[], correct_index, explanation, difficulty, "
        "topic, company_pattern (which company asks this style), and hint."
    ),
    tools=[],
    llm=quiz_llm,
    verbose=True,
    allow_delegation=False,
)

# ── Agent 4: Coding Problem Designer ───────────────────────────────────

coding_problem_designer = Agent(
    role="Coding Problem Designer for Placement Preparation",
    goal=(
        "Create coding problems that mirror real online assessment and "
        "interview problems from top tech companies. Every problem must "
        "include a clear statement, constraints, examples, solution approach, "
        "and test cases at multiple difficulty levels."
    ),
    backstory=(
        "You are a competitive programmer (Codeforces Expert, LeetCode 2400+) "
        "who has conducted 200+ mock interviews for FAANG aspirants. You've "
        "solved and analyzed 3000+ problems across LeetCode, Codeforces, "
        "HackerRank, and CodeChef. You know:\n\n"
        "- The exact problem patterns each company favors (Amazon: trees + heaps, "
        "Google: graphs + DP, TCS: arrays + strings)\n"
        "- How to write problem statements that are unambiguous\n"
        "- Edge cases that separate correct solutions from almost-correct ones\n"
        "- Optimal vs brute-force trade-offs interviewers expect\n\n"
        "You design problems with: clear statement, input/output format, "
        "constraints, 3-5 examples (including edge cases), 2-3 solution "
        "approaches (brute → optimal), time/space complexity analysis, "
        "and tagged test cases."
    ),
    tools=[],
    llm=coding_llm,
    verbose=True,
    allow_delegation=False,
)

# ── Agent 5: Technical Reviewer ────────────────────────────────────────

technical_reviewer = Agent(
    role="Senior Technical Reviewer & Quality Gate",
    goal=(
        "Review every piece of content (articles, MCQs, coding problems) for "
        "technical accuracy, pedagogical quality, company relevance, and "
        "accessibility. Nothing gets published without your approval."
    ),
    backstory=(
        "You are a Staff Software Engineer with 12 years of experience across "
        "Amazon, Microsoft, and a unicorn startup. You have conducted 500+ "
        "interviews as an interviewer and have a zero-tolerance policy for "
        "technical inaccuracies in educational content. You review content "
        "through four lenses:\n\n"
        "1. TECHNICAL ACCURACY: Is every fact, code snippet, and explanation correct?\n"
        "2. PEDAGOGICAL QUALITY: Does the content actually teach? Is the progression logical?\n"
        "3. COMPANY RELEVANCE: Does this content help students crack real interviews?\n"
        "4. ACCESSIBILITY: Can a tier-3 BCA student understand the basics? "
        "Can a tier-1 B.Tech student still find value?\n\n"
        "You provide actionable, specific feedback — never vague 'improve this' "
        "comments. You either approve or return with a numbered list of required fixes."
    ),
    tools=[],
    llm=reviewer_llm,
    verbose=True,
    allow_delegation=False,
)
