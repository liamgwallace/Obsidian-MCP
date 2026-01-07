# Obsidian MCP Server

A Model Context Protocol (MCP) server for executing bash commands within Obsidian vaults. This server provides secure, controlled access to vault operations through command execution and directory tree listing.

## Features

- Execute bash commands within Obsidian vault directories
- Auto-discovery of vaults from root directory
- List available vaults via MCP tool
- Configurable command whitelist for security
- Command timeout and output size limits
- Optional API token authentication
- Health check endpoint
- Docker deployment with automated GitHub Actions builds
- Comprehensive logging

## Quick Start

### Using Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/liamgwallace/obsidian-mcp.git
cd obsidian-mcp
```

2. Create your `.env` file from the template:
```bash
cp .env.example .env
```

3. Organize your vaults in a directory structure:
```
/home/user/obsidian-vaults/
├── personal-vault/
├── work-vault/
└── notes/
```

4. Edit `.env` to set your vault path:
```env
VAULT_PATH=/home/user/obsidian-vaults
```

The server will automatically discover all subdirectories as individual vaults (`personal-vault`, `work-vault`, `notes`).

5. Start the server:
```bash
docker-compose up -d
```

6. Check health:
```bash
curl http://localhost:8080/health
```

### Using Python Directly

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set `VAULT_ROOT` environment variable to point to your vaults directory:
```bash
export VAULT_ROOT=/home/user/obsidian-vaults
```

3. Run the server:
```bash
python server.py
```

## Configuration

All configuration is done via environment variables in the `.env` file.

### Vault Configuration

The server auto-discovers vaults from a root directory. Each subdirectory becomes a separate vault.

```env
# Path to your vaults directory on the HOST machine
VAULT_PATH=/home/user/obsidian-vaults
```

**Example directory structure:**
```
/home/user/obsidian-vaults/
├── personal/      → vault name: "personal"
├── work/          → vault name: "work"
└── projects/      → vault name: "projects"
```

**Note:** Hidden directories (starting with `.`) are ignored.

**How it works with Docker:**
- `VAULT_PATH` is your host machine path (set in `.env`)
- docker-compose mounts this to `/vaults` inside the container
- The server reads from `/vaults` (via `VAULT_ROOT` env var set in docker-compose)

### Server Configuration

```env
# Port for MCP server
MCP_PORT=8080

# Enable authentication (true/false)
MCP_AUTH_ENABLED=false

# API token (required if auth enabled)
MCP_AUTH_TOKEN=your-secret-token-here
```

### Command Execution

```env
# Command timeout in seconds (default: 30)
COMMAND_TIMEOUT=30

# Maximum output size in characters (default: 100000)
MAX_OUTPUT_SIZE=100000

# Enable command whitelist (default: true)
WHITELIST_ENABLED=true
```

### Logging

Logs are written to stdout and `logs/obsidian-mcp.log` by default. Configure log level if needed:

```env
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
LOG_LEVEL=INFO
```

## MCP Tools

### list_vaults

List all available Obsidian vaults.

**Parameters:** None

**Example:**
```json
{}
```

**Returns:**
- List of vault names

### execute_bash

Execute a bash command in a vault directory.

**Parameters:**
- `vault` (string, required): Name of the vault (e.g., "personal", "work")
- `command` (string, required): Bash command to execute

**Example:**
```json
{
  "vault": "personal",
  "command": "find . -name '*.md' | head -10"
}
```

**Returns:**
- Command output (stdout and stderr)
- Success/failure status
- Truncation indicator if output exceeded max size

### get_vault_tree

Get a directory tree structure of a vault.

**Parameters:**
- `vault` (string, required): Name of the vault
- `include_files` (boolean, optional): Include files (true) or directories only (false). Default: true

**Example:**
```json
{
  "vault": "personal",
  "include_files": true
}
```

**Returns:**
- Tree structure as text
- Filters out hidden files/directories (starting with .)

## Security

### Command Whitelist

By default, only whitelisted commands can be executed. Edit `whitelist.txt` to add/remove commands:

```text
# Whitelisted commands
cat
grep
find
ls
tree
mkdir
...
```

To disable whitelist checking, set `WHITELIST_ENABLED=false` in `.env`.

### Authentication

Enable authentication to require an API token for all MCP requests:

```env
MCP_AUTH_ENABLED=true
MCP_AUTH_TOKEN=your-secret-token
```

Generate a secure token:
```bash
openssl rand -hex 32
```

Include the token in requests:
```bash
curl -H "Authorization: Bearer your-secret-token" http://localhost:8080/messages
```

### Path Restrictions

All commands execute within the vault directory. The server validates that operations cannot escape the vault path.

## Endpoints

The server exposes these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check - returns vault status |
| `/sse` | GET | SSE endpoint for MCP client connection |
| `/messages/` | POST | Message endpoint for MCP communication |

### Health Check

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "healthy",
  "vaults": {
    "personal": {
      "path": "/vaults/personal",
      "accessible": true
    }
  },
  "whitelist_enabled": true,
  "auth_enabled": false
}
```

### n8n MCP Client Configuration

To connect from n8n's MCP Client node:

| Setting | Value |
|---------|-------|
| **Endpoint** | `http://your-server:8080/sse` |
| **Server Transport** | `SSE` |
| **Authentication** | None (or Bearer token if enabled) |

## Docker Image

Docker images are automatically built and pushed to GitHub Container Registry on every push to main/master.

### Pull the latest image:
```bash
docker pull ghcr.io/liamgwallace/obsidian-mcp:latest
```

### Available tags:
- `latest`: Latest build from main branch
- `main`: Latest build from main branch
- `pr-*`: Pull request builds
- `sha-*`: Specific commit builds
- `v*`: Semantic version tags (e.g., v1.0.0)

## Development

### Running locally:
```bash
export VAULT_ROOT=/path/to/your/vaults
python server.py
```

### Running tests:
```bash
# TODO: Add tests
```

### Building Docker image:
```bash
docker build -t obsidian-mcp .
```

## Customizing the Whitelist

The `whitelist.txt` file contains allowed commands. Each line is a command name:

```text
# File operations
cat
grep
find
ls

# Text processing
sed
awk
```

Comments start with `#`. Only the command name is checked - all flags and arguments are allowed.

## Logging

Logs are written to both stdout and `logs/obsidian-mcp.log`. Configure log level in `.env`:

```env
LOG_LEVEL=INFO
```

The logs directory is created automatically if it doesn't exist.

## Troubleshooting

### Server won't start

Check logs for configuration errors:
```bash
docker-compose logs obsidian-mcp
```

Common issues:
- `VAULT_PATH` not set in `.env` file
- Vault path doesn't exist or isn't accessible
- No subdirectories found in vault root (check directory structure)
- Port already in use

### Commands failing

- Check if command is whitelisted in `whitelist.txt`
- Verify vault name is correct (use `list_vaults` tool)
- Check command timeout setting if commands are slow
- Review logs for detailed error messages

### Authentication issues

- Verify `MCP_AUTH_TOKEN` matches in server config and client requests
- Ensure token is sent in `Authorization: Bearer` header format

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
