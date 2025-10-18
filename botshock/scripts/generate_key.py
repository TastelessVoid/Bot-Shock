#!/usr/bin/env python3
"""
Encryption key generator for Bot Shock.

This script generates a secure encryption key for storing OpenShock API tokens.
The key should be added to your .env file as ENCRYPTION_KEY.
"""

import sys
from pathlib import Path

from cryptography.fernet import Fernet


def main() -> int:
    """
    Generate and optionally save encryption key.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    print("\n" + "=" * 70)
    print("Bot Shock Encryption Key Generator")
    print("=" * 70 + "\n")

    # Check if .env file exists
    env_path = Path(".env")
    env_file_exists = env_path.exists()

    if env_file_exists:
        print("Found existing .env file")
        # Check if key already exists
        content = env_path.read_text()
        if "ENCRYPTION_KEY=" in content:
            print("\n⚠️  WARNING: ENCRYPTION_KEY already exists in .env file!")
            print("Changing the key will make existing encrypted data unreadable.")
            response = (
                input("\nDo you want to generate a new key anyway? (yes/no): ").strip().lower()
            )
            if response not in ["yes", "y"]:
                print("\nOperation cancelled.")
                return 0
    else:
        print("No .env file found. Will create one.")

    # Generate the key
    key = Fernet.generate_key().decode()

    print("\n" + "-" * 70)
    print("Generated encryption key:")
    print("-" * 70)
    print(f"\n{key}\n")
    print("-" * 70)

    # Offer to add to .env file automatically
    if env_file_exists:
        response = input("\nAdd this key to your .env file? (yes/no): ").strip().lower()
    else:
        response = input("\nCreate .env file with this key? (yes/no): ").strip().lower()

    if response in ["yes", "y"]:
        try:
            if env_file_exists:
                # Read existing content
                lines = env_path.read_text().splitlines()

                # Remove old ENCRYPTION_KEY if exists
                lines = [line for line in lines if not line.startswith("ENCRYPTION_KEY=")]

                # Add new key
                lines.append(f"ENCRYPTION_KEY={key}")

                # Write back
                env_path.write_text("\n".join(lines) + "\n")
                print("\n✅ Updated .env file with new encryption key")
            else:
                # Create new .env file
                env_path.write_text(f"ENCRYPTION_KEY={key}\nDISCORD_TOKEN=\n")
                print("\n✅ Created .env file with encryption key")
                print("⚠️  Don't forget to add your DISCORD_TOKEN to the .env file!")

            print("\n" + "=" * 70)
            print("Setup complete! You can now start the bot.")
            print("=" * 70 + "\n")
            return 0

        except Exception as e:
            print(f"\n❌ Error writing to .env file: {e}")
            return 1
    else:
        print("\n⚠️  Key not saved. Copy the key above and add it manually to your .env file:")
        print(f"   ENCRYPTION_KEY={key}")
        print("\n" + "=" * 70 + "\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
