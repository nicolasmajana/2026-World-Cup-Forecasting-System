"""
Qualitative news context — PHASE 1 STUB (not yet active).

Plan (decided 2026-06-05): annotate first, adjust later.

Phase 1 (this stub, when API keys are added):
  - Each morning, fetch recent football headlines (news API).
  - Have an LLM (Anthropic API) extract structured, match-relevant facts:
    injuries, suspensions, lineup doubts for the teams playing in the next 48h.
  - Write a short human-readable note into prediction_history.note for the
    affected fixtures. The note is DISPLAYED on the match page but does NOT
    change the model's numbers — the statistical model stays pure and the
    Brier score stays honest.

Phase 2 (future, needs validation):
  - Convert structured availability facts into a calibrated adjustment to a
    team's expected goals (e.g. key striker out -> small xG reduction), and
    record the adjustment alongside the inputs so every prediction stays
    auditable and reproducible.

Required secrets (GitHub Actions) before this runs:
  - ANTHROPIC_API_KEY
  - NEWS_API_KEY

This module is intentionally inert until those exist. The DB hook
(prediction_history.note) and the frontend display are already in place.
"""

import os


def is_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("NEWS_API_KEY"))


def annotate_upcoming(conn) -> int:
    """Attach context notes to upcoming fixtures. No-op until keys are set."""
    if not is_enabled():
        print("news_context: disabled (ANTHROPIC_API_KEY / NEWS_API_KEY not set).")
        return 0
    raise NotImplementedError(
        "Phase 1 news annotation not implemented yet — see module docstring."
    )


if __name__ == "__main__":
    print("news_context enabled:", is_enabled())
