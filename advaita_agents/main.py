"""
AdvaitaCode Placement Content Engine — Main Orchestrator.

Commands:
1. interactive — Interactive wizard (pick subject → topics → sub-topics → produce)
2. roadmap — Run Topic Strategist to generate/refresh the content roadmap
3. produce — Run Content Production for topics in the roadmap
4. gap — Run gap analysis on published content

Usage:
    uv run advaita_agents/main.py interactive        # Interactive content wizard
    uv run advaita_agents/main.py roadmap            # Generate content roadmap
    uv run advaita_agents/main.py produce            # Produce content for TIER 1 topics
    uv run advaita_agents/main.py produce --topic-id ds_arrays  # Produce for one topic
    uv run advaita_agents/main.py produce --topic-id ds_arrays --skip-checkpoints  # No human gates
    uv run advaita_agents/main.py gap                # Run gap analysis on published content
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# ── Load .env BEFORE any agent imports ─────────────────────────────────
# Crew AI instantiates LLM at Agent definition time (module level).
# Environment variables must be set before Python evaluates those imports.
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)

# Clear proxy env vars that would hijack Anthropic SDK calls.
# The free-claude-code proxy sets ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN
# in the shell — if inherited, the SDK routes to localhost instead of api.anthropic.com.
for _proxy_var in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
    if _proxy_var in os.environ:
        del os.environ[_proxy_var]

# Double-check required env vars are set
# DEEPSEEK: Research Agent (tool calls) + Topic Strategist (roadmap planning)
# CLAUDE: Writer, Quiz Designer, Coding Problem Designer, Technical Reviewer
_MISSING_KEYS: list[str] = []
if not os.getenv("DEEPSEEK_API_KEY"):
    _MISSING_KEYS.append(
        "DEEPSEEK_API_KEY -> needed by Research Agent + Topic Strategist"
    )
if not os.getenv("ANTHROPIC_API_KEY"):
    _MISSING_KEYS.append(
        "ANTHROPIC_API_KEY -> needed by 4 Claude agents (Writer, Quiz, Coding, Reviewer)"
    )
if not os.getenv("SERPER_API_KEY"):
    _MISSING_KEYS.append(
        "SERPER_API_KEY -> needed by Topic Strategist + Research Agent (web search)"
    )

if _MISSING_KEYS:
    print("MISSING API keys:")
    for key in _MISSING_KEYS:
        print(f"   - {key}")
    print("\n   Get keys at:")
    print("   - DeepSeek:  https://platform.deepseek.com/api_keys")
    print("   - Serper:    https://serper.dev")
    print(f"\n   Update {_ENV_PATH} and re-run.")
    sys.exit(1)

from advaita_agents.crew import (  # noqa: E402
    create_content_generation_crew,
    create_reviewer_crew,
    create_topic_strategy_crew,
)
from advaita_agents.taxonomy import (  # noqa: E402
    build_topic_map,
    compute_topic_score,
    flatten_taxonomy,
    topic_is_ready,
)

# ── Paths ──────────────────────────────────────────────────────────────

ROADMAP_FILE = Path("roadmap.json")
GAP_REPORT_FILE = Path("gap_report.json")
CONTENT_OUTPUT_DIR = Path("content_output")
PUBLISHED_INDEX_FILE = Path("published_index.json")


# ── Helpers ────────────────────────────────────────────────────────────


def load_json(path: Path) -> dict:
    """Load a JSON file, return empty dict if missing."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_json(path: Path, data: dict) -> None:
    """Save data as formatted JSON."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_published_index() -> dict[str, float]:
    """Load the published content index: {topic_id: coverage_pct}."""
    return load_json(PUBLISHED_INDEX_FILE)


def generate_roadmap(demand_signals: dict, existing_coverage: dict) -> dict:
    """Generate a scored and tiered roadmap from the taxonomy.

    This is a local fallback — the Topic Strategist agent produces a richer
    roadmap. Use this when you need a quick score without API calls.
    """
    topics = flatten_taxonomy()
    scored: list[dict] = []

    for topic in topics:
        score = compute_topic_score(topic, demand_signals, existing_coverage)
        topic["score"] = score
        topic["ready"] = topic_is_ready(topic["id"], set(existing_coverage.keys()))
        scored.append(topic)

    # Sort by score descending
    scored.sort(key=lambda t: t["score"], reverse=True)

    # Tier assignment
    tier_1, tier_2, tier_3 = [], [], []
    for t in scored:
        if t["score"] >= 7.0:
            tier_1.append(t)
        elif t["score"] >= 4.5:
            tier_2.append(t)
        else:
            tier_3.append(t)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_topics": len(scored),
            "tier_1_count": len(tier_1),
            "tier_2_count": len(tier_2),
            "tier_3_count": len(tier_3),
        },
        "tier_1": tier_1,
        "tier_2": tier_2,
        "tier_3": tier_3,
    }


# ── Commands ───────────────────────────────────────────────────────────


def cmd_roadmap() -> None:
    """Run the Topic Strategy Crew to generate a fresh roadmap."""
    print(f"\n{'=' * 60}")
    print("  AdvaitaCode -- Topic Strategy Crew")
    print("  Generating Content Roadmap...")
    print(f"{'=' * 60}")

    crew = create_topic_strategy_crew()
    result = crew.kickoff()

    # CrewAI 1.6+ returns CrewOutput; extract raw string for JSON parsing
    output_path = ROADMAP_FILE
    raw = str(result) if result is not None else ""

    try:
        data = json.loads(raw)
    except json.JSONDecodeError, TypeError:
        data = {
            "raw_output": raw,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    save_json(output_path, data)
    print(f"\n[OK] Roadmap saved to {output_path}")

    # Also generate the lightweight scored version
    demand: dict = {}
    if isinstance(data, dict) and "demand_signals" in data:
        ds = data["demand_signals"]
        if isinstance(ds, dict):
            demand = ds

    coverage = load_published_index()
    scored = generate_roadmap(demand, coverage)
    scored_path = Path("roadmap_scored.json")
    save_json(scored_path, scored)
    print(f"[OK] Scored roadmap saved to {scored_path}")

    # Print summary
    s = scored["summary"]
    print("\n[DATA] Roadmap Summary:")
    print(f"   Total topics: {s['total_topics']}")
    print(f"   TIER 1 (Must Have): {s['tier_1_count']}")
    print(f"   TIER 2 (Should Have): {s['tier_2_count']}")
    print(f"   TIER 3 (Nice to Have): {s['tier_3_count']}")

    if s["tier_1_count"] > 0:
        print("\n-> Top 5 TIER 1 Topics:")
        for t in scored["tier_1"][:5]:
            print(f"   [{t['score']:.1f}] {t['label']} ({t['id']})")


def cmd_produce(
    topic_id: str | None = None,
    language: str = "python",
    skip_checkpoints: bool = False,
) -> None:
    """Run the Content Production Crew for topic(s).

    If topic_id is given, produce for that one topic.
    Otherwise, produce for all TIER 1 topics in the roadmap.
    """
    if topic_id:
        _produce_topic(topic_id, language, skip_checkpoints=skip_checkpoints)
    else:
        roadmap = load_json(ROADMAP_FILE)
        if not roadmap:
            print("[FAIL] No roadmap found. Run 'roadmap' first.")
            sys.exit(1)

        tier_1 = roadmap.get("tier_1", [])
        if not tier_1:
            # Try scored roadmap
            scored = load_json(Path("roadmap_scored.json"))
            tier_1 = scored.get("tier_1", [])

        if not tier_1:
            print("[FAIL] No TIER 1 topics in roadmap.")
            sys.exit(1)

        print(f"\n[...] Producing content for {len(tier_1)} TIER 1 topics...\n")
        for i, topic in enumerate(tier_1, 1):
            tid = topic.get("id") or topic.get("topic_id", "")
            label = topic.get("label") or topic.get("topic_label", tid)
            print(f"\n{'=' * 50}")
            print(f"  [{i}/{len(tier_1)}] {label}")
            print(f"{'=' * 50}")
            _produce_topic(tid, language, skip_checkpoints=skip_checkpoints)


def _validate_task_outputs(
    task_outputs: dict[str, str | None],
    expected_quiz_count: int,
    expected_coding_count: int,
) -> list[str]:
    """Validate JSON structure of quiz and coding task outputs.

    Checks for truncation, missing JSON, and item count mismatches.
    Returns a list of validation error messages (empty = all passed).
    Call BEFORE the Reviewer's verdict is shown, so structural failures
    are surfaced immediately rather than being buried in the review JSON.
    """
    errors: list[str] = []

    # ── Quiz validation ──────────────────────────────────────────────────
    quiz_raw = task_outputs.get("quiz_content")
    if quiz_raw:
        # Strip markdown code fences if present
        quiz_text = _strip_code_fences(quiz_raw)
        # Check for "Thought:" preamble — same failure mode as Coding agent
        if quiz_text.strip().startswith("Thought") or quiz_text.strip().startswith(
            "Let me"
        ):
            errors.append(
                "QUIZ: Output starts with 'Thought:' or 'Let me...' preamble, "
                "not JSON. The Quiz agent submitted its internal design traces "
                "instead of formatted MCQ objects. Re-run the pipeline."
            )
        elif not quiz_text.strip().startswith("["):
            errors.append(
                f"QUIZ: Output does not start with '['. First 80 chars: "
                f"'{quiz_text.strip()[:80]}'. This is likely not valid JSON."
            )
        else:
            try:
                quiz_parsed = json.loads(quiz_text)
            except json.JSONDecodeError as exc:
                pos = exc.pos
                snippet = quiz_text[max(0, pos - 40) : pos + 40] if pos > 0 else "N/A"
                errors.append(
                    f"QUIZ: JSON is invalid — {exc}. Position {pos} context: '{snippet}'. "
                    "Quiz output is likely truncated mid-JSON (not enough max_tokens) "
                    "or contains unquoted internal monologue."
                )
            else:
                if not isinstance(quiz_parsed, list):
                    errors.append(
                        f"QUIZ: Expected a JSON array, got {type(quiz_parsed).__name__}. "
                        "The Quiz agent may have submitted scratch notes instead of "
                        "formatted JSON."
                    )
                elif len(quiz_parsed) < expected_quiz_count:
                    errors.append(
                        f"QUIZ: Expected {expected_quiz_count} questions, "
                        f"got {len(quiz_parsed)}. Missing "
                        f"{expected_quiz_count - len(quiz_parsed)} questions. "
                        "Quiz output may be truncated — check max_tokens."
                    )
                else:
                    # Per-question validation
                    for i, q in enumerate(quiz_parsed):
                        qid = q.get("id", f"q[{i}]")
                        if not isinstance(q, dict):
                            errors.append(
                                f"QUIZ {qid}: Not a valid object — may be truncated."
                            )
                            break
                        if "correct_index" not in q:
                            errors.append(f"QUIZ {qid}: Missing 'correct_index' field.")
                        if "options" not in q or not isinstance(q["options"], list):
                            errors.append(
                                f"QUIZ {qid}: Missing or invalid 'options' array."
                            )
                        elif q.get("correct_index", -1) >= len(q.get("options", [])):
                            errors.append(
                                f"QUIZ {qid}: correct_index "
                                f"{q.get('correct_index')} is out of range "
                                f"(only {len(q['options'])} options)."
                            )
    elif expected_quiz_count > 0:
        errors.append(
            "QUIZ: No quiz content produced at all — agent may have failed silently."
        )

    # ── Coding problems validation ───────────────────────────────────────
    coding_raw = task_outputs.get("coding_problems")
    if coding_raw:
        coding_text = _strip_code_fences(coding_raw)
        # Check for "Thought:" preamble — the most common format compliance failure
        if coding_text.strip().startswith("Thought") or coding_text.strip().startswith(
            "Let me"
        ):
            errors.append(
                "CODING: Output starts with design scratch-notes ('Thought:' or "
                "'Let me...'), not JSON. The Coding agent submitted its internal "
                "traces instead of formatted problem objects. Re-run the pipeline."
            )
        elif not coding_text.strip().startswith("["):
            errors.append(
                f"CODING: Output does not start with '['. First 80 chars: "
                f"'{coding_text.strip()[:80]}'. This is likely not valid JSON."
            )
        else:
            try:
                coding_parsed = json.loads(coding_text)
                if not isinstance(coding_parsed, list):
                    errors.append(
                        f"CODING: Expected a JSON array, got {type(coding_parsed).__name__}."
                    )
                elif len(coding_parsed) < expected_coding_count:
                    errors.append(
                        f"CODING: Expected {expected_coding_count} problems, "
                        f"got {len(coding_parsed)}. Missing "
                        f"{expected_coding_count - len(coding_parsed)} problems. "
                        "Coding output may be truncated — check max_tokens."
                    )
                else:
                    for i, cp in enumerate(coding_parsed):
                        cpid = cp.get("id", f"cp[{i}]")
                        if not isinstance(cp, dict):
                            errors.append(
                                f"CODING {cpid}: Not a valid object — may be truncated."
                            )
                            break
            except json.JSONDecodeError as exc:
                pos = exc.pos
                snippet = coding_text[max(0, pos - 40) : pos + 40] if pos > 0 else "N/A"
                errors.append(
                    f"CODING: JSON is invalid — {exc}. Position {pos} context: "
                    f"'{snippet}'. Output is likely truncated (not enough max_tokens) "
                    "or contains invalid JSON constructs."
                )
    elif expected_coding_count > 0:
        errors.append(
            "CODING: No coding problems produced at all — agent may have failed silently."
        )

    # ── Review report validation ────────────────────────────────────────────
    review_raw = task_outputs.get("review_report")
    if review_raw:
        review_text = _strip_code_fences(review_raw)
        review_text = _strip_double_braces(review_text)
        if review_text.strip().startswith("Thought") or review_text.strip().startswith(
            "Let me"
        ):
            errors.append(
                "REVIEW: Output starts with 'Thought:' or 'Let me...' preamble, "
                "not the review JSON. The Reviewer consumed all tokens on internal "
                "monologue and produced no verdict. Re-run the pipeline."
            )
        elif not review_text.strip().startswith("{"):
            errors.append(
                f"REVIEW: Output does not start with '{{'. First 80 chars: "
                f"'{review_text.strip()[:80]}'. This is likely not a valid review JSON."
            )
        else:
            try:
                review_parsed = json.loads(review_text)
                if not isinstance(review_parsed, dict):
                    errors.append(
                        f"REVIEW: Expected a JSON object, got {type(review_parsed).__name__}."
                    )
                elif "verdict" not in review_parsed:
                    errors.append(
                        "REVIEW: Missing 'verdict' field — Reviewer did not produce a decision."
                    )
            except json.JSONDecodeError as exc:
                pos = exc.pos
                snippet = review_text[max(0, pos - 40) : pos + 40] if pos > 0 else "N/A"
                errors.append(
                    f"REVIEW: JSON is invalid — {exc}. Position {pos} context: "
                    f"'{snippet}'. Review output may be truncated or malformed."
                )
    elif "review_report" in task_outputs:
        # Review report key exists but is empty/None — only flag when expected
        errors.append(
            "REVIEW: No review report produced at all — Reviewer may have failed silently."
        )

    return errors


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from agent output."""
    stripped = text.strip()
    if stripped.startswith("```json") or stripped.startswith("```"):
        # Find end of first line (the opening fence)
        first_nl = stripped.find("\n")
        if first_nl != -1:
            stripped = stripped[first_nl + 1 :]
        # Find and remove closing fence
        last_fence = stripped.rfind("```")
        if last_fence != -1:
            stripped = stripped[:last_fence]
    return stripped.strip()


