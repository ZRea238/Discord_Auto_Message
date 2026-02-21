from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands

from message import render_reminder_template
from reminder_store import (
    ReminderAlreadyExistsError,
    ReminderNotFoundError,
    WEEKDAY_NAMES,
    add_reminder,
    edit_reminder,
    find_reminder,
    format_send_time,
    load_reminders,
    parse_send_time,
    remove_reminder,
    save_reminders,
    set_notify_user,
    weekday_name,
)

WEEKDAY_CHOICES = [
    app_commands.Choice(name=name, value=index)
    for index, name in enumerate(WEEKDAY_NAMES)
]


def is_admin_user(interaction: discord.Interaction) -> bool:
    user = interaction.user
    if not isinstance(user, discord.Member):
        return False
    return user.guild_permissions.administrator


async def require_admin(interaction: discord.Interaction) -> bool:
    if is_admin_user(interaction):
        return True
    await interaction.response.send_message(
        "Only server admins can change reminders.",
        ephemeral=True,
    )
    return False


def control_channel_allowed(
    interaction: discord.Interaction,
    control_channel_id: int | None,
) -> bool:
    if control_channel_id is None:
        return True
    return interaction.channel_id == control_channel_id


def build_client() -> tuple[discord.Client, app_commands.CommandTree]:
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    return client, tree


