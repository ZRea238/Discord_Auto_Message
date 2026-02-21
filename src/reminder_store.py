from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

REMINDERS_PATH = Path(__file__).resolve().parent.parent / "reminders.json"
LEGACY_CONFIG_PATH = Path(__file__).resolve().parent.parent / "reminder_config.json"
LEGACY_STATE_PATH = Path(__file__).resolve().parent.parent / "reminder_state.json"

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
DEFAULT_SEND_HOUR = 17
DEFAULT_SEND_MINUTE = 0


@dataclass
class Reminder:
    id: str
    name: str
    message: str
    send_weekday: int
    send_hour: int
    send_minute: int
    target_weekday: int
    notify_user_id: int | None = None
    skip_next_send: bool = False
    last_sent_iso_week: str = ""
    last_warned_iso_week: str = ""


class ReminderNotFoundError(ValueError):
    pass


class ReminderAlreadyExistsError(ValueError):
    pass


def _validate_weekday(value: int, field_name: str) -> None:
    if value < 0 or value > 6:
        raise ValueError(f"{field_name} must be between 0 and 6")


def _validate_message(value: str) -> None:
    if not value.strip():
        raise ValueError("message cannot be empty")
    if len(value) > 1800:
        raise ValueError("message is too long; keep it under 1800 characters")


def _validate_name(value: str) -> None:
    if not value.strip():
        raise ValueError("name cannot be empty")
    if len(value.strip()) > 64:
        raise ValueError("name must be 64 characters or fewer")


def _validate_notify_user_id(value: int | None) -> None:
    if value is None:
        return
    if value <= 0:
        raise ValueError("notify_user_id must be a positive integer")


def _validate_send_time(hour: int, minute: int) -> None:
    if hour < 0 or hour > 23:
        raise ValueError("send_hour must be between 0 and 23")
    if minute < 0 or minute > 59:
        raise ValueError("send_minute must be between 0 and 59")


def weekday_name(index: int) -> str:
    _validate_weekday(index, "weekday")
    return WEEKDAY_NAMES[index]


def format_send_time(hour: int, minute: int) -> str:
    _validate_send_time(hour, minute)
    return f"{hour:02d}:{minute:02d}"


def parse_send_time(value: str) -> tuple[int, int]:
    text = value.strip()
    if ":" not in text:
        raise ValueError("send_time must be in HH:MM 24-hour format")
    hour_text, minute_text = text.split(":", 1)
    if not hour_text.isdigit() or not minute_text.isdigit():
        raise ValueError("send_time must be in HH:MM 24-hour format")
    hour = int(hour_text)
    minute = int(minute_text)
    _validate_send_time(hour, minute)
    return hour, minute


def iso_week_key(dt: datetime) -> str:
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _new_id() -> str:
    return uuid4().hex[:8]


def _load_legacy_reminder() -> list[Reminder]:
    if not LEGACY_CONFIG_PATH.exists():
        return []

    data = json.loads(LEGACY_CONFIG_PATH.read_text(encoding="utf-8"))
    message = str(data.get("message", "")).strip()
    send_weekday = int(data.get("send_weekday", 0))
    target_weekday = int(data.get("target_weekday", 2))
    if not message:
        return []

    _validate_message(message)
    _validate_weekday(send_weekday, "send_weekday")
    _validate_weekday(target_weekday, "target_weekday")

    reminder = Reminder(
        id=_new_id(),
        name="default",
        message=message,
        send_weekday=send_weekday,
        send_hour=DEFAULT_SEND_HOUR,
        send_minute=DEFAULT_SEND_MINUTE,
        target_weekday=target_weekday,
    )

    if LEGACY_STATE_PATH.exists():
        state = json.loads(LEGACY_STATE_PATH.read_text(encoding="utf-8"))
        reminder.skip_next_send = bool(state.get("skip_next_send", False))
        last_sent_epoch = state.get("last_sent_epoch")
        if last_sent_epoch is not None:
            last_dt = datetime.fromtimestamp(float(last_sent_epoch)).astimezone()
            reminder.last_sent_iso_week = iso_week_key(last_dt)

    return [reminder]


