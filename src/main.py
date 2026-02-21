from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable

from discord_sender import DiscordWebhookSender
from message import build_time_message, build_weekly_reminder_message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit reminder messages on a configurable interval."
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between messages (default: 5). For weekly reminders use 604800.",
    )
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=0,
        help="How many messages to send before stopping (0 = run forever).",
    )
    parser.add_argument(
        "--target",
        choices=("stdout", "discord"),
        default="stdout",
        help="Where to send messages (default: stdout).",
    )
    parser.add_argument(
        "--message-type",
        choices=("time", "weekly-reminder"),
        default="weekly-reminder",
        help="Message template to send (default: weekly-reminder).",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.getenv("DISCORD_WEBHOOK_URL", ""),
        help=(
            "Discord webhook URL (or set DISCORD_WEBHOOK_URL environment variable)."
        ),
    )
    parser.add_argument(
        "--reminder-text",
        default=(
            "Hey everyone, please confirm if you're still able to make this week's plan."
        ),
        help="Custom text for the weekly reminder template.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be sent without posting to Discord.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.interval <= 0:
        raise ValueError("--interval must be greater than 0")
    if args.count < 0:
        raise ValueError("--count cannot be negative")
    if args.target == "discord" and not args.webhook_url:
        raise ValueError(
            "--webhook-url is required when --target is discord "
            "(or set DISCORD_WEBHOOK_URL)"
        )


def get_message_builder(args: argparse.Namespace) -> Callable[[], str]:
    if args.message_type == "time":
        return build_time_message
    return lambda: build_weekly_reminder_message(args.reminder_text)


def run(args: argparse.Namespace) -> None:
    sent = 0
    build_message = get_message_builder(args)
    sender = None

    if args.target == "discord":
        sender = DiscordWebhookSender(args.webhook_url)

    while True:
        message = build_message()

        if args.target == "stdout":
            print(message, flush=True)
        elif args.dry_run:
            print("[DRY RUN] Would send to Discord:\n" + message, flush=True)
        else:
            sender.send(message)
            print("Sent message to Discord webhook.", flush=True)

        sent += 1
        if args.count and sent >= args.count:
            break

        time.sleep(args.interval)


def main() -> None:
    args = parse_args()
    validate_args(args)
    run(args)


if __name__ == "__main__":
    main()
