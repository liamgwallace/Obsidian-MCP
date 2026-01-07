"""Configuration management for Obsidian MCP Server."""

import os
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
        # Vault root configuration - the container path where vaults are mounted
        # In Docker, host path is mounted to /vaults in the container
        self.vault_root = os.getenv('VAULT_ROOT', '/vaults')

        root_path = Path(self.vault_root)
        if not root_path.exists():
            raise ValueError(f"Vault root does not exist: {self.vault_root}")
        if not root_path.is_dir():
            raise ValueError(f"Vault root is not a directory: {self.vault_root}")

        # Auto-discover vaults from root directory (each subdirectory is a vault)
        self.vaults: Dict[str, str] = {}
        try:
            for item in root_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    vault_name = item.name
                    self.vaults[vault_name] = str(item.resolve())
        except PermissionError:
            raise ValueError(f"Permission denied accessing vault root: {self.vault_root}")

        if not self.vaults:
            raise ValueError(f"No vaults found in {self.vault_root}. Ensure subdirectories exist.")

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
