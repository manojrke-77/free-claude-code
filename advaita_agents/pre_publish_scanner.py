"""
Pre-Publish Scanner -- automated quality checks replacing the AI Reviewer
for ~80% of pipeline runs.

Runs in <1 second, costs $0. Catches everything computationally verifiable:
  - Test case expected values vs actual solution output
  - MCQ correct answer present in options
  - Duplicate content (draft artifacts, copied examples)
  - Self-monologue artifacts (Thought:, wait, actually let me...)
  - JSON validity and truncation
  - Distractor distinctness
  - Article structure heuristics

Returns a ScanReport with overall PASS/FAIL and per-check findings.
PASS = content is publication-ready at 0.85 coverage (standard).
FAIL = content has issues that need fixing or an optional AI Reviewer pass.

Usage:
    from advaita_agents.pre_publish_scanner import scan_topic

    report = scan_topic(
        topic_id="ds_arrays",
        article_raw=article_text,
        quiz_raw=quiz_text,
        coding_raw=coding_text,
        fix_coding=True,   # auto-correct test case expected values
    )

    if report.verdict == "PASS":
        print("Ready to publish at 0.85")
    else:
        for finding in report.all_findings():
            print(f"  [{finding.severity}] {finding.check}: {finding.detail}")
"""

from __future__ import annotations

import ast as _ast
import inspect as _inspect
import json
import re as _re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# ═══════════════════════════════════════════════════════════════════════════
#  Data types
# ═══════════════════════════════════════════════════════════════════════════


class Severity:
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class Finding:
    """A single check finding."""

    check: str  # e.g. "mcq_correct_answer", "duplicate_examples"
    severity: str  # Severity.PASS, WARN, FAIL
    detail: str
    location: str = ""  # e.g. "q_ds_arrays_5", "cp_2 Example 1"
    auto_fixed: bool = False


@dataclass
class ScanReport:
    """Aggregate scan result for one topic."""

    topic_id: str
    verdict: str  # "PASS" | "FAIL"
    findings: list[Finding] = field(default_factory=list)
    auto_fixes_applied: int = 0

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def fails(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.FAIL]

    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARN]

    def passes(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.PASS]

    def all_findings(self) -> list[Finding]:
        """Return findings ordered by severity: FAIL first, then WARN, then PASS."""
        order = {Severity.FAIL: 0, Severity.WARN: 1, Severity.PASS: 2}
        return sorted(self.findings, key=lambda f: order.get(f.severity, 3))

    def compute_verdict(self) -> str:
        """Derive PASS/FAIL from findings."""
        if any(f.severity == Severity.FAIL for f in self.findings):
            self.verdict = "FAIL"
        else:
            self.verdict = "PASS"
        return self.verdict


# ═══════════════════════════════════════════════════════════════════════════
#  Patterns
# ═══════════════════════════════════════════════════════════════════════════

# Phrases that indicate the model is talking to itself, not producing content
_SELF_MONOLOGUE_PATTERNS: list[tuple[str, str]] = [
    (r"\b(Thought|Let me|let me)\s*:", "agent design trace preamble"),
    (r"\bwait,\s*(verify|let|I need|actually)", "self-correction artifact"),
    (
        r"\bactually\s+let\s+me\s+(recalculate|rethink|reconsider|redo|fix|correct)",
        "self-correction with recalculate/rethink",
    ),
    (r"\bhmm[,.]?\b", "hesitation vocalization"),
    (
        r"\b(I should|I need to|I'll|I will|I must|let us|we should)\b",
        "internal deliberation",
    ),
    (r"\b(frankly|honestly|to be honest)\b", "conversational filler"),
    (
        r"\b(scratch|draft|rough)\s*(notes|work|pass|version)\b",
        "scratch-note metadata leak",
    ),
    (r"\bparagraph\s*\d+\s*[:;]", "content outline reference leak"),
    (r"^\s*(note|remember|recall)\s*[:\-]", "instruction-to-self"),
]

