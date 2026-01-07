"""Configuration management for Obsidian MCP Server."""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for MCP server settings."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        # Vault roots configuration - auto-discover vaults from root directories
        vault_roots_str = os.getenv('VAULT_ROOTS', '["/home/liam/docker/obsidian/vaults"]')
        try:
            vault_roots = json.loads(vault_roots_str)
            if isinstance(vault_roots, str):
                vault_roots = [vault_roots]
            elif not isinstance(vault_roots, list):
                raise ValueError("VAULT_ROOTS must be a JSON array of paths or a single path string")
        except json.JSONDecodeError:
            raise ValueError("VAULT_ROOTS must be a valid JSON array of paths")

        # Auto-discover vaults from root directories
        self.vaults: Dict[str, str] = {}
        for root in vault_roots:
            root_path = Path(root)
            if not root_path.exists():
                logging.warning(f"Vault root does not exist: {root}")
                continue
            if not root_path.is_dir():
                logging.warning(f"Vault root is not a directory: {root}")
                continue

            # Scan for subdirectories (each is a vault)
            try:
                for item in root_path.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        vault_name = item.name
                        # Handle duplicate names by appending parent dir
                        if vault_name in self.vaults:
                            vault_name = f"{root_path.name}-{vault_name}"
                        self.vaults[vault_name] = str(item.resolve())
            except PermissionError:
                logging.warning(f"Permission denied accessing vault root: {root}")

        if not self.vaults:
            raise ValueError("No vaults found. Check VAULT_ROOTS configuration and ensure directories exist.")

        # MCP Server settings
        self.mcp_port = int(os.getenv('MCP_PORT', '8080'))
        self.mcp_auth_enabled = os.getenv('MCP_AUTH_ENABLED', 'false').lower() == 'true'
        self.mcp_auth_token = os.getenv('MCP_AUTH_TOKEN', '')

        if self.mcp_auth_enabled and not self.mcp_auth_token:
            raise ValueError("MCP_AUTH_TOKEN must be set when MCP_AUTH_ENABLED is true")

        # Command execution settings
        self.command_timeout = int(os.getenv('COMMAND_TIMEOUT', '30'))
        self.max_output_size = int(os.getenv('MAX_OUTPUT_SIZE', '100000'))

        # Whitelist settings
        self.whitelist_enabled = os.getenv('WHITELIST_ENABLED', 'true').lower() == 'true'
        self.whitelist_path = os.getenv('WHITELIST_PATH', 'whitelist.txt')

        # Logging settings
        log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.log_level = getattr(logging, log_level_str, logging.INFO)
        self.log_path = os.getenv('LOG_PATH', 'logs/obsidian-mcp.log')

    def get_vault_path(self, vault_name: str) -> Optional[str]:
        """Get the path for a specific vault."""
        return self.vaults.get(vault_name)

    def list_vaults(self) -> list:
        """Get list of available vault names."""
        return list(self.vaults.keys())

    def validate_path_in_vault(self, vault_name: str, target_path: str) -> bool:
        """Validate that a target path is within the vault directory."""
        vault_path = self.get_vault_path(vault_name)
        if not vault_path:
            return False

        vault_abs = Path(vault_path).resolve()
        target_abs = Path(target_path).resolve()

        try:
            target_abs.relative_to(vault_abs)
            return True
        except ValueError:
            return False

# Global config instance
config: Optional[Config] = None

def init_config():
    """Initialize the global configuration."""
    global config
    config = Config()
    return config

def get_config() -> Config:
    """Get the global configuration instance."""
    if config is None:
        raise RuntimeError("Configuration not initialized. Call init_config() first.")
    return config
