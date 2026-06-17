"""
Run Phase 2 (Reviewer-only) against existing Phase 1 content.

Usage: uv run python advaita_agents/run_phase2.py [timestamp]

Defaults to the latest content_output/<topic_id>/*_<timestamp>.json files.
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

for _proxy_var in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
    if _proxy_var in os.environ:
        del os.environ[_proxy_var]

if not os.getenv("ANTHROPIC_API_KEY"):
    print("Missing ANTHROPIC_API_KEY in advaita_agents/.env")
    sys.exit(1)

from advaita_agents.crew import create_reviewer_crew
from advaita_agents.main import _strip_code_fences, _strip_double_braces

# ── Config ─────────────────────────────────────────────────────────────

TOPIC_ID = "ds_arrays"
TOPIC_LABEL = "Arrays & Strings"
TOPIC_DIR = Path(f"content_output/{TOPIC_ID}")

# Use provided timestamp or find latest
if len(sys.argv) > 1:
    TIMESTAMP = sys.argv[1]
else:
    # Find latest article_content file
    article_files = sorted(TOPIC_DIR.glob("article_content_*.json"), reverse=True)
    if not article_files:
        print("No article_content files found.")
        sys.exit(1)
    TIMESTAMP = article_files[0].stem.replace("article_content_", "")
    print(f"Using latest timestamp: {TIMESTAMP}")


def load_content(key: str) -> str:
    path = TOPIC_DIR / f"{key}_{TIMESTAMP}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and list(data.keys()) == ["raw_output"]:
        return data["raw_output"]
    return json.dumps(data, ensure_ascii=False)


article_raw = load_content("article_content")
quiz_raw = load_content("quiz_content")
coding_raw = load_content("coding_problems")

print(
    f"Loaded: article={len(article_raw):,} chars, "
    f"quiz={len(quiz_raw):,} chars, "
    f"coding={len(coding_raw):,} chars"
)

# ── Run Reviewer ───────────────────────────────────────────────────────

print("\n[PHASE 2] Running Reviewer (~$0.10)...")

crew = create_reviewer_crew(
    topic_id=TOPIC_ID,
    topic_label=TOPIC_LABEL,
    article_raw=article_raw,
    quiz_raw=quiz_raw,
    coding_raw=coding_raw,
)

result = crew.kickoff()
review_raw = str(result) if result is not None else ""

# ── Save ───────────────────────────────────────────────────────────────

review_path = TOPIC_DIR / f"review_report_{TIMESTAMP}.json"
try:
    review_data = json.loads(review_raw)
except (json.JSONDecodeError, TypeError):
    review_data = {"raw_output": review_raw}

review_path.write_text(json.dumps(review_data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n[OK] review_report saved to {review_path}")

# ── Parse and display verdict ──────────────────────────────────────────

clean = _strip_double_braces(_strip_code_fences(review_raw))
try:
    rj = json.loads(clean)
    verdict = rj.get("verdict", "unknown")
    fixes = rj.get("required_fixes", [])
    print(f"\n{'=' * 60}")
    print(f"  VERDICT: {verdict.upper()}")
    print(f"  FIXES:   {len(fixes)}")
    print(f"{'=' * 60}")
    for i, f in enumerate(fixes):
        print(f"  {i + 1}. {str(f)[:200]}")
except json.JSONDecodeError as exc:
    pos = exc.pos
    ctx = clean[max(0, pos - 40) : pos + 40] if pos > 0 else "N/A"
    print(f"\n[FAIL] Invalid Reviewer JSON: {exc}")
    print(f"  Position {pos} context: '{ctx}'")
    print(f"\nRaw output ({len(review_raw):,} chars):")
    print(review_raw[:500])