def _strip_double_braces(text: str) -> str:
    """Normalize double-brace ``{{ ... }}`` wrapper to single-brace ``{ ... }``.

    The Reviewer agent sometimes reads the ``expected_output`` template's
    escaped braces literally and outputs ``{{...}}`` instead of ``{...}``.
    This strips the extra brace if present, handling leading/trailing whitespace.
    """
    stripped = text.strip()
    if stripped.startswith("{{") and stripped.endswith("}}"):
        # Check that removing both outer braces yields balanced inner content
        inner = stripped[1:-1]  # strip first { and last }
        inner_stripped = inner.strip()
        if inner_stripped.startswith("{") and inner_stripped.endswith("}"):
            # Double-brace wrapper detected: {{ { ... } }}
            return inner_stripped
    return text


def _validate_coding_solutions(
    coding_raw: str | None,
    *,
    fix: bool = False,
) -> tuple[list[str], str | None]:
    """Run every coding problem's solution against its test cases and examples.

    Extracts the optimal solution code from each problem, parses the function
    signature, then executes it against every test case input. Returns
    ``(mismatches, corrected_json_or_None)``.

    When *fix* is True and mismatches are found, the function corrects the
    expected/output values in the parsed problem dicts to match what the
    solution code ACTUALLY produces, then returns the corrected JSON string.
    This eliminates the #1 pipeline rejection cause: the Coding agent invents
    wrong expected outputs that its own solution doesn't produce.
    """
    if not coding_raw:
        return [], None

    coding_text = _strip_code_fences(coding_raw)
    try:
        problems = json.loads(coding_text)
    except json.JSONDecodeError as exc:
        return [f"CODING SOLUTIONS: Cannot parse coding JSON — {exc}"], None

    if not isinstance(problems, list):
        return [], None

    mismatches: list[str] = []
    fixes_applied = 0

    for prob_index, problem in enumerate(problems):
        if not isinstance(problem, dict):
            continue
        pid = problem.get("id", f"problem[{prob_index}]")
        solution = problem.get("solution", {})
        if not isinstance(solution, dict):
            continue

        optimal = solution.get("optimal", {})
        if not isinstance(optimal, dict):
            continue

        code = optimal.get("code", "")
        if not code:
            # Fall back to brute force if optimal is missing
            brute = solution.get("brute_force", {})
            if isinstance(brute, dict):
                code = brute.get("code", "")
        if not code:
            mismatches.append(
                f"{pid}: No solution code found — cannot verify test cases."
            )
            continue

        # ── Extract function name and parameters from code ───────────
        import re as _re

        fn_match = _re.search(r"^def\s+(\w+)\s*\(", code, _re.MULTILINE)
        if not fn_match:
            mismatches.append(
                f"{pid}: Cannot parse function signature from solution code."
            )
            continue

        fn_name = fn_match.group(1)
        paren_start = fn_match.end()  # position right after '('
        # Find matching ')' handling nested parens in type hints
        depth = 1
        paren_end = paren_start
        for i in range(paren_start, len(code)):
            if code[i] == "(":
                depth += 1
            elif code[i] == ")":
                depth -= 1
                if depth == 0:
                    paren_end = i
                    break
        if depth != 0:
            mismatches.append(
                f"{pid}: Cannot parse function parameters — unbalanced parentheses."
            )
            continue

        # Build a clean namespace for safe execution
        # Include __import__ so solution code can use standard library modules
        # (e.g. collections.deque, collections.defaultdict, math.inf, heapq)
        import collections as _collections
        import functools as _functools
        import heapq as _heapq
        import itertools as _itertools
        import math as _math

        _allowed_modules = {
            "collections": _collections,
            "math": _math,
            "heapq": _heapq,
            "itertools": _itertools,
            "functools": _functools,
        }

        def _safe_import(name, *args, **kwargs):
            if name in _allowed_modules:
                return _allowed_modules[name]
            raise ImportError(
                f"Import '{name}' is not allowed in coding problem validation"
            )

        safe_namespace: dict = {
            "__builtins__": {
                "len": len,
                "range": range,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "int": int,
                "str": str,
                "float": float,
                "bool": bool,
                "chr": chr,
                "ord": ord,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "sorted": sorted,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "reversed": reversed,
                "any": any,
                "all": all,
                "True": True,
                "False": False,
                "None": None,
                "print": print,
                "isinstance": isinstance,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "KeyError": KeyError,
                "IndexError": IndexError,
                "Exception": Exception,
                "__import__": _safe_import,
            },
            "__name__": "__validation__",
        }

        # ── Execute the solution code in the sandbox ──────────────────
        try:
            exec(code, safe_namespace)
        except Exception as exc:
            mismatches.append(f"{pid}: Solution code failed to compile/run: {exc}")
            continue

        fn = safe_namespace.get(fn_name)
        if not callable(fn):
            mismatches.append(
                f"{pid}: Function '{fn_name}' not found after executing solution code."
            )
            continue

        # ── Validate (and optionally fix) examples ────────────────────
        examples = problem.get("examples", [])
        if isinstance(examples, list):
            for ex_i, example in enumerate(examples):
                if not isinstance(example, dict):
                    continue
                err, actual = _check_one_case(
                    fn, fn_name, example, pid, f"Example {ex_i + 1}"
                )
                if err:
                    mismatches.append(err)
                    if fix and actual is not _NO_VALUE:
                        key = "expected" if "expected" in example else "output"
                        old = example.get(key, "")
                        example[key] = json.dumps(actual)
                        fixes_applied += 1
                        mismatches.append(
                            f"  └─ [AUTO-FIXED] {key}: {old!r} → {example[key]!r}"
                        )

        # ── Validate (and optionally fix) test cases ──────────────────
        test_cases = problem.get("test_cases", [])
        if isinstance(test_cases, list):
            for tc_i, tc in enumerate(test_cases):
                if not isinstance(tc, dict):
                    continue
                err, actual = _check_one_case(
                    fn, fn_name, tc, pid, f"Test case {tc_i + 1}"
                )
                if err:
                    mismatches.append(err)
                    if fix and actual is not _NO_VALUE:
                        key = "expected" if "expected" in tc else "output"
                        old = tc.get(key, "")
                        tc[key] = json.dumps(actual)
                        fixes_applied += 1
                        mismatches.append(
                            f"  └─ [AUTO-FIXED] {key}: {old!r} → {tc[key]!r}"
                        )

    corrected_json: str | None = None
    if fix and fixes_applied > 0:
        corrected_json = json.dumps(problems, indent=2, ensure_ascii=False)

    return mismatches, corrected_json


