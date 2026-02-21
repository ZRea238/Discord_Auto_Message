from __future__ import annotations

from datetime import datetime

from message import get_next_weekday_date, render_reminder_template


def test_render_reminder_template_resolves_tokens() -> None:
    now = datetime(2026, 2, 23, 17, 0, 0).astimezone()  # Monday
    rendered = render_reminder_template(
        "Target: {target_date_long} ({target_date}) sent {send_date} {send_time}",
        current=now,
        target_weekday=2,  # Wednesday
    )

    assert "Wednesday, February 25, 2026" in rendered
    assert "2026-02-25" in rendered
    assert "2026-02-23" in rendered


def test_get_next_weekday_never_returns_same_day() -> None:
    now = datetime(2026, 2, 25, 12, 0, 0).astimezone()  # Wednesday
    next_wed = get_next_weekday_date(now, target_weekday=2)
    assert next_wed.date().isoformat() == "2026-03-04"
