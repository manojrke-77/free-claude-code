"""
Test the Reviewer agent in isolation against existing content output.

Reads the article, quiz, and coding output from the latest ds_arrays combined
JSON, creates a minimal Crew with just the Reviewer, and runs it standalone.
No Research/Writer/Quiz/Coding API calls — only the Reviewer.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# ── Load .env BEFORE any agent imports ─────────────────────────────────
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)

# Clear proxy env vars that would hijack Anthropic SDK calls
for _proxy_var in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
    if _proxy_var in os.environ:
        del os.environ[_proxy_var]

if not os.getenv("ANTHROPIC_API_KEY"):
    print("Missing ANTHROPIC_API_KEY — set it in advaita_agents/.env")
    sys.exit(1)

from crewai import Agent, Crew, LLM, Process, Task

# ═══════════════════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════════════════

TOPIC_ID = "ds_arrays"
TOPIC_LABEL = "Arrays & Strings"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMBINED_PATH = _PROJECT_ROOT / f"content_output/{TOPIC_ID}/combined_20260617_041928.json"

# ═══════════════════════════════════════════════════════════════════════
#  Load existing content
# ═══════════════════════════════════════════════════════════════════════

with open(COMBINED_PATH, encoding="utf-8") as f:
    combined = json.load(f)

article_raw = combined["article_content"]
quiz_raw = combined["quiz_content"]
coding_raw = combined["coding_problems"]

print(f"Loaded content:")
print(f"  article:  {len(article_raw):,} chars")
print(f"  quiz:     {len(quiz_raw):,} chars")
print(f"  coding:   {len(coding_raw):,} chars")

# ═══════════════════════════════════════════════════════════════════════
#  Build Reviewer agent (identical to content_agents.py)
# ═══════════════════════════════════════════════════════════════════════

reviewer_llm = LLM(
    model="anthropic/claude-sonnet-4-6",
    max_tokens=8192,
    base_url="https://api.anthropic.com",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
)

technical_reviewer = Agent(
    role="Technical Reviewer",
    goal="Ensure every piece of content is accurate, clear, and publication-ready",
    backstory=(
        "You review placement preparation content for accuracy and pedagogy. "
        "You verify code examples, check MCQ correctness, and ensure problems "
        "are well-specified with correct test cases."
    ),
    llm=reviewer_llm,
    verbose=True,
)

# ═══════════════════════════════════════════════════════════════════════
#  Build task with content directly embedded (no context= needed)
# ═══════════════════════════════════════════════════════════════════════

# Reuse the reviewer prompt structure from content_tasks.py but embed
# the actual content directly instead of relying on context from prior tasks.
review_prompt = f"""REVIEW all content produced for '{TOPIC_LABEL}' (ID: {TOPIC_ID}).

You are the QUALITY GATE. Nothing gets published without your approval.

TOKEN BUDGET WARNING — READ THIS FIRST (it overrides everything below):
You have ~8000 output tokens. Tracing every example by hand WILL exhaust
your budget before you can write the verdict JSON. The #1 pipeline failure
is: you trace 15+ examples, run out of tokens, and produce NO JSON at all.
A shallow review with a valid JSON verdict is INFINITELY better than a
thorough trace that produces nothing.

YOUR FIRST ACTION: Type a single opening curly brace. Then fill in the
JSON section by section — verdict first, then article_review, mcq_review,
coding_problems_review, required_fixes, reviewer_notes. Write the JSON AS
you review, not after you finish reviewing. If you notice token pressure,
stop tracing and note in reviewer_notes: 'Spot-checked N/M items — token
limit reached.'

--- CONTENT TO REVIEW ---

=== ARTICLE ===
{article_raw}

=== QUIZ ===
{quiz_raw}

=== CODING PROBLEMS ===
{coding_raw}

--- REVIEW CHECKLIST (apply inside the JSON as you write it) ---

REVIEW THE ARTICLE through four lenses:

1. TECHNICAL ACCURACY (non-negotiable):
   - Is every concept definition correct?
   - Do ALL code examples compile and produce correct output?
   - Are complexity analyses (time/space) correct?
   - Are there any factual errors, even minor ones?

2. PEDAGOGICAL QUALITY:
   - Does the article teach effectively? Or just list facts?
   - Is the progression logical? (beginner → intermediate → advanced)
   - Are examples concrete or abstract? (concrete > abstract)
   - Would a tier-3 BCA student understand the beginner section?
   - Would a tier-1 B.Tech student find value in the advanced section?

3. COMPANY RELEVANCE:
   - Are the interview tips accurate for the tagged companies?
   - Are the practice problems representative of what those companies ask?
   - Is the difficulty calibration correct?

4. ACCESSIBILITY & CRISPNESS:
   - Is there filler content that should be cut?
   - Are any critical subtopics from the taxonomy MISSING?
   - Is the language clear, or are there jargon-heavy passages
     without explanation?

