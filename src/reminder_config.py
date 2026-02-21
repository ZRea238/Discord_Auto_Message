from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "reminder_config.json"
STATE_PATH = Path(__file__).resolve().parent.parent / "reminder_state.json"
DEFAULT_INTERVAL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_MESSAGE = "Hey everyone, quick check-in: can everyone still make it this week?"
DEFAULT_SEND_WEEKDAY = 0
DEFAULT_TARGET_WEEKDAY = 2
WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


@dataclass
class ReminderConfig:
    interval_seconds: int
    message: str
    send_weekday: int
    target_weekday: int


@dataclass
class ReminderState:
    last_sent_epoch: float | None
    skip_next_send: bool


def _validate_config(interval_seconds: int, message: str) -> None:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than 0")
    if not message.strip():
        raise ValueError("message cannot be empty")
    if len(message) > 1800:
        raise ValueError("message is too long; keep it under 1800 characters")


def _validate_weekday(value: int, field_name: str) -> None:
    if value < 0 or value > 6:
        raise ValueError(f"{field_name} must be between 0 and 6")


def load_config() -> ReminderConfig:
    if not CONFIG_PATH.exists():
        return ReminderConfig(
            interval_seconds=DEFAULT_INTERVAL_SECONDS,
            message=DEFAULT_MESSAGE,
            send_weekday=DEFAULT_SEND_WEEKDAY,
            target_weekday=DEFAULT_TARGET_WEEKDAY,
        )

    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    interval = int(data.get("interval_seconds", DEFAULT_INTERVAL_SECONDS))
    message = str(data.get("message", DEFAULT_MESSAGE))
    send_weekday = int(data.get("send_weekday", DEFAULT_SEND_WEEKDAY))
    target_weekday = int(data.get("target_weekday", DEFAULT_TARGET_WEEKDAY))
    _validate_config(interval, message)
    _validate_weekday(send_weekday, "send_weekday")
    _validate_weekday(target_weekday, "target_weekday")
    return ReminderConfig(
        interval_seconds=interval,
        message=message,
        send_weekday=send_weekday,
        target_weekday=target_weekday,
    )


def save_config(
    interval_seconds: int,
    message: str,
    send_weekday: int | None = None,
    target_weekday: int | None = None,
) -> ReminderConfig:
    _validate_config(interval_seconds, message)
    resolved_send_weekday = (
        DEFAULT_SEND_WEEKDAY if send_weekday is None else send_weekday
    )
    resolved_target_weekday = (
        DEFAULT_TARGET_WEEKDAY if target_weekday is None else target_weekday
    )
    _validate_weekday(resolved_send_weekday, "send_weekday")
    _validate_weekday(resolved_target_weekday, "target_weekday")

    config = ReminderConfig(
        interval_seconds=interval_seconds,
        message=message.strip(),
        send_weekday=resolved_send_weekday,
        target_weekday=resolved_target_weekday,
    )
    payload = {
        "interval_seconds": config.interval_seconds,
        "message": config.message,
        "send_weekday": config.send_weekday,
        "target_weekday": config.target_weekday,
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return config


def load_state() -> ReminderState:
    if not STATE_PATH.exists():
        return ReminderState(last_sent_epoch=None, skip_next_send=False)

    data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    value = data.get("last_sent_epoch")
    skip_next_send = bool(data.get("skip_next_send", False))
    if value is None:
        return ReminderState(last_sent_epoch=None, skip_next_send=skip_next_send)
    return ReminderState(last_sent_epoch=float(value), skip_next_send=skip_next_send)


def save_state(
    last_sent_epoch: float | None,
    skip_next_send: bool | None = None,
) -> ReminderState:
    current = load_state()
    resolved_skip = current.skip_next_send if skip_next_send is None else skip_next_send
    state = ReminderState(last_sent_epoch=last_sent_epoch, skip_next_send=resolved_skip)
    payload = {
        "last_sent_epoch": state.last_sent_epoch,
        "skip_next_send": state.skip_next_send,
    }
    STATE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return state


def set_skip_next_send(skip: bool) -> ReminderState:
    state = load_state()
    return save_state(last_sent_epoch=state.last_sent_epoch, skip_next_send=skip)


def should_send_now(interval_seconds: int, now_epoch: float | None = None) -> bool:
    state = load_state()
    if state.last_sent_epoch is None:
        return True

    current = now_epoch if now_epoch is not None else time.time()
    return (current - state.last_sent_epoch) >= interval_seconds


def weekday_name(index: int) -> str:
    _validate_weekday(index, "weekday")
    return WEEKDAY_NAMES[index]


def parse_interval_input(value: str) -> int:
    text = value.strip().lower()
    if not text:
        raise ValueError("interval cannot be empty")

    if text.isdigit():
        interval = int(text)
        if interval <= 0:
            raise ValueError("interval must be greater than 0")
        return interval

    unit_to_seconds = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
    }
    unit = text[-1]
    amount = text[:-1]
    if unit not in unit_to_seconds or not amount.isdigit():
        raise ValueError("use seconds or format like 30m, 12h, 7d, 1w")

    interval = int(amount) * unit_to_seconds[unit]
    if interval <= 0:
        raise ValueError("interval must be greater than 0")
    return interval


def format_interval(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)
