"""
Interactive content production wizard.

4-step flow before agents start:
  1. Pick a subject category
  2. Select topics (with add/delete)
  3. Select sub-topics per topic (with add/delete)
  4. Confirm and run production

Usage:  uv run advaita_agents/main.py interactive
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from advaita_agents.taxonomy import TAXONOMY, DIFFICULTY_BEGINNER


# ── ANSI helpers ──────────────────────────────────────────────────────────

C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_MAGENTA = "\033[35m"


def _header(text: str) -> str:
    return f"\n{C_BOLD}{C_CYAN}{'=' * 60}{C_RESET}\n{C_BOLD}{C_CYAN}  {text}{C_RESET}\n{C_BOLD}{C_CYAN}{'=' * 60}{C_RESET}"


def _ok(text: str) -> str:
    return f"{C_GREEN}[OK]{C_RESET} {text}"


def _warn(text: str) -> str:
    return f"{C_YELLOW}[WARN]{C_RESET} {text}"


def _fail(text: str) -> str:
    return f"{C_RED}[FAIL]{C_RESET} {text}"


def _dim(text: str) -> str:
    return f"{C_DIM}{text}{C_RESET}"


def _bold(text: str) -> str:
    return f"{C_BOLD}{text}{C_RESET}"


# ── Subject helpers ───────────────────────────────────────────────────────


def _get_subjects() -> list[dict[str, Any]]:
    """Return all top-level subject categories from the taxonomy."""
    subjects: list[dict[str, Any]] = []
    for key, node in TAXONOMY.items():
        subjects.append({
            "key": key,
            "id": node["id"],
            "label": node["label"],
            "weight": node.get("weight", 1),
            "children": node.get("children", {}),
        })
    return subjects


def _get_topics_for_subject(subject: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all leaf topics under a subject."""
    topics: list[dict[str, Any]] = []
    for _key, node in subject["children"].items():
        topics.append({
            "id": node["id"],
            "label": node["label"],
            "weight": node.get("weight", 5),
            "difficulties": node.get("difficulties", [DIFFICULTY_BEGINNER]),
            "prerequisites": node.get("prerequisites", []),
            "subtopics": list(node.get("subtopics", [])),
            "companies": node.get("companies", ["all"]),
            "content_types": node.get("content_types", ["article"]),
            "custom": False,
        })
    return topics


# ── Input helpers ─────────────────────────────────────────────────────────


def _prompt(text: str, default: str = "") -> str:
    """Prompt the user with an optional default value."""
    display = f"{C_BOLD}{text}{C_RESET}"
    if default:
        display += f" {_dim(f'[{default}]')}"
    display += " "
    try:
        result = input(display)
    except (EOFError, KeyboardInterrupt):
        print(f"\n{_warn('Interrupted. Exiting.')}")
        sys.exit(0)
    return result.strip() or default


def _confirm(text: str, default: str = "n") -> bool:
    """Ask a yes/no question."""
    suffix = " [Y/n]: " if default == "y" else " [y/N]: "
    response = _prompt(f"{text}{suffix}", default)
    return response.lower().startswith("y")


# ── Step 1: Pick Subject ─────────────────────────────────────────────────


def _pick_subject() -> dict[str, Any]:
    """Show all subject categories and let the user pick one."""
    print(_header("Step 1 of 4 — Pick a Subject"))

    subjects = _get_subjects()
    for i, s in enumerate(subjects, 1):
        topic_count = len(s["children"])
        weight_bar = _dim(f"[weight={s['weight']}]")
        print(f"  {C_BOLD}{i:>2}{C_RESET}. {s['label']} {_dim(f'({topic_count} topics)')} {weight_bar}")

    print(f"  {_dim('─' * 50)}")
    print(f"  {C_BOLD} 0{C_RESET}. {C_RED}Exit{C_RESET}")

    while True:
        choice = _prompt("\nEnter subject number")
        if choice == "0":
            print(_warn("Exiting."))
            sys.exit(0)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(subjects):
                selected = subjects[idx]
                print(f"\n  {_ok(f'Selected: {selected["label"]}')}")
                return selected
            print(_fail(f"Invalid choice: {choice}. Try again."))
        except ValueError:
            print(_fail(f"Invalid number: {choice}. Try again."))


# ── Step 2: Topic Selection ──────────────────────────────────────────────


