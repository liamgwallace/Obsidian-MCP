"""Obsidian MCP Server - SSE over HTTP version."""

import logging
import sys
import uvicorn
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

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
mcp_server = Server("obsidian-mcp")


# Define the tools
@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="list_vaults",
            description="List all available Obsidian vaults.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="execute_bash",
            description="Execute a bash command in an Obsidian vault directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "vault": {
                        "type": "string",
                        "description": "Name of the vault to execute command in"
                    },
                    "command": {
                        "type": "string",
                        "description": "Bash command to execute (will run in vault directory)"
                    }
                },
                "required": ["vault", "command"]
            }
        ),
        Tool(
            name="get_tree",
            description="Get directory tree structure of an Obsidian vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "vault": {
                        "type": "string",
                        "description": "Name of the vault"
                    },
                    "include_files": {
                        "type": "boolean",
                        "description": "Include files in tree (true) or only directories (false)",
                        "default": True
                    }
                },
                "required": ["vault"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")

    if name == "list_vaults":
        vaults = config.vaults
        if not vaults:
            result = "No vaults found"
        else:
            lines = ["Available vaults:", ""]
            for vault_name in sorted(vaults.keys()):
                lines.append(f"  - {vault_name}")
            result = "\n".join(lines)

        return [TextContent(type="text", text=result)]

    elif name == "execute_bash":
        vault = arguments.get("vault")
        command = arguments.get("command")

        if not vault or not command:
            return [TextContent(
                type="text",
                text="Error: Both 'vault' and 'command' parameters are required"
            )]

        result = await execute_bash_command(vault, command)

        if not result["success"]:
            response = f"Command failed: {result['error']}\n"
            if result["output"]:
                response += f"\nOutput:\n{result['output']}"
        else:
            response = result["output"]
            if result["truncated"]:
                response = f"[Output truncated to last {config.max_output_size} chars]\n\n{response}"

        return [TextContent(type="text", text=response)]

    elif name == "get_tree":
        vault = arguments.get("vault")
        include_files = arguments.get("include_files", True)

        if not vault:
            return [TextContent(
                type="text",
                text="Error: 'vault' parameter is required"
            )]

        result = await get_vault_tree(vault, include_files)

        if result["error"]:
            response = f"Error: {result['error']}"
        else:
            response = result["tree"]

        return [TextContent(type="text", text=response)]

    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


# Create SSE transport
sse_transport = SseServerTransport("/messages")


async def handle_health(request: Request):
    """Health check endpoint."""
    vaults = config.list_vaults()
    return JSONResponse({
        "status": "healthy",
        "vaults": vaults,
        "vault_count": len(vaults),
        "whitelist_enabled": config.whitelist_enabled
    })


async def handle_sse(request: Request):
    """Handle SSE connections."""
    async with sse_transport.connect_sse(
        request.scope,
        request.receive,
        request._send
    ) as streams:
        await mcp_server.run(
            streams[0],
            streams[1],
            mcp_server.create_initialization_options()
        )


# Create Starlette app
app = Starlette(
    debug=True,
    routes=[
        Route("/health", endpoint=handle_health, methods=["GET"]),
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
    ]
)


if __name__ == "__main__":
    logger.info("Starting Obsidian MCP Server with SSE transport")
    logger.info(f"Configured vaults: {', '.join(config.list_vaults())}")
    logger.info(f"Whitelist enabled: {config.whitelist_enabled}")
    logger.info(f"Port: {config.mcp_port}")
    logger.info(f"SSE endpoint: http://0.0.0.0:{config.mcp_port}/sse")

    # Run with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.mcp_port,
        log_level="info"
    )
