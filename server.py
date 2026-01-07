"""Obsidian MCP Server - Simple version using FastMCP."""

import logging
import sys
from pathlib import Path
from fastmcp import FastMCP
from config import init_config, get_config
from tools import init_whitelist, execute_bash_command, get_vault_tree

# Initialize config first
init_config()
config = get_config()

# Setup logging
logging.basicConfig(
    level=config.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.log_path),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize whitelist
init_whitelist()

# Create the MCP server
mcp = FastMCP("obsidian-mcp")


@mcp.tool()
def list_vaults() -> str:
    """List all available Obsidian vaults that can be accessed through this MCP server.

    Use this first to discover which vaults are available before using get_tree or execute_bash.
    Vaults are configured in the MCP server setup (via VAULT_PATHS environment variable or config)
    and correspond to different Obsidian vault directories on the system.

    This is the starting point for vault operations - run this to see what vaults you can work with,
    then use get_tree to explore a vault's structure, and execute_bash to run commands within it.

    Returns:
        List of vault names as strings, formatted as a bulleted list.
        If no vaults are configured, returns "No vaults found".

    Example output:
        Available vaults:

          - AI-Inbox
          - Liam-vault
          - Main-vault
          - Work-vault
    """
    vaults = config.vaults
    if not vaults:
        return "No vaults found"

    lines = ["Available vaults:", ""]
    for vault_name in sorted(vaults.keys()):
        lines.append(f"  - {vault_name}")
    return "\n".join(lines)


@mcp.tool()
async def execute_bash(vault: str, command: str) -> str:
    """Execute bash commands in an Obsidian vault directory.

    Use this for:
    - Searching file contents (grep, find, rg)
    - Counting/analyzing files (wc, ls, du)
    - Reading file contents (cat, head, tail, less)
    - Text processing (sed, awk, sort, uniq)
    - Creating/modifying files (mkdir, touch, cp, mv, rm)
    - Chaining commands with pipes (|) and operators (&& || ;)
    - Working with archives (tar, zip, unzip, gzip)
    - Processing JSON/YAML/CSV (jq, yq, csvkit)
    - Markdown operations (pandoc, glow)

    Commands run with whitelist enabled by default for safety. 161+ allowed commands include
    file operations, text processing, searching, and data manipulation tools.
    Commands are checked against whitelist.txt - if a command fails, the error message
    will show which command was blocked and list all allowed commands.
    To disable whitelist, set WHITELIST_ENABLED=false in environment.

    The command executes in the vault's root directory (/vaults/{vault_name}).

    Args:
        vault: Name of the vault (use list_vaults to see available vaults)
        command: Bash command string to execute

    Returns:
        Command output (stdout/stderr), or error message if command fails or is not whitelisted.

    Examples:
        - Find markdown files: "find . -name '*.md' | head -10"
        - Search content: "grep -r 'keyword' . --include='*.md'"
        - Count files: "find . -type f | wc -l"
        - Chain commands: "cat file.txt && wc -l file.txt"
        - Process with awk: "ls -la | awk '{print $9}'"
    """
    logger.info(f"execute_bash called: vault={vault}, command={command}")

    result = await execute_bash_command(vault, command)

    if not result["success"]:
        response = f"Command failed: {result['error']}\n"
        if result["output"]:
            response += f"\nOutput:\n{result['output']}"
        return response

    response = result["output"]
    if result["truncated"]:
        response = f"[Output truncated to last {config.max_output_size} chars]\n\n{response}"
    return response


@mcp.tool()
async def get_tree(vault: str, include_files: bool = True) -> str:
    """Get a hierarchical directory tree of an Obsidian vault.

    Use this to:
    - Explore vault structure before running bash commands
    - Understand folder organization and hierarchy
    - Find where specific files or folders are located
    - See all files and their paths at a glance
    - Get an overview of vault contents quickly

    This is often the best first step when working with a vault - it shows you
    the complete structure so you can make informed decisions about which commands to run.

    Set include_files=false to see only folder structure (faster for large vaults).
    Set include_files=true to see complete file listing with all markdown and attachment files.

    Hidden files and directories (starting with .) are automatically excluded.

    Args:
        vault: Name of the vault to inspect (use list_vaults to see available vaults)
        include_files: If true, shows all files. If false, shows only directories. Defaults to true.

    Returns:
        Tree structure showing nested folders and files (if enabled) with proper indentation.

    Example output:
        vault/
        ├──Projects/
        │   ├──Work/
        │   │   ├──meeting-notes.md
        │   │   └──tasks.md
        │   └──Personal/
        │       └──ideas.md
        └──Archive/
            └──old-notes.md
    """
    logger.info(f"get_tree called: vault={vault}, include_files={include_files}")

    result = await get_vault_tree(vault, include_files)

    if result["error"]:
        return f"Error: {result['error']}"
    return result["tree"]


if __name__ == "__main__":
    logger.info("Starting Obsidian MCP Server")
    logger.info(f"Configured vaults: {', '.join(config.list_vaults())}")
    logger.info(f"Whitelist enabled: {config.whitelist_enabled}")
    logger.info(f"Port: {config.mcp_port}")

    # Run with streamable HTTP transport
    mcp.run(transport="streamable-http", host="0.0.0.0", port=config.mcp_port)
