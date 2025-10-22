# Command Reference

Complete reference for all Bot Shock commands. All commands use Discord's slash command system (`/command`).

## Table of Contents
- [User Registration](#user-registration)
- [Device Status](#device-status)
- [Controller Management](#controller-management)
- [Shocking Commands](#shocking-commands)
- [Reminders (Scheduled Shocks)](#reminders-scheduled-shocks)
- [Triggers (Automated Shocks)](#triggers-automated-shocks)
- [Preferences](#preferences)
- [Action Logs](#action-logs)
- [Settings (Admin)](#settings-admin)

---

## User Registration

### `/openshock setup`
**Description:** Register your OpenShock account with the bot.

Opens a modal where you paste your OpenShock API token. This is required before using any other features.

**How to get your OpenShock API token:**
1. Log in to [OpenShock](https://openshock.app)
2. Go to Settings → API Tokens
3. Create a new token or copy an existing one
4. Paste it into the bot's modal

**Example:**
```
/openshock setup
→ Modal appears
→ Paste token: kUtJ4rPbDkSRzfVk8nYi2Mo...
→ Bot validates and confirms registration
```

---

### `/openshock add_shocker`
**Description:** Add a shocker device to your registered account.

The bot will fetch available shockers from your OpenShock account and let you select which ones to add.
This is usually done automatically during setup, but you can add more shockers later.

**Parameters:** None

**Example:**
```
/openshock add_shocker
→ Bot shows list of available shockers
→ Select one or more shockers
→ Confirm selection
```

---

### `/openshock remove_shocker`
**Description:** Remove a shocker from the bot.

**Parameters:**
- `shocker_id` (optional): Specific shocker ID to remove

**Example:**
```
/openshock remove_shocker
→ Shows list of your shockers
→ Select one to remove
```

---

### `/openshock unregister`
**Description:** Completely remove your account and all data from the bot.

⚠️ **Warning:** This is permanent and cannot be undone. All your reminders, triggers, and controller permissions will be deleted.

**Example:**
```
/openshock unregister
→ Confirmation prompt
→ All data deleted
```

---

## Device Status

Manage whether you're wearing your device. When your device status is set to "not wearing", controllers cannot send shock commands to you.

### `/openshock device_status`
**Description:** Toggle whether you're wearing your device.

When your device status is set to "not wearing", controllers cannot send shock commands to you. They will receive an error message instead.

**Parameters:** None

**Example:**
```
/openshock device_status
→ Status updated

If wearing: "You are now **✅ Wearing** your device."
If not wearing: "You are now **❌ Not Wearing** your device."
```

---

### `/openshock check_device`
**Description:** Check if you're currently wearing your device.

Shows your current device status and provides a quick link to toggle it.

**Parameters:** None

**Example:**
```
/openshock check_device
→ Current Status: ✅ **Wearing**
→ Shows option to toggle status
```
```

---

## Controller Management

Controllers are users or roles who have permission to control your devices. You explicitly grant them access. They can 
use the `/shock` command on your devices, set reminders and triggers for you.

### `/controllers add`
**Description:** Grant control permissions to users or roles.

Opens an interactive menu where you can select:
- Users (up to 25)
- Roles (up to 25)
- Or both

**Example:**
```
/controllers add
→ Select users and/or roles
→ Review selections
→ Confirm to grant permissions
```

---

### `/controllers remove`
**Description:** Revoke control permissions from a user or role.

**Parameters:**
- `user` (optional): User to remove
- `role` (optional): Role to remove

**Note:** Specify either user OR role, not both.

**Examples:**
```
/controllers remove user:@JohnDoe
→ JohnDoe can no longer control your device

/controllers remove role:@Dominants
→ Members of @Dominants role can no longer control your device
```

---

### `/controllers list`
**Description:** View all users and roles who can control your device.

Shows:
- Individual users with controller permissions
- Roles with controller permissions
- When permissions were granted

**Example:**
```
/controllers list
→ Shows all current controllers
```

---

## Shocking Commands

### `/shock`
**Description:** Send a shock/vibrate/sound command to a user's device.

**Requirements:**
- Target user must be wearing their device (see `/openshock check_device`)
- You must have permission to control the target user
- Target user must have at least one shocker registered

**Parameters:**
- `user` (optional): Target user (auto-selected if you control only one person)
- `intensity` (optional): 1-100, default uses your preferences
- `duration` (optional): 300-65535 milliseconds, default uses your preferences
- `shock_type` (optional): Shock/Vibrate/Sound, default uses your preferences
- `shocker_id` (optional): Specific shocker (auto-selected if target has only one)

**Smart Defaults:**
The bot remembers your last-used settings and applies them automatically. See [Preferences](#preferences) to configure defaults.

**Error Messages:**
- `"User is not wearing their device right now!"` - Target disabled their device status
- `"No permission to control this user"` - No controller permission granted
- `"User has no shockers registered"` - Target needs to add devices

**Examples:**
```
/shock user:@Alice intensity:50 duration:1000 shock_type:Shock
→ Shock Alice at 50% for 1 second

/shock user:@Alice
→ Uses your saved defaults/last-used settings

/shock intensity:30 duration:500 shock_type:Vibrate
→ Auto-selects target if you control only one person
```

---

## Reminders (Scheduled Shocks)

Create scheduled or recurring shock reminders.

### `/remind set`
**Description:** Create a new reminder.

**Parameters:**
- `time`: When to trigger (see time format below)
- `intensity`: 1-100
- `duration`: 300-65535 milliseconds
- `shock_type`: Shock/Vibrate/Sound
- `recurrence` (optional): Repeat pattern (see recurrence format below)
- `user` (optional): Target user (defaults to yourself)

**Time Format Examples:**
- `in 5 minutes`
- `in 2 hours`
- `tomorrow at 3pm`
- `2024-12-25 14:30`
- `next monday at 9am`

**Recurrence Format Examples:**
- `every day`
- `every 2 hours`
- `every weekday`
- `every monday at 10am`
- `every 30 minutes`

**Examples:**
```
/remind set time:"in 10 minutes" intensity:40 duration:1000 shock_type:Shock
→ One-time reminder in 10 minutes

/remind set time:"tomorrow at 9am" intensity:30 duration:500 shock_type:Vibrate recurrence:"every weekday"
→ Repeating reminder every weekday at 9am

/remind set time:"in 1 hour" intensity:50 duration:2000 shock_type:Shock user:@Alice recurrence:"every 2 hours"
→ Shock Alice every 2 hours starting in 1 hour
```

---

### `/remind list`
**Description:** View all your active reminders.

**Parameters:**
- `page` (optional): Page number for pagination

Shows:
- Reminder ID
- Target user
- Next trigger time
- Shock settings
- Recurrence pattern (if any)

**Example:**
```
/remind list
→ Shows all reminders with quick cancel buttons

/remind list page:2
→ Shows page 2 of reminders
```

---

### `/remind cancel`
**Description:** Cancel a reminder.

**Parameters:**
- `reminder_id`: The ID of the reminder to cancel

**Example:**
```
/remind cancel reminder_id:42
→ Reminder #42 cancelled
```

---

### `/remind info`
**Description:** Get detailed information about a specific reminder.

**Parameters:**
- `reminder_id`: The ID of the reminder

**Example:**
```
/remind info reminder_id:42
→ Shows full details of reminder #42
```

---

## Triggers (Automated Shocks)

Triggers activate automatically when a user sends a message matching a pattern.

### `/trigger add`
**Description:** Create a word/phrase trigger.

Opens a modal where you configure:
- **Trigger Name**: Descriptive name (optional)
- **Regex Pattern**: Words or phrases to match (case-insensitive)

**Parameters:**
- `intensity`: 1-100
- `duration`: 300-65535 milliseconds
- `shock_type`: Shock/Vibrate/Sound
- `cooldown`: Seconds before trigger can activate again (0-3600)
- `user` (optional): Target user (defaults to yourself)

**Pattern Examples:**
- `bad word` - Matches "bad word"
- `bad word|naughty phrase` - Matches either phrase
- `\bstupid\b` - Matches whole word "stupid"
- `oops|whoops|mistake` - Matches any of these

**Examples:**
```
/trigger add intensity:30 duration:1000 shock_type:Shock cooldown:60
→ Modal opens
→ Enter pattern: "bad word|naughty phrase"
→ Trigger created

/trigger add intensity:50 duration:2000 shock_type:Vibrate cooldown:300 user:@Alice
→ Create trigger for Alice
```

---

### `/trigger list`
**Description:** View all active triggers.

**Parameters:**
- `user` (optional): Filter by target user
- `page` (optional): Page number

**Example:**
```
/trigger list
→ Shows all your triggers

/trigger list user:@Alice
→ Shows only triggers targeting Alice
```

---

### `/trigger remove`
**Description:** Delete a trigger.

**Parameters:**
- `trigger_id`: The ID of the trigger to remove

**Example:**
```
/trigger remove trigger_id:7
→ Trigger #7 deleted
```

---

### `/trigger toggle`
**Description:** Enable or disable a trigger without deleting it.

**Parameters:**
- `trigger_id`: The ID of the trigger
- `enabled`: True/False

**Example:**
```
/trigger toggle trigger_id:7 enabled:False
→ Trigger #7 disabled (won't activate)

/trigger toggle trigger_id:7 enabled:True
→ Trigger #7 re-enabled
```

---

### `/trigger info`
**Description:** Get detailed information about a trigger.

**Parameters:**
- `trigger_id`: The ID of the trigger

**Example:**
```
/trigger info trigger_id:7
→ Shows full details and statistics
```

---

## Preferences

Manage your default shock settings.

### `/preferences set_defaults`
**Description:** Configure your default shock parameters.

When you use `/shock` without specifying all parameters, these defaults are used.

**Parameters:**
- `intensity`: Default intensity (1-100)
- `duration`: Default duration (300-65535 ms)
- `shock_type`: Default type (Shock/Vibrate/Sound)
- `target_user` (optional): Set different defaults per user

**Examples:**
```
/preferences set_defaults intensity:30 duration:1000 shock_type:Shock
→ Sets global defaults

/preferences set_defaults intensity:50 duration:2000 shock_type:Vibrate target_user:@Alice
→ Sets specific defaults for Alice
```

---

### `/preferences view`
**Description:** View your current preferences and defaults.

**Parameters:**
- `target_user` (optional): View preferences for specific user

**Example:**
```
/preferences view
→ Shows your global defaults and last-used settings

/preferences view target_user:@Alice
→ Shows your defaults for Alice
```

---

### `/preferences reset`
**Description:** Reset preferences to default values.

**Parameters:**
- `target_user` (optional): Reset preferences for specific user

**Example:**
```
/preferences reset
→ Resets all preferences

/preferences reset target_user:@Alice
→ Resets only Alice-specific preferences
```

---

## Action Logs

View the history of all shock commands.

### `/logs view`
**Description:** View action logs.

**Parameters:**
- `days` (optional): Number of days to look back (1-90, default: 7)
- `page` (optional): Page number

Shows:
- Who executed the command
- When it was executed
- Target user
- Shock parameters
- Source (manual, reminder, or trigger)

**Examples:**
```
/logs view
→ Shows last 7 days of actions

/logs view days:30
→ Shows last 30 days

/logs view days:7 page:2
→ Page 2 of last 7 days
```

---

### `/logs export`
**Description:** Export logs as a CSV file.

**Parameters:**
- `days` (optional): Number of days to export (1-90, default: 30)

Generates a downloadable CSV file with all action data.

**Example:**
```
/logs export days:90
→ Downloads CSV with 90 days of logs
```

---

## Settings (Admin)

Administrative commands for server configuration. Requires **Manage Roles** permission.

### `/settings set_control_roles`
**Description:** Configure administrative control roles.

**Note:** Bot Shock uses a consent-based system. Control roles are for administrative purposes only - users must still explicitly grant control via `/controllers add`.

Opens a role selector where you can choose which roles have administrative privileges.

**Example:**
```
/settings set_control_roles
→ Select admin roles
→ Members can help troubleshoot but still need consent to control devices
```

---

## Tips & Best Practices

### Smart Defaults
- Configure your preferences with `/preferences set_defaults`
- The bot remembers your last-used settings
- You can set different defaults per user

### Cooldowns
- Always set reasonable cooldowns on triggers
- Prevents accidental spam from repeated messages

### Testing
- Test new triggers with low intensity first
- Use `/trigger toggle` to temporarily disable triggers without deleting them

### Safety
- Start with low intensity values (10-20) and increase gradually
- Set reasonable duration limits (1000-2000ms recommended)
- Always establish safewords/safe signals outside the bot

### Organization
- Name your triggers descriptively
- Use `/remind list` and `/trigger list` regularly to review active items
- Clean up unused reminders and triggers

### Permissions
- Regularly review who has controller access with `/controllers list`
- Remove permissions when no longer needed with `/controllers remove`
- Check action logs periodically with `/logs view`
