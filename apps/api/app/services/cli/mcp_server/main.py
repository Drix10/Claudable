import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from .tools import get_tools_json, execute_tool_streaming
import argparse

app = FastAPI()

@app.get("/tools")
async def get_tools():
    return await get_tools_json()

@app.post("/execute")
async def execute_tool(request: dict):
    return StreamingResponse(execute_tool_streaming(request), media_type="application/json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)