REVIEW THE MCQs:
   - Is every correct answer actually correct?
   - Are the distractors plausible? (obviously wrong distractors = bad MCQ)
   - Are explanations accurate and educational?

REVIEW THE CODING PROBLEMS:
   - Are problem statements unambiguous?
   - Do test cases cover edge cases?
   - Are solutions truly optimal? Verify complexity analysis.
   - Are hints progressive (not giving away the solution in hint 1)?

DECISION:
- APPROVE: All checks pass. Ready for publish.
- APPROVE WITH MINOR FIXES: Small issues (typo, formatting) —
  list them, content can publish after fixes.
- REJECT WITH REQUIRED FIXES: Technical errors or major gaps —
  provide a numbered list of SPECIFIC required changes.
  Do not say 'improve the explanation' — say exactly what's wrong
  and what the correct explanation should be.

SPOT-CHECK (trace 2-3 examples per article section, 2-3 per coding
problem — NOT all of them):
1. Trace 2-3 examples/test cases per coding problem. Wrong expected
   outputs are the most damaging error — but sampling catches them.
   If a spot-check reveals an error, dig deeper on THAT problem only.
2. Cross-check test case inputs against stated constraints.
   If N_min=1, there must be no empty-array test case.
3. Verify subarray-counting problems: count each valid subarray
   individually and verify the total.
4. Check that solution descriptions match the code (e.g. if the text
   says 'count evens to the left of each odd' but the code counts odds
   to the left of each even, flag it).
5. Flag any vague/falsifiable claims (e.g. 'X engineers use this'
   without evidence).

⛔ FINAL REMINDER: Token budget warning from above still applies.
Your ENTIRE response must be ONE valid JSON object. First character =
single opening curly brace. Last character = single closing curly brace.
No 'Thought:', no 'Let me', no preamble. No trailing text. If you catch
yourself drafting a trace instead of JSON — STOP and switch to JSON
immediately. A 500-token review with valid JSON beats an 8000-token
trace with nothing. WRITE THE JSON FIRST."""

review_task = Task(
    description=review_prompt,
    expected_output=(
        "Review report JSON:\n"
        "{{\n"
        "  'verdict': 'approved'|'approved_with_minor_fixes'|'rejected',\n"
        "  'article_review': {{\n"
        "    'technical_errors': [...],\n"
        "    'pedagogical_issues': [...],\n"
        "    'completeness': {{'covered_subtopics': [...], 'missing_subtopics': [...]}},\n"
        "    'accessibility_score': <1-10>,\n"
        "    'crispness_score': <1-10>\n"
        "  }},\n"
        "  'mcq_review': {{...}},\n"
        "  'coding_problems_review': {{...}},\n"
        "  'required_fixes': ['<numbered list>'],\n"
        "  'reviewer_notes': '<summary>'\n"
        "}}"
    ),
    agent=technical_reviewer,
)

# ═══════════════════════════════════════════════════════════════════════
#  Run
# ═══════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print(f"  Reviewer Isolation Test — {TOPIC_LABEL}")
print("=" * 60)

crew = Crew(
    name="ReviewerIsolationTest",
    agents=[technical_reviewer],
    tasks=[review_task],
    process=Process.sequential,
    verbose=True,
    memory=False,
)

result = crew.kickoff()
raw_output = str(result) if result is not None else ""

print("\n" + "=" * 60)
print("  Reviewer Output")
print("=" * 60)
print(f"\nRaw output ({len(raw_output):,} chars):")
print(raw_output[:500])
if len(raw_output) > 500:
    print(f"... ({len(raw_output) - 500} more chars)")

# ── Validate ──────────────────────────────────────────────────────────
from advaita_agents.main import _strip_code_fences, _strip_double_braces

review_text = _strip_code_fences(raw_output)
review_text = _strip_double_braces(review_text)

# Check for "Thought:" preamble
if review_text.strip().startswith("Thought:") or review_text.strip().startswith("Let me"):
    print("\n[FAIL] Reviewer output starts with 'Thought:'/'Let me' preamble!")
else:
    print("\n[OK] Reviewer output does NOT start with preamble.")

# Try JSON parse
try:
    parsed = json.loads(review_text)
    print(f"[OK] Valid JSON. Verdict: {parsed.get('verdict', 'MISSING')}")
    fixes = parsed.get("required_fixes", [])
    print(f"[OK] Fixes listed: {len(fixes)}")
    for f in fixes[:3]:
        print(f"     - {f[:120]}...")
except json.JSONDecodeError as exc:
    pos = exc.pos
    context = review_text[max(0, pos - 50):pos + 50] if pos > 0 else "N/A"
    print(f"[FAIL] Invalid JSON: {exc}")
    print(f"  Position {pos} context: '{context}'")
