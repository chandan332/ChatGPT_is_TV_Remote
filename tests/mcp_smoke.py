import asyncio
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    async with stdio_client(StdioServerParameters(command=sys.executable, args=[str(Path(__file__).resolve().parents[1] / 'server.py')])) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert 'hold_volume' in {tool.name for tool in tools.tools}
            assert {'list_remote_controls', 'set_power', 'select_input', 'enter_channel', 'type_text'} <= {tool.name for tool in tools.tools}
            remote = next(tool for tool in tools.tools if tool.name == 'press_key')
            assert 'hdmi_1' in remote.inputSchema['properties']['key']['enum']
            controls = await session.call_tool('list_remote_controls', {})
            assert not controls.isError
            assert 'assistant' in str(controls)
            result = await session.call_tool('list_apps', {})
            assert not result.isError
            assert 'com.google.android.youtube.tv' in str(result)
            invalid = await session.call_tool('press_key', {'key': 'reboot;rm'})
            assert invalid.isError
            invalid_repeat = await session.call_tool('press_key', {'key': 'up', 'repeat': 31})
            assert invalid_repeat.isError
            print('MCP handshake, discovery, app listing and invalid-input rejection passed.')

if __name__ == '__main__':
    asyncio.run(main())
