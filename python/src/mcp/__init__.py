"""MCP server for the trading core (Phase 9 foundation).

Exposes read-only and proposal tools. Failures are logged with a request_id
to stderr and data/reports/mcp.log. All trade proposals go through RiskEngine.
No direct unrestricted order submission tools are registered.
"""
