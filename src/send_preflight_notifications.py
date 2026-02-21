from __future__ import annotations

import argparse
import os
from datetime import timedelta

import discord

from message import render_reminder_template
from reminder_store import iso_week_key, load_reminders, save_reminders


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send preflight DM notifications for reminders due today.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print notifications instead of sending DMs.",
    )
    return parser.parse_args()


def build_notification_text(
    reminder_name: str,
    rendered_message: str,
    send_time_text: str,
    control_channel_id: int | None,
) -> str:
    channel_hint = (
        f" in <#{control_channel_id}>" if control_channel_id is not None else ""
    )
    return (
        f"Heads up: reminder **{reminder_name}** is scheduled for {send_time_text}.\n"
        f"If needed, run `/reminder skip name:{reminder_name}`{channel_hint}.\n"
        f"Preview:\n{rendered_message}"
    )


def main() -> None:
    args = parse_args()
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token and not args.dry_run:
        raise ValueError("Missing DISCORD_BOT_TOKEN environment variable")

    fallback_admin_id_text = os.getenv("DISCORD_REMINDER_ADMIN_USER_ID", "").strip()
    fallback_admin_id = int(fallback_admin_id_text) if fallback_admin_id_text else None

    control_channel_text = os.getenv("DISCORD_CONTROL_CHANNEL_ID", "").strip()
    control_channel_id = int(control_channel_text) if control_channel_text else None

    reminders = load_reminders()
    if not reminders:
        print("No reminders configured.")
        return

    now = discord.utils.utcnow().astimezone()
    current_week = iso_week_key(now)

    due = []
    for reminder in reminders:
        if reminder.send_weekday != now.weekday():
            continue
        scheduled = now.replace(
            hour=reminder.send_hour,
            minute=reminder.send_minute,
            second=0,
            microsecond=0,
        )
        preflight_time = scheduled - timedelta(hours=1)
        if now < preflight_time:
            continue
        if reminder.skip_next_send:
            continue
        if reminder.last_sent_iso_week == current_week:
            continue
        if reminder.last_warned_iso_week == current_week:
            continue
        due.append(reminder)

    if not due:
        print("No reminder preflight notifications were due.")
        return

    if args.dry_run:
        for reminder in due:
            notify_user_id = reminder.notify_user_id or fallback_admin_id
            if notify_user_id is None:
                print(f"[DRY RUN] '{reminder.name}' has no notification recipient.")
                continue
            scheduled = now.replace(
                hour=reminder.send_hour,
                minute=reminder.send_minute,
                second=0,
                microsecond=0,
            )
            send_time_text = scheduled.strftime("%Y-%m-%d %H:%M %Z")
            rendered = render_reminder_template(
                reminder.message,
                current=now,
                target_weekday=reminder.target_weekday,
            )
            print(f"[DRY RUN] Would DM <@{notify_user_id}> for '{reminder.name}'")
            print(
                build_notification_text(
                    reminder.name,
                    rendered,
                    send_time_text,
                    control_channel_id,
                )
            )
            reminder.last_warned_iso_week = current_week
        save_reminders(reminders)
        return

    intents = discord.Intents.none()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        changed = False
        for reminder in due:
            notify_user_id = reminder.notify_user_id or fallback_admin_id
            if notify_user_id is None:
                print(f"Skipping '{reminder.name}': no notification recipient configured.")
                continue
            scheduled = now.replace(
                hour=reminder.send_hour,
                minute=reminder.send_minute,
                second=0,
                microsecond=0,
            )
            send_time_text = scheduled.strftime("%Y-%m-%d %H:%M %Z")

            rendered = render_reminder_template(
                reminder.message,
                current=now,
                target_weekday=reminder.target_weekday,
            )
            text = build_notification_text(
                reminder.name,
                rendered,
                send_time_text,
                control_channel_id,
            )

            try:
                user = await client.fetch_user(notify_user_id)
                await user.send(text)
                reminder.last_warned_iso_week = current_week
                changed = True
                print(f"Sent preflight DM for '{reminder.name}' to user {notify_user_id}.")
            except Exception as exc:  # noqa: BLE001
                print(
                    f"Failed to send preflight DM for '{reminder.name}' "
                    f"to user {notify_user_id}: {exc}"
                )

        if changed:
            save_reminders(reminders)

        await client.close()

    client.run(token)


if __name__ == "__main__":
    main()
