"""MCP tools for Obsidian vault operations."""

import asyncio
import logging
import subprocess
import shlex
from pathlib import Path
from typing import Optional, Set
from config import get_config

logger = logging.getLogger(__name__)

class WhitelistManager:
    """Manages command whitelist."""

    def __init__(self, whitelist_path: str):
        """Initialize whitelist manager."""
        self.whitelist_path = whitelist_path
        self.commands: Set[str] = set()
        self.load_whitelist()

    def load_whitelist(self):
        """Load whitelist from file."""
        try:
            with open(self.whitelist_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.commands.add(line)
            logger.info(f"Loaded {len(self.commands)} whitelisted commands")
        except FileNotFoundError:
            logger.warning(f"Whitelist file not found: {self.whitelist_path}")
            self.commands = set()

    def is_allowed(self, command: str) -> bool:
        """Check if a command is whitelisted."""
        # Extract the base command (first word)
        base_command = shlex.split(command)[0] if command else ""
        # Get just the command name without path
        base_command = Path(base_command).name
        return base_command in self.commands

# Global whitelist manager
whitelist_manager: Optional[WhitelistManager] = None

def init_whitelist():
    """Initialize the whitelist manager."""
    global whitelist_manager
    config = get_config()
    whitelist_manager = WhitelistManager(config.whitelist_path)
    return whitelist_manager

async def execute_bash_command(vault_name: str, command: str) -> dict:
    """
    Execute a bash command in the specified vault directory.

    Args:
        vault_name: Name of the vault to execute command in
        command: Bash command to execute

    Returns:
        dict with 'output', 'error', 'success', and 'truncated' fields
    """
    config = get_config()

    # Validate vault exists
    vault_path = config.get_vault_path(vault_name)
    if not vault_path:
        return {
            "output": "",
            "error": f"Unknown vault: {vault_name}. Available vaults: {', '.join(config.list_vaults())}",
            "success": False,
            "truncated": False
        }

    # Check whitelist if enabled
    if config.whitelist_enabled:
        if not whitelist_manager.is_allowed(command):
            return {
                "output": "",
                "error": f"Command not whitelisted. Enable WHITELIST_ENABLED=false to disable whitelist.",
                "success": False,
                "truncated": False
            }

    logger.info(f"Executing command in vault '{vault_name}': {command}")

    try:
        # Execute command with timeout
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=vault_path
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=config.command_timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "output": "",
                "error": f"Command timed out after {config.command_timeout} seconds",
                "success": False,
                "truncated": False
            }

        # Decode output
        stdout_str = stdout.decode('utf-8', errors='replace')
        stderr_str = stderr.decode('utf-8', errors='replace')

        # Combine stdout and stderr
        combined_output = stdout_str
        if stderr_str:
            combined_output += f"\n--- stderr ---\n{stderr_str}"

        # Check if output needs truncation
        truncated = False
        if len(combined_output) > config.max_output_size:
            truncated = True
            # Truncate from beginning, keep the end
            combined_output = "... [output truncated] ...\n" + combined_output[-config.max_output_size:]

        success = process.returncode == 0

        return {
            "output": combined_output,
            "error": "" if success else f"Command exited with code {process.returncode}",
            "success": success,
            "truncated": truncated
        }

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return {
            "output": "",
            "error": f"Execution error: {str(e)}",
            "success": False,
            "truncated": False
        }

async def get_vault_tree(vault_name: str, include_files: bool = True) -> dict:
    """
    Get a tree structure of the vault.

    Args:
        vault_name: Name of the vault
        include_files: Whether to include files or just directories

    Returns:
        dict with 'tree' and 'error' fields
    """
    config = get_config()

    # Validate vault exists
    vault_path = config.get_vault_path(vault_name)
    if not vault_path:
        return {
            "tree": "",
            "error": f"Unknown vault: {vault_name}. Available vaults: {', '.join(config.list_vaults())}"
        }

    logger.info(f"Generating tree for vault '{vault_name}' (include_files={include_files})")

    try:
        vault_root = Path(vault_path)
        tree_lines = []

        def build_tree(path: Path, prefix: str = "", is_last: bool = True):
            """Recursively build tree structure."""
            # Skip hidden files/directories
            if path.name.startswith('.'):
                return

            # Add current item
            connector = "└──" if is_last else "├──"
            if path.is_dir():
                tree_lines.append(f"{prefix}{connector}{path.name}/")
            elif include_files:
                tree_lines.append(f"{prefix}{connector}{path.name}")

            # Process directory contents
            if path.is_dir():
                try:
                    items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
                    # Filter out hidden items
                    items = [item for item in items if not item.name.startswith('.')]

                    for i, item in enumerate(items):
                        is_last_item = i == len(items) - 1
                        extension = "    " if is_last else "│   "
                        build_tree(item, prefix + extension, is_last_item)
                except PermissionError:
                    pass

        # Start with vault name
        tree_lines.append(f"{vault_root.name}/")

        # Build tree
        try:
            items = sorted(vault_root.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            items = [item for item in items if not item.name.startswith('.')]

            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                build_tree(item, "", is_last)
        except PermissionError:
            return {
                "tree": "",
                "error": f"Permission denied accessing vault: {vault_path}"
            }

        return {
            "tree": "\n".join(tree_lines),
            "error": ""
        }

    except Exception as e:
        logger.error(f"Error generating tree: {e}")
        return {
            "tree": "",
            "error": f"Error generating tree: {str(e)}"
        }
