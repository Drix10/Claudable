import json
import os
from app.services.cli.unified_manager import UnifiedCLIManager
from app.api.deps import get_db
from typing import AsyncGenerator

async def get_tools_json():
    # This should read the tools.json file and format it for the MCP server
    tools_path = os.path.join(os.path.dirname(__file__), "..", "tools.json")
    with open(tools_path) as f:
        return json.load(f)

async def execute_tool_streaming(request: dict) -> AsyncGenerator[str, None]:
    """
    Executes the tool and yields the JSON-formatted result as a single chunk.
    This fulfills the streaming requirement of the MCP protocol.
    """
    tool_name = request.get("toolName") # Gemini CLI sends toolName
    if not tool_name:
        tool_name = request.get("tool_name") # Fallback for direct calls

    tool_args = request.get("args", {})

    # In a real-world scenario, project_id and other context would be retrieved
    # based on the request, perhaps via a token or session lookup.
    # For now, we assume the CWD is the project path, set by the parent process.
    db_session = next(get_db())
    cli_manager = UnifiedCLIManager(
        project_id="gemini_mcp_project",
        project_path=os.getcwd(), 
        session_id="gemini_mcp_session",
        conversation_id="gemini_mcp_conversation",
        db=db_session
    )

    result = await cli_manager.execute_tool_with_retry({
        "name": tool_name,
        "args": tool_args
    })
    
    yield json.dumps(result)

