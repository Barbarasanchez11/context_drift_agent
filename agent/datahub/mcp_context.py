"""MCP Consumer: fetches rich context from DataHub's MCP Server.

Spawns mcp-server-datahub as a stdio subprocess and calls:
  - get_lineage(urn, upstream=False) → downstream blast radius
  - get_entities([urn])             → owners, domain, platform

Falls back gracefully if mcp-server-datahub is not installed or DataHub
is unreachable — the pipeline continues with GraphQL-only context.

Requires: mcp>=1.0, mcp-server-datahub>=0.6 (uvx mcp-server-datahub)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.models import DownstreamAsset, RichContext

logger = logging.getLogger(__name__)

_MCP_SERVER_COMMAND = "uvx"
_MCP_SERVER_ARGS = ["mcp-server-datahub"]


async def _call_tool(session: ClientSession, name: str, arguments: dict) -> Any:
    result = await session.call_tool(name, arguments)
    # FastMCP returns content as a list of TextContent blocks
    if result.content and hasattr(result.content[0], "text"):
        import json
        return json.loads(result.content[0].text)
    return {}


async def _fetch_rich_context(urn: str, gms_url: str, token: str) -> RichContext:
    server_params = StdioServerParameters(
        command=_MCP_SERVER_COMMAND,
        args=_MCP_SERVER_ARGS,
        env={"DATAHUB_GMS_URL": gms_url, "DATAHUB_GMS_TOKEN": token},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            downstream_assets: list[DownstreamAsset] = []
            owners: list[str] = []
            domain: str | None = None

            # Downstream lineage — upstream=False means downstream direction
            try:
                lineage = await _call_tool(session, "get_lineage", {
                    "urn": urn,
                    "upstream": False,
                    "max_results": 10,
                    "max_hops": 2,
                })
                for item in (lineage.get("downstreams", {}).get("searchResults") or []):
                    entity = item.get("entity", {})
                    if not entity:
                        continue
                    asset_urn = entity.get("urn", "")
                    name = (
                        (entity.get("properties") or {}).get("name")
                        or (entity.get("editableProperties") or {}).get("name")
                        or asset_urn.split(",")[-2] if "," in asset_urn else asset_urn
                    )
                    entity_type = entity.get("type", "UNKNOWN")
                    platform = (
                        (entity.get("platform") or {}).get("name")
                        or (entity.get("platform") or {}).get("urn", "").split(":")[-1]
                    )
                    downstream_assets.append(DownstreamAsset(
                        urn=asset_urn,
                        name=str(name),
                        entity_type=entity_type,
                        platform=platform or None,
                    ))
            except Exception as exc:
                logger.debug("get_lineage failed for %s: %s", urn, exc)

            # Entity details for ownership and domain
            try:
                entities = await _call_tool(session, "get_entities", {"urns": [urn]})
                entity = entities[0] if isinstance(entities, list) else entities
                ownership = (entity.get("ownership") or {})
                for owner_entry in (ownership.get("owners") or []):
                    owner_urn = (owner_entry.get("owner") or {}).get("urn")
                    if owner_urn:
                        owners.append(owner_urn)
                domain_obj = entity.get("domain") or {}
                domain_props = (domain_obj.get("domain") or {}).get("properties") or {}
                domain = domain_props.get("name")
            except Exception as exc:
                logger.debug("get_entities failed for %s: %s", urn, exc)

            return RichContext(
                dataset_urn=urn,
                downstream_assets=downstream_assets,
                owners=owners,
                domain=domain,
                data_source="mcp",
            )


def get_rich_context(urn: str, gms_url: str, token: str | None) -> RichContext:
    """Synchronous wrapper — safe to call from the polling loop."""
    try:
        result = asyncio.run(_fetch_rich_context(urn, gms_url, token or ""))
        logger.info(
            "MCP context for %s: %d downstream asset(s), %d owner(s)%s",
            urn,
            len(result.downstream_assets),
            len(result.owners),
            f", domain={result.domain}" if result.domain else "",
        )
        return result
    except Exception as exc:
        logger.warning(
            "MCP context unavailable for %s (%s) — continuing with GraphQL context only",
            urn,
            exc,
        )
        return RichContext(dataset_urn=urn, data_source="unavailable")