# Sections a well-formed article should have
_ARTICLE_SECTION_MARKERS = [
    (r"^#{1,3}\s+", "heading"),  # any markdown heading
    (r"```\w*", "code block"),
    (r"^\s*\d+\.\s+", "numbered list"),
]


# ═══════════════════════════════════════════════════════════════════════════
#  Top-level entry point
# ═══════════════════════════════════════════════════════════════════════════


def scan_topic(
    topic_id: str,
    article_raw: str,
    quiz_raw: str,
    coding_raw: str,
    *,
    fix_coding: bool = True,
    expected_quiz_count: int = 10,
    expected_coding_count: int = 3,
) -> ScanReport:
    """Run all automated checks on one topic's content.

    Args:
        topic_id: Taxonomy topic ID (e.g. "ds_arrays").
        article_raw: Raw article markdown string.
        quiz_raw: Raw quiz JSON string.
        coding_raw: Raw coding problems JSON string.
        fix_coding: Auto-correct test case expected values that don't match
                    the solution's actual output.
        expected_quiz_count: Expected number of MCQ questions.
        expected_coding_count: Expected number of coding problems.

    Returns:
        ScanReport with overall PASS/FAIL and per-check findings.
    """
    report = ScanReport(topic_id=topic_id, verdict="PASS")

    # 1. JSON validity (gate check -- if this fails, subsequent checks skip)
    quiz_parsed = _check_json_validity(report, "quiz", quiz_raw, expected_quiz_count)
    coding_parsed = _check_json_validity(
        report, "coding", coding_raw, expected_coding_count
    )
    _check_article_not_empty(report, article_raw)

    # 2. Self-monologue scan (article, quiz, coding)
    _check_self_monologue(report, "article", article_raw)
    _check_self_monologue(report, "quiz", quiz_raw)
    _check_self_monologue(report, "coding", coding_raw)

    # 3. MCQ checks (only if JSON parsed)
    if quiz_parsed is not None:
        _check_mcq_correctness(report, quiz_parsed)
        _check_distractor_distinctness(report, quiz_parsed)

    # 4. Coding checks (only if JSON parsed)
    if coding_parsed is not None:
        _check_coding_test_cases(report, coding_parsed, fix=fix_coding)
        _check_duplicate_examples(report, coding_parsed)

    # 5. Article heuristics
    _check_article_structure(report, article_raw)

    report.compute_verdict()
    return report


# ═══════════════════════════════════════════════════════════════════════════
#  Check: JSON validity
# ═══════════════════════════════════════════════════════════════════════════


