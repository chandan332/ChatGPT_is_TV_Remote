"""Read-only MCP timing through a fresh local Docker session; no remote buttons."""
import asyncio
import json
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(command='docker', args=[
        'compose', '-f', str(root / 'compose.yaml'), 'run', '--rm', '-T', 'tv-adapter',
    ])
    started = time.perf_counter()
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            startup_ms = round((time.perf_counter() - started) * 1000, 2)
            # Connect once for this disposable session, not before each command.
            connected = await session.call_tool('connect_tv', {})
            if connected.isError:
                raise RuntimeError('TV connection failed; check debugging and TV authorization')
            started = time.perf_counter()
            result = await session.call_tool('measure_tv_latency', {'samples': 3})
            round_trip_ms = round((time.perf_counter() - started) * 1000, 2)
            if result.isError:
                raise RuntimeError('TV probe failed; check debugging and TV authorization')
            stats = await session.call_tool('get_latency_stats', {'limit': 1})
            print(json.dumps({
                'docker_mcp_startup_ms': startup_ms,
                'probe_mcp_round_trip_ms': round_trip_ms,
                'probe': result.structuredContent,
                'server_timing': stats.structuredContent,
                'scope': 'Local Docker/MCP/ADB only; excludes ChatGPT and cloud tunnel delay',
            }, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