async def reminder_name_autocomplete(
    _: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    reminders = load_reminders()
    needle = current.strip().lower()
    names = [r.name for r in reminders]
    if needle:
        names = [n for n in names if needle in n.lower()]
    return [app_commands.Choice(name=n, value=n) for n in names[:25]]


def format_reminder_line(
    name: str,
    send_weekday: int,
    send_hour: int,
    send_minute: int,
    target_weekday: int,
    skipped: bool,
    notify_user_id: int | None,
) -> str:
    notify_label = f"<@{notify_user_id}>" if notify_user_id is not None else "none"
    return (
        f"- **{name}** | send: {weekday_name(send_weekday)} | "
        f"time: {format_send_time(send_hour, send_minute)} | "
        f"target: {weekday_name(target_weekday)} | "
        f"skip-next: {'yes' if skipped else 'no'} | "
        f"notify: {notify_label}"
    )


def next_send_preview_time(
    now: datetime,
    send_weekday: int,
    send_hour: int,
    send_minute: int,
) -> datetime:
    days_until_send = (send_weekday - now.weekday()) % 7
    preview = (now + timedelta(days=days_until_send)).replace(
        hour=send_hour,
        minute=send_minute,
        second=0,
        microsecond=0,
    )
    if preview <= now:
        preview += timedelta(days=7)
    return preview


def main() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN", "")
    if not token:
        raise ValueError("Missing DISCORD_BOT_TOKEN environment variable")

    control_channel = os.getenv("DISCORD_CONTROL_CHANNEL_ID", "").strip()
    control_channel_id = int(control_channel) if control_channel else None
    guild_id_text = os.getenv("DISCORD_GUILD_ID", "").strip()
    guild_id = int(guild_id_text) if guild_id_text else None

    client, tree = build_client()
    reminder_group = app_commands.Group(name="reminder", description="Manage reminders")
    synced = False

    @client.event
    async def on_ready() -> None:
        nonlocal synced
        if not synced:
            tree.add_command(reminder_group)
            if guild_id is None:
                await tree.sync()
            else:
                guild = discord.Object(id=guild_id)
                tree.copy_global_to(guild=guild)
                await tree.sync(guild=guild)
            synced = True
        print(f"Bot logged in as {client.user}")

    @reminder_group.command(name="list", description="List all configured reminders")
    async def list_reminders(interaction: discord.Interaction) -> None:
        if not control_channel_allowed(interaction, control_channel_id):
            await interaction.response.send_message(
                f"Use this command in channel ID `{control_channel_id}`.",
                ephemeral=True,
            )
            return

        reminders = load_reminders()
        if not reminders:
            await interaction.response.send_message(
                "No reminders configured.",
                ephemeral=True,
            )
            return

        now = datetime.now().astimezone()
        lines: list[str] = []
        for r in reminders:
            preview_time = next_send_preview_time(
                now,
                r.send_weekday,
                r.send_hour,
                r.send_minute,
            )
            rendered_message = render_reminder_template(
                r.message,
                current=preview_time,
                target_weekday=r.target_weekday,
            )
            lines.append(
                format_reminder_line(
                    r.name,
                    r.send_weekday,
                    r.send_hour,
                    r.send_minute,
                    r.target_weekday,
                    r.skip_next_send,
                    r.notify_user_id,
                )
                + f"\n  Next send preview time: {preview_time:%Y-%m-%d %H:%M:%S %Z}"
                + f"\n  Template: {r.message}"
                + f"\n  Rendered: {rendered_message}"
            )
        await interaction.response.send_message(
            "Configured reminders:\n" + "\n".join(lines),
            ephemeral=True,
        )

    @reminder_group.command(name="add", description="Add a new reminder")
    @app_commands.describe(
        name="Unique reminder name",
        send_day="Day reminder is sent",
        send_time="Send time in HH:MM 24-hour format",
        target_day="Day inserted in {target_date}",
        message="Reminder text",
        notify_user="User to DM before send (defaults to creator)",
    )
    @app_commands.choices(send_day=WEEKDAY_CHOICES, target_day=WEEKDAY_CHOICES)
    async def add_command(
        interaction: discord.Interaction,
        name: str,
        send_day: app_commands.Choice[int],
        send_time: str,
        target_day: app_commands.Choice[int],
        message: str,
        notify_user: Optional[discord.Member] = None,
    ) -> None:
        if not control_channel_allowed(interaction, control_channel_id):
            await interaction.response.send_message(
                f"Use this command in channel ID `{control_channel_id}`.",
                ephemeral=True,
            )
            return
        if not await require_admin(interaction):
            return

        reminders = load_reminders()
        try:
            send_hour, send_minute = parse_send_time(send_time)
            added = add_reminder(
                reminders,
                name=name,
                message=message,
                send_weekday=send_day.value,
                send_hour=send_hour,
                send_minute=send_minute,
                target_weekday=target_day.value,
                notify_user_id=(
                    notify_user.id if notify_user is not None else interaction.user.id
                ),
            )
            save_reminders(reminders)
        except (ValueError, ReminderAlreadyExistsError) as exc:
            await interaction.response.send_message(f"Could not add reminder: {exc}", ephemeral=True)
            return

        await interaction.response.send_message(
            "Added reminder:\n"
            + format_reminder_line(
                added.name,
                added.send_weekday,
                added.send_hour,
                added.send_minute,
                added.target_weekday,
                added.skip_next_send,
                added.notify_user_id,
            ),
            ephemeral=True,
        )

    @reminder_group.command(name="edit", description="Edit an existing reminder")
    @app_commands.describe(
        name="Existing reminder name",
        send_day="Optional new send day",
        send_time="Optional new send time (HH:MM)",
        target_day="Optional new target day",
        message="Optional new message",
        new_name="Optional new reminder name",
        notify_user="Optional user to DM before send",
    )
    @app_commands.autocomplete(name=reminder_name_autocomplete)
    @app_commands.choices(send_day=WEEKDAY_CHOICES, target_day=WEEKDAY_CHOICES)
    async def edit_command(
        interaction: discord.Interaction,
        name: str,
        send_day: Optional[app_commands.Choice[int]] = None,
        send_time: Optional[str] = None,
        target_day: Optional[app_commands.Choice[int]] = None,
        message: Optional[str] = None,
        new_name: Optional[str] = None,
        notify_user: Optional[discord.Member] = None,
    ) -> None:
        if not control_channel_allowed(interaction, control_channel_id):
            await interaction.response.send_message(
                f"Use this command in channel ID `{control_channel_id}`.",
                ephemeral=True,
            )
            return
        if not await require_admin(interaction):
            return

        if (
            send_day is None
            and send_time is None
            and target_day is None
            and message is None
            and new_name is None
            and notify_user is None
        ):
            await interaction.response.send_message(
                "No changes provided. Supply at least one field to edit.",
                ephemeral=True,
            )
            return

        reminders = load_reminders()
        try:
            send_hour: int | None = None
            send_minute: int | None = None
            if send_time is not None:
                send_hour, send_minute = parse_send_time(send_time)
            edited = edit_reminder(
                reminders,
                name=name,
                new_name=new_name,
                message=message,
                send_weekday=send_day.value if send_day is not None else None,
                send_hour=send_hour,
                send_minute=send_minute,
                target_weekday=target_day.value if target_day is not None else None,
                notify_user_id=(notify_user.id if notify_user is not None else None),
            )
            save_reminders(reminders)
        except (ValueError, ReminderNotFoundError, ReminderAlreadyExistsError) as exc:
            await interaction.response.send_message(f"Could not edit reminder: {exc}", ephemeral=True)
            return

        await interaction.response.send_message(
            "Updated reminder:\n"
            + format_reminder_line(
                edited.name,
                edited.send_weekday,
                edited.send_hour,
                edited.send_minute,
                edited.target_weekday,
                edited.skip_next_send,
                edited.notify_user_id,
            ),
            ephemeral=True,
        )

    @reminder_group.command(name="remove", description="Remove a reminder")
    @app_commands.describe(name="Reminder name to remove")
    @app_commands.autocomplete(name=reminder_name_autocomplete)
    async def remove_command(interaction: discord.Interaction, name: str) -> None:
        if not control_channel_allowed(interaction, control_channel_id):
            await interaction.response.send_message(
                f"Use this command in channel ID `{control_channel_id}`.",
                ephemeral=True,
            )
            return
        if not await require_admin(interaction):
            return

        reminders = load_reminders()
        try:
            removed = remove_reminder(reminders, name)
            save_reminders(reminders)
        except (ValueError, ReminderNotFoundError) as exc:
            await interaction.response.send_message(f"Could not remove reminder: {exc}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Removed reminder '{removed.name}'.",
            ephemeral=True,
        )

    @reminder_group.command(name="skip", description="Skip next send for one reminder")
    @app_commands.describe(name="Reminder name to skip once")
    @app_commands.autocomplete(name=reminder_name_autocomplete)
    async def skip_command(interaction: discord.Interaction, name: str) -> None:
        if not control_channel_allowed(interaction, control_channel_id):
            await interaction.response.send_message(
                f"Use this command in channel ID `{control_channel_id}`.",
                ephemeral=True,
            )
            return
        if not await require_admin(interaction):
            return

        reminders = load_reminders()
        try:
            reminder = find_reminder(reminders, name)
        except ReminderNotFoundError as exc:
            await interaction.response.send_message(f"Could not skip reminder: {exc}", ephemeral=True)
            return

        if reminder.skip_next_send:
            await interaction.response.send_message(
                f"Reminder '{reminder.name}' is already queued to skip next send.",
                ephemeral=True,
            )
            return

        reminder.skip_next_send = True
        save_reminders(reminders)
        await interaction.response.send_message(
            f"Queued skip for reminder '{reminder.name}'.",
            ephemeral=True,
        )

    @reminder_group.command(
        name="notify",
        description="Set or clear who gets DM preflight reminders",
    )
    @app_commands.describe(
        name="Reminder name",
        user="User to DM one hour before send",
        clear="Set true to clear notification recipient",
    )
    @app_commands.autocomplete(name=reminder_name_autocomplete)
    async def notify_command(
        interaction: discord.Interaction,
        name: str,
        user: Optional[discord.Member] = None,
        clear: bool = False,
    ) -> None:
        if not control_channel_allowed(interaction, control_channel_id):
            await interaction.response.send_message(
                f"Use this command in channel ID `{control_channel_id}`.",
                ephemeral=True,
            )
            return
        if not await require_admin(interaction):
            return

        if clear and user is not None:
            await interaction.response.send_message(
                "Choose either `user` or `clear`, not both.",
                ephemeral=True,
            )
            return

        reminders = load_reminders()
        try:
            reminder = set_notify_user(
                reminders,
                name=name,
                notify_user_id=None if clear else (user.id if user is not None else interaction.user.id),
            )
            save_reminders(reminders)
        except (ValueError, ReminderNotFoundError) as exc:
            await interaction.response.send_message(
                f"Could not update notification recipient: {exc}",
                ephemeral=True,
            )
            return

        recipient = f"<@{reminder.notify_user_id}>" if reminder.notify_user_id else "none"
        await interaction.response.send_message(
            f"Updated notification recipient for '{reminder.name}' to {recipient}.",
            ephemeral=True,
        )

    client.run(token)


if __name__ == "__main__":
    main()
