"""Tests for the pre-publish scanner module.

All tests are hermetic — no external services, no API calls.
Uses crafted inputs and/or existing content_output files as fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from advaita_agents.pre_publish_scanner import (
    Finding,
    ScanReport,
    Severity,
    scan_topic,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Unit tests: individual check logic via scan_topic
# ═══════════════════════════════════════════════════════════════════════════


class TestJsonValidity:
    """Checks for JSON parse errors, truncation, and format compliance."""

    def test_empty_quiz_fails(self) -> None:
        report = scan_topic(
            "test", article_raw="# Test", quiz_raw="", coding_raw="[]"
        )
        assert report.verdict == "FAIL"
        fails = report.fails()
        assert any("No quiz content" in f.detail for f in fails)

    def test_empty_coding_fails(self) -> None:
        report = scan_topic(
            "test", article_raw="# Test", quiz_raw="[]", coding_raw=""
        )
        assert report.verdict == "FAIL"
        fails = report.fails()
        assert any("No coding" in f.detail for f in fails)

    def test_empty_article_fails(self) -> None:
        report = scan_topic(
            "test", article_raw="", quiz_raw="[]", coding_raw="[]"
        )
        assert report.verdict == "FAIL"
        fails = report.fails()
        assert any("No article content" in f.detail for f in fails)

    def test_malformed_quiz_json_fails(self) -> None:
        report = scan_topic(
            "test",
            article_raw="# Test Article\nContent here.",
            quiz_raw="[{bad json",
            coding_raw="[]",
        )
        assert report.verdict == "FAIL"
        fails = report.fails()
        assert any("Invalid JSON" in f.detail and "quiz" in f.check for f in fails)

    def test_thought_preamble_fails(self) -> None:
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw="Thought: Let me create the MCQs now...\n[{}]",
            coding_raw="[]",
        )
        assert report.verdict == "FAIL"
        fails = report.fails()
        assert any("Thought" in f.detail and "quiz" in f.check for f in fails)

    def test_code_fence_wrapped_json_parses(self) -> None:
        quiz_data = json.dumps(
            [
                {
                    "id": "q_1",
                    "question": "Test?",
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 0,
                    "explanation": "Test explanation.",
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test Article\nContent here.",
            quiz_raw=f"```json\n{quiz_data}\n```",
            coding_raw="[]",
            expected_quiz_count=1,
            expected_coding_count=0,
        )
        assert report.verdict == "PASS"
        passes = report.passes()
        assert any("Valid JSON" in f.detail and "quiz" in f.check for f in passes)

    def test_insufficient_items_fails(self) -> None:
        quiz_data = json.dumps([{"id": "q_1", "options": ["A"], "correct_index": 0}])
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw=quiz_data,
            coding_raw="[]",
            expected_quiz_count=5,
            expected_coding_count=0,
        )
        fails = report.fails()
        assert any("Expected 5" in f.detail for f in fails)


class TestSelfMonologue:
    """Detection of agent internal thought patterns leaking into output."""

    def test_wait_verify_flagged(self) -> None:
        report = scan_topic(
            "test",
            article_raw="The prefix sum is computed as follows. wait, verify: the formula is prefix[i] = prefix[i-1] + arr[i].",
            quiz_raw="[]",
            coding_raw="[]",
            expected_quiz_count=0,
            expected_coding_count=0,
        )
        warns = report.warnings()
        assert any("wait," in f.detail.lower() for f in warns)

    def test_actually_let_me_flagged(self) -> None:
        report = scan_topic(
            "test",
            article_raw="The complexity is O(n). actually let me recalculate that...",
            quiz_raw="[]",
            coding_raw="[]",
            expected_quiz_count=0,
            expected_coding_count=0,
        )
        warns = report.warnings()
        assert any("recalculate" in f.detail for f in warns)

    def test_hmm_hesitation_flagged(self) -> None:
        report = scan_topic(
            "test",
            article_raw="Hmm, this edge case requires careful handling.",
            quiz_raw="[]",
            coding_raw="[]",
            expected_quiz_count=0,
            expected_coding_count=0,
        )
        warns = report.warnings()
        assert any("hesitation" in f.detail for f in warns)

    def test_scratch_notes_flagged(self) -> None:
        report = scan_topic(
            "test",
            article_raw="Scratch notes: version 3 of the article...",
            quiz_raw="[]",
            coding_raw="[]",
            expected_quiz_count=0,
            expected_coding_count=0,
        )
        warns = report.warnings()
        assert any("scratch-note" in f.detail for f in warns)

    def test_clean_article_passes(self) -> None:
        report = scan_topic(
            "test",
            article_raw=(
                "# Introduction to Arrays\n\n"
                "Arrays are the most fundamental data structure in computer science. "
                "An array stores elements of the same type in contiguous memory locations. "
                "Access is O(1), insertion/deletion is O(n).\n\n"
                "## Prefix Sum Technique\n\n"
                "The prefix sum array allows O(1) range sum queries after O(n) preprocessing."
            ),
            quiz_raw="[]",
            coding_raw="[]",
            expected_quiz_count=0,
            expected_coding_count=0,
        )
        warns = report.warnings()
        assert not any("self_monologue" in f.check for f in warns if f.severity == Severity.WARN)


class TestMcqCorrectness:
    """MCQ answer verification checks."""

    def test_correct_index_in_range_passes(self) -> None:
        quiz_data = json.dumps(
            [
                {
                    "id": "q_1",
                    "question": "What is 2+2?",
                    "options": ["A) 3", "B) 4", "C) 5", "D) 6"],
                    "correct_index": 1,
                    "explanation": "2+2=4, so the answer is 4.",
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw=quiz_data,
            coding_raw="[]",
            expected_quiz_count=1,
            expected_coding_count=0,
        )
        passes = report.passes()
        assert any(
            "All 1 MCQs have valid correct_index" in f.detail for f in passes
        )

    def test_correct_index_out_of_range_fails(self) -> None:
        quiz_data = json.dumps(
            [
                {
                    "id": "q_1",
                    "options": ["A", "B", "C"],
                    "correct_index": 5,
                    "explanation": "Test",
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw=quiz_data,
            coding_raw="[]",
            expected_quiz_count=1,
            expected_coding_count=0,
        )
        fails = report.fails()
        assert any("out of range" in f.detail for f in fails)

    def test_missing_correct_index_fails(self) -> None:
        quiz_data = json.dumps(
            [{"id": "q_1", "options": ["A", "B"], "explanation": "Test"}]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw=quiz_data,
            coding_raw="[]",
            expected_quiz_count=1,
            expected_coding_count=0,
        )
        fails = report.fails()
        assert any("Missing 'correct_index'" in f.detail for f in fails)

    def test_answer_in_distractor_not_correct_option_fails(self) -> None:
        """Explanation says answer=1, option A says 1, but correct_index points to B."""
        quiz_data = json.dumps(
            [
                {
                    "id": "q_1",
                    "question": "What is 1+0?",
                    "options": ["A) 1", "B) 2", "C) 3", "D) 4"],
                    "correct_index": 1,  # points to "B) 2" — WRONG
                    "explanation": "The answer is 1, and this matches option A.",
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw=quiz_data,
            coding_raw="[]",
            expected_quiz_count=1,
            expected_coding_count=0,
        )
        fails = report.fails()
        assert any("correct_index likely points to the wrong option" in f.detail for f in fails)

    def test_non_dict_question_fails(self) -> None:
        quiz_data = json.dumps(
            ["not a dict", {"id": "ok", "options": ["A"], "correct_index": 0}]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw=quiz_data,
            coding_raw="[]",
            expected_quiz_count=2,
            expected_coding_count=0,
        )
        fails = report.fails()
        assert any("not a valid object" in f.detail for f in fails)


class TestDistractorDistinctness:
    """Near-identical distractor detection."""

    def test_identical_distractors_flagged(self) -> None:
        quiz_data = json.dumps(
            [
                {
                    "id": "q_1",
                    "options": [
                        "A) Sorting takes O(n log n)",
                        "B) Sorting takes O(n log n)",  # identical to A
                        "C) Sorting takes O(n^2)",
                        "D) Sorting takes O(n)",
                    ],
                    "correct_index": 0,
                    "explanation": "Sorting comparison.",
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw=quiz_data,
            coding_raw="[]",
            expected_quiz_count=1,
            expected_coding_count=0,
        )
        warns = report.warnings()
        assert any("identical" in f.detail.lower() for f in warns)

    def test_distinct_distractors_pass(self) -> None:
        quiz_data = json.dumps(
            [
                {
                    "id": "q_1",
                    "options": [
                        "A) O(1) constant time",
                        "B) O(log n) logarithmic time",
                        "C) O(n) linear time",
                        "D) O(n^2) quadratic time",
                    ],
                    "correct_index": 0,
                    "explanation": "Correct.",
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw=quiz_data,
            coding_raw="[]",
            expected_quiz_count=1,
            expected_coding_count=0,
        )
        passes = report.passes()
        assert any("sufficiently distinct" in f.detail for f in passes)


class TestDuplicateExamples:
    """Duplicate example detection in coding problems."""

    def test_duplicate_example_flagged(self) -> None:
        coding_data = json.dumps(
            [
                {
                    "id": "cp_1",
                    "title": "Two Sum",
                    "examples": [
                        {"input": "[1,2,3]", "output": "5"},
                        {"input": "[1,2,3]", "output": "5"},  # duplicate
                    ],
                    "solution": {"optimal": {"code": "def solve(arr): return sum(arr)"}},
                    "test_cases": [],
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw="[]",
            coding_raw=coding_data,
            expected_quiz_count=0,
            expected_coding_count=1,
        )
        fails = report.fails()
        assert any("identical to an earlier example" in f.detail for f in fails)

    def test_unique_examples_pass(self) -> None:
        coding_data = json.dumps(
            [
                {
                    "id": "cp_1",
                    "title": "Two Sum",
                    "examples": [
                        {"input": "[1,2,3]", "output": "5"},
                        {"input": "[4,5,6]", "output": "15"},
                    ],
                    "solution": {"optimal": {"code": "def solve(arr): return sum(arr)"}},
                    "test_cases": [],
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw="[]",
            coding_raw=coding_data,
            expected_quiz_count=0,
            expected_coding_count=1,
        )
        passes = report.passes()
        assert any("No duplicate examples" in f.detail for f in passes)


class TestCodingTestCases:
    """Sandbox execution of coding solution against test cases."""

    def test_correct_test_case_matches(self) -> None:
        coding_data = json.dumps(
            [
                {
                    "id": "cp_1",
                    "title": "Sum Array",
                    "examples": [],
                    "solution": {
                        "optimal": {
                            "code": "def sum_arr(arr):\n    total = 0\n    for x in arr:\n        total += x\n    return total",
                            "time": "O(n)",
                            "space": "O(1)",
                        }
                    },
                    "test_cases": [
                        {"input": "arr = [1, 2, 3, 4]", "expected": "10"},
                        {"input": "arr = [5, -3, 2]", "expected": "4"},
                    ],
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw="[]",
            coding_raw=coding_data,
            expected_quiz_count=0,
            expected_coding_count=1,
        )
        passes = report.passes()
        assert any("All test cases match" in f.detail for f in passes)

    def test_wrong_expected_value_flagged(self) -> None:
        coding_data = json.dumps(
            [
                {
                    "id": "cp_1",
                    "title": "Sum Array",
                    "solution": {
                        "optimal": {
                            "code": "def sum_arr(arr):\n    return sum(arr)",
                        }
                    },
                    "test_cases": [
                        {"input": "arr = [1, 2, 3]", "expected": "999"},  # WRONG
                    ],
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw="[]",
            coding_raw=coding_data,
            expected_quiz_count=0,
            expected_coding_count=1,
        )
        fails = report.fails()
        assert any("MISMATCH" in f.detail for f in fails)

    def test_tree_problem_gracefully_warns(self) -> None:
        """TreeNode problems can't execute in sandbox — should WARN, not FAIL."""
        coding_data = json.dumps(
            [
                {
                    "id": "cp_tree_1",
                    "title": "Tree Inorder",
                    "solution": {
                        "optimal": {
                            "code": (
                                "def inorder(root):\n"
                                "    result = []\n"
                                "    def dfs(node):\n"
                                "        if not node:\n"
                                "            return\n"
                                "        dfs(node.left)\n"
                                "        result.append(node.val)\n"
                                "        dfs(node.right)\n"
                                "    dfs(root)\n"
                                "    return result"
                            ),
                        }
                    },
                    "test_cases": [
                        {"input": "root = [1, null, 2, 3]", "expected": "[1, 3, 2]"},
                    ],
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw="[]",
            coding_raw=coding_data,
            expected_quiz_count=0,
            expected_coding_count=1,
        )
        # Should NOT have FAIL for test cases (sandbox limitation)
        fails = report.fails()
        assert not any("coding_test_cases" in f.check for f in fails)

        # Should WARN about sandbox limitation
        warns = report.warnings()
        assert any("sandbox" in f.detail.lower() or "custom data structure" in f.detail.lower() for f in warns)

    def test_solution_syntax_error_handled(self) -> None:
        coding_data = json.dumps(
            [
                {
                    "id": "cp_1",
                    "title": "Broken",
                    "solution": {
                        "optimal": {
                            "code": "def bad_syntax(\n  return 1",  # unclosed paren
                        }
                    },
                    "test_cases": [{"input": "[1]", "expected": "1"}],
                }
            ]
        )
        report = scan_topic(
            "test",
            article_raw="# Test",
            quiz_raw="[]",
            coding_raw=coding_data,
            expected_quiz_count=0,
            expected_coding_count=1,
        )
        warns = report.warnings()
        assert any("could not compile" in f.detail.lower() for f in warns)


class TestArticleStructure:
    """Basic article quality heuristics."""

    def test_short_article_warns(self) -> None:
        report = scan_topic(
            "test",
            article_raw="Short.",
            quiz_raw="[]",
            coding_raw="[]",
            expected_quiz_count=0,
            expected_coding_count=0,
        )
        warns = report.warnings()
        assert any("short" in f.detail.lower() for f in warns)

    def test_no_headings_warns(self) -> None:
        long_text = (
            "This is a long enough article with enough content to pass minimum "
            "length requirements. " * 50
        )
        report = scan_topic(
            "test",
            article_raw=long_text,
            quiz_raw="[]",
            coding_raw="[]",
            expected_quiz_count=0,
            expected_coding_count=0,
        )
        warns = report.warnings()
        assert any("NO markdown headings" in f.detail for f in warns)

    def test_well_structured_article_passes(self) -> None:
        content_paragraph = (
            "This section covers the fundamental concepts needed to build a solid "
            "understanding. We start from first principles and work our way up to "
            "more advanced applications. Every concept is illustrated with concrete "
            "code examples that you can run and modify yourself.\n\n"
        )
        article = (
            "# Introduction to Data Structures\n\n"
            f"{content_paragraph * 10}"
            "## Beginner Concepts\n\n"
            f"{content_paragraph * 10}"
            "### Arrays\n\n"
            "```python\narr = [1, 2, 3]\nprint(sum(arr))\n```\n\n"
            f"{content_paragraph * 5}"
            "## Intermediate Patterns\n\n"
            f"{content_paragraph * 10}"
            "### Two Pointers\n\n"
            "```python\ndef two_sum(arr, target):\n    pass\n```\n\n"
            "## Advanced Techniques\n\n"
            f"{content_paragraph * 5}"
        )
        report = scan_topic(
            "test",
            article_raw=article,
            quiz_raw="[]",
            coding_raw="[]",
            expected_quiz_count=0,
            expected_coding_count=0,
        )
        passes = report.passes()
        assert report.verdict == "PASS"
        assert any("article_structure" in f.check for f in passes)


# ═══════════════════════════════════════════════════════════════════════════
#  Integration tests: real content files
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "topic_id,expected_verdict",
    [
        ("ds_arrays", "PASS"),
        ("ds_hash", "PASS"),
        # ds_trees should FAIL due to wrong MCQ answers
        ("ds_trees", "FAIL"),
    ],
)
def test_scan_real_content(topic_id: str, expected_verdict: str) -> None:
    """End-to-end scan of real content_output files."""
    project_root = Path(__file__).resolve().parent.parent
    topic_dir = project_root / "content_output" / topic_id

    if not topic_dir.is_dir():
        pytest.skip(f"No content_output directory for '{topic_id}'")

    combined_files = sorted(topic_dir.glob("combined_*.json"), reverse=True)
    if not combined_files:
        pytest.skip(f"No combined JSON files in {topic_dir}")

    data = json.loads(combined_files[0].read_text(encoding="utf-8"))

    article = data.get("article_content", "")
    quiz = data.get("quiz_content", "")
    coding = data.get("coding_problems", "")

    report = scan_topic(
        topic_id=topic_id,
        article_raw=article if isinstance(article, str) else json.dumps(article),
        quiz_raw=quiz if isinstance(quiz, str) else json.dumps(quiz),
        coding_raw=coding if isinstance(coding, str) else json.dumps(coding),
    )

    assert report.verdict == expected_verdict, (
        f"Expected {expected_verdict} for {topic_id}, got {report.verdict}. "
        f"Failures: {len(report.fails())}, Warnings: {len(report.warnings())}"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  ScanReport dataclass unit tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScanReport:
    """ScanReport data structure behavior."""

    def test_empty_report_passes(self) -> None:
        report = ScanReport(topic_id="test", verdict="PASS")
        report.compute_verdict()
        assert report.verdict == "PASS"

    def test_single_fail_makes_fail(self) -> None:
        report = ScanReport(topic_id="test", verdict="PASS")
        report.add(Finding("test_check", Severity.FAIL, "Broken"))
        report.compute_verdict()
        assert report.verdict == "FAIL"

    def test_warns_dont_fail(self) -> None:
        report = ScanReport(topic_id="test", verdict="PASS")
        report.add(Finding("test_check", Severity.WARN, "Heads up"))
        report.compute_verdict()
        assert report.verdict == "PASS"

    def test_all_findings_ordered_by_severity(self) -> None:
        report = ScanReport(topic_id="test", verdict="PASS")
        report.add(Finding("a", Severity.PASS, "ok"))
        report.add(Finding("b", Severity.FAIL, "bad"))
        report.add(Finding("c", Severity.WARN, "hmm"))
        report.add(Finding("d", Severity.FAIL, "also bad"))
        ordered = report.all_findings()
        severities = [f.severity for f in ordered]
        assert severities == [Severity.FAIL, Severity.FAIL, Severity.WARN, Severity.PASS]

    def test_filters_return_correct_subsets(self) -> None:
        report = ScanReport(topic_id="test", verdict="PASS")
        report.add(Finding("a", Severity.PASS, "ok"))
        report.add(Finding("b", Severity.FAIL, "bad"))
        report.add(Finding("c", Severity.WARN, "hmm"))
        assert len(report.fails()) == 1
        assert len(report.warnings()) == 1
        assert len(report.passes()) == 1
