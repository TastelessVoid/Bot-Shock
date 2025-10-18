# User Guide

A comprehensive guide for users of BotShock. This guide assumes the bot is already installed and running in your Discord server.

## Table of Contents
- [Getting Started](#getting-started)
- [Basic Usage](#basic-usage)
- [Controllers System](#controllers-system)
- [Scheduled Reminders](#scheduled-reminders)
- [Automated Triggers](#automated-triggers)
- [Safety and Best Practices](#safety-and-best-practices)

---

## Getting Started

### What is BotShock?

BotShock is a Discord bot that lets you:
- Control OpenShock devices through Discord
- Give specific people permission to control your device
- Set up scheduled reminders
- Create automated word triggers
- View a complete history of all actions

### First Time Setup

#### 1. Get Your OpenShock API Token

1. Go to [OpenShock](https://openshock.app) and log in
2. Click on your profile → **Settings**
3. Go to **API Tokens** section
4. Click **Create Token** or copy an existing one
5. **Important:** Keep this token secret!

#### 2. Register with the Bot

In Discord, use the command:
```
/openshock setup
```

A modal will appear asking for your OpenShock API token. Paste it there and submit.

The bot will:
- Verify your token works
- Encrypt it securely
- Store it in the database

#### 3. Add Your Shocker

After verifying your API token the bot will automatically prompt you to add your shocker device(s). 
If you skip this step, you can always add them later with:

```
/openshock add_shocker
```

The bot will show you a list of shockers from your OpenShock account. Select the one(s) you want to use with the bot.

**Done!** You're now registered and ready to use BotShock.

---

## Basic Usage

### Manual Shock Commands

The basic command for sending a shock is:
```
/shock
```

**Parameters:**
- `user` - Who to shock (yourself or someone who gave you permission)
- `intensity` - Strength from 1-100
- `duration` - Length in milliseconds (300-65535)
- `shock_type` - Shock, Vibrate, or Sound
- `shocker_id` - Specific device (auto-selected if only one)

**Examples:**

Shock yourself:
```
/shock intensity:30 duration:1000 shock_type:Shock
```

Shock someone else (if they gave you permission):
```
/shock user:@Alice intensity:40 duration:1500 shock_type:Vibrate
```

Use smart defaults (bot remembers your last settings):
```
/shock
```

### Smart Defaults

BotShock remembers your preferences:
- **Last-used settings** - Automatically applied when you don't specify parameters
- **Configured defaults** - Set your preferred values

To configure defaults:
```
/preferences set_defaults intensity:30 duration:1000 shock_type:Shock
```

Now whenever you use `/shock` without specifying values, it will use your defaults!

### Check Your Settings

View your current preferences:
```
/preferences view
```

This shows:
- Your configured defaults
- Your last-used settings
- Per-user preferences (if you've set any)

---

## Controllers System

BotShock uses a **consent-based** system. Nobody can control your device unless you explicitly give them permission.

### Giving Someone Permission

To let someone control your device:
```
/controllers add
```

A selection menu will appear where you can choose:
- **Users** - Specific Discord users
- **Roles** - Anyone with a certain role
- **Both** - Mix of users and roles

Select the people/roles you trust, review your selections, then confirm.

### Viewing Your Controllers

See who currently has permission:
```
/controllers list
```

This shows:
- Users who can control you
- Roles that can control you
- When permission was granted

### Removing Permission

To revoke someone's access:
```
/controllers remove user:@JohnDoe
```

Or remove a role:
```
/controllers remove role:@Dominants
```

They will immediately lose permission to control your device.

### Safety Tips

✅ **Good practices:**
- Only add people you completely trust
- Review your controller list regularly
- Remove permissions when relationships change
- Establish clear boundaries and safewords

❌ **Avoid:**
- Adding people under pressure
- Giving permissions "to see if it works"
- Leaving old permissions active
- Assuming roles are always safe

---

## Scheduled Reminders

Reminders are scheduled shock commands that execute automatically.

### Creating a Reminder

Basic command:
```
/remind set time:"in 10 minutes" intensity:30 duration:1000 shock_type:Shock
```

**Time formats:**
- `in 5 minutes`
- `in 2 hours`
- `tomorrow at 3pm`
- `next monday at 9am`
- `2024-12-25 14:30`

### Recurring Reminders

Add the `recurrence` parameter:
```
/remind set time:"tomorrow at 8am" intensity:25 duration:1000 shock_type:Vibrate recurrence:"every weekday"
```

**Recurrence patterns:**
- `every day` - Daily
- `every weekday` - Monday-Friday
- `every 2 hours` - Every 2 hours
- `every monday at 10am` - Weekly on Monday
- `every 30 minutes` - Every half hour

### Examples

Morning alarm (yourself):
```
/remind set time:"tomorrow at 7am" intensity:40 duration:2000 shock_type:Vibrate recurrence:"every weekday"
```

One-time reminder:
```
/remind set time:"in 30 minutes" intensity:30 duration:1000 shock_type:Shock
```

Reminder for someone you control:
```
/remind set time:"in 1 hour" intensity:35 duration:1500 shock_type:Shock user:@Alice recurrence:"every 2 hours"
```

### Managing Reminders

**View all reminders:**
```
/remind list
```

**Get details on a specific reminder:**
```
/remind info reminder_id:42
```

**Cancel a reminder:**
```
/remind cancel reminder_id:42
```

The list view also has quick cancel buttons for each reminder!

---

## Automated Triggers

Triggers automatically shock you when you say certain words or phrases in Discord.

### How Triggers Work

1. You create a trigger with a word pattern
2. When you send a message matching that pattern, the trigger activates
3. The configured shock is sent automatically
4. Cooldown prevents spam (trigger won't activate again for X seconds)

### Creating a Trigger

```
/trigger add intensity:30 duration:1000 shock_type:Shock cooldown:60
```

A modal will appear asking for:
- **Trigger Name** (optional) - Descriptive name
- **Regex Pattern** - Words or phrases to match

**Pattern examples:**
- `bad word` - Matches "bad word"
- `oops|mistake|whoops` - Matches any of these
- `stupid|dumb|idiot` - Matches any of these words

### Pattern Tips

**Simple patterns:**
```
word1|word2|word3
```
Matches any of these words (case-insensitive).

**Whole words only:**
```
\bstupid\b
```
The `\b` means word boundary - won't match "stupid" inside another word.

**Phrases:**
```
bad word|naughty phrase
```
Matches complete phrases.

**Test your patterns** at [regex101.com](https://regex101.com/) before creating triggers!

### Managing Triggers

**View all triggers:**
```
/trigger list
```

**View triggers for specific user:**
```
/trigger list user:@Alice
```

**Get trigger details:**
```
/trigger info trigger_id:7
```

**Disable temporarily (don't delete):**
```
/trigger toggle trigger_id:7 enabled:False
```

**Re-enable:**
```
/trigger toggle trigger_id:7 enabled:True
```

**Delete permanently:**
```
/trigger remove trigger_id:7
```

### Trigger Safety

**Start with safe values:**
- Intensity: 25-30%
- Duration: 1000ms (1 second)
- Cooldown: 60-120 seconds (1-2 minutes)

**Test carefully:**
1. Create trigger with low intensity
2. Test with a few messages
3. Check if pattern is too broad or too narrow
4. Adjust and test again
5. Increase intensity once comfortable

**Common mistakes:**
- **Too broad:** Pattern matches too many messages
- **No cooldown:** Trigger spams you repeatedly
- **Too high intensity:** Starts too strong
- **False positives:** Pattern matches unintended words

---

## Action Logs

Every shock command is logged for transparency and safety.

### Viewing Logs

See your action history:
```
/logs view
```

**Parameters:**
- `days` - How far back to look (1-90, default 7)
- `page` - Page number for pagination

**Examples:**
```
/logs view days:30
```
Shows last 30 days of activity.

### What's in the Logs

Each log entry shows:
- **Timestamp** - When it happened
- **Controller** - Who sent the command
- **Target** - Who received it
- **Shock details** - Type, intensity, duration
- **Source** - Manual, reminder, or trigger

### Exporting Logs

Download logs as a CSV file:
```
/logs export days:90
```

This gives you a spreadsheet with all action data for your own records.

### Why Logs Matter

Logs provide:
- **Accountability** - Clear record of who did what
- **Safety** - Detect unauthorized activity
- **Analysis** - Review patterns and frequency
- **Evidence** - Documentation if needed

**Review logs regularly!** Especially if you have multiple controllers or triggers.

---

## Safety and Best Practices

### Start Slow

**For new users:**
1. Start with intensity 20-30%
2. Use short durations (500-1000ms)
3. Test in a safe, private environment
4. Gradually increase as you learn your limits

### Establish Boundaries

**Before giving control:**
- Discuss limits and expectations
- Establish safewords/signals OUTSIDE Discord
- Agree on maximum intensity and frequency
- Set clear rules about when control is active

### Regular Reviews

**Weekly checklist:**
- [ ] Review who has controller permissions
- [ ] Check active reminders
- [ ] Review active triggers
- [ ] Look at action logs for unusual activity
- [ ] Test emergency procedures

### Emergency Procedures

**If something goes wrong:**

1. **Disable triggers immediately:**
   ```
   /trigger toggle trigger_id:X enabled:False
   ```

2. **Cancel active reminders:**
   ```
   /remind cancel reminder_id:X
   ```

3. **Remove controller access:**
   ```
   /controllers remove user:@Person
   ```

4. **Complete removal (nuclear option):**
   ```
   /openshock unregister
   ```

5. **Physical device control:**
   - Power off the device
   - Use OpenShock app for manual control
   - Remove device if needed

**Always have:**
- Safeword/signal outside the bot
- OpenShock app installed on your phone
- Easy access to device power
- Someone you trust available to help

### Privacy Considerations

**What the bot knows:**
- Your Discord user ID
- Your encrypted OpenShock API token
- Your device IDs
- Who can control you
- History of all shock commands

**Your responsibilities:**
- Keep your Discord account secure
- Don't share your API token
- Review privacy policy
- Understand the bot is self-hosted (admin can access database)

### Responsible Use

**Do:**
- Use consensually
- Respect limits and boundaries
- Communicate clearly
- Keep safewords sacred
- Check in regularly

**Don't:**
- Pressure others to participate
- Ignore safewords or limits
- Use while impaired
- Use during activities requiring full attention
- Assume consent is permanent

---

## Common Scenarios

### Scenario 1: Daily Morning Routine

You want a gentle vibration every weekday morning:
```
/remind set time:"tomorrow at 7am" intensity:25 duration:1000 shock_type:Vibrate recurrence:"every weekday"
```

### Scenario 2: Word Accountability

You want to reduce saying "um" and "uh":
```
/trigger add intensity:30 duration:800 shock_type:Shock cooldown:90
→ Pattern: \bum\b|\buh\b
```

### Scenario 3: Gaming Sessions

Friend wants to control your device during gaming:

1. Set specific defaults for them:
   ```
   /preferences set_defaults intensity:40 duration:1500 shock_type:Shock target_user:@Friend
   ```

2. Give them permission:
   ```
   /controllers add
   → Select @Friend
   ```

3. When gaming ends, remove permission:
   ```
   /controllers remove user:@Friend
   ```

### Scenario 4: Temporary Control

Give someone access for a few hours:

1. Add them as controller
2. Set a reminder to notify you:
   ```
   /remind set time:"in 3 hours" intensity:10 duration:300 shock_type:Sound
   → Reminder to remove their access
   ```
3. Remove their permission when done

---

## FAQ

**Q: Can I use the bot in DMs?**
A: No, the bot only works in servers. This is for accountability and the permission system.

**Q: Can I control multiple people?**
A: Yes, if they each give you permission with `/controllers add`.

**Q: What happens if I lose my encryption key?**
A: You'll need to re-register with `/openshock setup` and add your shockers again.

**Q: Can the bot admin see my API token?**
A: It's encrypted in the database, but a determined admin with the encryption key could decrypt it. Only use trusted bot instances.

**Q: How do I know if someone is trying to control me without permission?**
A: Check logs with `/logs view`. All attempts (authorized or not) are logged.

**Q: Can I use multiple bots with the same OpenShock account?**
A: Yes, but use different API tokens for each bot for better security.

**Q: What if OpenShock is down?**
A: Commands will fail. Check https://status.openshock.app

**Q: Can triggers activate in any channel?**
A: Yes, unless the bot doesn't have access to that channel. Be careful in public channels!

---

## Getting Help

- Check [TROUBLESHOOTING](/docs/TROUBLESHOOTING.md) for common issues
- Ask server administrators for help
- Review command reference: [COMMANDS](/docs/COMMANDS.md)
- Test with low intensities first

**Remember: Your safety is paramount. Don't hesitate to use emergency procedures if needed!**