_NO_VALUE = (
    object()
)  # sentinel: no actual value computed (parse error, compile error, etc.)


def _check_one_case(
    fn,
    fn_name: str,
    case: dict,
    problem_id: str,
    case_label: str,
) -> tuple[str | None, object]:
    """Execute one test case against the solution function.

    Supports these input formats:
    - ``"[3, 7, 1, 9, 4]"`` — bare value, passed as single positional arg
    - ``"stalls = [1,2,3]\\nk = 2"`` — newline-separated assignments
    - ``"stalls = [1,2,3], k = 2"`` — comma-separated assignments on one line

    Returns ``(error_message_or_None, actual_computed_value)``.  The second
    element is ``_NO_VALUE`` when the case could not be executed at all
    (parse error, compile error, etc.), otherwise the function's return value.
    """
    import ast as _ast
    import inspect as _inspect

    input_str = case.get("input", "")
    expected_str = case.get("expected") or case.get("output", "")
    if not input_str:
        return None, _NO_VALUE

    # ── Parse expected value ───────────────────────────────────────────
    try:
        expected_val = _ast.literal_eval(expected_str)
    except ValueError, SyntaxError:
        expected_val = expected_str

    # ── Parse inputs into a local namespace ────────────────────────────
    local_ns: dict = {}

    # Strategy A: try splitting by newlines, then try comma-separated multi-assign
    lines = [line.strip() for line in input_str.split("\n") if line.strip()]
    if not lines:
        lines = [input_str.strip()]

    def _exec_line(ns: dict, line: str) -> bool:
        """Execute one line. Return True if it produced variables."""
        before = set(ns.keys())
        try:
            exec(line, {}, ns)
            return True
        except SyntaxError:
            # Try splitting commas: "a = [1,2], b = 3" → "a = [1,2]" , "b = 3"
            parts = _split_assignments(line)
            if len(parts) > 1:
                for part in parts:
                    try:
                        exec(part, {}, ns)
                    except Exception:
                        return False
                return len(ns) > len(before)
            return False
        except Exception:
            return False

    for line in lines:
        _exec_line(local_ns, line)

    # Strategy B: no variables created → treat whole input as a bare literal
    if not local_ns:
        try:
            bare_val = _ast.literal_eval(input_str.strip())
        except ValueError, SyntaxError:
            # Last resort: exec as expression
            try:
                bare_val = eval(input_str.strip(), {}, {})
            except Exception as exc:
                return (
                    f"{problem_id} {case_label}: Cannot parse input — {exc}. "
                    f"Input: '{input_str[:80]}'"
                ), _NO_VALUE
        local_ns = {"__arg__": bare_val}

    # ── Call the function ──────────────────────────────────────────────
    sig = _inspect.signature(fn)
    param_names = list(sig.parameters.keys())

    try:
        if len(param_names) == 1 and len(local_ns) == 1:
            # Single param: pass the sole variable (or bare literal)
            actual = fn(next(iter(local_ns.values())))
        elif len(local_ns) >= len(param_names):
            # Try keyword matching first (input var names → param names)
            kwargs = {k: v for k, v in local_ns.items() if k in param_names}
            if len(kwargs) == len(param_names):
                actual = fn(**kwargs)
            else:
                # Positional fallback: order of local_ns values
                actual = fn(*list(local_ns.values())[: len(param_names)])
        else:
            # Fewer vars than params — pass what we have positionally
            actual = fn(*list(local_ns.values()))
    except Exception as exc:
        return (
            f"{problem_id} {case_label}: Solution raised {type(exc).__name__}: {exc}",
            _NO_VALUE,
        )

    # ── Compare ───────────────────────────────────────────────────────
    if actual != expected_val:
        return (
            f"{problem_id} {case_label}: MISMATCH — "
            f"got {actual!r}, expected {expected_str!r}. "
            f"Input: {input_str[:100]}"
        ), actual

    return None, _NO_VALUE


