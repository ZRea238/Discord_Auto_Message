# Discord_auto_message

This project has two pieces:

- A Discord control bot where admins manage reminders.
- systemd timers that DM preflight warnings and send due reminders via webhook.

## How It Works

1. Admins create reminders with `/reminder add`.
2. Each reminder has its own message, send day, send time, target day, and recipient for preflight DM.
3. Preflight check DMs reminder recipients one hour before each reminder's send time.
4. Sender posts reminders when each reminder is due.

## 1) Install Dependency

```bash
python3 -m pip install -r requirements.txt
```

## 2) Create a Discord Webhook

In your Discord channel:

1. Channel Settings -> Integrations -> Webhooks
2. Create webhook and copy URL

Set environment variable:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

## 3) Create Discord Bot

In Discord Developer Portal:

1. Create app and bot
2. Copy bot token

```bash
export DISCORD_BOT_TOKEN="your_bot_token_here"
```

3. Invite bot with read/send/application command permissions.

Optional:

```bash
export DISCORD_CONTROL_CHANNEL_ID="123456789012345678"
export DISCORD_GUILD_ID="123456789012345678"
export DISCORD_REMINDER_ADMIN_USER_ID="123456789012345678"
```

`DISCORD_REMINDER_ADMIN_USER_ID` is a fallback DM recipient if a reminder has no notify user set.

## 4) Run Control Bot

```bash
python3 src/bot_control.py
```

Slash commands:

- `/reminder list`
- `/reminder add`
- `/reminder edit`
- `/reminder remove`
- `/reminder skip`
- `/reminder notify`

Notes:

- Edit/remove/skip/notify support reminder-name autocomplete.
- Only admins can add/edit/remove/skip/notify.
- Non-admins can still run `/reminder list`.
- `/reminder add` defaults notify recipient to the creator.
- `/reminder edit` can change one field or many fields.
- `/reminder notify` sets who gets the one-hour preflight DM for a reminder.
- `/reminder notify clear:true` removes the recipient for that reminder.
- Use `send_time` in `HH:MM` 24-hour format (example: `17:00`).

## Reminder Variables

Use these in reminder message text:

- `{target_date}`: next configured target day as `YYYY-MM-DD`
- `{target_date_long}`: next configured target day in long form
- `{send_date}`: date message is sent
- `{send_time}`: time message is sent

Example:

```text
Can everyone confirm for ({target_date_long})?
```

## Test

Dry-run due reminder sending:

```bash
python3 src/send_reminder.py --dry-run
```

Force send all reminders now:

```bash
python3 src/send_reminder.py --force
```

Dry-run preflight DMs:

```bash
python3 src/send_preflight_notifications.py --dry-run
```

Run automated tests:

```bash
python3 -m pip install -r requirements-dev.txt
pytest -q --cov=src --cov-report=term-missing --cov-report=xml:coverage.xml
```

CI:

- GitHub Actions runs tests on pull requests and on pushes to `main`.
- Workflow file: `.github/workflows/tests.yml`.
- Coverage XML is published as a workflow artifact (`coverage-xml`).

Branch protection recommendation:

1. In GitHub: `Settings` -> `Branches` -> add/edit a protection rule for `main`.
2. Enable `Require status checks to pass before merging`.
3. Add required check: `Tests / test`.
4. Optional: enable `Require branches to be up to date before merging`.

## systemd (Auto-Start, No Login Required)

Install units:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/discord-reminder-bot.service ~/.config/systemd/user/
cp systemd/discord-reminder-send.service ~/.config/systemd/user/
cp systemd/discord-reminder-send.timer ~/.config/systemd/user/
cp systemd/discord-reminder-notify.service ~/.config/systemd/user/
cp systemd/discord-reminder-notify.timer ~/.config/systemd/user/
cp systemd/discord-auto-message.env.example systemd/discord-auto-message.env
```

Set real values in `systemd/discord-auto-message.env`:

- `DISCORD_BOT_TOKEN`
- `DISCORD_WEBHOOK_URL`

Enable services:

```bash
systemctl --user daemon-reload
systemctl --user enable --now discord-reminder-bot.service
systemctl --user enable --now discord-reminder-notify.timer
systemctl --user enable --now discord-reminder-send.timer
```

Allow user services while logged out:

```bash
loginctl enable-linger $USER
```

Timer behavior:

- `discord-reminder-notify.timer` runs every minute.
- `discord-reminder-send.timer` runs every minute.
- App only notifies/sends reminders due on their configured send day/time.

## Files

- `src/bot_control.py`: Slash command management for multiple reminders.
- `src/reminder_store.py`: Reminder persistence and CRUD.
- `src/send_preflight_notifications.py`: DMs one-hour preflight warnings.
- `src/send_reminder.py`: Sends all due reminders.
- `src/message.py`: Message templates/variable rendering.
- `src/discord_sender.py`: Webhook sender.