def _select_topics(subject: dict[str, Any]) -> list[dict[str, Any]]:
    """Show topics under a subject. Allow add/delete."""
    topics = _get_topics_for_subject(subject)

    while True:
        print(_header(f"Step 2 of 4 — Topics for: {subject['label']}"))

        for i, t in enumerate(topics, 1):
            marker = _dim("[custom]") if t.get("custom") else ""
            print(f"  {C_BOLD}{i:>2}{C_RESET}. {t['label']} {marker}")
            print(f"      {_dim(f'ID: {t['id']}  | weight: {t['weight']}  | ' +
                           f'{len(t['subtopics'])} sub-topics')}")

        print(f"\n  {C_BOLD}Commands:{C_RESET}")
        print(f"  {_bold('a')} <topic-name>  {_dim('— Add a custom topic')}")
        print(f"  {_bold('d')} <number>     {_dim('— Delete topic by number')}")
        print(f"  {_bold('done')}           {_dim('— Approve and proceed')}")
        print(f"  {_bold('q')}              {_dim('— Quit')}")

        cmd = _prompt("\n>", "done")

        if cmd.lower() == "done":
            if not topics:
                print(_fail("No topics selected. Add at least one topic."))
                continue
            print(f"\n  {_ok(f'{len(topics)} topic(s) approved:')}")
            for t in topics:
                print(f"     - {t['label']}")
            return topics

        if cmd.lower() == "q":
            print(_warn("Exiting."))
            sys.exit(0)

        if cmd.lower().startswith("a "):
            name = cmd[2:].strip()
            if not name:
                print(_fail("Usage: a <topic-name>"))
                continue
            topic_id = f"custom_{name.lower().replace(' ', '_')}"
            topics.append({
                "id": topic_id,
                "label": name,
                "weight": 5,
                "difficulties": [DIFFICULTY_BEGINNER],
                "prerequisites": [],
                "subtopics": [],
                "companies": ["all"],
                "content_types": ["article", "mcq"],
                "custom": True,
            })
            print(_ok(f'Added custom topic: "{name}"'))
            continue

        if cmd.lower().startswith("d "):
            try:
                num = int(cmd[2:].strip())
                if 1 <= num <= len(topics):
                    removed = topics.pop(num - 1)
                    print(_warn(f'Removed: "{removed["label"]}"'))
                else:
                    print(_fail(f"Invalid number: {num}. Choose 1-{len(topics)}."))
            except ValueError:
                print(_fail(f"Usage: d <number> (1-{len(topics)})"))
            continue

        print(_fail(f"Unknown command: {cmd}"))


# ── Step 3: Sub-topic Selection ──────────────────────────────────────────


def _select_subtopics_for_one(
    topic: dict[str, Any],
    topic_num: int,
    total: int,
) -> None:
    """Edit sub-topics for a single topic. Mutates topic['subtopics'] in place."""
    subtopics: list[str] = list(topic["subtopics"])

    while True:
        print(f"\n{C_BOLD}{C_MAGENTA}─{'─' * 58}{C_RESET}")
        print(
            f"{C_BOLD}  Topic {topic_num}/{total}: {topic['label']}{C_RESET}"
        )
        print(f"{C_BOLD}{C_MAGENTA}─{'─' * 58}{C_RESET}")

        if subtopics:
            print(f"\n  {_bold('Sub-topics:')}")
            for i, st in enumerate(subtopics, 1):
                print(f"    {C_BOLD}{i:>2}{C_RESET}. {st}")
        else:
            print(f"\n  {_dim('No sub-topics defined yet.')}")

        print(f"\n  {C_BOLD}Commands:{C_RESET}")
        print(f"  {_bold('a')} <sub-topic>   {_dim('— Add a sub-topic')}")
        print(f"  {_bold('d')} <number>      {_dim('— Delete sub-topic by number')}")
        print(f"  {_bold('done')}            {_dim('— Approve and proceed')}")
        print(f"  {_bold('skip')}            {_dim('— Skip this topic entirely')}")
        print(f"  {_bold('q')}               {_dim('— Quit')}")

        cmd = _prompt("\n>", "done")

        if cmd.lower() == "done":
            if not subtopics:
                print(_warn("No sub-topics. The agent will research broadly."))
                yn = _confirm("Continue without sub-topics?", "y")
                if not yn:
                    continue
            topic["subtopics"] = subtopics
            print(_ok(f'{len(subtopics)} sub-topic(s) saved for "{topic["label"]}"'))
            return

        if cmd.lower() == "skip":
            print(_warn(f'Skipping topic: "{topic["label"]}"'))
            topic["subtopics"] = []  # mark as skipped
            topic["_skip"] = True
            return

        if cmd.lower() == "q":
            print(_warn("Exiting."))
            sys.exit(0)

        if cmd.lower().startswith("a "):
            name = cmd[2:].strip()
            if not name:
                print(_fail("Usage: a <sub-topic-name>"))
                continue
            subtopics.append(name)
            print(_ok(f'Added sub-topic: "{name}"'))
            continue

        if cmd.lower().startswith("d "):
            try:
                num = int(cmd[2:].strip())
                if 1 <= num <= len(subtopics):
                    removed = subtopics.pop(num - 1)
                    print(_warn(f'Removed sub-topic: "{removed}"'))
                else:
                    print(_fail(f"Invalid number: {num}. Choose 1-{len(subtopics)}."))
            except ValueError:
                print(_fail(f"Usage: d <number> (1-{len(subtopics)})"))
            continue

        print(_fail(f"Unknown command: {cmd}"))


