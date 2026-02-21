from __future__ import annotations

import argparse
import os
from datetime import datetime

from discord_sender import DiscordWebhookSender
from message import build_weekly_reminder_message
from reminder_store import iso_week_key, load_reminders, save_reminders, weekday_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send due reminders from reminders.json."
    )
    parser.add_argument(
        "--webhook-url",
        default=os.getenv("DISCORD_WEBHOOK_URL", ""),
        help="Discord webhook URL (or set DISCORD_WEBHOOK_URL).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print messages instead of sending.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Send all reminders now, ignoring weekday/skip/already-sent checks.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reminders = load_reminders()
    if not reminders:
        print("No reminders configured.")
        return

    now = datetime.now().astimezone()
    current_week = iso_week_key(now)

    if not args.dry_run and not args.webhook_url:
        raise ValueError(
            "Missing webhook URL. Set DISCORD_WEBHOOK_URL or pass --webhook-url."
        )

    sender = None if args.dry_run else DiscordWebhookSender(args.webhook_url)
    changed = False
    sent = 0

    for reminder in reminders:
        if not args.force:
            if now.weekday() != reminder.send_weekday:
                continue
            scheduled = now.replace(
                hour=reminder.send_hour,
                minute=reminder.send_minute,
                second=0,
                microsecond=0,
            )
            if now < scheduled:
                continue

            if reminder.skip_next_send:
                reminder.skip_next_send = False
                changed = True
                print(f"Skipped '{reminder.name}' (consumed one-time skip).")
                continue

            if reminder.last_sent_iso_week == current_week:
                continue

        message = build_weekly_reminder_message(
            reminder.message,
            target_weekday=reminder.target_weekday,
            now=now,
        )

        if args.dry_run:
            print(f"[DRY RUN] Reminder '{reminder.name}'")
            print(message)
        else:
            sender.send(message)
            print(f"Sent reminder '{reminder.name}'.")

        reminder.last_sent_iso_week = current_week
        changed = True
        sent += 1

    if changed:
        save_reminders(reminders)

    if sent == 0:
        print("No reminders were due.")


if __name__ == "__main__":
    main()