def _split_assignments(line: str) -> list[str]:
    """Split comma-separated assignments like 'a = [1,2], b = 3' into ['a = [1,2]', 'b = 3'].

    Must handle commas inside brackets, parens, and quoted strings.
    """
    parts: list[str] = []
    current: list[str] = []
    depth_paren = 0
    depth_bracket = 0
    in_single_quote = False
    in_double_quote = False

    for ch in line:
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif not in_single_quote and not in_double_quote:
            if ch == "(":
                depth_paren += 1
            elif ch == ")":
                depth_paren -= 1
            elif ch == "[":
                depth_bracket += 1
            elif ch == "]":
                depth_bracket -= 1
            elif ch == "," and depth_paren == 0 and depth_bracket == 0:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                continue
        current.append(ch)

    if current:
        part = "".join(current).strip()
        if part:
            parts.append(part)

    return parts


def _produce_topic(
    topic_id: str,
    language: str = "python",
    label: str | None = None,
    subtopics: list[str] | None = None,
    difficulties: str | None = None,
    content_types: str | None = None,
    companies: str | None = None,
    skip_checkpoints: bool = False,
) -> None:
    """Run content production for a single topic.

    Uses the split pipeline: Phase 1 (generation) → Checkpoint #1 →
    Phase 2 (reviewer) → Checkpoint #2 → publish.

    Args:
        topic_id: Taxonomy topic ID (e.g. "ds_arrays") or custom ID.
        language: Programming language for code examples.
        label: Override the human-readable label (used for custom topics).
        subtopics: Optional custom sub-topic list. Falls back to taxonomy.
        difficulties: Comma-separated difficulty levels override.
        content_types: Comma-separated content types override.
        companies: Comma-separated company list override.
        skip_checkpoints: If True, auto-approve both checkpoints (for CI/non-TTY).
    """
    topic_map = build_topic_map()
    topic = topic_map.get(topic_id)

    if topic:
        label = label or topic["label"]
        difficulties = difficulties or ",".join(topic.get("difficulties", ["beginner"]))
        content_types = content_types or ",".join(
            topic.get("content_types", ["article"])
        )
        companies = companies or ",".join(topic.get("companies", ["all"])[:5])
        if subtopics is None:
            subtopics = list(topic.get("subtopics", []))
    else:
        # Custom topic — use provided values or sensible defaults
        label = label or topic_id.replace("custom_", "").replace("_", " ").title()
        difficulties = difficulties or "beginner"
        content_types = content_types or "article,mcq"
        companies = companies or "all"
        if subtopics is None:
            subtopics = []
        print(f"[DATA] Custom topic: {label} (no taxonomy entry)")

    # Build sub-topic context string for the research task
    subtopic_context = ""
    if subtopics:
        subtopic_context = (
            "FOCUS ON THESE SPECIFIC SUB-TOPICS:\n"
            + "\n".join(f"- {s}" for s in subtopics)
            + "\n\n"
        )

    # Determine number of questions/problems
    num_quiz = 10 if "mcq" in content_types else 0
    num_coding = 3 if "coding" in content_types else 0

    # ── Phase 1: Content Generation (4 agents, no Reviewer) ───────────────
    gen_crew = create_content_generation_crew()
    gen_result = gen_crew.kickoff(
        inputs={
            "topic_id": topic_id,
            "topic_label": label,
            "subtopic_context": subtopic_context,
            "difficulty_levels": difficulties,
            "content_types": content_types,
            "language": language,
            "num_quiz_questions": str(num_quiz),
            "num_coding_problems": str(num_coding),
            "company_context": companies,
        }
    )

    # Set up output directory
    CONTENT_OUTPUT_DIR.mkdir(exist_ok=True)
    topic_dir = CONTENT_OUTPUT_DIR / topic_id
    topic_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    # ── Extract generation task outputs (research, article, quiz, coding) ──
    gen_task_names = [
        "research_notes",
        "article_content",
        "quiz_content",
        "coding_problems",
    ]
    task_outputs: dict[str, str | None] = dict.fromkeys(gen_task_names)

    tasks_raw_list = getattr(gen_result, "tasks_output", None)
    if isinstance(tasks_raw_list, list) and tasks_raw_list:
        for i, task_output in enumerate(tasks_raw_list):
            if i >= len(gen_task_names):
                break
            raw = (
                str(task_output)
                if task_output is None
                else str(getattr(task_output, "raw", task_output))
            )
            key = gen_task_names[i]
            task_outputs[key] = raw
            _save_task_output(topic_dir, key, raw, timestamp)
            print(f"[OK] {key} saved to {topic_dir / f'{key}_{timestamp}.json'}")
    else:
        print("[ERROR] No tasks_output from generation crew — cannot continue.")
        return

    # ── Validate task outputs (JSON structure, truncation, format compliance) ─
    validation_errors = _validate_task_outputs(task_outputs, num_quiz, num_coding)
    if validation_errors:
        print("\n[VALIDATE] Post-production validation found issues:")
        for err in validation_errors:
            print(f"   [FAIL] {err}")
    else:
        print("\n[VALIDATE] Quiz and coding JSON outputs structurally valid.")

    # ── Auto-fix: validate coding solutions against test cases ─────────────
    if num_coding > 0 and task_outputs.get("coding_problems"):
        solution_errors, corrected_coding = _validate_coding_solutions(
            task_outputs["coding_problems"], fix=True
        )
        if solution_errors:
            actual_errors = [e for e in solution_errors if not e.startswith("  └─")]
            auto_fixes = [e for e in solution_errors if e.startswith("  └─")]
            print(
                f"\n[SOLUTION] Solution vs test case validation found "
                f"{len(actual_errors)} issue(s):"
            )
            for err in actual_errors:
                print(f"   [MISMATCH] {err}")
            if auto_fixes:
                print(
                    f"   [AUTO-FIXED] Corrected {len(auto_fixes)} expected "
                    f"value(s) to match the solution code's actual output."
                )
            else:
                print(
                    "   [SOLUTION] These test cases have WRONG expected outputs "
                    "and could not be auto-corrected."
                )
        else:
            print("\n[SOLUTION] All test cases match solution output — no mismatches.")

        if corrected_coding:
            task_outputs["coding_problems"] = corrected_coding
            _save_task_output(topic_dir, "coding_problems", corrected_coding, timestamp)
            print(
                "   [AUTO-FIXED] Coding problems JSON updated with corrected "
                "expected values."
            )

    # ── Checkpoint #1: Human edits content before Reviewer ─────────────────
    if not _human_checkpoint_pre_review(topic_dir, timestamp, skip_checkpoints):
        print("[ABORT] Human chose to regenerate. Run the pipeline again.")
        return

    # Re-load content files (human may have edited them)
    for key in gen_task_names:
        filepath = topic_dir / f"{key}_{timestamp}.json"
        if filepath.exists():
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                # Unwrap {"raw_output": "..."} wrapper used for non-JSON content
                if isinstance(data, dict) and list(data.keys()) == ["raw_output"]:
                    task_outputs[key] = str(data["raw_output"])
                else:
                    task_outputs[key] = json.dumps(data, ensure_ascii=False)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  [WARN] Could not re-read {key}: {exc}")

    # ── Phase 2: Reviewer (standalone, content embedded directly) ──────────
    article_raw = task_outputs.get("article_content") or ""
    quiz_raw = task_outputs.get("quiz_content") or ""
    coding_raw = task_outputs.get("coding_problems") or ""

    print("\n[PHASE 2] Running Reviewer (~$0.10)...")
    print(f"  article: {len(article_raw):,} chars")
    print(f"  quiz:    {len(quiz_raw):,} chars")
    print(f"  coding:  {len(coding_raw):,} chars")

    review_crew = create_reviewer_crew(
        topic_id=topic_id,
        topic_label=label,
        article_raw=article_raw,
        quiz_raw=quiz_raw,
        coding_raw=coding_raw,
    )
    review_result = review_crew.kickoff()
    review_raw = str(review_result) if review_result is not None else ""

    task_outputs["review_report"] = review_raw
    _save_task_output(topic_dir, "review_report", review_raw, timestamp)
    print(
        f"[OK] review_report saved to {topic_dir / f'review_report_{timestamp}.json'}"
    )

    # ── Parse Reviewer verdict ────────────────────────────────────────────
    coverage_increment = 0.0
    verdict = "unknown"
    fixes: list[str] = []

    try:
        review_clean = _strip_double_braces(_strip_code_fences(review_raw))
        review_json = json.loads(review_clean)
        verdict = review_json.get("verdict", "unknown")
        fixes = review_json.get("required_fixes", [])

        if verdict == "approved":
            coverage_increment = 1.0
        elif verdict == "approved_with_minor_fixes":
            coverage_increment = 0.85
        else:
            coverage_increment = 0.25  # rejected: partial credit for effort
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        print(f"[WARN] Could not parse Reviewer JSON: {exc}")
        verdict = "parse_error"
        coverage_increment = 0.25

    # ── Save combined output ──────────────────────────────────────────────
    combined = {
        "topic_id": topic_id,
        "topic_label": label,
        "generated_at": datetime.now(UTC).isoformat(),
        "research_notes": task_outputs.get("research_notes"),
        "article_content": task_outputs.get("article_content"),
        "quiz_content": task_outputs.get("quiz_content"),
        "coding_problems": task_outputs.get("coding_problems"),
        "review_report": review_raw,
    }
    combined_path = topic_dir / f"combined_{timestamp}.json"
    save_json(combined_path, combined)
    print(f"[OK] Combined output saved to {combined_path}")

    # ── Print summary of what was produced ────────────────────────────────
    print(f"\n[DATA] Production Summary for {label}:")
    for key, value in task_outputs.items():
        status = "[OK]" if value else "[MISS]"
        length = len(value) if value else 0
        print(f"   {status} {key}: {length} chars")

    # ── Show Reviewer verdict ─────────────────────────────────────────────
    print(f"\n[VERDICT] {verdict.upper()}")
    if fixes:
        print(f"[FIXES] {len(fixes)} required changes:")
        for f in fixes[:5]:
            print(f"   - {str(f)[:150]}")
        if len(fixes) > 5:
            print(f"   ... and {len(fixes) - 5} more")

    # ── Checkpoint #2: Human sign-off on publication ──────────────────────
    if not _human_checkpoint_post_review(
        verdict, fixes, coverage_increment, skip_checkpoints
    ):
        print("[ABORT] Human rejected publication. Coverage not updated.")
        return

    # ── Update published index ────────────────────────────────────────────
    published = load_published_index()
    published[topic_id] = round(
        max(published.get(topic_id, 0.0), coverage_increment), 2
    )
    save_json(PUBLISHED_INDEX_FILE, published)

    print(f"[DATA] Published index updated: {topic_id} = {published[topic_id]:.0%}")


