# Make Your Laptop TV Remote

Docker MCP service for opening apps, remote keys, TV status and screenshots. ChatGPT connects through an MCP client/tunnel; no OpenAI API key is required by this service. The model runs in the cloud.

Build: `docker compose build`

Run with an MCP client over stdio: `docker compose run --rm -T tv-adapter`

Configure the MCP client command as `docker` with arguments `compose -f D:/android_app/TV_adapter/compose.yaml run --rm -T tv-adapter`. Keep the directory available. For ChatGPT, connect a supported private MCP tunnel to this stdio command; creating the server does not automatically add it to ChatGPT.

Enable TV USB/network debugging, keep TV on Wi-Fi, then call connect_tv and accept the authorization prompt on the TV. This creates a separate persistent Docker ADB identity. Call open_app with youtube, netflix, prime_video or jiohotstar. Live control requires debugging enabled and this Docker ADB key authorized on the TV.

The default endpoint is 192.168.68.51:5555. Override TV_ENDPOINT if the address changes. No container ports are published. Do not expose TV ADB to the internet. The adapter supports fixed apps and keys, validates resolved activities and has command timeouts. It does not provide arbitrary shell execution. No Docker socket or privileged mode is required.

HTTP mode for a trusted local tunnel: set MCP_TRANSPORT=streamable-http; the server listens on container port 8000 at /mcp. Add authentication before exposing HTTP beyond a trusted local environment. Default stdio is recommended.

Protected video/HDMI can prevent screenshots. Power-on from full shutdown and app-specific video search are not implemented.

Rapid volume: call hold_volume(direction='up' or 'down', seconds=2). Duration accepts 0.2–10 seconds and automatically stops. Repeated Android key events simulate holding the remote. Refresh the ChatGPT tool connection after restarting the tunnel to discover the new tool.

Start the configured tunnel: `./start-tunnel.ps1` in PowerShell. It prompts securely for the runtime API key if absent. Keep the window running.

Development checks (create a disposable Python environment first): install `requirements.txt` and `pytest`, then run `python -m pytest tests` and `python tests/mcp_smoke.py`. Local Python environments and caches are generated and are not part of the project.