def _select_subtopics(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Loop over approved topics and let the user edit sub-topics per topic."""
    print(_header("Step 3 of 4 — Sub-topic Selection"))

    active = [t for t in topics if not t.get("_skip")]
    if not active:
        # re-check: maybe all were skipped in a re-run
        active = topics

    for i, topic in enumerate(topics, 1):
        _select_subtopics_for_one(topic, i, len(topics))

    # Filter out skipped topics
    remaining = [t for t in topics if not t.get("_skip")]
    print(f"\n  {_ok(f'{len(remaining)} topic(s) will be produced.')}")
    return remaining


# ── Step 4: Confirm & Run ────────────────────────────────────────────────


def _confirm_and_run(
    subject: dict[str, Any],
    topics: list[dict[str, Any]],
    produce_fn: Callable[[str, list[str] | None], None],
) -> None:
    """Show summary and start production if confirmed."""
    print(_header("Step 4 of 4 — Confirm & Run"))

    total_subtopics = sum(len(t.get("subtopics", [])) for t in topics)
    est_cost = len(topics) * 0.003  # ~$0.003 per topic with DeepSeek
    est_time = len(topics) * 8  # ~8 min per topic

    print(f"\n  {_bold('Subject:')}     {subject['label']}")
    print(f"  {_bold('Topics:')}      {len(topics)}")
    if topics:
        for t in topics:
            subs = len(t.get("subtopics", []))
            print(f"    - {t['label']} ({subs} sub-topics)")
    print(f"  {_bold('Sub-topics:')}  {total_subtopics} total")
    print(f"  {_bold('Est. cost:')}   ~${est_cost:.3f} (DeepSeek)")
    print(f"  {_bold('Est. time:')}   ~{est_time} minutes")
    print()

    if not _confirm("Proceed with content production?", "n"):
        print(_warn("Cancelled. No content was produced."))
        return

    print(f"\n{_ok('Starting content production...')}")

    for i, topic in enumerate(topics, 1):
        print(
            f"\n{C_BOLD}{'━' * 50}{C_RESET}\n"
            f"  [{i}/{len(topics)}] Producing: {topic['label']} ({topic['id']})\n"
            f"{C_BOLD}{'━' * 50}{C_RESET}"
        )
        subtopics: list[str] | None = topic.get("subtopics")
        produce_fn(topic["id"], subtopics if subtopics else None)


# ── Entry Point ──────────────────────────────────────────────────────────


def run_interactive(
    produce_fn: Callable[[str, list[str] | None], None],
) -> None:
    """Run the full interactive wizard, then produce content.

    Args:
        produce_fn: Called with (topic_id, subtopics) for each approved topic.
                   Pass subtopics=None when the topic has no sub-topic list.
    """
    print(f"\n{C_BOLD}{C_CYAN}  AdvaitaCode — Interactive Content Wizard{C_RESET}")
    print(f"  {_dim('4 steps. Add/delete at topic and sub-topic level.')}")
    print(f"  {_dim('Type "done" to proceed, "q" to quit at any prompt.')}")

    # Step 1
    subject = _pick_subject()

    # Step 2
    topics = _select_topics(subject)

    # Step 3
    topics = _select_subtopics(topics)

    if not topics:
        print(_fail("No topics remaining after sub-topic filtering."))
        return

    # Step 4
    _confirm_and_run(subject, topics, produce_fn)