def _checkpoint_print(*args, **kwargs) -> None:
    """Print to the REAL stdout, bypassing CrewAI's monkey-patched sys.stdout.

    CrewAI replaces sys.stdout with a wrapper that enforces cp1252 encoding
    on Windows. This bypasses that for checkpoint prompts that need human input.
    """
    end = kwargs.get("end", "\n")
    text = " ".join(str(a) for a in args) + end
    sys.__stdout__.write(text)
    sys.__stdout__.flush()


def _checkpoint_input(prompt: str) -> str:
    """Read input from the REAL stdin, bypassing any CrewAI redirection."""
    _checkpoint_print(prompt, end="")
    return sys.__stdin__.readline().strip().lower()


def _human_checkpoint_pre_review(
    topic_dir: Path, timestamp: str, skip_checkpoints: bool = False
) -> bool:
    """Checkpoint #1: Let human edit content files before the Reviewer runs.

    Opens each content file for the human to inspect and fix surface errors
    (typos, draft artifacts, duplicate examples, wrong distractor arithmetic).

    Returns True if the human signals "ok" (content is ready for review),
    False if they signal "regenerate" (discard and re-run the pipeline).
    """
    files_to_check = [
        ("article", topic_dir / f"article_content_{timestamp}.json"),
        ("quiz", topic_dir / f"quiz_content_{timestamp}.json"),
        ("coding", topic_dir / f"coding_problems_{timestamp}.json"),
    ]

    _checkpoint_print()
    _checkpoint_print("=" * 60)
    _checkpoint_print("  [CHECKPOINT #1] Human Content Review")
    _checkpoint_print("=" * 60)
    _checkpoint_print()
    _checkpoint_print("The content generation agents have finished. Open these files")
    _checkpoint_print("and fix surface errors BEFORE the Reviewer evaluates them:")
    _checkpoint_print()
    for label, path in files_to_check:
        exists = "[EXISTS]" if path.exists() else "[MISSING]"
        _checkpoint_print(f"  {exists} {label}: {path}")
    _checkpoint_print()
    _checkpoint_print("Common things to fix (these take seconds for a human, but cost")
    _checkpoint_print("the LLM Reviewer its entire token budget to flag):")
    _checkpoint_print("  - Duplicate draft examples with inline corrections")
    _checkpoint_print('  - "wait, verify:" self-correction artifacts in article text')
    _checkpoint_print("  - Contradictory distractor arithmetic in MCQs")
    _checkpoint_print("  - Typos and formatting issues")
    _checkpoint_print("  - Inconsistent variable names in code snippets")
    _checkpoint_print()
    _checkpoint_print("After editing the files, type 'ok' to proceed to review,")
    _checkpoint_print("or 'regenerate' to discard this run and re-generate.")

    if skip_checkpoints or not sys.__stdin__.isatty():
        if not sys.__stdin__.isatty():
            _checkpoint_print(
                "[CHECKPOINT] Non-interactive mode — auto-approved for review."
            )
        else:
            _checkpoint_print(
                "[CHECKPOINT] --skip-checkpoints set — auto-approved for review."
            )
        return True

    while True:
        try:
            response = _checkpoint_input("\n  [ok / regenerate]: ")
        except EOFError, KeyboardInterrupt:
            return False

        if response == "ok":
            _checkpoint_print("[CHECKPOINT] Human approved content for review.")
            return True
        if response in ("regenerate", "regen"):
            _checkpoint_print("[CHECKPOINT] Human requested regeneration.")
            return False
        _checkpoint_print("  Type 'ok' or 'regenerate'.")


