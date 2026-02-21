from __future__ import annotations

import argparse
from datetime import datetime

import discord

import reminder_store
import send_preflight_notifications
from reminder_store import Reminder, load_reminders, save_reminders


def test_preflight_dry_run_marks_warned_when_due(tmp_path, monkeypatch, capsys) -> None:
    reminders_path = tmp_path / "reminders.json"
    monkeypatch.setattr(reminder_store, "REMINDERS_PATH", reminders_path)
    monkeypatch.setattr(reminder_store, "LEGACY_CONFIG_PATH", tmp_path / "legacy.json")
    monkeypatch.setattr(reminder_store, "LEGACY_STATE_PATH", tmp_path / "legacy_state.json")

    reminders = [
        Reminder(
            id="x1",
            name="weekly",
            message="See you {target_date_long}",
            send_weekday=0,  # Monday
            send_hour=17,
            send_minute=0,
            target_weekday=2,
            notify_user_id=999,
        )
    ]
    save_reminders(reminders)

    fixed_now = datetime(2026, 2, 23, 16, 5, 0).astimezone()  # Monday 4:05 PM
    monkeypatch.setattr(discord.utils, "utcnow", lambda: fixed_now)
    monkeypatch.setattr(
        send_preflight_notifications,
        "parse_args",
        lambda: argparse.Namespace(dry_run=True),
    )

    send_preflight_notifications.main()
    out = capsys.readouterr().out

    assert "Would DM <@999>" in out
    updated = load_reminders()
    assert updated[0].last_warned_iso_week == "2026-W09"


def test_preflight_dry_run_skips_if_too_early(tmp_path, monkeypatch, capsys) -> None:
    reminders_path = tmp_path / "reminders.json"
    monkeypatch.setattr(reminder_store, "REMINDERS_PATH", reminders_path)
    monkeypatch.setattr(reminder_store, "LEGACY_CONFIG_PATH", tmp_path / "legacy.json")
    monkeypatch.setattr(reminder_store, "LEGACY_STATE_PATH", tmp_path / "legacy_state.json")

    reminders = [
        Reminder(
            id="x1",
            name="weekly",
            message="msg",
            send_weekday=0,
            send_hour=17,
            send_minute=0,
            target_weekday=2,
            notify_user_id=999,
        )
    ]
    save_reminders(reminders)

    fixed_now = datetime(2026, 2, 23, 15, 10, 0).astimezone()  # Monday 3:10 PM
    monkeypatch.setattr(discord.utils, "utcnow", lambda: fixed_now)
    monkeypatch.setattr(
        send_preflight_notifications,
        "parse_args",
        lambda: argparse.Namespace(dry_run=True),
    )

    send_preflight_notifications.main()
    out = capsys.readouterr().out

    assert "No reminder preflight notifications were due." in out
    updated = load_reminders()
    assert updated[0].last_warned_iso_week == ""
