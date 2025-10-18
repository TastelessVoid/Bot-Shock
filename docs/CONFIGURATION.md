# Configuration Guide

Bot Shock is configured through environment variables in a `.env` file. This guide covers all available configuration options.

## Configuration File Location

The `.env` file should be placed in the same directory where you run the bot:
```
BotShock/
├── .env          ← Configuration file here
├── botshock/
├── requirements.txt
└── ...
```

## Required Settings

### DISCORD_TOKEN
**Type:** String  
**Required:** Yes  
**Description:** Your Discord bot token from the Discord Developer Portal.

```env
DISCORD_TOKEN=MTIzNDU2Nzg5M...
```

**How to get:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Go to "Bot" section
4. Click "Reset Token" and copy the token

### ENCRYPTION_KEY
**Type:** String (Base64-encoded Fernet key)  
**Required:** Yes  
**Description:** Encryption key for securing OpenShock API tokens in the database.

```env
ENCRYPTION_KEY=abcdefghijklmno...
```

**How to generate:**
```bash
botshock-keygen
```

**⚠️ Important:**
- Keep this key secret and secure
- If you lose this key, users will need to re-register their OpenShock tokens
- Never commit this to version control
- Back it up securely

## Optional Settings

### Database Configuration

#### DATABASE_PATH
**Type:** String (file path)  
**Default:** `botshock.db`  
**Description:** Path to the SQLite database file.

```env
DATABASE_PATH=botshock.db
# Or use an absolute path:
# DATABASE_PATH=/var/lib/botshock/data.db
```

#### DATABASE_POOL_SIZE
**Type:** Integer  
**Default:** `5`  
**Range:** 1-20  
**Description:** Number of concurrent database connections in the pool.

```env
DATABASE_POOL_SIZE=5
```

Increase if you have a very active server (100+ users), decrease for low-resource systems.

### Logging Configuration

#### LOG_LEVEL
**Type:** String  
**Default:** `INFO`  
**Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`  
**Description:** Logging verbosity level.

```env
LOG_LEVEL=INFO
```

- `DEBUG`: Very verbose, shows all operations (for development/troubleshooting)
- `INFO`: Normal operation logs (recommended)
- `WARNING`: Only warnings and errors
- `ERROR`: Only errors and critical issues
- `CRITICAL`: Only critical failures

#### LOG_DIR
**Type:** String (directory path)  
**Default:** `logs`  
**Description:** Directory where log files are stored.

```env
LOG_DIR=logs
# Or use an absolute path:
# LOG_DIR=/var/log/botshock
```

Log files are automatically rotated:
- Current log: `logs/bot.log`
- Timestamped logs: `logs/bot_YYYYMMDD_HHMMSS.log`
- Keeps last 10 log files by default (configurable)

#### LOG_MAX_OLD_FILES
**Type:** Integer  
**Default:** `10`  
**Range:** `0+`  
**Description:** Maximum number of rotated log files to keep. Set to `0` to disable keeping rotated files (only current log remains).

```env
LOG_MAX_OLD_FILES=10
```

#### LOG_RETENTION_DAYS
**Type:** Integer (days)  
**Default:** `0` (disabled)  
**Range:** `0+`  
**Description:** Time-based pruning for rotated logs. When > 0, any `bot_*.log` older than this many days will be deleted on startup. This is additive to `LOG_MAX_OLD_FILES`.

```env
# Keep rotated logs for 30 days, still cap total rotated files to 10
LOG_RETENTION_DAYS=30
LOG_MAX_OLD_FILES=10
```

Notes:
- Time-based pruning applies to rotated files (`bot_*.log`). The active `bot.log` continues to be written and is snapshotted on startup.
- For stricter compliance, consider lower values (e.g., 14 days) and avoid `DEBUG` level in production.

### API Configuration

#### API_BASE_URL
**Type:** String (URL)  
**Default:** `https://api.openshock.app`  
**Description:** Base URL for OpenShock API.

```env
API_BASE_URL=https://api.openshock.app
```

Only change this if using a custom OpenShock instance or proxy.

#### API_TIMEOUT
**Type:** Integer (seconds)  
**Default:** `10`  
**Range:** 1-60  
**Description:** Timeout for API requests to OpenShock.

```env
API_TIMEOUT=10
```

Increase if you experience frequent timeout errors. Decrease for faster failure detection.