def load_reminders() -> list[Reminder]:
    if not REMINDERS_PATH.exists():
        reminders = _load_legacy_reminder()
        if reminders:
            save_reminders(reminders)
        return reminders

    data = json.loads(REMINDERS_PATH.read_text(encoding="utf-8"))
    rows = data.get("reminders", []) if isinstance(data, dict) else data
    reminders: list[Reminder] = []
    for row in rows:
        reminder = Reminder(
            id=str(row.get("id") or _new_id()),
            name=str(row["name"]).strip(),
            message=str(row["message"]),
            send_weekday=int(row["send_weekday"]),
            send_hour=int(row.get("send_hour", DEFAULT_SEND_HOUR)),
            send_minute=int(row.get("send_minute", DEFAULT_SEND_MINUTE)),
            target_weekday=int(row["target_weekday"]),
            notify_user_id=(
                int(row["notify_user_id"])
                if row.get("notify_user_id") is not None
                else None
            ),
            skip_next_send=bool(row.get("skip_next_send", False)),
            last_sent_iso_week=str(row.get("last_sent_iso_week", "")),
            last_warned_iso_week=str(row.get("last_warned_iso_week", "")),
        )
        _validate_name(reminder.name)
        _validate_message(reminder.message)
        _validate_weekday(reminder.send_weekday, "send_weekday")
        _validate_send_time(reminder.send_hour, reminder.send_minute)
        _validate_weekday(reminder.target_weekday, "target_weekday")
        _validate_notify_user_id(reminder.notify_user_id)
        reminders.append(reminder)

    seen: set[str] = set()
    for reminder in reminders:
        key = _normalize_name(reminder.name)
        if key in seen:
            raise ValueError(f"duplicate reminder name: {reminder.name}")
        seen.add(key)

    return reminders


def save_reminders(reminders: list[Reminder]) -> None:
    payload = {"version": 1, "reminders": [asdict(r) for r in reminders]}
    REMINDERS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def find_reminder(reminders: list[Reminder], name: str) -> Reminder:
    key = _normalize_name(name)
    for reminder in reminders:
        if _normalize_name(reminder.name) == key:
            return reminder
    raise ReminderNotFoundError(f"reminder '{name}' not found")


def add_reminder(
    reminders: list[Reminder],
    name: str,
    message: str,
    send_weekday: int,
    send_hour: int,
    send_minute: int,
    target_weekday: int,
    notify_user_id: int | None = None,
) -> Reminder:
    _validate_name(name)
    _validate_message(message)
    _validate_weekday(send_weekday, "send_weekday")
    _validate_send_time(send_hour, send_minute)
    _validate_weekday(target_weekday, "target_weekday")
    _validate_notify_user_id(notify_user_id)

    key = _normalize_name(name)
    if any(_normalize_name(r.name) == key for r in reminders):
        raise ReminderAlreadyExistsError(f"reminder '{name}' already exists")

    reminder = Reminder(
        id=_new_id(),
        name=name.strip(),
        message=message.strip(),
        send_weekday=send_weekday,
        send_hour=send_hour,
        send_minute=send_minute,
        target_weekday=target_weekday,
        notify_user_id=notify_user_id,
    )
    reminders.append(reminder)
    return reminder


def edit_reminder(
    reminders: list[Reminder],
    name: str,
    new_name: str | None,
    message: str | None,
    send_weekday: int | None,
    send_hour: int | None,
    send_minute: int | None,
    target_weekday: int | None,
    notify_user_id: int | None = None,
) -> Reminder:
    reminder = find_reminder(reminders, name)

    if new_name is not None:
        _validate_name(new_name)
        new_key = _normalize_name(new_name)
        for other in reminders:
            if other.id != reminder.id and _normalize_name(other.name) == new_key:
                raise ReminderAlreadyExistsError(f"reminder '{new_name}' already exists")
        reminder.name = new_name.strip()

    if message is not None:
        _validate_message(message)
        reminder.message = message.strip()

    if send_weekday is not None:
        _validate_weekday(send_weekday, "send_weekday")
        reminder.send_weekday = send_weekday

    if send_hour is not None:
        _validate_send_time(send_hour, reminder.send_minute)
        reminder.send_hour = send_hour

    if send_minute is not None:
        _validate_send_time(reminder.send_hour, send_minute)
        reminder.send_minute = send_minute

    if target_weekday is not None:
        _validate_weekday(target_weekday, "target_weekday")
        reminder.target_weekday = target_weekday

    if notify_user_id is not None:
        _validate_notify_user_id(notify_user_id)
        reminder.notify_user_id = notify_user_id

    return reminder


def remove_reminder(reminders: list[Reminder], name: str) -> Reminder:
    reminder = find_reminder(reminders, name)
    reminders[:] = [r for r in reminders if r.id != reminder.id]
    return reminder


def set_notify_user(
    reminders: list[Reminder],
    name: str,
    notify_user_id: int | None,
) -> Reminder:
    _validate_notify_user_id(notify_user_id)
    reminder = find_reminder(reminders, name)
    reminder.notify_user_id = notify_user_id
    return reminder
