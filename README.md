# Bot Shock

Bot Shock is your ever-dutiful gentleman companion, here to assist with your most electrifying whims. By linking your OpenShock account to Discord, he’ll help you administer shocks, schedule jolting reminders, and even grant trusted associates access to your device. Naturally, he insists on proper etiquette: safety and consent above all, dear user.


### This project is still a work in progress!

## Key Features

- **User Management**: Register users and link their OpenShock accounts with Discord
- **Controller System**: Flexible permission system allowing users to grant control to others
- **Scheduled Reminders**: Set up recurring or one-time reminders with customizable actions
- **Automated Triggers**: Create regex-based triggers that activate when specific conditions are met
- **Action Logging**: Complete audit trail of all device actions

## Quick Start

1. **Installation**:
   ```bash
   pip install -e .
   ```

2. **Configuration**:
   Create a `.env` file with your Discord bot token and encryption key:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   ENCRYPTION_KEY=your_encryption_key
   ```

3. **Generate Encryption Key**:
   ```bash
   botshock-keygen
   ```

4. **Run the Bot**:
   ```bash
   botshock
   ```

## Documentation

For detailed documentation including:
- Complete setup instructions
- Command reference
- Configuration options
- Troubleshooting

Please see the [docs](/docs) directory.

## Requirements

- Python 3.10 or higher
- Discord bot with appropriate permissions
- OpenShock account and API access

## Privacy & Security

Review the [Privacy Policy](PRIVACY.md) to understand how Bot Shock handles your data.

## Terms of Service

By using this software you agree to the [Terms of Service](TERMS.md). Please read them carefully.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This bot is designed for consensual use only. Users are responsible for ensuring all interactions comply with applicable laws and the terms of service of OpenShock and Discord. Always prioritize safety and consent.
