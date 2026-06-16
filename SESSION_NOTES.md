# Session Notes — Advaita Agents Pipeline Iteration (2026-06-15)

## State after run 16 (ds_arrays)

- **Quiz agent**: FIXED. `⛔ FINAL OUTPUT RULE` (last line before `expected_output`) reliably produces valid `[...]` JSON. No more "Thought:" preambles.
- **Reviewer agent**: PARTIALLY FIXED. Produces verdict JSON (no more silent token exhaustion), but wraps it in `{{ ... }}` double braces. Root cause: the `expected_output` template uses `{{"verdict":...}}` (Python format-string escaping) and the LLM reads the double braces literally. `_strip_double_braces()` in `main.py` handles this defensively.
- **Coding agent**: STILL TRUNCATED after 3-problem scope reduction. JSON ends mid-string at ~14.6K chars. Claude Sonnet API effectively caps output at ~8192 tokens regardless of requested `max_tokens=10000`.
- **Coding validation**: `_validate_coding_solutions()` sandbox lacks `ord`/`chr` builtins, causing 7 false-positive `NameError` mismatches. The solutions are correct; the sandbox is too restrictive.

## Files changed this session

| File | Change | Why |
|------|--------|-----|
| `CLAUDE.md` | Updated guardrail system (~17→~25, 10→16 runs), added FINAL OUTPUT RULE discovery, added fix-cycle section, updated LLM table | Document all architectural changes from 6 extra pipeline runs |
| `AGENTS.md` | Full sync from CLAUDE.md | Companion file must match |
| `advaita_agents/agents/content_agents.py` | Fixed stale comment: "4 problems" → "3 problems" | Coding agent scope was reduced but comment wasn't updated |

## Key architectural patterns discovered

### `⛔ FINAL OUTPUT RULE` — positional salience fix
Position matters more than wording. The same guardrail mid-task is invisible; as the last line before `expected_output`, it reliably prevents "Thought:" preambles across all 3 Claude agents (Quiz, Coding, Reviewer).

### `_strip_double_braces()` — template confusion defense
The Reviewer reads `{{` in the expected_output template as literal output, producing `{{\n  "verdict": ...\n}}`. Defensive stripping in `main.py` handles this. Prompt clarification ("just one brace, NOT two") may fix the root cause.

### 6 guardrail categories (from 16-run analysis)
Self-monologue ban, output verification, JSON validity, completeness, reference accuracy, format compliance.

## Pending work (priority order)

### 1. Fix sandbox builtins (`main.py` ~line 410)
Add `ord`, `chr`, `any`, `all`, `enumerate` to the sandbox namespace. Currently only these are available: `abs, bool, dict, float, int, len, list, max, min, pow, range, reversed, round, set, sorted, str, sum, tuple, type, zip`.

### 2. Re-run pipeline on ds_arrays
```bash
uv run python advaita_agents/main.py produce --topic-id ds_arrays
```
Verify:
- Reviewer now produces single-brace `{...}` (not `{{...}}`) after prompt update
- Coding truncation status with current 3-problem scope
- Validated mismatch count after sandbox builtin fix

### 3. Address Coding truncation (if still broken)
Options:
- (a) Reduce to 2 problems
- (b) Reduce examples/test cases further
- (c) Split coding into 2 sequential tasks

## Key files
- `advaita_agents/main.py` — validation functions, sandbox, pipeline orchestration
- `advaita_agents/tasks/content_tasks.py` — task prompts with ~25 guardrails
- `advaita_agents/agents/content_agents.py` — LLM configurations
- `content_output/ds_arrays/` — run 16 output files
- `published_index.json` — topic coverage tracking
