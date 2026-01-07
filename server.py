"""Obsidian MCP Server - Execute bash commands in Obsidian vaults."""

import json
import logging
import sys
from pathlib import Path
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
import uvicorn
from config import init_config, get_config
from tools import init_whitelist, execute_bash_command, get_vault_tree

# Initialize logging
def setup_logging():
    """Configure logging based on config settings."""
    config = get_config()

    # Create logs directory if it doesn't exist
    log_path = Path(config.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=config.log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.log_path),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp_server = Server("obsidian-mcp")

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    config = get_config()
    vault_list = ", ".join(config.list_vaults())

    return [
        Tool(
            name="list_vaults",
            description="List all available Obsidian vaults",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="execute_bash",
            description=f"Execute a bash command in an Obsidian vault directory. Available vaults: {vault_list}",
            inputSchema={
                "type": "object",
                "properties": {
                    "vault": {
                        "type": "string",
                        "description": f"Name of the vault to execute command in. Options: {vault_list}"
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
            name="get_vault_tree",
            description=f"Get directory tree structure of an Obsidian vault. Available vaults: {vault_list}",
            inputSchema={
                "type": "object",
                "properties": {
                    "vault": {
                        "type": "string",
                        "description": f"Name of the vault. Options: {vault_list}"
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
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool execution requests."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")

    try:
        if name == "list_vaults":
            config = get_config()
            vaults = config.vaults

            if not vaults:
                return [TextContent(type="text", text="No vaults found")]

            lines = ["Available vaults:", ""]
            for vault_name in sorted(vaults.keys()):
                lines.append(f"  - {vault_name}")

            return [TextContent(type="text", text="\n".join(lines))]

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
                    response = f"[Output was truncated to last {get_config().max_output_size} characters]\n\n{response}"

            return [TextContent(type="text", text=response)]

        elif name == "get_vault_tree":
            vault = arguments.get("vault")
            include_files = arguments.get("include_files", True)

            if not vault:
                return [TextContent(
                    type="text",
                    text="Error: 'vault' parameter is required"
                )]

            result = await get_vault_tree(vault, include_files)

            if result["error"]:
                return [TextContent(type="text", text=f"Error: {result['error']}")]

            return [TextContent(type="text", text=result["tree"])]

        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error executing tool: {str(e)}"
        )]


async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint."""
    config = get_config()

    # Check vault paths are accessible
    vault_status = {}
    all_healthy = True

    for name, path in config.vaults.items():
        vault_path = Path(path)
        accessible = vault_path.exists() and vault_path.is_dir()
        vault_status[name] = {
            "path": path,
            "accessible": accessible
        }
        if not accessible:
            all_healthy = False

    status_code = 200 if all_healthy else 503

    return JSONResponse({
        "status": "healthy" if all_healthy else "unhealthy",
        "vaults": vault_status,
        "whitelist_enabled": config.whitelist_enabled,
        "auth_enabled": config.mcp_auth_enabled
    }, status_code=status_code)


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for MCP endpoints."""

    async def dispatch(self, request: Request, call_next):
        config = get_config()

        # Skip auth for health check
        if request.url.path == "/health":
            return await call_next(request)

        # Check if auth is enabled
        if not config.mcp_auth_enabled:
            return await call_next(request)

        # Validate authorization header
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == config.mcp_auth_token:
                return await call_next(request)

        logger.warning(f"Unauthorized access attempt from {request.client.host}")
        return JSONResponse(
            {"error": "Unauthorized"},
            status_code=401
        )


def create_app() -> Starlette:
    """Create and configure the Starlette application."""
    config = get_config()

    # Create SSE transport
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> Response:
        """Handle SSE connections."""
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send
        ) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options()
            )
        return Response()

    # Create Starlette app with routes
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        middleware=[
            Middleware(AuthMiddleware)
        ]
    )

    return app


def main():
    """Main entry point."""
    try:
        # Initialize configuration
        init_config()
        config = get_config()

        # Setup logging
        setup_logging()

        # Initialize whitelist
        init_whitelist()

        logger.info("Starting Obsidian MCP Server")
        logger.info(f"Configured vaults: {', '.join(config.list_vaults())}")
        logger.info(f"Whitelist enabled: {config.whitelist_enabled}")
        logger.info(f"Auth enabled: {config.mcp_auth_enabled}")
        logger.info(f"Port: {config.mcp_port}")

        # Create and run the app
        app = create_app()

        logger.info(f"Server running on http://0.0.0.0:{config.mcp_port}")
        logger.info("Health check available at /health")
        logger.info("SSE endpoint available at /sse")
        logger.info("Messages endpoint available at /messages/")

        uvicorn.run(app, host="0.0.0.0", port=config.mcp_port, log_level="info")

    except Exception as e:
        print(f"Failed to start server: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