def _human_checkpoint_post_review(
    verdict: str,
    fixes: list[str],
    coverage_increment: float,
    skip_checkpoints: bool = False,
) -> bool:
    """Checkpoint #2: Human sign-off on the Reviewer's verdict.

    Shows the verdict and required fixes, lets the human decide whether
    to publish at the Reviewer's coverage level or reject the content.

    Returns True to publish, False to discard.
    """
    _checkpoint_print()
    _checkpoint_print("=" * 60)
    _checkpoint_print("  [CHECKPOINT #2] Reviewer Verdict Sign-off")
    _checkpoint_print("=" * 60)
    _checkpoint_print(f"  Verdict:  {verdict.upper()}")
    _checkpoint_print(
        f"  Coverage: {coverage_increment:.0%} (0.25=rejected, 0.85=minor_fixes, 1.0=approved)"
    )
    _checkpoint_print(f"  Fixes:    {len(fixes)} required")

    if fixes:
        _checkpoint_print("  Required fixes:")
        for i, f in enumerate(fixes[:10]):
            _checkpoint_print(f"    {i + 1}. {str(f)[:150]}")
        if len(fixes) > 10:
            _checkpoint_print(f"    ... and {len(fixes) - 10} more")

    _checkpoint_print()
    _checkpoint_print("Options:")
    _checkpoint_print(
        "  'publish' - Accept the verdict and apply coverage to published_index"
    )
    _checkpoint_print("  'reject'  - Discard this run (no coverage applied)")

    if skip_checkpoints or not sys.__stdin__.isatty():
        if not sys.__stdin__.isatty():
            _checkpoint_print("[CHECKPOINT] Non-interactive mode — auto-publishing.")
        else:
            _checkpoint_print("[CHECKPOINT] --skip-checkpoints set — auto-publishing.")
        return True

    while True:
        try:
            response = _checkpoint_input("\n  [publish / reject]: ")
        except EOFError, KeyboardInterrupt:
            return False

        if response in ("publish", "pub"):
            _checkpoint_print("[CHECKPOINT] Human approved publication.")
            return True
        if response in ("reject", "rej"):
            _checkpoint_print("[CHECKPOINT] Human rejected publication.")
            return False
        _checkpoint_print("  Type 'publish' or 'reject'.")


