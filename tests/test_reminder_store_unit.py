from __future__ import annotations

import json
from datetime import datetime

import pytest

import reminder_store
from reminder_store import (
    ReminderAlreadyExistsError,
    add_reminder,
    edit_reminder,
    find_reminder,
    format_send_time,
    iso_week_key,
    load_reminders,
    parse_send_time,
    remove_reminder,
    save_reminders,
)


def test_parse_send_time_and_format() -> None:
    assert parse_send_time("07:05") == (7, 5)
    assert format_send_time(7, 5) == "07:05"

    with pytest.raises(ValueError):
        parse_send_time("7:65")

    with pytest.raises(ValueError):
        parse_send_time("nope")


def test_add_edit_remove_roundtrip(tmp_path, monkeypatch) -> None:
    reminders_path = tmp_path / "reminders.json"
    legacy_config = tmp_path / "legacy_config.json"
    legacy_state = tmp_path / "legacy_state.json"
    monkeypatch.setattr(reminder_store, "REMINDERS_PATH", reminders_path)
    monkeypatch.setattr(reminder_store, "LEGACY_CONFIG_PATH", legacy_config)
    monkeypatch.setattr(reminder_store, "LEGACY_STATE_PATH", legacy_state)

    reminders = load_reminders()
    assert reminders == []

    added = add_reminder(
        reminders,
        name="GameNight",
        message="Can you make it on {target_date_long}?",
        send_weekday=0,
        send_hour=17,
        send_minute=30,
        target_weekday=2,
        notify_user_id=123,
    )
    save_reminders(reminders)

    with pytest.raises(ReminderAlreadyExistsError):
        add_reminder(
            reminders,
            name="gamenight",
            message="dup",
            send_weekday=0,
            send_hour=17,
            send_minute=30,
            target_weekday=2,
        )

    edit_reminder(
        reminders,
        name="GameNight",
        new_name="Main Game Night",
        message="New text",
        send_weekday=1,
        send_hour=18,
        send_minute=15,
        target_weekday=3,
        notify_user_id=456,
    )
    save_reminders(reminders)

    loaded = load_reminders()
    found = find_reminder(loaded, "main game night")
    assert found.message == "New text"
    assert found.send_weekday == 1
    assert (found.send_hour, found.send_minute) == (18, 15)
    assert found.target_weekday == 3
    assert found.notify_user_id == 456

    removed = remove_reminder(loaded, "Main Game Night")
    assert removed.name == "Main Game Night"
    save_reminders(loaded)
    assert load_reminders() == []


def test_load_reminders_migrates_legacy_files(tmp_path, monkeypatch) -> None:
    reminders_path = tmp_path / "reminders.json"
    legacy_config = tmp_path / "legacy_config.json"
    legacy_state = tmp_path / "legacy_state.json"
    monkeypatch.setattr(reminder_store, "REMINDERS_PATH", reminders_path)
    monkeypatch.setattr(reminder_store, "LEGACY_CONFIG_PATH", legacy_config)
    monkeypatch.setattr(reminder_store, "LEGACY_STATE_PATH", legacy_state)

    legacy_config.write_text(
        json.dumps(
            {
                "message": "Legacy reminder",
                "send_weekday": 0,
                "target_weekday": 2,
            }
        ),
        encoding="utf-8",
    )
    legacy_state.write_text(
        json.dumps({"skip_next_send": True, "last_sent_epoch": 1771962000}),
        encoding="utf-8",
    )

    reminders = load_reminders()
    assert len(reminders) == 1
    migrated = reminders[0]
    assert migrated.name == "default"
    assert migrated.skip_next_send is True
    assert migrated.send_hour == 17
    assert migrated.send_minute == 0

    expected_week = iso_week_key(datetime.fromtimestamp(1771962000).astimezone())
    assert migrated.last_sent_iso_week == expected_week
    assert reminders_path.exists()
