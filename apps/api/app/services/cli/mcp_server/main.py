# main.py
import asyncio
import json
import argparse
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import logging
from app.services.cli.unified_manager import UnifiedCLIManager
from app.api.deps import get_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI()

# Global variables to store server state
PROJECT_ID = None
PROJECT_PATH = None
SESSION_ID = None
CONVERSATION_ID = None

def get_cli_manager():
    """Get a CLI manager instance with current server state"""
    try:
        db_session = next(get_db())
        return UnifiedCLIManager(
            project_id=PROJECT_ID,
            project_path=PROJECT_PATH,
            session_id=SESSION_ID,
            conversation_id=CONVERSATION_ID,
            db=db_session
        )
    except Exception as e:
        logger.error(f"Failed to create CLI manager: {e}")
        raise

# Root endpoint for health check
@app.get("/")
async def root():
    return {"status": "MCP Server running", "tools_available": True}

# Compatibility endpoints for various MCP client conventions
@app.get("/mcp/tools")
async def list_tools_mcp():
    return await list_tools()

# MCP Protocol endpoints - multiple formats to catch different implementations
@app.get("/tools")
async def list_tools():
    """List available tools - primary endpoint"""
    logger.info("Tools requested via GET /tools")
    
    def get_schema(schema: dict):
        return {"input_schema": schema}

    tools = [
        {
            "name": "run_shell_command",
            "description": "Executes a shell command within a secure, sandboxed environment",
            **get_schema({
                "type": "object",
                "properties": {"command": {"type": "string", "description": "The shell command to execute"}},
                "required": ["command"]
            })
        },
        {
            "name": "write_file",
            "description": "Writes content to a file",
            **get_schema({
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["file_path", "content"]
            })
        },
        {
            "name": "read_file",
            "description": "Reads content from a file",
            **get_schema({
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "Path to the file"}},
                "required": ["file_path"]
            })
        },
        {
            "name": "replace",
            "description": "Replaces text in a file",
            **get_schema({
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "old_string": {"type": "string", "description": "Text to replace"},
                    "new_string": {"type": "string", "description": "Replacement text"},
                    "expected_replacements": {"type": "integer", "description": "Number of replacements expected. Defaults to 1."}
                },
                "required": ["file_path", "old_string", "new_string"]
            })
        },
        {
            "name": "list_directory",
            "description": "Lists directory contents",
            **get_schema({
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory path"}},
                "required": ["path"]
            })
        },
        {
            "name": "glob",
            "description": "Find files matching a pattern",
            **get_schema({
                "type": "object",
                "properties": {"pattern": {"type": "string", "description": "Glob pattern"}},
                "required": ["pattern"]
            })
        },
        {
            "name": "search_file_content",
            "description": "Search for patterns in files",
            **get_schema({
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern"},
                    "path": {"type": "string", "description": "Optional search path"},
                    "include": {"type": "string", "description": "Optional glob pattern to filter files"}
                },
                "required": ["pattern"]
            })
        }
    ]

    server_name = "claudable-tools"
    tools_response = {
        "tools": tools,
        "server_name": server_name
    }
    logger.info(f"Returning {len(tools_response['tools'])} tools for server '{server_name}'")
    return JSONResponse(tools_response)
@app.post("/mcp/tools")
async def list_tools_post_mcp():
    logger.info("Tools requested via POST /mcp/tools")
    return await list_tools()

@app.post("/tools")
async def list_tools_post():
    """List available tools - POST version"""
    logger.info("Tools requested via POST /tools")
    return await list_tools()

# Tool execution endpoints - multiple formats
@app.post("/call_tool")
async def call_tool(request: dict):
    """Execute a tool - MCP standard format"""
    logger.info(f"Tool call received: {request}")
    return await execute_tool_internal(request)

# Additional compatibility endpoints
@app.post("/mcp/callTool")
async def call_tool_mcp(request: dict):
    logger.info(f"Tool call received via /mcp/callTool: {request}")
    return await execute_tool_internal(request)

@app.post("/mcp/tool")
async def call_tool_mcp_alt(request: dict):
    logger.info(f"Tool call received via /mcp/tool: {request}")
    return await execute_tool_internal(request)

@app.post("/execute")  
async def execute_tool_legacy(request: dict):
    """Execute a tool - legacy format"""
    logger.info(f"Tool execution received (legacy): {request}")
    return await execute_tool_internal(request)

@app.post("/tool")
async def execute_tool_alt(request: dict):
    """Execute a tool - alternative format"""
    logger.info(f"Tool execution received (alt): {request}")
    return await execute_tool_internal(request)

import os

async def execute_tool_internal(request: dict):
    """Internal tool execution logic"""
    try:
        tool_name = (request.get("name") or 
                    request.get("tool") or
                    request.get("tool_name") or 
                    request.get("toolName") or
                    (request.get("function") or {}).get("name") or
                    (request.get("tool") or {}).get("name"))
        
        if isinstance(tool_name, str) and "/" in tool_name:
            tool_name = tool_name.split("/")[-1]
        
        arguments = (request.get("arguments") or
                    request.get("args") or
                    request.get("parameters") or
                    request.get("input") or
                    (request.get("function") or {}).get("arguments") or
                    (request.get("tool") or {}).get("arguments") or
                    (request.get("tool") or {}).get("input") or
                    {})
        
        # arguments[arg] = os.path.abspath(os.path.join(repo_path, arguments[arg]))
        # logger.info(f"Resolved relative path '{arg}' to '{arguments[arg]}'")

        logger.info(f"Executing tool: {tool_name} with args: {arguments}")

        if not tool_name:
            return JSONResponse({"isError": True, "content": [{"type": "text", "text": "Missing tool name in request"}]})
        
        cli_manager = get_cli_manager()
        result = await cli_manager.execute_tool_with_retry({
            "name": tool_name,
            "args": arguments
        })
        
        logger.info(f"Tool {tool_name} result: {result.get('success', 'unknown')}")
        
        response = {
            "isError": not result.get("success", False),
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
        }
        return JSONResponse(response)
            
    except Exception as e:
        logger.error(f"Error executing tool: {e}")
        return JSONResponse({"isError": True, "content": [{"type": "text", "text": f"Internal server error: {str(e)}"}]})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--project-id", type=str, required=True)
    parser.add_argument("--project-path", type=str, required=True)
    parser.add_argument("--session-id", type=str, required=True)
    parser.add_argument("--conversation-id", type=str, required=True)
    args = parser.parse_args()

    # Set global state
    PROJECT_ID = args.project_id
    PROJECT_PATH = args.project_path
    SESSION_ID = args.session_id
    CONVERSATION_ID = args.conversation_id
    
    logger.info(f"Starting MCP server on port {args.port}")
    logger.info(f"Project: {PROJECT_ID} at {PROJECT_PATH}")
    
    # Run the FastAPI server
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")