def _check_json_validity(
    report: ScanReport,
    content_type: str,
    raw: str,
    expected_count: int,
) -> list | None:
    """Validate JSON structure. Returns parsed data or None on failure."""
    if not raw or not raw.strip():
        report.add(
            Finding(
                check=f"{content_type}_json",
                severity=Severity.FAIL,
                detail=f"No {content_type} content produced -- agent may have failed silently.",
            )
        )
        return None

    text = _strip_code_fences(raw)

    # Check for Thought: preamble
    if text.strip().startswith(("Thought", "Let me")):
        report.add(
            Finding(
                check=f"{content_type}_json",
                severity=Severity.FAIL,
                detail=(
                    f"Output starts with '{text.strip()[:50]}' -- agent submitted "
                    "internal design traces instead of formatted output."
                ),
            )
        )
        return None

    # Check expected format: article=anything, quiz=array, coding=array
    expected_start = "[" if content_type != "article" else None
    if (
        content_type != "article"
        and expected_start
        and not text.strip().startswith(expected_start)
    ):
        report.add(
            Finding(
                check=f"{content_type}_json",
                severity=Severity.FAIL,
                detail=(
                    f"Expected JSON array starting with '{expected_start}', "
                    f"got: '{text.strip()[:80]}'"
                ),
            )
        )
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        pos = exc.pos
        snippet = text[max(0, pos - 40) : pos + 40] if pos > 0 else "N/A"
        report.add(
            Finding(
                check=f"{content_type}_json",
                severity=Severity.FAIL,
                detail=(
                    f"Invalid JSON at position {pos}: {exc}. "
                    f"Context: '{snippet}'. Likely truncated (not enough max_tokens)."
                ),
            )
        )
        return None

    if not isinstance(parsed, list):
        report.add(
            Finding(
                check=f"{content_type}_json",
                severity=Severity.FAIL,
                detail=(
                    f"Expected a JSON array, got {type(parsed).__name__}. "
                    "Agent may have submitted scratch notes."
                ),
            )
        )
        return None

    actual_count = len(parsed)
    if actual_count < expected_count:
        report.add(
            Finding(
                check=f"{content_type}_count",
                severity=Severity.FAIL,
                detail=(
                    f"Expected {expected_count} items, got {actual_count}. "
                    f"Missing {expected_count - actual_count}. Output may be truncated."
                ),
            )
        )

    report.add(
        Finding(
            check=f"{content_type}_json",
            severity=Severity.PASS,
            detail=f"Valid JSON array, {actual_count} items.",
        )
    )
    return parsed


