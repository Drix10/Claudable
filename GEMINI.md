# Plan: A Production-Ready Architecture for Gemini CLI via MCP

## Primary Objective

To implement a secure, resilient, and extensible architecture that enables advanced, multi-step tool-calling capabilities for the Gemini CLI. This will be achieved by creating a local MCP (Model Context Protocol) server that integrates with the existing `UnifiedCLIManager`, keeping the architecture CLI-centric while enabling powerful new features.

---

## Core Architecture

The system will be built on a three-pillar architecture:

1.  **Gemini CLI (as the orchestrator):** The user's `gemini` command-line tool, which will be configured to communicate with our local MCP server.
2.  **Local MCP Server (as the tool provider):** A new, lightweight FastAPI application running as a background process. It will expose our existing toolset (`run_shell_command`, `write_file`) to the Gemini CLI over HTTP, following the MCP specification.
3.  **Secure Tool Executor (`UnifiedCLIManager`):** The existing, hardened service that is responsible for the actual, secure execution of tools. The MCP server will delegate all execution requests to this manager.

---

## Detailed Implementation Plan

### Step 1: Create the MCP Server Application

A new FastAPI application will be created to serve as the MCP bridge.

**File Structure:**
```
apps/api/app/services/cli/mcp_server/
├── __init__.py
├── main.py         # FastAPI app definition
└── tools.py        # Tool discovery and execution logic
```

**`main.py` - FastAPI App:**
*   Will define a simple FastAPI app.
*   It will have two primary endpoints as required by the MCP protocol:
    *   `GET /tools`: Returns a JSON list of available tools, their schemas, and how to invoke them. This will be dynamically generated from our `tools.json` file.
    *   `POST /execute`: Receives a tool execution request from the Gemini CLI, validates it, and passes it to the `UnifiedCLIManager` for secure execution. It will stream the results back.
*   The server will be started as a background process by the `GeminiCLI` execution loop.

**`tools.py` - Tool Logic:**
*   `get_tools_json()`: A function to read `apps/api/app/services/cli/tools.json` and format it into the MCP-compliant JSON structure that `/tools` will return.
*   `execute_tool_streaming()`: An async function that will be called by the `/execute` endpoint. It will:
    1.  Receive the `tool_name` and `args` from the request.
    2.  Instantiate the `UnifiedCLIManager`.
    3.  Call `UnifiedCLIManager.execute_tool_with_retry()`.
    4.  Stream the JSON-formatted result back to the caller, chunk by chunk, as an HTTP response.

### Step 2: Update `GeminiCLI` to Manage the MCP Server

The `GeminiCLI.execute_with_streaming` method will be completely refactored to manage the lifecycle of the MCP server and interact with the `gemini` command correctly.

**Key Logic for `GeminiCLI.execute_with_streaming`:**

1.  **Start MCP Server:**
    *   Before executing the `gemini` command, it will start the MCP FastAPI server as a background process using `uvicorn`.
    *   It will select a random, available port to avoid conflicts.
2.  **Configure Gemini CLI:**
    *   It will dynamically create a temporary `settings.json` file for the Gemini CLI.
    *   This file will contain the configuration to point the CLI to our local MCP server running on the randomly selected port.
    *   Example `temp-settings.json`:
        ```json
        {
          "mcpServers": [
            {
              "name": "claudable-tools",
              "command": ["python", "-m", "app.services.cli.mcp_server.main", "--port", "PORT"],
              "transport": "http",
              "readiness": { "http": "/tools" }
            }
          ]
        }
        ```
3.  **Invoke `gemini` Command:**
    *   It will construct the `gemini` command with the correct arguments:
        *   `-p, --prompt`: The user's instruction.
        *   `--allowed-mcp-server-names`: "claudable-tools"
        *   It will use an environment variable to point to the temporary `settings.json`.
    *   It will **not** use the unsupported `--json` or `--stream` flags. Instead, it will capture the raw stdout from the command.
4.  **Process Output and Yield Messages:**
    *   It will read the stdout from the `gemini` process line by line.
    *   It will parse the output to identify text responses, tool calls, and final results, wrapping them in our standard `Message` format and yielding them to the UI.
5.  **Shutdown MCP Server:**
    *   In a `finally` block, it will ensure the background MCP server process is terminated cleanly, regardless of whether the `gemini` command succeeded or failed.

### Step 3: Harden the Secure Tool Executor (`UnifiedCLIManager`)

The existing security measures in `UnifiedCLIManager` will be leveraged by the MCP server. No major changes are needed here, but we will verify the integration.

*   **Path Sandboxing:** The `_get_safe_path()` helper will continue to ensure all file operations are confined to the project directory.
*   **Command Analysis:** The `_analyze_shell_command()` helper will continue to block dangerous shell commands.
*   **Resource Limiting:** `_write_file` will continue to enforce file size limits.
*   **Structured Errors:** The rich JSON error objects will be passed back through the MCP server to the Gemini CLI, giving the AI actionable feedback to recover from errors.

This updated plan provides a clear and robust path to achieving the desired multi-step tool-calling functionality in a way that is fully compliant with the Gemini CLI's documented architecture.