def _save_task_output(
    topic_dir: Path,
    key: str,
    raw: str,
    timestamp: str,
) -> None:
    """Save a single task output as JSON."""
    path = topic_dir / f"{key}_{timestamp}.json"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError, TypeError:
        data = {"raw_output": raw}
    save_json(path, data)


def _scan_content_output(topic_id: str) -> dict | None:
    """Scan content_output/ for a topic's latest combined JSON.

    Returns metadata dict with files, generated_at, and content types found,
    or None if no content exists for this topic.
    """
    topic_dir = CONTENT_OUTPUT_DIR / topic_id
    if not topic_dir.is_dir():
        return None

    combined_files = sorted(topic_dir.glob("combined_*.json"), reverse=True)
    if not combined_files:
        return None

    latest = combined_files[0]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"error": str(exc), "file": str(latest)}

    generated_at = data.get("generated_at", "")
    content_types_found: list[str] = []
    if data.get("article_content"):
        content_types_found.append("article")
    if data.get("quiz_content"):
        content_types_found.append("mcq")
    if data.get("coding_problems"):
        content_types_found.append("coding")

    # Determine verdict from reviewer
    verdict = "unknown"
    review_raw = data.get("review_report", "")
    if review_raw:
        try:
            review = (
                json.loads(_strip_double_braces(review_raw))
                if isinstance(review_raw, str)
                else review_raw
            )
            verdict = review.get("verdict", "unknown")
        except json.JSONDecodeError, TypeError:
            pass

    return {
        "generated_at": generated_at,
        "verdict": verdict,
        "content_types_found": content_types_found,
        "file": str(latest),
    }