#### API_MAX_CONNECTIONS
**Type:** Integer  
**Default:** `100`  
**Range:** 10-500  
**Description:** Maximum concurrent connections to OpenShock API.

```env
API_MAX_CONNECTIONS=100
```

Higher values allow more simultaneous shock commands but increase memory usage.

#### API_REQUESTS_PER_MINUTE
**Type:** Integer  
**Default:** `60`  
**Range:** 10-300  
**Description:** Rate limit for API requests per minute.

```env
API_REQUESTS_PER_MINUTE=60
```

Adjust based on your OpenShock API limits. Too high may result in rate limiting from OpenShock.

## Example Configurations

### Development Setup
```env
# Development Configuration
DISCORD_TOKEN=your_token_here
ENCRYPTION_KEY=your_key_here
LOG_LEVEL=DEBUG
DATABASE_PATH=botshock_dev.db
LOG_MAX_OLD_FILES=5
LOG_RETENTION_DAYS=0
```

### Production Setup
```env
# Production Configuration
DISCORD_TOKEN=your_token_here
ENCRYPTION_KEY=your_key_here
LOG_LEVEL=INFO
LOG_DIR=/var/log/botshock
DATABASE_PATH=/var/lib/botshock/production.db
DATABASE_POOL_SIZE=10
API_MAX_CONNECTIONS=150
# Logs: keep at most 10 rotated files and prune anything older than 30 days
LOG_MAX_OLD_FILES=10
LOG_RETENTION_DAYS=30
```

### Low-Resource Server
```env
# Optimized for Raspberry Pi or low-spec VPS
DISCORD_TOKEN=your_token_here
ENCRYPTION_KEY=your_key_here
LOG_LEVEL=WARNING
DATABASE_POOL_SIZE=3
API_MAX_CONNECTIONS=50
API_REQUESTS_PER_MINUTE=30
LOG_MAX_OLD_FILES=3
LOG_RETENTION_DAYS=14
```

### High-Traffic Server
```env
# Optimized for large Discord servers
DISCORD_TOKEN=your_token_here
ENCRYPTION_KEY=your_key_here
LOG_LEVEL=INFO
DATABASE_POOL_SIZE=15
API_MAX_CONNECTIONS=200
API_REQUESTS_PER_MINUTE=120
LOG_MAX_OLD_FILES=20
LOG_RETENTION_DAYS=90
```

## Environment-Specific Configuration

### Multiple Environments

You can maintain separate configurations for different environments:

```bash
# Development
cp .env.example .env.dev
# Edit .env.dev

# Production
cp .env.example .env.prod
# Edit .env.prod

# Run with specific config
botshock  # Uses .env by default
```

### Docker Configuration

If running in Docker, use environment variables directly:

```yaml
version: '3'
services:
  botshock:
    build: .
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - LOG_LEVEL=INFO
      - LOG_MAX_OLD_FILES=10
      - LOG_RETENTION_DAYS=30
    volumes:
      - ./data:/app/data
```

## Security Considerations

### Protecting Your .env File

1. **Never commit to version control:**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Set proper file permissions:**
   ```bash
   chmod 600 .env
   ```

3. **Use environment variables in production:**
   Instead of `.env` files, use system environment variables or secrets management.

### Encryption Key Rotation

If you need to change your encryption key:

1. **Backup your database:**
   ```bash
   cp botshock.db botshock.db.backup
   ```

2. **Generate new key:**
   ```bash
   botshock-keygen
   ```

3. **Update .env file** with new key

4. **Important:** All users must re-register their OpenShock tokens using `/openshock setup`

### Secure Storage Locations

**Recommended:**
- `/var/lib/botshock/` - Database
- `/var/log/botshock/` - Logs
- `/etc/botshock/.env` - Configuration (with restricted permissions)

**Avoid:**
- World-readable directories
- Shared hosting /tmp directories
- Version-controlled directories

## Validation

To validate your configuration, run:

```bash
botshock
```

The bot will report any configuration errors on startup:
- Missing required values
- Invalid value formats
- Permission issues

## Getting Help

If you encounter configuration issues:

1. Check the logs: `tail -f logs/bot.log`
2. Verify .env file location and permissions
3. Test with minimal configuration (only required fields)
4. See [Troubleshooting Guide](TROUBLESHOOTING.md)
