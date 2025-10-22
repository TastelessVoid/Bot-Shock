# Device Worn Feature

## Overview
This feature allows device wearers to specify whether they are currently wearing their collar/device. When a device is not being worn, controllers cannot send shocks to that user.

## Changes Made

### 1. Database Schema (botshock/core/database.py)
- **Added `device_worn` column** to the `users` table with default value of `1` (true)
- **Migration code** included in `init_database()` method to add the column to existing databases
- Migration checks if the column exists before attempting to add it

### 2. Database Methods (botshock/core/database.py)
Two new async methods added to the `Database` class:

#### `async def get_device_worn_status(discord_id: int, guild_id: int) -> bool`
- Retrieves whether a user's device is currently worn
- Returns `True` by default if user not found
- Converts SQLite boolean (0/1) to Python bool

#### `async def set_device_worn(discord_id: int, guild_id: int, is_worn: bool) -> bool`
- Updates whether a user's device is worn
- Returns `True` on success, `False` on failure
- Logs the status change

### 3. Validation (botshock/utils/validators.py)
- **Updated `ShockValidator.validate_shock_request()`** to check device worn status
- If target user's device is not worn, returns error: `"User [mention] is not wearing their device right now!"`
- Check occurs before shocker selection, preventing any shock attempts

### 4. User Commands (botshock/cogs/user_commands.py)
Added three new sub-commands to the `/openshock` command group:

#### `/openshock device_status`
- Toggles the device worn status (worn ↔ not wearing)
- Confirms the new status with emoji indicators (✅ Wearing / ❌ Not Wearing)
- Explains the implications of the status

#### `/openshock check_device`
- Displays current device worn status
- Shows whether controllers can send shocks
- Provides link to toggle status command

#### Both commands:
- Verify user is registered before proceeding
- Provide helpful feedback in ephemeral messages
- Include logging for audit trail

### 5. Tests (tests/unit/test_validators_more.py)
- Updated `FakeDB` test mock to include `device_worn` parameter
- Added `get_device_worn_status()` method to test mock
- All 68 tests pass

## Usage

### For Device Wearers

1. **Check current device status:**
   ```
   /openshock check_device
   ```
   This shows whether your device is currently marked as worn.

2. **Toggle device status:**
   ```
   /openshock device_status
   ```
   This toggles your device status. When not wearing it, controllers cannot send shocks.

### For Controllers

When attempting to send a shock to a user not wearing their device:
```
/shock user:<user> intensity:50 duration:1000 shock_type:Shock
```
Response: `❌ User @username is not wearing their device right now!`

## Default Behavior

- **New users:** Device status defaults to `1` (wearing) when registered
- **Existing users:** Database migration sets all existing users to `1` (wearing) for backward compatibility
- **Error handling:** If status cannot be retrieved, defaults to `True` (wearing) to allow commands

## Database Migration

For existing installations, the migration runs automatically on bot startup:
1. Checks if `device_worn` column exists in `users` table
2. If missing, adds the column with `NOT NULL DEFAULT 1`
3. All existing users are set to worn status (1)

The migration includes both:
- Synchronous init in `init_database()` for disk-based databases
- Asynchronous init in `_init_schema_async()` for in-memory databases

## Implementation Details

### Validation Flow
1. Shock request initiated
2. Permission checks pass
3. Device worn status is checked
4. If not worn, validation fails with appropriate error message
5. If worn, command proceeds normally

### Security Considerations
- Device worn status is stored per user per guild
- Status is checked at command time (not cached)
- Prevents accidental shocks when device is removed
- Can be toggled at any time

## Testing

All unit and integration tests pass (68/68 tests):
- Validator tests confirm device worn status is checked
- Database tests confirm status can be get/set
- FakeDB mock supports device worn status for tests
- Backward compatibility maintained for existing data

