# Session Notes — Advaita Agents Pipeline Iteration (2026-06-16)

## Run 17 results (ds_arrays)

### ✅ RESOLVED issues

- **Sandbox builtins**: Added `ord`, `chr` to safe namespace. `enumerate`, `any`, `all` were already present. No NameError false positives in run 17.
- **Reviewer double-brace**: ✅ FIXED. Run 17 produces clean single-brace `{...}` JSON. The `_strip_double_braces()` defense is still in place but no longer triggered.
- **Coding truncation**: ✅ NOT TRUNCATED. 13,111 chars, 3 problems fit in single Claude Sonnet response. The 3-problem scope reduction (from 4) is effective — no further action needed.
- **Quiz format**: ✅ Valid JSON array, no "Thought:" preamble.

### 🔧 FIXED this session

- **`_check_one_case` key mismatch**: Agent uses `"output"` for examples but `"expected"` for test_cases. Validator only looked for `"expected"`, causing 7 false-positive MISMATCH errors on examples. Fix: `case.get("expected") or case.get("output", "")` fallback at line 652.

### Verified pipeline flow

```
Research (DeepSeek, 12 iter, hit limit) → Writer (Claude) → Quiz (Claude) → Coding (Claude) → Reviewer (Claude)
```
All 5 agents produced valid output. Research hit `max_iter=12` (known DeepSeek pattern). Reviewer verdict: `approved_with_minor_fixes` (9 fixes, 2 critical).

### Genuine validation findings (after key fix)
- cp_ds_arrays_2 Test case 5: expected 3, got 2 — wrong expected output
- cp_ds_arrays_2 Test case 6: expected 5, got 6 — wrong expected output
- These are the known "Fix-cycle" issue from CLAUDE.md — agent fabricates expected values

### State
- `published_index.json`: `{"ds_arrays": 0.85}` (approved_with_minor_fixes)

---

## Run 18 — Reviewer prompt restructure (abandoned)

### Problem discovered
Reviewer agent consumed all 8192 tokens on hand-tracing code examples, produced no verdict JSON. Root cause: instruction "trace EVERY example" contradicted "write JSON first" — the thoroughness impulse won.

### Attempted fix (didn't work)
"FINAL OUTPUT RULE" at the bottom saying "read this last — it overrides everything above" created an adversarial relationship between thoroughness and output. The model still traced everything.

---

## Run 19 — Two-tier Reviewer prompt (✅ WORKING)

### Two-tier structure (in `content_tasks.py`)

1. **TOP — Token budget warning** (before the checklist): explains *why* tracing kills output. "The #1 pipeline failure is: you trace 15+ examples, run out of tokens, and produce NO JSON at all."
2. **"YOUR FIRST ACTION: Type a single opening curly brace"** — concrete behavioral instruction
3. **SPOT-CHECK replaces "trace EVERY"**: "Trace 2-3 examples per article section, 2-3 per coding problem — NOT all of them. If a spot-check reveals an error, dig deeper on THAT problem only."
4. **BOTTOM — Short FINAL REMINDER**: "If you catch yourself drafting a trace instead of JSON — STOP and switch to JSON immediately."

### Run 19 results

- ✅ Valid JSON produced: ~4.7K tokens of 8K budget (56% headroom)
- ✅ No "Thought:" preamble
- ✅ Spot-checked 3/3 coding + 8/10 MCQs (not "EVERY" example)
- ✅ Verdict: `rejected` — correctly identified 3 CRITICAL + 2 HIGH bugs:
  1. **MCQ q_ds_arrays_5**: correct answer is 19 but option B says 18, 19 isn't even an option
  2. **Coding cp_ds_arrays_2**: duplicated malformed example with wrong output `[21,13]`
  3. **Coding cp_ds_arrays_2 test case 4**: expected `[53,5,33]` should be `[56,5,33]`

### 🔧 FIXED: Code fence parsing in verdict/coverage paths

The Reviewer wraps its JSON in ` ```json ``` ` fences. In the coverage increment and verdict print logic (`main.py` ~lines 938 and 966), only `_strip_double_braces()` was called — missing `_strip_code_fences()`. This caused `json.loads()` to silently fail, hiding the `rejected` verdict behind `max(old_0.85, 0.25) = 0.85`.

**Fix**: Both paths now chain `_strip_code_fences()` → `_strip_double_braces()` before `json.loads()`. The `_validate_task_outputs()` path at line 375 already chained them correctly.

