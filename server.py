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
    """List all available Obsidian vaults."""
    vaults = config.vaults
    if not vaults:
        return "No vaults found"

    lines = ["Available vaults:", ""]
    for vault_name in sorted(vaults.keys()):
        lines.append(f"  - {vault_name}")
    return "\n".join(lines)


@mcp.tool()
async def execute_bash(vault: str, command: str) -> str:
    """Execute a bash command in an Obsidian vault directory.

    Args:
        vault: Name of the vault to execute command in
        command: Bash command to execute (will run in vault directory)
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
    """Get directory tree structure of an Obsidian vault.

    Args:
        vault: Name of the vault
        include_files: Include files in tree (true) or only directories (false)
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

    # Run with SSE transport on configured port
    mcp.run(transport="sse", host="0.0.0.0", port=config.mcp_port)
