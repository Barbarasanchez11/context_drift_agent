from __future__ import annotations

import tomllib
from pathlib import Path

from agent import mcp_server

EXPECTED_TOOLS = {"check_drift", "get_drift_status", "list_monitored_datasets"}


class TestModuleImports:
    def test_module_imports(self) -> None:
        # Regression guard: the MCP SDK renamed FastMCP to MCPServer and moved it
        # to mcp.server.mcpserver. The stale import left this module unimportable
        # while every other test still passed.
        assert mcp_server.mcp is not None

    def test_run_is_callable(self) -> None:
        assert callable(mcp_server.run)


class TestRegisteredTools:
    async def test_exposes_the_documented_tools(self) -> None:
        tools = await mcp_server.mcp.list_tools()
        assert {t.name for t in tools} == EXPECTED_TOOLS

    async def test_every_tool_has_a_description(self) -> None:
        tools = await mcp_server.mcp.list_tools()
        assert all(t.description for t in tools)

    async def test_urn_taking_tools_declare_the_urn_argument(self) -> None:
        tools = {t.name: t for t in await mcp_server.mcp.list_tools()}
        for name in ("check_drift", "get_drift_status"):
            assert "urn" in tools[name].input_schema["properties"]


class TestEntryPoint:
    def test_console_script_targets_run(self) -> None:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        scripts = tomllib.loads(pyproject.read_text())["project"]["scripts"]
        assert scripts["context-drift-mcp"] == "agent.mcp_server:run"
