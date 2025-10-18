# Troubleshooting Guide

Common issues and their solutions for Bot Shock.

## Table of Contents
- [Installation Issues](#installation-issues)
- [Configuration Issues](#configuration-issues)
- [Command Issues](#command-issues)
- [API Issues](#api-issues)
- [Database Issues](#database-issues)
- [Permission Issues](#permission-issues)
- [Performance Issues](#performance-issues)

---

## Installation Issues

### "Command not found: botshock"

**Cause:** Bot not installed or not in PATH.

**Solutions:**
```bash
# Verify installation
pip list | grep botshock

# Reinstall
pip install -e .

# Or use Python module directly
python -m botshock
```

### "ModuleNotFoundError: No module named 'disnake'"

**Cause:** Dependencies not installed.

**Solution:**
```bash
pip install -e .
# Or
pip install -r requirements.txt
```

### "Python version 3.10 or higher required"

**Cause:** Python version too old.

**Solution:**
```bash
# Check version
python --version

# Install newer Python (Ubuntu/Debian)
sudo apt install python3.11 python3.11-pip

# Use specific version
python3.11 -m pip install -e .
python3.11 -m botshock
```

---

## Configuration Issues

### "DISCORD_TOKEN not found in environment variables"

**Cause:** Missing or incorrectly formatted .env file.

**Solutions:**
1. Check .env file exists:
   ```bash
   ls -la .env
   ```

2. Verify .env format (no spaces around `=`):
   ```env
   DISCORD_TOKEN=your_token_here
   ENCRYPTION_KEY=your_key_here
   ```

3. Check you're running from correct directory:
   ```bash
   pwd
   # Should be in project directory
   ```

4. Try absolute path to .env:
   ```bash
   set -x DISCORD_TOKEN "your_token"
   set -x ENCRYPTION_KEY "your_key"
   botshock
   ```

### "ENCRYPTION_KEY not found"

**Cause:** Missing encryption key.

**Solution:**
```bash
# Generate key
botshock-keygen

# Add to .env
echo "ENCRYPTION_KEY=<generated_key>" >> .env
```

### "Invalid Discord token"

**Cause:** Token is incorrect or expired.

**Solutions:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application → Bot
3. Click "Reset Token"
4. Copy new token to .env file
5. Restart bot

### "Invalid encryption key format"

**Cause:** Malformed encryption key.

**Solution:**
```bash
# Generate new valid key
botshock-keygen

# Update .env with the exact output (should end with =)
```

---

## Command Issues

### "Slash commands not appearing"

**Cause:** Commands not synced with Discord.

**Solutions:**
1. Wait 5-10 minutes for Discord to sync commands
2. Verify bot has `applications.commands` scope
3. Check bot invite URL includes scope:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_ID&permissions=277025770496&scope=bot%20applications.commands
   ```
4. Re-invite the bot with correct scope
5. Restart Discord client (Ctrl+R)

### "This interaction failed"

**Cause:** Bot took too long to respond (3 second limit).

**Common causes:**
- API timeout
- Database lock
- Heavy load

**Solutions:**
1. Check bot logs: `tail -f logs/bot.log`
2. Increase API timeout in .env:
   ```env
   API_TIMEOUT=20
   ```
3. Reduce database pool contention:
   ```env
   DATABASE_POOL_SIZE=10
   ```

### "Not Registered" error

**Cause:** User hasn't registered their OpenShock account.

**Solution:**
```
/openshock setup
```
Paste OpenShock API token in the modal.

### "Permission Denied" error

**Cause:** User doesn't have permission to control target.

**Solutions:**
1. Target user must grant permission:
   ```
   /controllers add
   ```
   Select the controller user/role.

2. Verify permissions:
   ```
   /controllers list
   ```

---

## API Issues

### "API request timeout"

**Cause:** OpenShock API not responding.

**Solutions:**
1. Check OpenShock status: https://status.openshock.app
2. Verify internet connectivity
3. Increase timeout:
   ```env
   API_TIMEOUT=20
   ```
4. Check API URL is correct:
   ```env
   API_BASE_URL=https://api.openshock.app
   ```

### "Invalid API token"

**Cause:** OpenShock API token expired or incorrect.

**Solutions:**
1. Regenerate token on OpenShock dashboard
2. Re-register with bot:
   ```
   /openshock unregister
   /openshock setup
   ```

### "Rate limited by API"

**Cause:** Too many requests to OpenShock.

**Solutions:**
1. Reduce request rate:
   ```env
   API_REQUESTS_PER_MINUTE=30
   ```
2. Check for trigger spam (reduce cooldown)
3. Disable problematic triggers temporarily

### "Cannot connect to OpenShock API"

**Cause:** Network or SSL issues.

**Solutions:**
1. Test connectivity:
   ```bash
   curl -I https://api.openshock.app
   ```
2. Check firewall/proxy settings
3. Verify DNS resolution:
   ```bash
   nslookup api.openshock.app
   ```
4. Update CA certificates:
   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install ca-certificates
   ```

---

## Database Issues

### "Database is locked"

**Cause:** Multiple processes accessing database.

**Solutions:**
1. Check for multiple bot instances:
   ```bash
   ps aux | grep botshock
   # Kill duplicates if found
   ```
2. Increase pool size:
   ```env
   DATABASE_POOL_SIZE=10
   ```
3. Check file permissions:
   ```bash
   ls -l botshock.db
   chmod 600 botshock.db
   ```

### "No such table" error

**Cause:** Database not initialized.

**Solutions:**
1. Delete corrupted database:
   ```bash
   mv botshock.db botshock.db.backup
   ```
2. Restart bot (will recreate database)
3. Users will need to re-register

### "Database corruption detected"

**Cause:** Database file corrupted.

**Solutions:**
1. Stop bot immediately
2. Backup current database:
   ```bash
   cp botshock.db botshock.db.corrupt
   ```
3. Try recovery:
   ```bash
   sqlite3 botshock.db "PRAGMA integrity_check;"
   ```
4. If recovery fails, restore from backup:
   ```bash
   cp botshock.db.backup botshock.db
   ```
5. If no backup, start fresh (data loss)

### "Unable to write to database"

**Cause:** Permission issues.

**Solutions:**
```bash
# Check permissions
ls -l botshock.db

# Fix permissions
chmod 600 botshock.db
chown your_user:your_group botshock.db

# Check disk space
df -h
```

---

## Permission Issues

### "Cannot add controller: Permission denied"

**Cause:** User trying to grant permissions for someone else's device.

**Solution:** Only device owners can add controllers for their own devices.

### "Manage Roles permission required"

**Cause:** User doesn't have Discord permissions for `/settings` commands.

**Solution:** User needs "Manage Roles" or "Administrator" permission in Discord server.

### "Cannot control this user"

**Cause:** Controller hasn't been granted permission.

**Solutions:**
1. Device owner grants permission:
   ```
   /controllers add
   ```
2. Verify with:
   ```
   /controllers list
   ```

---

## Performance Issues

### Bot slow to respond

**Causes & Solutions:**

1. **High CPU usage:**
   ```bash
   # Check resource usage
   top -p $(pgrep -f botshock)
   
   # Reduce logging:
   LOG_LEVEL=WARNING
   ```

2. **Many concurrent users:**
   ```env
   # Increase connection pools
   DATABASE_POOL_SIZE=15
   API_MAX_CONNECTIONS=150
   ```

3. **Slow disk I/O:**
   - Move database to SSD
   - Reduce log verbosity
   - Clean up old logs

4. **Network latency:**
   ```env
   API_TIMEOUT=15
   ```

### Memory leaks / Growing memory usage

**Solutions:**
1. Restart bot regularly (systemd timer)
2. Check for leaked connections in logs
3. Update to latest version
4. Report issue with logs

### Database growing too large

**Solutions:**
1. Archive old action logs:
   ```bash
   sqlite3 botshock.db "DELETE FROM action_logs WHERE timestamp < datetime('now', '-90 days');"
   ```

2. Vacuum database:
   ```bash
   sqlite3 botshock.db "VACUUM;"
   ```

3. Regular cleanup schedule:
   ```bash
   # Add to crontab
   0 3 * * 0 cd /path/to/BotShock && sqlite3 botshock.db "DELETE FROM action_logs WHERE timestamp < datetime('now', '-90 days'); VACUUM;"
   ```

---

## Logging and Debugging

### Enable debug logging

Edit .env:
```env
LOG_LEVEL=DEBUG
```

Restart bot and check logs:
```bash
tail -f logs/bot.log
```

### View specific errors

```bash
# Recent errors
grep -i error logs/bot.log | tail -20

# Permission issues
grep -i permission logs/bot.log

# API issues
grep -i "api\|timeout" logs/bot.log
```

### Check bot status

```bash
# Is bot running?
ps aux | grep botshock

# Check systemd status
systemctl status botshock

# View recent logs
journalctl -u botshock -f
```

---

## Common Error Messages

### "Shocker not found"

**Cause:** Shocker removed from OpenShock or ID changed.

**Solution:**
```
/openshock remove_shocker
/openshock add_shocker
```

### "Invalid time format"

**Cause:** Time string for reminder not recognized.

**Valid formats:**
- `in 5 minutes`
- `in 2 hours`
- `tomorrow at 3pm`
- `2024-12-25 14:30`

### "Trigger pattern invalid"

**Cause:** Regex pattern syntax error.

**Solutions:**
- Test pattern: https://regex101.com/
- Use simple patterns: `word1|word2|word3`
- Escape special characters: `\(parenthesis\)`

### "Cooldown active"

**Cause:** Trigger cooldown hasn't expired.

**Solution:** Wait for cooldown period or increase cooldown value.

---

## Getting More Help

### Collect diagnostic information

```bash
# System info
uname -a
python --version

# Bot info
pip show botshock

# Recent logs
tail -50 logs/bot.log

# Error logs
grep -i error logs/bot.log | tail -20
```

### Check the logs

Most issues can be diagnosed from logs:
```bash
# Live log monitoring
tail -f logs/bot.log

# Search for specific user
grep "user_id:123456" logs/bot.log

# Search for errors
grep -i "error\|exception\|failed" logs/bot.log
```

### Report a bug

When reporting issues, include:
1. Python version (`python --version`)
2. BotShock version
3. Relevant error messages from logs
4. Steps to reproduce
5. Expected vs actual behavior

### Additional Resources

- Check README.md for basic setup
- Review CONFIGURATION.md for environment variables
- See SECURITY.md for security-related issues
- Consult COMMANDS.md for command usage

---

## Emergency Procedures

### Bot won't start

```bash
# 1. Check configuration
cat .env

# 2. Test Python
python -c "import disnake; print('OK')"

# 3. Check database
sqlite3 botshock.db ".tables"

# 4. Start with verbose logging
LOG_LEVEL=DEBUG python -m botshock
```

### Need to reset everything

```bash
# Backup current state
cp botshock.db botshock.db.backup
cp .env .env.backup

# Generate new keys
botshock-keygen

# Update .env with new keys

# Start fresh
mv botshock.db botshock.db.old
botshock

# Users will need to re-register
```

### Database recovery

```bash
# Check integrity
sqlite3 botshock.db "PRAGMA integrity_check;"

# Dump data
sqlite3 botshock.db .dump > backup.sql

# Restore to new database
sqlite3 botshock_new.db < backup.sql

# Replace old database
mv botshock.db botshock.db.corrupt
mv botshock_new.db botshock.db
```