def cmd_gap() -> None:
    """Run gap analysis to find missing/stale content.

    Uses local taxonomy + published index — no API calls needed.
    """
    print("=" * 60)
    print("  AdvaitaCode — Gap Analysis")
    print("=" * 60)

    # Load local data
    taxonomy_topics = flatten_taxonomy()
    published = load_published_index()

    fully_covered: list[str] = []
    partial_coverage: list[dict] = []
    completely_missing: list[dict] = []
    stale_content: list[dict] = []

    now = datetime.now(UTC)

    for topic in taxonomy_topics:
        tid = topic["id"]
        label = topic["label"]
        weight = topic["weight"]
        required_types = set(topic.get("content_types", ["article"]))
        coverage_pct = published.get(tid, 0.0)

        content_meta = _scan_content_output(tid)

        # ── Missing ───────────────────────────────────────────────────
        if coverage_pct == 0.0 or content_meta is None:
            completely_missing.append(
                {
                    "topic_id": tid,
                    "label": label,
                    "weight": weight,
                    "urgency": "CRITICAL"
                    if weight >= 9
                    else "HIGH"
                    if weight >= 7
                    else "MEDIUM",
                }
            )
            continue

        # ── Staleness check ───────────────────────────────────────────
        generated_at = content_meta.get("generated_at", "")
        age_days: int | None = None
        is_stale = False
        if generated_at:
            try:
                gen_dt = datetime.fromisoformat(generated_at)
                age_days = (now - gen_dt).days
                is_stale = age_days > 365
            except ValueError, OverflowError:
                pass

        if is_stale:
            stale_content.append(
                {
                    "topic_id": tid,
                    "label": label,
                    "last_updated": generated_at,
                    "age_days": age_days,
                    "reason_stale": f"Content is {age_days} days old (>365 day threshold).",
                    "suggested_action": "Regenerate to incorporate latest interview patterns and company trends.",
                }
            )

        # ── Completeness check ────────────────────────────────────────
        found_types = set(content_meta.get("content_types_found", []))
        missing_types = sorted(required_types - found_types)
        missing_subtopics_estimate: list[str] = []
        required_difficulties = set(topic.get("difficulties", ["beginner"]))
        # We can't easily check if ALL subtopics/difficulties are covered
        # without parsing the content. Flag topics missing content types.
        # For a full check, we'd parse the reviewer report.

        completeness_score = len(found_types) / max(len(required_types), 1)

        if completeness_score >= 0.85 and coverage_pct >= 0.85:
            fully_covered.append(tid)
        else:
            partial_coverage.append(
                {
                    "topic_id": tid,
                    "label": label,
                    "coverage_pct": coverage_pct,
                    "missing_content_types": missing_types,
                    "missing_subtopics_estimate": missing_subtopics_estimate,
                    "missing_difficulty_levels": [],
                    "verdict": content_meta.get("verdict", "unknown"),
                    "needs_rewrite": content_meta.get("verdict") == "rejected",
                    "last_updated": generated_at or None,
                }
            )

    # ── Compute overall coverage ───────────────────────────────────────
    total = len(taxonomy_topics)
    covered_count = len(fully_covered) + len(partial_coverage)
    overall_pct = round((len(fully_covered) / total) * 100, 1) if total > 0 else 0.0

    report = {
        "generated_at": now.isoformat(),
        "overall_coverage_pct": overall_pct,
        "summary": {
            "total_topics": total,
            "fully_covered": len(fully_covered),
            "partial_coverage": len(partial_coverage),
            "completely_missing": len(completely_missing),
            "stale_content": len(stale_content),
        },
        "fully_covered": sorted(fully_covered),
        "partial_coverage": partial_coverage,
        "completely_missing": completely_missing,
        "stale_content": stale_content,
    }

    save_json(GAP_REPORT_FILE, report)
    print(f"\n[OK] Gap report saved to {GAP_REPORT_FILE}")

    # Print summary
    s = report["summary"]
    print(
        f"\n[DATA] Overall Coverage: {overall_pct}% ({covered_count}/{total} topics have content)"
    )
    print(f"   [DONE] Fully Covered:    {s['fully_covered']}")
    print(f"   [WARN] Partial Coverage:  {s['partial_coverage']}")
    print(f"   [ERR]  Completely Missing: {s['completely_missing']}")
    print(f"   [WARN] Stale Content:      {s['stale_content']}")

    if completely_missing:
        print("\n[ERR] Top 10 missing topics by weight:")
        missing_sorted = sorted(
            completely_missing, key=lambda t: t["weight"], reverse=True
        )[:10]
        for t in missing_sorted:
            print(
                f"   [{t['urgency']}] {t['label']} ({t['topic_id']}) — weight {t['weight']}"
            )

    if partial_coverage:
        needs_rewrite = [t for t in partial_coverage if t.get("needs_rewrite")]
        missing_types = [t for t in partial_coverage if t.get("missing_content_types")]
        if needs_rewrite:
            print("\n[WARN] Topics needing rewrite (reviewer rejected):")
            for t in needs_rewrite:
                print(
                    f"   - {t['label']} ({t['topic_id']}) — coverage {t['coverage_pct']:.0%}"
                )
        if missing_types:
            print("\n[WARN] Topics missing content types:")
            for t in missing_types:
                print(
                    f"   - {t['label']} ({t['topic_id']}) — missing: {t['missing_content_types']}"
                )


def cmd_interactive() -> None:
    """Run the 4-step interactive content wizard."""
    from advaita_agents.interactive import run_interactive

    def _internal_produce(topic_id: str, subtopics: list[str] | None) -> None:
        """Thin wrapper so interactive.py doesn't import main."""
        _produce_topic(topic_id, subtopics=subtopics)

    run_interactive(_internal_produce)


# ── Entry Point ────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "interactive":
        cmd_interactive()
    elif command == "roadmap":
        cmd_roadmap()
    elif command == "produce":
        # Check for flags
        topic_id = None
        language = "python"
        skip_checkpoints = False
        for i, arg in enumerate(sys.argv[2:], start=2):
            if arg == "--topic-id" and i + 1 < len(sys.argv):
                topic_id = sys.argv[i + 1]
            elif arg == "--language" and i + 1 < len(sys.argv):
                language = sys.argv[i + 1]
            elif arg == "--skip-checkpoints":
                skip_checkpoints = True
        cmd_produce(topic_id, language, skip_checkpoints=skip_checkpoints)
    elif command == "gap":
        cmd_gap()
    else:
        print(f"[FAIL] Unknown command: {command}")
        print("Available: interactive, roadmap, produce, gap")
        sys.exit(1)


if __name__ == "__main__":
    main()
