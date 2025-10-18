# Installation Guide

This guide will walk you through installing and setting up Bot Shock on your server.

## Prerequisites

- **Python 3.10 or higher** (Python 3.11-3.13 recommended)
- **Discord bot account** with appropriate permissions
- **OpenShock account** with API access
- **Linux/Windows/macOS** server or personal computer

## Step 1: Install Python

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3.11 python3.11-pip python3.11-venv
```

### macOS
```bash
brew install python@3.11
```

### Windows
Download Python from [python.org](https://www.python.org/downloads/) and install it, making sure to check "Add Python to PATH".

## Step 2: Clone or Download Bot Shock

```bash
# If using git
git clone <repository-url>
cd BotShock

# Or download and extract the ZIP file, then navigate to the folder
```

## Step 3: Create a Virtual Environment (Recommended)

```bash
python3 -m venv venv

# Activate it:
# Linux/macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

## Step 4: Install Bot Shock

```bash
# Install in development mode (recommended for easy updates)
pip install -e .

# Or install normally
pip install .
```

This will install Bot Shock and all its dependencies:
- `disnake` - Discord API wrapper
- `aiohttp` - Async HTTP client for OpenShock API
- `python-dotenv` - Environment variable management
- `cryptography` - Encryption for API tokens
- `aiosqlite` - Async SQLite database

## Step 5: Generate Encryption Key

Bot Shock uses encryption to securely store OpenShock API tokens. Generate a key:

```bash
botshock-keygen
```

This will output an encryption key. **Save this securely!** You'll need it in the next step.

## Step 6: Configure Environment Variables

Create a `.env` file in the project directory:

```bash
touch .env
```

Edit the `.env` file with your preferred text editor and add:

```env
# Required Settings
DISCORD_TOKEN=your_discord_bot_token_here
ENCRYPTION_KEY=your_generated_encryption_key_here

# Optional Settings (uncomment to customize)
# DATABASE_PATH=botshock.db
# DATABASE_POOL_SIZE=5
# LOG_LEVEL=INFO
# LOG_DIR=logs
# API_BASE_URL=https://api.openshock.app
# API_TIMEOUT=10
# API_MAX_CONNECTIONS=100
# API_REQUESTS_PER_MINUTE=60
```

### Getting Your Discord Bot Token

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section
4. Click "Reset Token" to get your bot token
5. Copy the token and paste it into your `.env` file

### Bot Permissions

Your bot needs the following Discord permissions:
- **Send Messages**
- **Embed Links**
- **Read Message History**
- **Use Slash Commands**
- **Attach Files**

Permission Integer: `2147600384`

### Invite the Bot

Use this URL template to invite your bot (replace `YOUR_CLIENT_ID`):
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=2147600384&scope=bot%20applications.commands
```

## Step 7: Run Bot Shock

```bash
botshock
```

You should see output indicating the bot is starting and connecting to Discord.

## Step 8: Verify Installation

In your Discord server, try the command:
```
/openshock setup
```

If you see a modal popup asking for your OpenShock API token, the bot is working correctly!

## Troubleshooting

### "DISCORD_TOKEN not found"
- Make sure your `.env` file is in the same directory where you run the bot
- Check that there are no typos in your `.env` file
- Ensure the token has no extra spaces

### "ENCRYPTION_KEY not found"
- Run `botshock-keygen` to generate a key
- Add it to your `.env` file

### Bot doesn't respond to commands
- Make sure you invited the bot with the correct permissions
- Check that the bot has the "applications.commands" scope
- Wait a few minutes for Discord to register the slash commands

### Import errors
- Make sure you installed the package: `pip install -e .`
- Try reinstalling: `pip install --force-reinstall -e .`

### Database errors
- Make sure the bot has write permissions in its directory
- Check that `botshock.db` isn't locked by another process

## Updating Bot Shock

If you installed in development mode (`pip install -e .`):

```bash
git pull  # If using git
# Or download the latest version

# Restart the bot
```

If you need to reinstall dependencies:
```bash
pip install --upgrade -e .
```

## Running as a Service (Linux)

To keep Bot Shock running in the background:

### Using systemd

Create `/etc/systemd/system/botshock.service`:

```ini
[Unit]
Description=Bot Shock Discord Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/BotShock
Environment="PATH=/path/to/BotShock/venv/bin"
ExecStart=/path/to/BotShock/venv/bin/botshock
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable botshock
sudo systemctl start botshock
sudo systemctl status botshock
```

### Using screen (Simple alternative)

```bash
screen -S botshock
cd /path/to/BotShock
source venv/bin/activate
botshock

# Press Ctrl+A then D to detach
# Reattach with: screen -r botshock
```

## Next Steps

- Read the [Configuration Guide](CONFIGURATION.md) for detailed settings
- Check the [Command Reference](COMMANDS.md) to learn all commands
- Set up your first user with `/openshock setup`