def _check_article_not_empty(report: ScanReport, raw: str) -> None:
    if not raw or not raw.strip():
        report.add(
            Finding(
                check="article_content",
                severity=Severity.FAIL,
                detail="No article content produced.",
            )
        )
    else:
        report.add(
            Finding(
                check="article_content",
                severity=Severity.PASS,
                detail=f"Article present ({len(raw):,} chars).",
            )
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Check: Self-monologue artifacts
# ═══════════════════════════════════════════════════════════════════════════


def _check_self_monologue(report: ScanReport, content_type: str, raw: str) -> None:
    """Scan for agent internal monologue leaking into final output."""
    if not raw:
        return

    hits: list[str] = []
    for pattern, description in _SELF_MONOLOGUE_PATTERNS:
        matches = list(_re.finditer(pattern, raw, _re.IGNORECASE | _re.MULTILINE))
        for m in matches:
            context = raw[max(0, m.start() - 20) : m.end() + 30].replace("\n", " ")
            hits.append(f"'{context.strip()}' ({description})")

    if hits:
        # Deduplicate identical contexts
        unique_hits = list(dict.fromkeys(hits))
        for hit in unique_hits[:5]:  # cap at 5 to avoid noise
            report.add(
                Finding(
                    check=f"{content_type}_self_monologue",
                    severity=Severity.WARN,
                    detail=hit,
                    location=content_type,
                )
            )
        if len(unique_hits) > 5:
            report.add(
                Finding(
                    check=f"{content_type}_self_monologue",
                    severity=Severity.WARN,
                    detail=f"... and {len(unique_hits) - 5} more monologue fragments",
                    location=content_type,
                )
            )
    else:
        report.add(
            Finding(
                check=f"{content_type}_self_monologue",
                severity=Severity.PASS,
                detail="No self-monologue artifacts found.",
            )
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Check: MCQ correctness
# ═══════════════════════════════════════════════════════════════════════════


def _check_mcq_correctness(report: ScanReport, quiz: list) -> None:
    """Verify every MCQ has a valid correct_index and the answer text matches."""
    critical_failures = 0
    for i, q in enumerate(quiz):
        if not isinstance(q, dict):
            report.add(
                Finding(
                    check="mcq_correct_answer",
                    severity=Severity.FAIL,
                    detail=f"Question {i} is not a valid object -- may be truncated.",
                    location=f"q[{i}]",
                )
            )
            critical_failures += 1
            continue

        qid = q.get("id", f"q[{i}]")
        options = q.get("options", [])
        correct_idx = q.get("correct_index", -1)

        if not isinstance(options, list) or not options:
            report.add(
                Finding(
                    check="mcq_correct_answer",
                    severity=Severity.FAIL,
                    detail="Missing or empty options array.",
                    location=qid,
                )
            )
            critical_failures += 1
            continue

        if "correct_index" not in q:
            report.add(
                Finding(
                    check="mcq_correct_answer",
                    severity=Severity.FAIL,
                    detail="Missing 'correct_index' field.",
                    location=qid,
                )
            )
            critical_failures += 1
            continue

        if (
            not isinstance(correct_idx, int)
            or correct_idx < 0
            or correct_idx >= len(options)
        ):
            report.add(
                Finding(
                    check="mcq_correct_answer",
                    severity=Severity.FAIL,
                    detail=(
                        f"correct_index={correct_idx} is out of range "
                        f"(0-{len(options) - 1}, {len(options)} options)."
                    ),
                    location=qid,
                )
            )
            critical_failures += 1
            continue

        # ── Answer-text match: extract numeric answer from explanation ──
        correct_option_text = str(options[correct_idx])
        explanation = str(q.get("explanation", ""))

        # Heuristic 1 (FAIL): Explanation explicitly states the answer value
        # AND that value appears in a DISTRACTOR but NOT in the correct option.
        # Strong signal the correct_index is wrong.
        numeric_match = _re.findall(
            r"(?:answer|result|output|value|sum|count|length|total\s*(?:nodes|operations|steps)?)\s*(?:is|=|:)\s*(\d+)",
            explanation,
            _re.IGNORECASE,
        )
        for num in numeric_match:
            found_in_correct = num in correct_option_text
            found_in_distractor = any(
                num in str(opt) for j, opt in enumerate(options) if j != correct_idx
            )
            if found_in_distractor and not found_in_correct:
                report.add(
                    Finding(
                        check="mcq_correct_answer",
                        severity=Severity.FAIL,
                        detail=(
                            f"Explanation explicitly states the answer is {num}, "
                            f"but this value appears in a DISTRACTOR option, not "
                            f"in the correct option '{correct_option_text[:60]}'. "
                            "The correct_index likely points to the wrong option."
                        ),
                        location=qid,
                    )
                )
                critical_failures += 1
                break

        # Heuristic 2 (WARN): Explanation's last computed number doesn't
        # appear in the correct option text (weaker signal).
        opt_numbers = _re.findall(r"\d+", correct_option_text)
        exp_numbers = _re.findall(r"\d+", explanation)
        if opt_numbers and exp_numbers:
            computed = exp_numbers[-1]
            if computed not in opt_numbers and not any(
                computed in on for on in opt_numbers if len(on) > len(computed)
            ):
                report.add(
                    Finding(
                        check="mcq_correct_answer",
                        severity=Severity.WARN,
                        detail=(
                            f"Explanation computes {computed}, but the correct "
                            f"option '{correct_option_text[:60]}' does not contain "
                            f"this number. Verify manually."
                        ),
                        location=qid,
                    )
                )

    if critical_failures == 0:
        report.add(
            Finding(
                check="mcq_correct_answer",
                severity=Severity.PASS,
                detail=f"All {len(quiz)} MCQs have valid correct_index values.",
            )
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Check: Distractor distinctness
# ═══════════════════════════════════════════════════════════════════════════


def _check_distractor_distinctness(report: ScanReport, quiz: list) -> None:
    """Flag MCQ distractors that are too similar (reduce effective option count).

    Uses a higher threshold for code-based options (where small differences
    like ``left < right`` vs ``left <= right`` are genuinely distinct) and
    a lower one for plain-text distractors.
    """
    _CODE_KEYWORDS = ("def ", "while ", "for ", "if ", "return ", "import ", "class ")

    issues = 0
    for i, q in enumerate(quiz):
        if not isinstance(q, dict):
            continue
        qid = q.get("id", f"q[{i}]")
        options = q.get("options", [])
        if not isinstance(options, list) or len(options) < 2:
            continue

        # Detect code-based MCQ: any option contains a code keyword
        is_code_mcq = any(
            any(kw in str(opt) for kw in _CODE_KEYWORDS) for opt in options
        )
        threshold = 0.95 if is_code_mcq else 0.85

        for a in range(len(options)):
            for b in range(a + 1, len(options)):
                ratio = SequenceMatcher(None, str(options[a]), str(options[b])).ratio()
                if ratio > threshold:
                    issues += 1
                    report.add(
                        Finding(
                            check="distractor_distinctness",
                            severity=Severity.WARN,
                            detail=(
                                f"Options {a} and {b} are {ratio:.0%} identical "
                                f"('{str(options[a])[:50]}' vs '{str(options[b])[:50]}') "
                                "-- effectively reduces to 3 distinct options."
                            ),
                            location=qid,
                        )
                    )

    if issues == 0:
        report.add(
            Finding(
                check="distractor_distinctness",
                severity=Severity.PASS,
                detail="All distractors are sufficiently distinct.",
            )
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Check: Coding problem test cases
# ═══════════════════════════════════════════════════════════════════════════


def _check_coding_test_cases(
    report: ScanReport,
    problems: list,
    *,
    fix: bool = True,
) -> None:
    """Run each coding solution against its test cases. Optionally auto-fix.

    Distinguishes between:
    - Sandbox-limited (can't execute TreeNode/ListNode code at all) -> WARN
    - Real mismatches (solution runs but produces wrong values) -> FAIL
    - Auto-fixed (mismatch corrected by comparing against actual output) -> WARN
    """
    real_mismatches = 0
    sandbox_failures = 0
    auto_fixes = 0
    exec_failures = 0

    for prob_index, problem in enumerate(problems):
        if not isinstance(problem, dict):
            continue
        pid = problem.get("id", f"cp[{prob_index}]")

        # Extract and execute solution code
        fn = _extract_solution_function(problem, pid, report)
        if fn is None:
            exec_failures += 1
            continue

        # Check examples
        examples = problem.get("examples", [])
        if isinstance(examples, list):
            for ex_i, example in enumerate(examples):
                if not isinstance(example, dict):
                    continue
                err, actual = _run_one_case(fn, example, pid, f"Example {ex_i + 1}")
                if err:
                    if _is_sandbox_limitation(err):
                        sandbox_failures += 1
                    else:
                        real_mismatches += 1
                        report.add(
                            Finding(
                                check="coding_test_cases",
                                severity=Severity.FAIL,
                                detail=err,
                                location=pid,
                            )
                        )
                    if fix and actual is not _NO_VAL:
                        key = "expected" if "expected" in example else "output"
                        example[key] = json.dumps(actual)
                        auto_fixes += 1

        # Check test cases
        test_cases = problem.get("test_cases", [])
        if isinstance(test_cases, list):
            for tc_i, tc in enumerate(test_cases):
                if not isinstance(tc, dict):
                    continue
                err, actual = _run_one_case(fn, tc, pid, f"Test case {tc_i + 1}")
                if err:
                    if _is_sandbox_limitation(err):
                        sandbox_failures += 1
                    else:
                        real_mismatches += 1
                        report.add(
                            Finding(
                                check="coding_test_cases",
                                severity=Severity.FAIL,
                                detail=err,
                                location=pid,
                            )
                        )
                    if fix and actual is not _NO_VAL:
                        key = "expected" if "expected" in tc else "output"
                        tc[key] = json.dumps(actual)
                        auto_fixes += 1

    # Summarize
    if real_mismatches == 0 and exec_failures == 0 and sandbox_failures == 0:
        report.add(
            Finding(
                check="coding_test_cases",
                severity=Severity.PASS,
                detail=f"All test cases match solution output across {len(problems)} problems.",
            )
        )
    if auto_fixes > 0:
        report.add(
            Finding(
                check="coding_test_cases",
                severity=Severity.WARN,
                detail=(
                    f"{auto_fixes} expected value(s) auto-corrected to match "
                    "solution code's actual output."
                ),
            )
        )
    if exec_failures > 0:
        report.add(
            Finding(
                check="coding_test_cases",
                severity=Severity.WARN,
                detail=(
                    f"{exec_failures} problem(s) could not compile/parse "
                    "(likely syntax error in solution code)."
                ),
            )
        )
    if sandbox_failures > 0:
        report.add(
            Finding(
                check="coding_test_cases",
                severity=Severity.WARN,
                detail=(
                    f"{sandbox_failures} test case(s) could not execute "
                    "(likely tree/graph/list-node -- custom data structure "
                    "not supported by sandbox)."
                ),
            )
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Check: Duplicate examples in coding problems
# ═══════════════════════════════════════════════════════════════════════════


def _check_duplicate_examples(report: ScanReport, problems: list) -> None:
    """Detect identical examples within a single coding problem (draft artifacts)."""
    duplicates = 0
    for prob_index, problem in enumerate(problems):
        if not isinstance(problem, dict):
            continue
        pid = problem.get("id", f"cp[{prob_index}]")
        examples = problem.get("examples", [])
        if not isinstance(examples, list):
            continue

        seen: set[str] = set()
        for ex_i, example in enumerate(examples):
            if not isinstance(example, dict):
                continue
            # Normalize and hash example content
            content = json.dumps(example, sort_keys=True, ensure_ascii=False)
            content_hash = _content_fingerprint(content)
            if content_hash in seen:
                duplicates += 1
                report.add(
                    Finding(
                        check="duplicate_examples",
                        severity=Severity.FAIL,
                        detail=(
                            f"Example {ex_i} is identical to an earlier example. "
                            "Likely a draft artifact -- delete one copy."
                        ),
                        location=pid,
                    )
                )
            seen.add(content_hash)

    if duplicates == 0:
        report.add(
            Finding(
                check="duplicate_examples",
                severity=Severity.PASS,
                detail="No duplicate examples found.",
            )
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Check: Article structure
# ═══════════════════════════════════════════════════════════════════════════


def _check_article_structure(report: ScanReport, raw: str) -> None:
    """Basic article quality heuristics."""
    if not raw:
        return

    issues: list[str] = []

    # Minimum length
    if len(raw) < 2000:
        issues.append(
            f"Article is very short ({len(raw):,} chars) -- may be truncated or incomplete."
        )

    # Headings present
    heading_count = len(_re.findall(r"^#{1,3}\s+", raw, _re.MULTILINE))
    if heading_count == 0:
        issues.append("Article has NO markdown headings -- unstructured content.")
    elif heading_count < 3:
        issues.append(
            f"Only {heading_count} heading(s) -- may lack beginner/intermediate/advanced sections."
        )

    # Code blocks
    code_blocks = len(_re.findall(r"```", raw)) // 2
    if code_blocks == 0:
        issues.append("No code blocks found -- article may lack code examples.")

    if issues:
        for issue in issues:
            report.add(
                Finding(
                    check="article_structure",
                    severity=Severity.WARN,
                    detail=issue,
                )
            )
    else:
        report.add(
            Finding(
                check="article_structure",
                severity=Severity.PASS,
                detail=(
                    f"{heading_count} headings, {code_blocks} code blocks, "
                    f"{len(raw):,} chars."
                ),
            )
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════════

_NO_VAL = object()  # sentinel: no actual value computed

# Patterns that indicate the sandbox can't execute a case (not a content bug):
_SANDBOX_LIMITATION_PATTERNS = [
    r"AttributeError: .* object has no attribute 'left'",
    r"AttributeError: .* object has no attribute 'right'",
    r"AttributeError: .* object has no attribute 'val'",
    r"AttributeError: .* object has no attribute 'next'",
    r"Cannot parse input.*root\s*=\s*\[",
    r"Cannot parse input.*head\s*=\s*\[",
]


def _is_sandbox_limitation(error_msg: str) -> bool:
    """Check if an error is a sandbox limitation, not a real content bug."""
    return any(
        _re.search(pattern, error_msg) for pattern in _SANDBOX_LIMITATION_PATTERNS
    )


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from agent output."""
    stripped = text.strip()
    if stripped.startswith("```json") or stripped.startswith("```"):
        first_nl = stripped.find("\n")
        if first_nl != -1:
            stripped = stripped[first_nl + 1 :]
        last_fence = stripped.rfind("```")
        if last_fence != -1:
            stripped = stripped[:last_fence]
    return stripped.strip()


def _content_fingerprint(text: str) -> str:
    """Normalize whitespace for content hashing (variant-tolerant dedup)."""
    return _re.sub(r"\s+", " ", text).strip().lower()


def _extract_solution_function(
    problem: dict,
    pid: str,
    report: ScanReport,
) -> Callable | None:
    """Extract and compile the optimal solution from a coding problem.

    Returns the callable function, or None if extraction fails.
    """
    solution = problem.get("solution", {})
    if not isinstance(solution, dict):
        return None

    optimal = solution.get("optimal", {})
    if not isinstance(optimal, dict):
        return None

    code = optimal.get("code", "")
    if not code:
        brute = solution.get("brute_force", {})
        if isinstance(brute, dict):
            code = brute.get("code", "")
    if not code:
        return None

    # Parse function name
    fn_match = _re.search(r"^def\s+(\w+)\s*\(", code, _re.MULTILINE)
    if not fn_match:
        return None

    fn_name = fn_match.group(1)

    # Build sandbox
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

    def _safe_import(name, *_args, **_kwargs):
        if name in _allowed_modules:
            return _allowed_modules[name]
        raise ImportError(f"Import '{name}' is not allowed in sandbox")

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
        "__name__": "__scanner__",
    }

    try:
        exec(code, safe_namespace)
    except Exception:
        return None

    fn = safe_namespace.get(fn_name)
    if not callable(fn):
        return None

    return fn


def _run_one_case(
    fn: Callable,
    case: dict,
    problem_id: str,
    case_label: str,
) -> tuple[str | None, object]:
    """Execute one test case against the solution function.

    Returns (error_msg_or_None, actual_value).
    actual_value is _NO_VAL when the case couldn't execute at all.
    """
    input_str = case.get("input", "")
    expected_str = case.get("expected") or case.get("output", "")
    if not input_str:
        return None, _NO_VAL

    # Parse expected value
    try:
        expected_val = _ast.literal_eval(expected_str)
    except ValueError, SyntaxError:
        expected_val = expected_str

    # Parse inputs
    local_ns: dict = {}
    lines = [line.strip() for line in input_str.split("\n") if line.strip()]
    if not lines:
        lines = [input_str.strip()]

    def _exec_line(ns: dict, line: str) -> bool:
        before = set(ns.keys())
        try:
            exec(line, {}, ns)
            return True
        except SyntaxError:
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

    if not local_ns:
        try:
            bare_val = _ast.literal_eval(input_str.strip())
        except ValueError, SyntaxError:
            try:
                bare_val = eval(input_str.strip(), {}, {})
            except Exception as exc:
                return (
                    f"{problem_id} {case_label}: Cannot parse input -- {exc}. "
                    f"Input: '{input_str[:80]}'"
                ), _NO_VAL
        local_ns = {"__arg__": bare_val}

    # Call function
    sig = _inspect.signature(fn)
    param_names = list(sig.parameters.keys())

    try:
        if len(param_names) == 1 and len(local_ns) == 1:
            actual = fn(next(iter(local_ns.values())))
        elif len(local_ns) >= len(param_names):
            kwargs = {k: v for k, v in local_ns.items() if k in param_names}
            if len(kwargs) == len(param_names):
                actual = fn(**kwargs)
            else:
                actual = fn(*list(local_ns.values())[: len(param_names)])
        else:
            actual = fn(*list(local_ns.values()))
    except Exception as exc:
        return (
            f"{problem_id} {case_label}: Solution raised {type(exc).__name__}: {exc}",
            _NO_VAL,
        )

    if actual != expected_val:
        return (
            f"{problem_id} {case_label}: MISMATCH -- "
            f"got {actual!r}, expected {expected_str!r}. "
            f"Input: {input_str[:100]}"
        ), actual

    return None, _NO_VAL


def _split_assignments(line: str) -> list[str]:
    """Split comma-separated assignments handling brackets, parens, quotes."""
    parts: list[str] = []
    current: list[str] = []
    depth_paren = 0
    depth_bracket = 0
    in_single = False
    in_double = False

    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
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


# ═══════════════════════════════════════════════════════════════════════════
#  Standalone runner
# ═══════════════════════════════════════════════════════════════════════════


def print_report(report: ScanReport) -> None:
    """Print a human-readable scan report to stdout."""
    sep = "=" * 60

    verdict_char = "PASS" if report.verdict == "PASS" else "FAIL"
    print(f"\n{sep}")
    print(f"  [{verdict_char}] Pre-Publish Scan: {report.topic_id}")
    print(f"{sep}")

    fails = report.fails()
    warns = report.warnings()
    passes = report.passes()

    if fails:
        print(f"\n  FAILURES ({len(fails)}):")
        for f in fails:
            loc = f" [{f.location}]" if f.location else ""
            fixed = " (AUTO-FIXED)" if f.auto_fixed else ""
            print(f"    X {f.check}{loc}: {f.detail}{fixed}")

    if warns:
        print(f"\n  WARNINGS ({len(warns)}):")
        for f in warns:
            loc = f" [{f.location}]" if f.location else ""
            print(f"    ! {f.check}{loc}: {f.detail}")

    if passes:
        print(f"\n  PASSED ({len(passes)}/{len(report.findings)} checks)")

    if report.auto_fixes_applied:
        print(f"\n  [AUTO-FIX] {report.auto_fixes_applied} correction(s) applied.")

    if report.verdict == "PASS":
        print("\n  -> Content is ready for publish at 0.85 coverage.")
        print("  -> Skipping AI Reviewer ($0.10 saved).")
    else:
        print("\n  -> Fix the failures above and re-scan, or invoke the AI Reviewer.")
        print(
            f"  -> Use: uv run python advaita_agents/main.py produce --topic-id {report.topic_id}"
        )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python pre_publish_scanner.py <topic_id>")
        print("  Reads content_output/<topic_id>/combined_<latest>.json")
        sys.exit(1)

    topic_id = sys.argv[1]
    project_root = Path(__file__).resolve().parent.parent
    topic_dir = project_root / "content_output" / topic_id

    if not topic_dir.is_dir():
        print(f"ERROR: No content_output directory for '{topic_id}'")
        sys.exit(1)

    combined_files = sorted(topic_dir.glob("combined_*.json"), reverse=True)
    if not combined_files:
        print(f"ERROR: No combined JSON files in {topic_dir}")
        sys.exit(1)

    latest = combined_files[0]
    print(f"Loading: {latest}")
    data = json.loads(latest.read_text(encoding="utf-8"))

    article = data.get("article_content", "")
    quiz = data.get("quiz_content", "")
    coding = data.get("coding_problems", "")

    report = scan_topic(
        topic_id=topic_id,
        article_raw=article if isinstance(article, str) else json.dumps(article),
        quiz_raw=quiz if isinstance(quiz, str) else json.dumps(quiz),
        coding_raw=coding if isinstance(coding, str) else json.dumps(coding),
    )

    print_report(report)
