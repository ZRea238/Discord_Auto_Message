from __future__ import annotations

from datetime import datetime, timedelta


def build_time_message(now: datetime | None = None) -> str:
    """Return a consistent date/time message string."""
    current = now or datetime.now().astimezone()
    return (
        "Current Date/Time Update\n"
        f"Date: {current:%Y-%m-%d}\n"
        f"Time: {current:%H:%M:%S %Z}"
    )


def build_weekly_reminder_message(
    reminder_text: str,
    target_weekday: int = 2,
    now: datetime | None = None,
) -> str:
    """Return a weekly reminder message suitable for a Discord channel."""
    current = now or datetime.now().astimezone()
    rendered_text = render_reminder_template(
        reminder_text,
        current,
        target_weekday=target_weekday,
    )
    return (
        "Weekly Check-In Reminder\n"
        f"{rendered_text}\n"
        "React with: ✅ Can make it | ❌ Can't make it | 🤔 Not sure yet\n"
        f"Sent: {current:%Y-%m-%d %H:%M:%S %Z}"
    )


def render_reminder_template(
    template_text: str,
    current: datetime,
    target_weekday: int = 2,
) -> str:
    """Render supported template variables inside a reminder message."""
    target_date = get_next_weekday_date(current, target_weekday=target_weekday)
    replacements = {
        "{target_date}": target_date.strftime("%Y-%m-%d"),
        "{target_date_long}": target_date.strftime("%A, %B %d, %Y"),
        "{send_date}": current.strftime("%Y-%m-%d"),
        "{send_time}": current.strftime("%H:%M:%S %Z"),
    }

    rendered = template_text
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def get_next_weekday_date(current: datetime, target_weekday: int) -> datetime:
    """Return the next target weekday after current date (never same-day)."""
    days_ahead = (target_weekday - current.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return current + timedelta(days=days_ahead)
