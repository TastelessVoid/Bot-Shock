# Privacy Policy for Bot Shock

**Last Updated**: October 18, 2025

## Introduction

Bot Shock is a self-hosted Discord bot designed to manage OpenShock devices. This privacy policy explains what data the bot collects, how it's used, and how it's protected.

## Data Collected

### User Information
- **Discord User ID**: Used to identify users and associate them with their settings
- **Discord Username**: Stored for logging and display purposes
- **Server (Guild) ID**: Used to manage server-specific settings

### OpenShock Integration
- **OpenShock API Tokens**: Encrypted and stored to communicate with OpenShock services
- **OpenShock User IDs**: Stored to associate Discord users with their OpenShock accounts
- **Device Shocker IDs**: Stored to enable device control

### Usage Data
- **Action Logs**: Records of all device actions including timestamps, users, controllers, and action parameters
- **Reminders**: Scheduled reminder settings including recurrence patterns and action details
- **Triggers**: Word-based trigger configurations and their associated actions
- **Controller Relationships**: Records of which users have granted control to others
- **Preferences**: User-specific settings such as default intensity and duration values

## How Data Is Used

Data is used exclusively to:
- Authenticate with the OpenShock API on your behalf
- Execute commands and scheduled actions
- Maintain permission controls and user relationships
- Provide logging and accountability features
- Store your preferences and settings

## Data Storage and Security

### Local Storage
- All data is stored locally in a SQLite database (`botshock.db`) on the server running the bot
- The database is not transmitted to any external services except OpenShock API

### Encryption
- OpenShock API tokens are encrypted at rest using Fernet symmetric encryption
- The encryption key is stored separately from the database and should be kept secure
- Encrypted data cannot be accessed without the encryption key

### Access Control
- Only the bot administrator (server owner) has direct access to the database file
- Discord users can only access their own data through bot commands
- Controller relationships are enforced by the bot's permission system

## Data Retention

- **Active Data**: User data is retained as long as the user is registered with the bot
- **Action Logs (database)**: By default retained for accountability. Bot administrators may define their own retention policies and purge older entries if required by law or policy.
- **Bot Logs (files)**: Retention is configurable by the administrator using environment variables:
  - `LOG_MAX_OLD_FILES` (default 10) to cap the number of rotated files
  - `LOG_RETENTION_DAYS` (default 0 = disabled) to time-prune rotated logs older than N days
- **Deletion**: Users can request data deletion through the `/unregister` command. Administrators should also consider purging historical action logs upon verifiable requests if required by applicable law.

## Data Sharing

Bot Shock does **NOT**:
- Share your data with third parties
- Sell or monetize your data
- Transmit data to external services except OpenShock API for device control
- Store data outside the local database

Bot Shock **DOES**:
- Send API requests to OpenShock servers using your encrypted API token
- Display your Discord username to other users in certain contexts (e.g., action logs)
- Allow controllers you've authorized to see relevant information about you

## Third-Party Services

### Discord
Bot Shock operates on Discord's platform and is subject to [Discord's Privacy Policy](https://discord.com/privacy).

### OpenShock
Bot Shock communicates with OpenShock's API to control devices. This is subject to [OpenShock's Privacy Policy and Terms of Service](https://openshock.app/).

## Self-Hosted Nature

**Important**: Bot Shock is designed to be self-hosted. This means:
- You (or your server administrator) control where the data is stored
- The privacy and security of your data depends on how the bot is hosted and configured
- No central authority has access to your bot's database
- You are responsible for securing the server and encryption keys

## User Rights

You have the right to:
- **Access**: View your registered information using bot commands
- **Deletion**: Remove your data using the `/unregister` command
- **Control**: Manage who has permission to control your devices
- **Transparency**: Review action logs to see what actions were performed

## Changes to This Policy

This privacy policy may be updated from time to time. Changes will be reflected in the "Last Updated" date above. Continued use of the bot after changes constitutes acceptance of the updated policy.

## Data Breach Protocol

In the unlikely event of a data breach:
1. The bot administrator should immediately rotate the encryption key
2. All users should be notified through Discord
3. Users should regenerate their OpenShock API tokens
4. The database should be audited for unauthorized access

## Contact and Compliance

For questions about this privacy policy or data handling:
- Contact your bot administrator (the person hosting the bot)
- Review the documentation in [docs](/docs) for technical details

## Consent and Responsibility

By using Bot Shock, you acknowledge that:
- You consent to the data collection and usage described in this policy
- You are responsible for the security of your own Discord account
- You will only use the bot in compliance with all applicable laws
- You understand the self-hosted nature of the bot and where your data is stored

## Recommendations for Bot Administrators

If you host Bot Shock, you should:
- Keep the encryption key secure and separate from the database
- Regularly back up the database
- Restrict file system access to the bot's directory
- Use secure hosting practices
- Inform users about your hosting setup
- Configure log retention (`LOG_RETENTION_DAYS`, `LOG_MAX_OLD_FILES`) according to your jurisdiction
- Comply with applicable data protection laws (GDPR, CCPA, etc.)
