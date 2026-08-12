# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Keep AGENTS.md and CLAUDE.md identical.

## ARCHITECTURE

This is an Anthropic-compatible proxy that routes Claude Code traffic to 17+ provider backends. The request flow:

```
Claude Code CLI → FastAPI (/v1/messages) → ModelRouter → Provider Transport → Provider API
                                    ↑                                    ↓
                            /v1/models                          Anthropic SSE
                         (gateway picks /model)               (normalized back)
```

**Key layers:**
- **`server.py`** — ASGI entry point; builds the app from `api.app.create_asgi_app()`
- **`api/`** — FastAPI routes (`/v1/messages`, `/v1/messages/count_tokens`, `/v1/models`), model routing, request detection/optimizations, admin UI
- **`config/`** — `settings.py` (Pydantic Settings with all env vars), `provider_catalog.py` (provider metadata + capabilities), `provider_ids.py`, `constants.py` (shared defaults), `paths.py` (runtime paths), `logging_config.py`, `nim.py` (NIM-specific settings)
- **`core/anthropic/`** — Shared protocol helpers: SSE building, Anthropic↔OpenAI conversion, thinking block parsing, tool parsing, token counting
- **`providers/`** — Transport layer. Two base classes: `AnthropicMessagesTransport` (open_router, deepseek, wafer, kimi, fireworks, zai, lmstudio, llamacpp, ollama) and `OpenAIChatTransport` (nvidia_nim, gemini, mistral, mistral_codestral, opencode, opencode_go, cerebras, groq). Register new providers in `registry.py`.
- **`cli/`** — Package entry points (`fcc-server`, `fcc-claude`, `fcc-init`) and Claude CLI process management
- **`messaging/`** — Discord/Telegram bot adapters with `platforms/` (base + Discord + Telegram), `trees/` (message session tree data structures + queue), `rendering/` (platform-specific markdown), `voice.py`, `transcript.py`, `transcription.py` (local Whisper + NVIDIA NIM voice)

**Config file cascade (later overrides earlier):**
1. `.env` (repo root)
2. Managed env file (Admin UI writes)
3. `FCC_ENV_FILE` (explicit override)

**Anthropic SDK proxy hijack:** The `fcc-claude` launcher sets `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` in the shell. If inherited by other Python processes, the Anthropic SDK routes ALL calls to the local proxy (`localhost:8082`) instead of `api.anthropic.com`. Any code making direct Anthropic SDK calls must clear these env vars first:
```python
for v in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
    os.environ.pop(v, None)
```

**`advaita_agents/`** — Standalone CrewAI content agent project. Not packaged in the wheel. Uses `[dependency-groups] content` (`crewai`, `crewai-tools`). Has its own `.env`. Install with `uv sync --group content`.