### 🆕 Created `test_reviewer.py`

Isolated Reviewer test — runs ONLY the Reviewer agent against existing content, bypassing Research/Writer/Quiz/Coding. **Cost: ~$0.10 vs ~$1.00 full pipeline.** Used to verify Reviewer prompt changes before committing to a full 5-agent pipeline.

---

## CLAUDE.md / AGENTS.md updates

Added 4 new sections to both files (kept in sync):
1. **Isolated Reviewer testing** (~line 136-143): test_reviewer.py usage and run command
2. **`_save_task_output()` wrapping** (~line 158): why individual task JSONs have different shape than combined JSON
3. **Code fence parsing in verdict/coverage paths** (~line 160): bug documentation and fix
4. **Verified working in run 19** (~line 204): metrics and two-tier structure confirmation

---

## Files changed this session

| File | Change | Why |
|------|--------|-----|
| `advaita_agents/main.py` | Added `chr`, `ord` to safe_namespace builtins | Fix `NameError` false positives in solution validation |
| `advaita_agents/main.py` | `_check_one_case`: try `"expected"` key, fall back to `"output"` | Agent uses both key names; 7/9 mismatches were false positives |
| `advaita_agents/main.py` | Added `_strip_code_fences()` to verdict/coverage paths (lines 938, 967) | Reviewer wraps JSON in code fences — caused silent parse failure |
| `advaita_agents/tasks/content_tasks.py` | Two-tier Reviewer prompt restructure | Run 18 found "trace EVERY" contradicted "write JSON" — model traced everything, produced no verdict |
| `advaita_agents/test_reviewer.py` | **NEW** — isolated Reviewer test | ~$0.10 per run vs ~$1.00 full pipeline; verify prompt changes safely |
| `CLAUDE.md` | +4 sections: test_reviewer, save_task_output, code fence fix, run 19 docs | Comprehensive documentation of runs 17-19 |
| `AGENTS.md` | Synced from CLAUDE.md | Identical after line 5 |
| `published_index.json` | ds_arrays: 0.85 (unchanged from run 17) | Run 19 rejected covered by `max(old, new)` |

---

## Pending work

### 1. Fix 3 CRITICAL bugs in ds_arrays content and re-run pipeline
```bash
uv run python advaita_agents/main.py produce --topic-id ds_arrays
```
The Reviewer found bugs that need fixing in the agent prompts (not the content — these are agent output errors):
- MCQ q_ds_arrays_5: correct answer not in options list (prompt guardrail issue)
- cp_ds_arrays_2: duplicated malformed example + wrong expected test output

### 2. (Optional) Fix coding agent key consistency
Update `content_tasks.py` Coding task prompt to use `"expected"` for ALL test case and example output fields. Currently the agent uses `"output"` for examples and `"expected"` for test_cases. The validator fallback handles this, but consistency would be cleaner.

### 3. Next topic pipeline
After ds_arrays reaches `approved`, move to next topic from `roadmap_scored.json`.

## Key files
- `advaita_agents/main.py` — pipeline orchestration, validation, sandbox, verdict parsing
- `advaita_agents/tasks/content_tasks.py` — two-tier Reviewer prompt (lines 433-504), quality guardrails
- `advaita_agents/test_reviewer.py` — isolated Reviewer test (~$0.10/run)
- `content_output/ds_arrays/` — run 17 (152819), run 19 (162528) output files
- `published_index.json` — `ds_arrays: 0.85`
- `CLAUDE.md` / `AGENTS.md` — full documentation synced

---

## Run 20 — Guardrail improvements + content fixes (2026-06-17)

### Guardrails added to `content_tasks.py`

**Quiz task:**
- **CHECK 4 — OPTION-VALUE MATCH**: After computing the correct answer numerically, verify the exact value appears in the option text. Prevents self-contradictions where explanation computes 19 but option says 18.
- **DISTRACTOR DISTINCTNESS**: Every distractor must describe a DIFFERENT outcome. Two options with identical outcomes (even for different reasons) reduce the question to 3-option.

**Coding task:**
- **NO DUPLICATE DRAFT EXAMPLES**: Each example must appear exactly ONCE. Draft versions with inline corrections must be deleted before submission.
- **DIFFERENCE ARRAY CORRECTNESS**: Diff array has size n+1, so `diff[r+1] -= v` is always safe for r <= n-1. Don't guard with `if r + 1 < n`.
- **TEST CASE VERIFICATION** strengthened: Explicitly mentions difference-array reconstruction, sliding-window enumeration, and manual recomputation from scratch.

