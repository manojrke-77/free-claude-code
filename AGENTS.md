# AGENTS.md

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
- **`config/`** — `settings.py` (Pydantic Settings with all env vars), `provider_catalog.py` (provider metadata + capabilities), `provider_ids.py`
- **`core/anthropic/`** — Shared protocol helpers: SSE building, Anthropic↔OpenAI conversion, thinking block parsing, tool parsing, token counting
- **`providers/`** — Transport layer. Two base classes: `AnthropicMessagesTransport` (deepseek, wafer, kimi, fireworks, llama.cpp, ollama) and `OpenAIChatTransport` (nvidia_nim, open_router, mistral, gemini, groq, cerebras, lmstudio). Register new providers in `registry.py`.
- **`cli/`** — Package entry points (`fcc-server`, `fcc-claude`, `fcc-init`) and Claude CLI process management
- **`messaging/`** — Discord/Telegram bot adapters with session trees, transcript processing, voice transcription

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

### File structure

```
advaita_agents/
  main.py                  # CLI entry point (4 commands)
  crew.py                  # Crew assembly (TopicStrategyCrew, ContentProductionCrew)
  taxonomy.py              # 44-topic master taxonomy + scoring constants + utilities
  interactive.py           # 4-step interactive topic selection wizard
  agents/
    content_agents.py      # 5 production agents (Research→Writer→Quiz→Coding→Reviewer)
    topic_strategist.py    # 1 strategy agent (roadmap planning, demand signals)
  tasks/
    content_tasks.py       # 5 production tasks with quality guardrails
    topic_curation.py      # 3 strategy tasks (demand collection, prioritization, gap analysis)
```

### Data flow

```
main.py commands
  ├─ roadmap  → TopicStrategyCrew → roadmap.json (AI-generated, via DeepSeek agent)
  │                                   roadmap_scored.json (lightweight fallback)
  ├─ produce  → ContentProductionCrew → content_output/<topic_id>/{5 task outputs + combined JSON}
  │                                   → published_index.json (updated with coverage %)
  ├─ gap      → local-only computation (NO API calls) → gap_report.json
  └─ interactive → taxonomy browser → delegates to _produce_topic()
```

**Key data files** (repo root):
- `roadmap.json` / `roadmap_scored.json` — prioritized topic roadmap
- `published_index.json` — `{topic_id: coverage_pct (0.0–1.0)}` — feeds gap analysis + roadmap scoring
- `gap_report.json` — structured gap report (fully/partial/missing/stale topics)
- `content_output/<topic_id>/` — per-topic output directory with 5 individual task JSONs + combined JSON

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

### Content production pipeline

5 sequential tasks via CrewAI `Process.sequential`:

1. **Research** (DeepSeek, max_iter=12) → web searches + scrapes → structured research notes
2. **Writer** (Claude) → markdown article (beginner→intermediate→advanced structure)
3. **Quiz Designer** (Claude) → JSON array of MCQs with distractors + explanations
4. **Coding Problem Designer** (Claude) → JSON array of coding problems with test cases + solutions
5. **Technical Reviewer** (Claude) → quality gate: verdict (approved/rejected) + numbered fix list

The Reviewer is the quality bottleneck — it catches wrong test outputs, unverifiable claims, truncated code, and pedagogical issues. Task prompts contain explicit quality guardrails (e.g. banned percentages without cited sources, required manual test case verification). When rejected, `published_index.json` records partial coverage (0.25 for rejected, 0.85 for approved_with_minor_fixes, 1.0 for approved).

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

**Key discovery — `⛔ FINAL OUTPUT RULE` as the universal format-compliance fix:** Positional salience matters. A guardrail in the middle of a 60-line task description is invisible; the same guardrail as the LAST LINE before `expected_output` reliably prevents "Thought:" preambles. All three Claude agents (Quiz, Coding, Reviewer) now end with this pattern:

```
⛔ FINAL OUTPUT RULE (read this last — it overrides everything above):
Your response MUST start with '[' (or '{' for Reviewer) and end with ']' (or '}').
Nothing before the opening bracket/brace. No "Thought:" or "Let me" preamble.
JUST the JSON. If even ONE character appears before/after, your submission is void.
```

Before this fix, the Quiz and Reviewer agents regularly consumed all tokens on internal monologue traces, producing no valid JSON. After the fix, all three agents produce valid JSON (Quiz: 100%, Reviewer: produces valid JSON but may wrap in `{{ }}` from template confusion).

### Post-production JSON validation

After CrewAI kickoff, `_validate_task_outputs()` in `main.py` runs structural checks on quiz, coding, and review outputs BEFORE the Reviewer's verdict summary is printed:

- **Quiz**: Validates JSON parses, correct item count, `correct_index` in-range, detects "Thought:" preambles
- **Coding**: Detects "Thought:" preambles (format compliance failure), validates JSON parses, correct item count
- **Reviewer**: Detects "Thought:" preambles, validates JSON parses, checks for `verdict` field
- **Truncation detection**: Reports parse errors with position context so token limits can be diagnosed immediately
- `_strip_code_fences()` handles agents that wrap their JSON in ` ```json ... ``` ` fences
- `_strip_double_braces()` normalizes `{{...}}` → `{...}` (Reviewer sometimes copies the expected_output template pattern literally)

Validation errors are printed but don't block the combined save — they surface structural failures instantly instead of burying them in the review JSON.

### Fix-cycle: automated solution validation

`_validate_coding_solutions()` in `main.py` runs every coding problem's solution code against its own test cases:

1. Parses the coding JSON, extracts the optimal solution code
2. Finds the function name via a balanced-paren signature scanner
3. Executes the code in a **sandboxed namespace** (restricted builtins + allowed stdlib modules only)
4. Runs each test case's input through the solution and compares output to `expected`
5. Returns list of MISMATCH messages

Input parsing supports three formats: bare literals (`"[3,7,1,9,4]"` → single positional arg), newline-separated assignments, and comma-separated assignments (via `_split_assignments()` state-machine parser respecting brackets/parens/quotes). Argument mapping uses `inspect.signature()` with positional fallback when input var names don't match param names.

This catches the #1 rejection cause: the Coding agent invents expected outputs that its own solution code doesn't produce.

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

### Reviewer JSON-first constraint

The Reviewer task ends with `⛔ FINAL OUTPUT RULE`: the entire response must be ONLY the review JSON, starting with `{` and ending with `}`. No code traces, no "verifying…" monologue, no text outside the JSON. WRITE THE JSON FIRST with 1-2 sentence assessments. This constraint exists because the Reviewer previously consumed all 8192 tokens exhaustively tracing every code example line-by-line, producing no verdict JSON at all. The final output rule directs: "A shallow review that produces valid JSON is FAR better than a thorough review that produces nothing."

**Note:** The Reviewer sometimes confuses `{{` in Python format-string templates with literal output, producing `{{...}}` (double-brace wrapper). The `_strip_double_braces()` function in `main.py` normalizes this back to `{...}` before parsing.

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
- `main.py` no longer imports `create_topic_strategy_crew` — gap analysis is fully offline

### Run commands

```bash
uv sync --group content                                    # install crewai deps
uv run python advaita_agents/main.py roadmap               # generate content roadmap (AI)
uv run python advaita_agents/main.py produce --topic-id ds_arrays  # produce one topic
uv run python advaita_agents/main.py produce               # produce all TIER 1 topics
uv run python advaita_agents/main.py interactive           # interactive wizard
uv run python advaita_agents/main.py gap                   # gap analysis (local, instant)
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
