"""
Idempotent seed of >=30 realistic complaints in Urdu-influenced English,
spread across categories (§2.3). Running this twice must not duplicate rows.

TODO(you): implement idempotency — the cleanest approach is a deterministic
synthetic id (or a unique "seed_tag" column/constraint) so a second run can
UPSERT / ON CONFLICT DO NOTHING rather than blindly INSERT.

Run with: python -m scripts.seed   (TODO(you): confirm this once app packaging
is finalized — do NOT document a command in the README you haven't actually run)
"""
from __future__ import annotations

import asyncio

# TODO(you): write >=30 realistic complaint strings here, e.g.:
SAMPLE_COMPLAINTS: list[dict] = [
    {
        "text": "Burst water main flooding Street 12 since fajr, water entering ground floors",
        "location": "Street 12, Gulshan-e-Iqbal",
    },
    # TODO(you): add ~29 more across water / electricity / sanitation / roads /
    # streetlights / other, in a citizen-complaint register (not formal English) —
    # the spec explicitly asks for "Urdu-influenced English", so write these the
    # way a real WhatsApp/web-form complaint would actually read.
]


async def seed() -> None:
    """
    TODO(you):
      1. Open a session via app.db.session.async_session_factory
      2. For each entry in SAMPLE_COMPLAINTS, either:
         a. run it through your real triage pipeline (slower, but exercises
            the whole system and gives you varied category/priority data), or
         b. assign category/priority directly for speed and determinism —
            document which you chose and why.
      3. Insert idempotently (see module docstring).
      4. Commit once at the end, not per-row, for speed.
    """
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(seed())
