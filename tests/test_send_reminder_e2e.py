from __future__ import annotations

import argparse
from datetime import datetime

import reminder_store
import send_reminder
from reminder_store import Reminder, load_reminders, save_reminders


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls(2026, 2, 23, 17, 30, 0, tzinfo=tz)  # Monday 5:30 PM


class FakeSender:
    sent_messages: list[str] = []

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, content: str) -> None:
        self.sent_messages.append(content)


def test_send_reminder_sends_due_and_updates_week(tmp_path, monkeypatch, capsys) -> None:
    reminders_path = tmp_path / "reminders.json"
    monkeypatch.setattr(reminder_store, "REMINDERS_PATH", reminders_path)
    monkeypatch.setattr(reminder_store, "LEGACY_CONFIG_PATH", tmp_path / "legacy.json")
    monkeypatch.setattr(reminder_store, "LEGACY_STATE_PATH", tmp_path / "legacy_state.json")

    reminders = [
        Reminder(
            id="a1",
            name="due",
            message="msg {target_date}",
            send_weekday=0,
            send_hour=17,
            send_minute=0,
            target_weekday=2,
        ),
        Reminder(
            id="b2",
            name="not-due",
            message="later",
            send_weekday=1,
            send_hour=17,
            send_minute=0,
            target_weekday=3,
        ),
    ]
    save_reminders(reminders)

    monkeypatch.setattr(send_reminder, "datetime", FixedDateTime)
    monkeypatch.setattr(send_reminder, "DiscordWebhookSender", FakeSender)
    monkeypatch.setattr(
        send_reminder,
        "parse_args",
        lambda: argparse.Namespace(webhook_url="https://example", dry_run=False, force=False),
    )

    FakeSender.sent_messages = []
    send_reminder.main()
    out = capsys.readouterr().out

    assert "Sent reminder 'due'." in out
    assert len(FakeSender.sent_messages) == 1
    assert "Weekly Check-In Reminder" in FakeSender.sent_messages[0]

    updated = load_reminders()
    due = next(r for r in updated if r.name == "due")
    assert due.last_sent_iso_week == "2026-W09"


def test_send_reminder_consumes_skip_once(tmp_path, monkeypatch, capsys) -> None:
    reminders_path = tmp_path / "reminders.json"
    monkeypatch.setattr(reminder_store, "REMINDERS_PATH", reminders_path)
    monkeypatch.setattr(reminder_store, "LEGACY_CONFIG_PATH", tmp_path / "legacy.json")
    monkeypatch.setattr(reminder_store, "LEGACY_STATE_PATH", tmp_path / "legacy_state.json")

    reminders = [
        Reminder(
            id="a1",
            name="skip-me",
            message="msg",
            send_weekday=0,
            send_hour=17,
            send_minute=0,
            target_weekday=2,
            skip_next_send=True,
        )
    ]
    save_reminders(reminders)

    monkeypatch.setattr(send_reminder, "datetime", FixedDateTime)
    monkeypatch.setattr(send_reminder, "DiscordWebhookSender", FakeSender)
    monkeypatch.setattr(
        send_reminder,
        "parse_args",
        lambda: argparse.Namespace(webhook_url="https://example", dry_run=False, force=False),
    )

    FakeSender.sent_messages = []
    send_reminder.main()
    out = capsys.readouterr().out

    assert "consumed one-time skip" in out
    assert len(FakeSender.sent_messages) == 0
    updated = load_reminders()
    assert updated[0].skip_next_send is False
