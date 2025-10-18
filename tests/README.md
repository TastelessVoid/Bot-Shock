# BotShock Tests

This directory contains comprehensive tests for BotShock, demonstrating how to test Discord bots without needing actual Discord context.

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures and Discord mocks
├── unit/                    # Unit tests for individual components
│   ├── test_bot.py         # Bot class tests
│   └── test_utils.py       # Utility function tests
├── integration/             # Integration tests for workflows
│   └── test_workflows.py   # End-to-end workflow tests
└── fixtures/                # Additional test fixtures
```

## The "Context" Problem

Discord bots rely heavily on Discord-specific context objects like:
- `disnake.Interaction` (for slash commands)
- `disnake.Message` (for message events)
- `disnake.User`, `disnake.Member` (for user data)
- `disnake.Guild`, `disnake.Channel` (for server/channel data)

These objects can't be easily created in tests because they require an active Discord connection and internal Discord API state.

## The Solution

This is solved with comprehensive mocking using `conftest.py` fixtures.

### 1. Mock Discord Objects

`conftest.py` provides fixtures for all Discord objects:

```python
def test_my_command(mock_interaction, mock_user, mock_guild):
    # Use mock objects that behave like real Discord objects
    assert mock_interaction.user.id == mock_user.id
    assert mock_interaction.guild.id == mock_guild.id
```

### 2. Mock Bot Components

Fixtures are provided for bot services:

```python
async def test_database_operation(mock_database):
    # Use real database with in-memory SQLite
    await mock_database.register_user(123, 456, "token")
    is_registered = await mock_database.is_user_registered(123, 456)
    assert is_registered is True
```

### 3. Integration Testing

For integration tests, use the `real_bot` fixture:

```python
async def test_full_workflow(real_bot, mock_interaction):
    # Use real bot instance with mocked Discord context
    await real_bot.setup_hook()
    # Test actual bot behavior
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=botshock --cov-report=html
```

### Run specific test file
```bash
pytest tests/unit/test_bot.py
```

### Run specific test
```bash
pytest tests/unit/test_bot.py::TestBotShockInitialization::test_bot_creation
```

### Run with verbose output
```bash
pytest -v
```

### Run only unit tests
```bash
pytest tests/unit/
```

### Run only integration tests
```bash
pytest tests/integration/
```

## Writing New Tests

### Testing a Command

```python
@pytest.mark.asyncio
async def test_my_command(mock_interaction, mock_database):
    # Setup
    user_id = mock_interaction.user.id
    await mock_database.register_user(user_id, 123, "token")
    
    # Execute command
    cog = MyCog(mock_bot)
    await cog.my_command(mock_interaction)
    
    # Assert
    mock_interaction.response.send_message.assert_called_once()
```

### Testing with API Calls

```python
@pytest.mark.asyncio
async def test_api_call(mock_api_client):
    # Mock API client returns expected data
    result = await mock_api_client.send_action(
        api_token="test",
        shocker_id="123",
        action="vibrate",
        intensity=50,
        duration=2
    )
    
    assert result["success"] is True
```

### Testing Error Handling

```python
@pytest.mark.asyncio
async def test_error_handling(mock_bot, mock_interaction):
    error = ValidationError("Invalid input")
    
    await mock_bot.on_slash_command_error(mock_interaction, error)
    
    # Verify error message was sent
    call_args = mock_interaction.response.send_message.call_args
    assert "Invalid input" in call_args[0][0]
```

## Available Fixtures

### Configuration
- `mock_config` - Bot configuration for tests

### Discord Mocks
- `mock_user` - Mock Discord user
- `mock_member` - Mock guild member
- `mock_guild` - Mock Discord server
- `mock_channel` - Mock text channel
- `mock_interaction` - Mock slash command interaction
- `mock_message` - Mock Discord message

### Bot Components
- `mock_database` - In-memory database
- `mock_api_client` - Mock API client
- `mock_bot` - Mock bot instance
- `real_bot` - Real bot instance (for integration tests)

### Test Data
- `sample_shocker_data` - Example shocker data
- `sample_api_token` - Example API token
- `sample_trigger_data` - Example trigger data
- `sample_reminder_data` - Example reminder data

## Best Practices

1. Use fixtures from `conftest.py` instead of creating mocks manually
2. Focus on testing behavior, not implementation details
3. Mark async tests with `@pytest.mark.asyncio`
4. Use `@pytest.mark.parametrize` for testing multiple inputs
5. Keep tests isolated and independent
6. Use descriptive test names that explain intent
7. Structure tests with clear arrange-act-assert phases

## Continuous Integration

Tests are automatically run on:
- Every commit
- Every pull request
- Before deployment

Ensure all tests pass before submitting changes.