### Run 20 results

- **Verdict**: `approved_with_minor_fixes` (improved from run 19's `rejected`)
- **Quiz**: Clean — no CRITICAL MCQ bugs. All correct answers match options. Distractor quality: 8/10, Explanations: 9/10.
- **Coding**: Still had same bug classes despite stronger guardrails:
  1. cp_ds_arrays_2 test case 4: expected=4 should be 6 (prefix-sum subarray count)
  2. cp_ds_arrays_3: Duplicate draft example with inline self-correction
  3. cp_ds_arrays_3: Example claims [3,2,1] has ≤2 distinct types (it has 3)
- **Automated validator** caught both mismatches (fixed before Reviewer run)

### Content fixes applied (manual post-generation)

All 5 CRITICAL + MODERATE fixes from Reviewer's list applied to individual output files:
1. cp_ds_arrays_2 test case 4: expected "4" → "6"
2. cp_ds_arrays_3 examples: Removed duplicate draft example, fixed [3,2,1] reference
3. Article: Removed "wait, verify:" self-correction comment in subarray_sum_equals_k
4. Quiz q_ds_arrays_7: Fixed distractor C contradiction (4+2+5=11, not 9)

### test_reviewer.py verified fixed content

- Ran isolated Reviewer against fixed content → `approved_with_minor_fixes`
- 5 remaining fixes all MINOR (pedagogical clarifications, missing subtopic bullet, variable name consistency)
- No CRITICAL or HIGH issues remain

### Key insight: Coding agent cannot reliably verify its own output

The same bug class (wrong test case expected values, duplicate draft examples) persists across runs 19 and 20 despite progressively stronger guardrails. The LLM fundamentally cannot execute its own code mentally and verify outputs. The automated validator `_validate_coding_solutions()` catches wrong expected values post-hoc, but there's no auto-fix mechanism.

**Future improvement**: Consider running `_validate_coding_solutions()` as a pre-Reviewer step and auto-correcting mismatched expected values, or adding a "test case auto-fix" pass before the Reviewer runs.

### State
- `published_index.json`: `{"ds_arrays": 0.85}` (approved_with_minor_fixes)
- Remaining fixes are all minor/pedagogical — content is publication-ready at 0.85

### Files changed this session

| File | Change | Why |
|------|--------|-----|
| `advaita_agents/tasks/content_tasks.py` | +4 Quiz guardrails (CHECK 4, DISTRACTOR DISTINCTNESS) | Prevent MCQ correct-answer-not-in-options bug from run 19 |
| `advaita_agents/tasks/content_tasks.py` | +3 Coding guardrails (no duplicate examples, diff array, stronger test verification) | Prevent draft artifacts + wrong expected outputs |
| `content_output/ds_arrays/quiz_content_20260616_162528.json` | Fixed q_ds_arrays_5 option B (18→19), q_ds_arrays_4 distractor D, q_ds_arrays_8 option C | Run 19 content fixes (safety net) |
| `content_output/ds_arrays/coding_problems_20260616_162528.json` | Removed duplicate example, fixed test case 4, fixed diff array code | Run 19 content fixes |
| `content_output/ds_arrays/article_content_20260616_162528.json` | Fixed "reportedlycommon" typo | Run 19 content fix |
| `content_output/ds_arrays/coding_problems_20260617_041928.json` | Fixed test case 4 (4→6), removed duplicate example | Run 20 content fixes |
| `content_output/ds_arrays/article_content_20260617_041928.json` | Removed "wait, verify:" self-correction comment | Run 20 content fix |
| `content_output/ds_arrays/quiz_content_20260617_041928.json` | Fixed q_ds_arrays_7 distractor C contradiction | Run 20 content fix |
| `advaita_agents/test_reviewer.py` | Fixed COMBINED_PATH to use absolute path from script dir | Bug fix — relative path resolved from wrong cwd |

### Next steps

1. **Move to next topic** from `roadmap_scored.json` (ds_arrays is at 0.85, acceptable for now)
2. **Coding agent auto-fix**: Consider running `_validate_coding_solutions()` as a pre-Reviewer step that auto-corrects expected values in the coding JSON before the Reviewer sees it