**Notable subsystems:**
- **Admin UI** at `/admin` — localhost-only web UI for editing proxy settings, validating changes, and checking provider liveness. Routes in `api/admin_routes.py`, templates in `api/admin_urls.py`.
- **Web server tools** in `api/web_tools/` — proxies `web_search` / `web_fetch` tool calls (from Claude Code's server-side tools) through provider backends with egress policy enforcement (`egress.py`), streaming (`streaming.py`), and request parsing (`parsers.py`).
- **Voice transcription** — `messaging/transcription.py` (local Whisper via Hugging Face transformers + NVIDIA NIM via Riva client in `providers/nvidia_nim/voice.py`). Opt-in extras: `voice` (Riva client), `voice_local` (torch, transformers, librosa).
- **Messaging session trees** in `messaging/trees/` — `MessageTree`/`MessageNode` with snapshot-capable `_SnapshotQueue`. Each Discord/Telegram reply is one node; branching forms a conversation tree. `queue_manager.py` handles cross-session message serialization.
- **`api/runtime.py`** — `AppRuntime` owns the `ProviderRegistry`, `CLISessionManager`, and model-list refresh lifecycle at startup/shutdown.

### File structure

```
advaita_agents/
  main.py                     # CLI entry point (4 commands: roadmap, produce, interactive, gap)
  crew.py                     # Crew assembly (TopicStrategyCrew, ContentGenerationCrew, ReviewerOnlyCrew, ContentProductionCrew [legacy])
  taxonomy.py                 # 44-topic master taxonomy + scoring constants + utilities
  interactive.py              # 4-step interactive topic selection wizard
  pre_publish_scanner.py      # Automated quality checks (<1 sec, $0) — replaces AI Reviewer for ~80% of runs
  run_phase2.py               # Optional standalone Reviewer re-run against existing content
  test_reviewer.py            # Isolated Reviewer test (~$0.10 vs $1.00 full pipeline)
  agents/
    content_agents.py         # 5 production agents (Research→Writer→Quiz→Coding→Reviewer)
    topic_strategist.py       # 1 strategy agent (roadmap planning, demand signals)
  tasks/
    content_tasks.py          # 5 production tasks with quality guardrails
    topic_curation.py         # 3 strategy tasks (demand collection, prioritization, gap analysis)
```

### Data flow

```
main.py commands
  ├─ roadmap  → TopicStrategyCrew → roadmap.json (AI-generated, via DeepSeek agent)
  │                                   roadmap_scored.json (lightweight fallback)
  ├─ produce  → ContentGenerationCrew (4 agents) → auto-fix → pre-publish scanner
  │            → ⏸ Unified Checkpoint (publish / fix / review / discard)
  │              ├─ publish  → Skip AI Reviewer, publish at 0.85 ($0.10 saved)
  │              └─ review   → ReviewerOnlyCrew (1 agent) → human sign-off → publish
  │            → content_output/<topic_id>/{6 task outputs + combined JSON}
  │            → published_index.json (updated with coverage %)
  ├─ gap      → local-only computation (NO API calls) → gap_report.json
  └─ interactive → taxonomy browser → delegates to _produce_topic()
```

**Key data files** (all paths relative to repo root — `main.py` resolves them from `Path(".")`):
- `roadmap.json` / `roadmap_scored.json` — prioritized topic roadmap
- `published_index.json` — `{topic_id: coverage_pct (0.0–1.0)}` — feeds gap analysis + roadmap scoring
- `gap_report.json` — structured gap report (fully/partial/missing/stale topics)
- `content_output/<topic_id>/` — per-topic output directory with 6 JSONs per run: 5 individual task files (research_notes, article_content, quiz_content, coding_problems, review_report) + combined
- Note: stale copies of `published_index.json` and `gap_report.json` may exist inside `advaita_agents/` — ignore those; the live ones are in the repo root

### Agent lineup

```
Topic Strategist → Research → Writer → Quiz → Coding → Reviewer
   DeepSeek       DeepSeek   Claude   Claude   Claude    Claude
```

- **Topic Strategist + Research on DeepSeek** — the only agents with tools (SerperDev + ScrapeWebsite). Claude Sonnet 4.6 does NOT support assistant message prefill, which CrewAI needs for tool-calling loops. DeepSeek handles tool iterations reliably. Research Agent uses `max_iter=12` (needs ~8-10 iterations for 5+ web searches + scrapes).
- **Writer, Quiz, Coding, Reviewer on Claude** — all student-facing output runs on Claude Sonnet 4.6 for quality.
- **No agents use Gemini** — the original Gemini agents were migrated to Claude.

The `main.py` clears `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` from `os.environ` before agent imports. These proxy env vars are inherited from the free-claude-code shell context and would hijack Anthropic SDK calls to `localhost:8082` instead of `api.anthropic.com`. It also loads `advaita_agents/.env` via dotenv before any CrewAI imports.

### Scoring system (`taxonomy.py`)

Each of the 44 leaf topics has: `id`, `label`, `weight` (1-10), `difficulties`, `prerequisites`, `subtopics`, `companies`, `content_types`. Scoring formula:
- 40% demand_signal (from web scraping, normalized to 0-10)
- 40% taxonomy_weight (1-10 directly)
- 20% coverage_gap ((1.0 - coverage) × 10, boosted to 10 for core topics with <50% coverage)

Tier cutoffs: ≥7.0 = TIER 1, ≥4.5 = TIER 2, <4.5 = TIER 3.

### Content production pipeline (scanner-first, single checkpoint)

The pipeline runs Phase 1 (4 agents), then a pre-publish scanner, then a single unified human checkpoint. The AI Reviewer is optional — invoked only when the human chooses `review` at the checkpoint.

```
Phase 1: Generation Crew (4 agents, ~$0.95)
  Research → Writer → Quiz → Coding
    ↓
Auto-fix (sandbox solution validation)
    ↓
Pre-Publish Scanner (<1 sec, $0)
    ↓
Unified Human Checkpoint
  ├─ publish  → Skip AI Reviewer, publish at 0.85 ($0.10 saved)
  ├─ fix      → Edit content files, re-run pipeline
  ├─ review   → Run AI Reviewer (~$0.10) for deeper quality check
  └─ discard  → No coverage update
    ↓
published_index.json updated
```

**Phase 1 — Content Generation** (4 agents, ~$0.95, via `create_content_generation_crew()`):
1. **Research** (DeepSeek, max_iter=12) → web searches + scrapes → structured research notes
2. **Writer** (Claude) → markdown article (beginner→intermediate→advanced structure)
3. **Quiz Designer** (Claude) → JSON array of MCQs with distractors + explanations
4. **Coding Problem Designer** (Claude) → JSON array of coding problems with test cases + solutions

Then auto-fix runs (`_validate_coding_solutions(fix=True)`) — sandbox execution corrects wrong expected test values.

**Pre-Publish Scanner** (`pre_publish_scanner.py`, <1 sec, $0): Automated quality checks that replace the AI Reviewer for ~80% of pipeline runs. Catches everything computationally verifiable:

| Check | How | Catches |
|---|---|---|
| Test case expected values | Sandbox execute solution code | Wrong expected outputs (Reviewer's #1 catch) |
| MCQ answer in options | `correct_index` in range, answer value text-match vs explanation | Answer computed as 19 but option says 18 |
| Duplicate content | Hash examples, flag identical pairs | Draft artifacts with inline self-corrections |
| Self-monologue artifacts | Regex for "wait,", "actually let me", "Thought:", "hmm" | Writer artifacts that waste Reviewer tokens |
| JSON validity | `json.loads()` + truncation detection | Format compliance failures |
| Distractor distinctness | SequenceMatcher ratio between option texts | Near-identical distractors (code-MCQ threshold: 95%, plain-text: 85%) |
| Article structure | Heading count, code block count, min length | Unstructured or truncated articles |
| Sandbox limitations | Distinct WARN for TreeNode/ListNode errors | Prevents false FAILs on tree/graph problems |

Returns `ScanReport` with PASS/FAIL and per-check `Finding` objects. FAIL = issues that need fixing or an optional AI Reviewer pass. PASS = content publication-ready at 0.85 (standard). Usage:
```python
from advaita_agents.pre_publish_scanner import scan_topic
report = scan_topic("ds_arrays", article_raw=..., quiz_raw=..., coding_raw=...)
if report.verdict == "PASS":
    print("Ready to publish at 0.85")
```

**Unified Human Checkpoint** (`_human_unified_checkpoint`): Single checkpoint replacing the old two-gate flow (CP#1: human edits + CP#2: Reviewer sign-off). Shows scanner results and offers 4 options:
- `publish` — Standard 0.85 coverage, skip AI Reviewer (~80% of runs, saves $0.10 and 1-2 min)
- `fix` — Edit content files and re-run the pipeline
- `review` — Run AI Reviewer for deeper quality check (~20% of runs)
- `discard` — No coverage update

**AI Reviewer** (Claude, ~$0.10, via `create_reviewer_crew()`): Optional Phase 2, invoked only via `review` at the checkpoint. Runs the Technical Reviewer with content embedded directly in task description (no CrewAI context chaining). Verdict: approved (1.0), approved_with_minor_fixes (0.85), rejected (0.25).

Coverage mapping: scanner-PASS → 0.85 (standard). AI Reviewer: `rejected → 0.25`, `approved_with_minor_fixes → 0.85`, `approved → 1.0`.

The old two-checkpoint pipeline and monolithic `create_content_production_crew()` (5 agents in one kickoff) are still available for backward compatibility.

### Quality guardrail system

Task prompts in `content_tasks.py` contain ~25 guardrails organized into 6 root-cause categories, discovered from analyzing 16 consecutive pipeline runs:

| Category | What it prevents | Example violations | Added in |
|---|---|---|---|
| **Self-monologue ban** | LLM narration bleeding into final output | "wait," "actually let's recalculate," "hmm" in articles/MCQs | Round 1 |
| **Output verification** | Unverified answers shipped as final content | MCQ correct answer not among options, wrong expected test output | Round 1 |
| **JSON validity** | Malformed JSON breaking the publish pipeline | Duplicate keys, keys with colons (`"correct_index: "`), trailing commas | Round 1 |
| **Completeness** | Truncated or unfinished content | Explanations cut off mid-sentence, missing counterexamples | Round 1 |
| **Reference accuracy** | Wrong hyperlinks or problem categorization | Valid Palindrome link leads to string rotation page, LeetCode # mismatch | Round 2 |
| **Format compliance** | Design scratch-notes submitted instead of JSON | Agent outputs "Thought: I need to create..." instead of JSON objects | Round 2 |

Guardrails are marked `⛔ BAN` (zero-tolerance), `⛔ CRITICAL` (auto-rejection on violation), or unmarked (quality requirement — accumulates toward rejection). When content is repeatedly rejected, classify the reviewer's error list against these categories. If an error pattern doesn't fit an existing guardrail, add one that targets the root cause in the appropriate task description.

**Key discovery — prompt ordering determines token allocation:** The Quiz and Coding agents use `⛔ FINAL OUTPUT RULE` at the **bottom** of the task description (last line before `expected_output`) and it reliably prevents "Thought:" preambles — positional salience works for tasks that fit within token limits.

The **Reviewer** is different: it has to check three content types (article, MCQs, coding) AND trace code examples. When the prompt said "trace EVERY example" before "write JSON," the model exhausted all 8192 tokens on hand-tracing (run 18 traced 15+ examples mid-response) and produced no verdict JSON. The fix is a **two-tier structure**:

1. **TOP — Token budget warning** (before the checklist): explains *why* tracing kills the output. "The #1 pipeline failure is: you trace 15+ examples, run out of tokens, and produce NO JSON at all."

2. **BOTTOM — Short FINAL REMINDER** (reinforces): "If you catch yourself drafting a trace instead of JSON — STOP and switch to JSON immediately."

3. **SPOT-CHECK replaces "trace EVERY":** "Trace 2-3 examples per article section, 2-3 per coding problem — NOT all of them. If a spot-check reveals an error, dig deeper on THAT problem only."

The key insight: the impulse to "be thorough" + examples → the model traces everything. The fix isn't just repositioning text — it's removing the contradictory "trace EVERY" instruction entirely and adding a concrete numeric bound.

### Isolated Reviewer testing (`test_reviewer.py`)

`test_reviewer.py` runs ONLY the Reviewer agent against previously-generated content, bypassing the Research/Writer/Quiz/Coding agents entirely. **Cost: ~$0.10 vs ~$1.00 for a full pipeline run.** Used to verify Reviewer prompt changes before committing to a full 5-agent pipeline.

- Loads article, quiz, and coding content from `content_output/<topic_id>/combined_*.json`
- Creates a minimal Crew with just the Reviewer agent
- Validates: no "Thought:" preamble, valid JSON, verdict field present
- Run: `uv run python advaita_agents/test_reviewer.py`

### Post-production JSON validation

`_validate_task_outputs()` in `main.py` runs structural checks on quiz, coding, and review outputs after Phase 1 completes. The pre-publish scanner (`pre_publish_scanner.py`) provides deeper automated validation (<1 sec, $0) that supersedes the Reviewer for ~80% of runs. Both run before the unified checkpoint:

- **`_validate_task_outputs()`** — Fast structural checks: JSON parse validity, item count, `correct_index` in-range, "Thought:" preamble detection, truncation detection
- **Pre-Publish Scanner** — Richer validation: sandbox test case execution, MCQ answer-text matching, duplicate detection, distractor distinctness, self-monologue scanning, article structure heuristics. Returns `ScanReport` with PASS/FAIL.

- `_strip_code_fences()` handles agents that wrap their JSON in ` ```json ... ``` ` fences
- `_strip_double_braces()` normalizes `{{...}}` → `{...}` (Reviewer sometimes copies the expected_output template pattern literally)

Validation errors are printed but don't block the combined save — they surface structural failures instantly at the checkpoint.

**`_save_task_output()` wrapping:** When a raw task output fails `json.loads()`, it's wrapped as `{"raw_output": "<original text>"}`. This means individual task JSON files (e.g. `review_report_*.json`) have a different shape than the combined JSON (where all values are raw strings). Always parse individual task outputs defensively: try `json.loads()` first, then access `data.get("raw_output", data)` if it doesn't match expectations.

**Code fence parsing in verdict/coverage paths:** When the AI Reviewer runs (via `review` at the checkpoint), its output is wrapped in ` ```json ... ``` ` fences. The verdict-reading code path in the `ai_review` branch of `_produce_topic()` chains `_strip_code_fences()` → `_strip_double_braces()` before `json.loads()`. The `_validate_task_outputs()` path also chains them correctly. Run 19 revealed a missing `_strip_code_fences()` call, causing silent JSON parse failures that masked the Reviewer's `rejected` verdict (fell to `except → coverage_increment = 0.25`, but `max(old_0.85, 0.25) = 0.85` hid it). Both paths now chain both functions correctly.

### Fix-cycle: automated solution validation + auto-correction

`_validate_coding_solutions()` in `main.py` runs every coding problem's solution code against its own test cases:

1. Parses the coding JSON, extracts the optimal solution code
2. Finds the function name via a balanced-paren signature scanner
3. Executes the code in a **sandboxed namespace** with 22 restricted builtins (`len`, `range`, `list`, `dict`, `set`, `tuple`, `int`, `str`, `float`, `bool`, `chr`, `ord`, `min`, `max`, `sum`, `abs`, `sorted`, `enumerate`, `zip`, `map`, `filter`, `reversed`, `any`, `all`, `True`, `False`, `None`, `print`, `isinstance`, + exception types) and a whitelist of 5 stdlib modules (`collections`, `math`, `heapq`, `itertools`, `functools`) accessed via a custom `__import__` hook
4. Runs each test case's input through the solution and compares output to the expected value
5. Returns `(mismatches: list[str], corrected_json: str | None)`

**Auto-fix mode (`fix=True`, enabled by default in the pipeline):** When a mismatch is found, the function corrects the `expected`/`output` value in the parsed problem dict to match what the solution code ACTUALLY produces (using `json.dumps(actual)`). The corrected JSON string is returned as the second tuple element, and the pipeline re-saves the individual coding file AND uses the corrected version in the combined output that the Reviewer sees.

This eliminates the #1 pipeline rejection cause: the Coding agent cannot execute code — it can only simulate execution — so it invents wrong expected outputs that its own solution doesn't produce. No amount of prompt engineering can fix this; only actual Python execution can.

The pre-publish scanner (`pre_publish_scanner.py`) has its own independent sandbox execution (`_check_coding_test_cases()`). It additionally distinguishes between real mismatches (FAIL — solution produces a different result than expected) and sandbox limitations (WARN — TreeNode/ListNode code can't execute in the sandbox). This prevents false FAIL verdicts on tree/graph/linked-list topics.

**Key detail — `"output"` vs `"expected"` key handling:** The Coding agent uses `"output"` for examples but `"expected"` for test_cases. The validator uses `case.get("expected") or case.get("output", "")` as a defensive fallback. Auto-fix preserves whichever key was found — if the case dict has `"expected"`, it updates that; otherwise it updates `"output"`.

**`_check_one_case` return signature:** Returns `(error_or_None, actual_value)`. The second element is the function's actual return value on mismatch, or `_NO_VALUE` sentinel when the case couldn't be executed (parse error, compile error, etc.). This enables the caller to auto-correct without re-executing.

### LLM configuration (`content_agents.py`, `topic_strategist.py`)

All agents use **explicit `crewai.LLM()` constructors** with `max_tokens` set, NOT string notation (`"provider/model"`). String notation defaults to `max_tokens=4096` which silently truncates output mid-response. Values:

| Agent | Model | max_tokens | Rationale |
|---|---|---|---|
| Topic Strategist | `deepseek/deepseek-chat` | 8192 | Web search results need space |
| Research | `deepseek/deepseek-chat` | 8192 | 5+ search+scrape iterations |
| Content Writer | `anthropic/claude-sonnet-4-6` | 8192 | Full article with code examples |
| **Quiz Designer** | `anthropic/claude-sonnet-4-6` | 8192 | 10 MCQs with explanations (bumped from 6000 after truncation at 6K) |
| **Coding Problem Designer** | `anthropic/claude-sonnet-4-6` | 10000 | 3 problems with solutions + tests (bumped from 8192; Claude Sonnet API caps at ~8192 effective output, so scope was reduced from 4→3 problems, examples 3-5→2-3, test cases 8-10→5-6) |
| **Technical Reviewer** | `anthropic/claude-sonnet-4-6` | 8192 | Review JSON with numbered fixes |

### Reviewer prompt structure (two-tier)

The Reviewer is the quality bottleneck — it checks articles, MCQs, and coding problems in a single run with only 8192 output tokens. Run 18 revealed that the instruction "trace EVERY example" contradicted "write JSON first" — the thoroughness impulse won and the model consumed all tokens on hand-tracing with no verdict JSON.

The current prompt uses a **token-budget-first** design:

1. **Token budget warning at the TOP** (before any checklist) — ~100 tokens that frame the budget constraint as the first thing the model reads
2. **"YOUR FIRST ACTION: Type a single opening curly brace"** — concrete behavioral instruction
3. **Checklist with SPOT-CHECK limits** — "trace 2-3 examples per article section, 2-3 per coding problem — NOT all of them"
4. **Short FINAL REMINDER at the bottom** — reinforces the top warning without contradicting it

The old `FINAL OUTPUT RULE` said "read this last — it overrides everything above" which created an adversarial relationship between thoroughness and output. The new design makes them allies: you CAN spot-check, just do it inside the JSON.

**Verified working in run 19:** The two-tier structure produced valid JSON (~4.7K tokens of 8K budget, 56% headroom), no "Thought:" preamble, spot-checked 3/3 coding problems and 8/10 MCQs (not "EVERY" example). The Reviewer correctly identified 3 CRITICAL bugs (factually wrong MCQ answer where correct value wasn't even an option, duplicated malformed coding example, wrong test-case expected output) plus 2 HIGH issues (misleading code conditional, self-contradictory distractor explanation). Verdict: `rejected`.

**Coverage mapping:** `verdict=rejected → 0.25`, `approved_with_minor_fixes → 0.85`, `approved → 1.0` in `published_index.json`.

### Known transient failures

- **DeepSeek Chat** sometimes produces ~264-char internal monologue with no research output (not a timeout — appears to be a model-side generation abort). Re-run the pipeline.
- **DeepSeek Chat** can exhaust `max_iter=12` on tool-call loops without producing meaningful output. The Research agent is the only tool-using agent; if it fails 2+ consecutive runs, skip the topic or fall back to the lightweight roadmap scorer.
- **Anthropic API** (`api.anthropic.com`) experiences intermittent DNS resolution failures (`APIConnectionError: Connection error`). These are transient; wait a few minutes and retry.

### Gap analysis (local, no API calls)

`cmd_gap()` was rewritten from CrewAI agent-based web search to **pure local computation**:
- Scans `content_output/<topic_id>/combined_*.json` for each taxonomy topic
- Extracts verdict, content types found, and generation date from actual files
- Cross-references against `published_index.json` and the 44-topic taxonomy
- Classifies as: fully_covered, partial_coverage (incomplete/missing types/rejected), completely_missing, stale (>365 days)
- Gap analysis is fully offline — no API calls, pure local computation against taxonomy + content_output + published_index

### Run commands

```bash
uv sync --group content                                    # install crewai deps
uv run python advaita_agents/main.py roadmap               # generate content roadmap (AI)
uv run python advaita_agents/main.py produce --topic-id ds_arrays  # produce one topic
uv run python advaita_agents/main.py produce               # produce all TIER 1 topics
uv run python advaita_agents/main.py interactive           # interactive wizard
uv run python advaita_agents/main.py gap                   # gap analysis (local, instant)
uv run python advaita_agents/main.py produce --topic-id ds_arrays --skip-checkpoints  # auto-publish (no human gate)
uv run python advaita_agents/pre_publish_scanner.py ds_arrays  # run scanner against existing content
uv run python advaita_agents/test_reviewer.py              # isolated Reviewer test (~$0.10, no full pipeline)
uv run python advaita_agents/run_phase2.py [timestamp]     # optional Reviewer re-run against existing content
```

## CODING ENVIRONMENT

- Install astral uv using "curl -LsSf https://astral.sh/uv/install.sh | sh" if not already installed and if already installed then update it to the latest version
- Install Python 3.14.0 stable using `uv python install 3.14.0` if not already installed (requires uv >=0.9; see `[tool.uv] required-version` in `pyproject.toml`)
- Always use `uv run` to run files instead of the global `python` command.
- Current uv ruff formatter is set to py314 which has supports multiple exception types without paranthesis (except TypeError, ValueError:)
- Read `.env.example` for environment variables.
- All CI checks must pass; failing checks block merge.
- Add tests for new changes (including edge cases).
- Before pushing, prefer `./scripts/ci.sh` (macOS/Linux) or `.\scripts\ci.ps1` (Windows) to run the local CI sequence; requires `uv` on PATH. The local scripts run Ruff in repair mode (`ruff format`, then `ruff check --fix`) before type checking and tests.
- Use `--only` / `--skip` (PowerShell: `-Only` / `-Skip`) to run a subset when iterating; use `--dry-run` to print commands without running them.
- GitHub CI remains check-only for Ruff (`ruff format --check`, `ruff check`) so branch protection verifies committed code.
- Fall back to individual repair commands when debugging local failures: `uv run ruff format`, `uv run ruff check --fix`, `uv run ty check`, `uv run pytest -v --tb=short`. Use GitHub-style checks only when verifying enforcement locally: `uv run ruff format --check`, `uv run ruff check`.
- Do not add `# type: ignore` or `# ty: ignore`; fix the underlying type issue.
- Do not add `from __future__ import annotations`; Python 3.14 native lazy annotations are the project standard.
- All 5 check IDs are represented in `scripts/ci.sh` / `scripts/ci.ps1` and enforced in `tests.yml` on push/merge (parallel jobs: suppression grep, ruff-format, ruff-check, ty, pytest).
- GitHub CI runs on `push`, `pull_request`, and `merge_group` so required checks validate merge queue candidates before they land.
- Repository protection should use rulesets: a non-bypassable main integrity ruleset requires pull requests, merge queue, required checks, and blocks direct/force pushes to `main`; a separate review ruleset may allow `Alishahryar1`/admins to bypass review only.
- Required status checks: set **required status checks** to **all** of those statuses (e.g. **Ban suppressions and legacy annotations**, **ruff-format**, **ruff-check**, **ty**, **pytest**—use the exact labels GitHub shows, which may be prefixed with **CI /**). Remove **ci** from required checks if it was previously added for the old gate job.

## TESTING

**Unit/contract tests:** `uv run pytest` (hermetic, no external services). Uses pytest-xdist with `-n auto` by default (see `pyproject.toml`). Key markers: `provider`, `messaging`, `live`, `contract`, `xdist_group(name)`.

**Smoke tests (live E2E):** Require `FCC_LIVE_SMOKE=1`. See `smoke/README.md` for full docs.
```bash
# Run all smoke (requires provider config)
FCC_LIVE_SMOKE=1 uv run pytest smoke -n 0 -s --tb=short

# Run specific targets
FCC_LIVE_SMOKE=1 FCC_SMOKE_TARGETS="providers,api" uv run pytest smoke -n auto --dist=loadgroup -s --tb=short

# Run specific provider
FCC_LIVE_SMOKE=1 FCC_SMOKE_TARGETS="deepseek" uv run pytest smoke/prereq smoke/product -n 0 -s --tb=short
```

## IDENTITY & CONTEXT

- You are an expert Software Architect and Systems Engineer.
- Goal: Zero-defect, root-cause-oriented engineering for bugs; test-driven engineering for new features. Think carefully; no need to rush.
- Code: Write the simplest code possible. Keep the codebase minimal and modular.

## ARCHITECTURE PRINCIPLES

- **Shared utilities**: Put shared Anthropic protocol logic in neutral `src/free_claude_code/core/anthropic/` modules. Do not have one provider import from another provider's utils.
- **Failure ownership**: Keep canonical failure semantics and redaction SDK-free in `core/`; providers alone classify SDK/HTTP failures and own retries; protocol/API adapters alone choose wire error types and commit-boundary serialization.
- **DRY**: Extract shared base classes to eliminate duplication. Prefer composition over copy-paste.
- **Encapsulation**: Use accessor methods for internal state (e.g. `set_current_task()`), not direct `_attribute` assignment from outside.
- **Provider-specific config**: Keep provider-specific fields (e.g. `nim_settings`) in provider constructors, not in the base `ProviderConfig`.
- **Model-independent reasoning**: Resolve client reasoning intent once at the application boundary; provider adapters translate documented provider capabilities. Never branch on upstream model names or versions to choose reasoning behavior.
- **Dead code**: Remove unused code, legacy systems, and hardcoded values. Use settings/config instead of literals (e.g. `settings.provider_type` not `"nvidia_nim"`).
- **Performance**: Use list accumulation for strings (not `+=` in loops), cache env vars at init, prefer iterative over recursive when stack depth matters.
- **Platform-agnostic naming**: Use generic names (e.g. `PLATFORM_EDIT`) not platform-specific ones (e.g. `TELEGRAM_EDIT`) in shared code.
- **No type ignores**: Do not add `# type: ignore` or `# ty: ignore`. Fix the underlying type issue.
- **Python 3.14 annotations**: Do not use `from __future__ import annotations`; rely on native lazy annotations and fix circular import boundaries instead of hiding them with annotation stringization.
- **Imports**: Prefer top-level imports. Avoid `TYPE_CHECKING` and local imports for first-party or required dependencies; if a top-level import creates a cycle, move shared types/protocols to a neutral owner.
- **Complete migrations**: When moving modules, update imports to the new owner and remove old compatibility shims in the same change unless preserving a published interface is explicitly required.
- **Maximum Test Coverage**: There should be maximum test coverage for everything, preferably live smoke test coverage to catch bugs early

## EXTENDING PROVIDERS

- **OpenAI-compatible** providers extend `OpenAIChatTransport` → implements OpenAI Chat Completions → proxy converts Anthropic SSE
- **Anthropic Messages** providers extend `AnthropicMessagesTransport` → native `/v1/messages` endpoint (fewer conversions)
- Register provider metadata in `config/provider_catalog.py` and factory wiring in `providers/registry.py`.
- Add messaging platforms by implementing the `MessagingPlatform` interface in `messaging/`.

## COGNITIVE WORKFLOW

1. **ANALYZE**: Read relevant files. Do not guess.
2. **PLAN**: Map out the logic. Identify root cause or required changes. Order changes by dependency.
3. **EXECUTE**: Fix the cause, not the symptom. Execute incrementally with clear commits.
4. **VERIFY**: Run `./scripts/ci.sh` or `.\scripts\ci.ps1`, plus relevant smoke tests when needed. Confirm the fix via logs or output.
5. **SPECIFICITY**: Do exactly as much as asked; nothing more, nothing less.
6. **PROPAGATION**: Changes impact multiple files; propagate updates correctly.
7. **VERSION**: If the commit touches production files on `main`, bump semver in the same commit (see [Versioning](#versioning-main)).

## VERSIONING (MAIN)

Every commit on `main` that changes a **production file** must include a semver bump in **`pyproject.toml`** in the **same commit**. Do not merge or push prod changes without updating the version.

### Production files

These paths count as production (runtime, packaging, or install surface):

- `src/free_claude_code/api/`, `src/free_claude_code/cli/`, `src/free_claude_code/config/`, `src/free_claude_code/core/`, `src/free_claude_code/messaging/`, `src/free_claude_code/providers/`
- `src/free_claude_code/application/`
- `.env.example`
- `pyproject.toml` (dependencies, scripts, packaging)
- `scripts/install.sh`, `scripts/install.ps1`, `scripts/uninstall.sh`, `scripts/uninstall.ps1`, `scripts/ci.sh`, `scripts/ci.ps1`

These do **not** require a version bump on their own:

- `tests/`, `smoke/`
- Docs and assets: `README.md`, `assets/`, `AGENTS.md`, `CLAUDE.md`
- CI and repo config: `.github/`, `.gitignore`

If a single commit mixes production and non-production edits, still bump the version.

### Semver rules

Use `[project].version` as `MAJOR.MINOR.PATCH`:

- **PATCH** (`x.y.Z+1`): bug fixes, refactors with no user-visible behavior change, dependency updates, packaging/install fixes.
- **MINOR** (`x.Y+1.0`): backward-compatible features—new providers, admin fields, CLI commands, config options, or behavior additions.
- **MAJOR** (`X+1.0.0`): breaking changes—removed or renamed env vars, incompatible API/CLI/default changes, or migrations users must act on.

When unsure between PATCH and MINOR, prefer PATCH for fixes and MINOR for new capability.

### Required steps

1. Classify the change and choose the bump level.
2. Update `version` in `pyproject.toml`.
3. Run `uv lock` so `uv.lock` reflects the new package version.
4. Include the version and lockfile updates in the same commit as the production change.

Example commit on `main` after a packaging fix: bump `1.2.38` → `1.2.39`, run `uv lock`, commit together with the fix.

## SUMMARY STANDARDS

- Summaries must be technical and granular.
- Include: [Files Changed], [Logic Altered], [Verification Method], [Residual Risks] (if no residual risks then say none).

## TOOLS

- Prefer built-in tools (grep, read_file, etc.) over manual workflows. Check tool availability before use.
