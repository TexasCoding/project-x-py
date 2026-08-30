# Authentication

## API Credentials

To use the ProjectX Python SDK, you need:

1. **API Key** - Your TopStepX API key
2. **Username** - Your TopStepX username
3. **Account Name** (optional) - For specific account selection

## Setting Up Credentials

### Environment Variables (Recommended)

Set environment variables in your shell:

```bash
export PROJECT_X_API_KEY="your-api-key-here"  # pragma: allowlist secret
export PROJECT_X_USERNAME="your-username"
export PROJECT_X_ACCOUNT_NAME="optional-account-name"
```

Or create a `.env` file in your project root:

```bash
# .env file
PROJECT_X_API_KEY=your-api-key-here
PROJECT_X_USERNAME=your-username
PROJECT_X_ACCOUNT_NAME=optional-account-name
```

### Configuration File

Create a JSON configuration file at `~/.config/projectx/config.json`:

```json
{
  "api_key": "your-api-key-here",  # pragma: allowlist secret
  "username": "your-username",
  "account_name": "optional-account-name"
}
```

### Programmatic Authentication

```python
from project_x_py import ProjectX

# Using environment variables (recommended)
async with ProjectX.from_env() as client:
    await client.authenticate()
    print(f"Connected: {client.account_info.name}")

# Direct credentials (not recommended for production)
async with ProjectX(
    api_key="your-api-key"  # pragma: allowlist secret,
    username="your-username"
) as client:
    await client.authenticate()
```

## TradingSuite Authentication

The TradingSuite handles authentication automatically:

```python
from project_x_py import TradingSuite

# Automatically uses environment variables
suite = await TradingSuite.create(["MNQ"])

# Or pass credentials directly
suite = await TradingSuite.create(
    ["MNQ"],
    username="your-username",
    api_key="your-api-key",  # pragma: allowlist secret
)
```

## JWT Token Management

The SDK automatically manages JWT tokens:

- Tokens are refreshed automatically before expiration
- Preemptive refresh at 80% of token lifetime
- Secure token storage in memory
- Automatic retry on authentication failures

```python
# Get current JWT token (if needed for custom integrations)
async with ProjectX.from_env() as client:
    await client.authenticate()
    jwt_token = client.get_session_token()
    print(f"JWT Token: {jwt_token[:20]}...")
```

## Security Best Practices

1. **Never hardcode credentials** in your source code
2. **Use environment variables** or secure configuration files
3. **Add `.env` to `.gitignore`** to prevent accidental commits
4. **Rotate API keys regularly**
5. **Use read-only keys** when possible for analysis-only applications
6. **Implement proper error handling** for authentication failures

## Troubleshooting

### Common Authentication Errors

```python
from project_x_py.exceptions import ProjectXAuthenticationError

try:
    async with ProjectX.from_env() as client:
        await client.authenticate()
except ProjectXAuthenticationError as e:
    print(f"Authentication failed: {e}")
```

### Debugging Authentication

Enable debug logging to troubleshoot authentication issues:

```python
import logging

logging.basicConfig(level=logging.DEBUG)

async with ProjectX.from_env() as client:
    await client.authenticate()
```

## Next Steps

- [Configuration](configuration.md) - Advanced configuration options
- [Quick Start](quickstart.md) - Start using the SDK
- [Trading Suite](../guide/trading-suite.md) - Complete trading setup
