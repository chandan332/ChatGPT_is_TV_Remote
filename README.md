# Make Your Laptop TV Remote

Docker MCP service with 78 remote buttons, app shortcuts, text entry, TV status and screenshots. ChatGPT connects through an MCP client/tunnel; no OpenAI API key is required by this service. The model runs in the cloud.

Build: `docker compose build`

Run with an MCP client over stdio: `docker compose run --rm -T tv-adapter`

Configure the MCP client command as `docker` with arguments `compose -f D:/android_app/TV_adapter/compose.yaml run --rm -T tv-adapter`. Keep the directory available. For ChatGPT, connect a supported private MCP tunnel to this stdio command; creating the server does not automatically add it to ChatGPT.

Enable TV USB/network debugging, keep TV on Wi-Fi, then call connect_tv and accept the authorization prompt on the TV. This creates a separate persistent Docker ADB identity. Call open_app with youtube, netflix, prime_video or jiohotstar. Live control requires debugging enabled and this Docker ADB key authorized on the TV.

The default endpoint is 192.168.68.51:5555. Override TV_ENDPOINT if the address changes. No container ports are published. Do not expose TV ADB to the internet. The adapter supports fixed apps and keys, validates resolved activities and has command timeouts. It does not provide arbitrary shell execution. No Docker socket or privileged mode is required.

HTTP mode for a trusted local tunnel: set MCP_TRANSPORT=streamable-http; the server listens on container port 8000 at /mcp. Add authentication before exposing HTTP beyond a trusted local environment. Default stdio is recommended.

Protected video/HDMI can prevent screenshots. Power-on from full shutdown and app-specific video search are not implemented.

## Remote controls

Call `list_remote_controls()` for the full button list. `press_key(key, long_press=False, repeat=1)` supports Android long presses and 1–30 repeated presses. Existing tool calls remain compatible.

| Controls | Buttons / tools |
| --- | --- |
| Navigation | Home, Back, directional arrows, OK, Menu, Settings, app launcher, recent apps, Help |
| Sound | Volume up/down, mute, `hold_volume`, audio-track button |
| Power | `set_power('on')` to wake, `set_power('off')` to sleep; `power` toggles standby |
| Playback | Play/pause, separate play and pause, stop, rewind, fast-forward, next/previous, skip forward/backward, record |
| Live TV | TV, digits 0–9, channel up/down, last channel, guide, info, `enter_channel('07-2')` |
| Inputs | `select_input('input')` for picker; HDMI 1–4, composite 1–2, component 1–2, VGA, antenna, TV |
| Extra TV controls | Captions, teletext, red/green/yellow/blue buttons, picture-in-picture, zoom in/out |
| Search and typing | Search, assistant button, `type_text('movie title')`, Enter, delete/backspace, forward delete, Escape, Tab, Space, page up/down |
| App shortcuts | YouTube, Netflix, Prime Video, JioHotstar through `open_app` |

Examples:

```python
press_key('ok', long_press=True)
press_key('down', repeat=5)
select_input('hdmi_1')
enter_channel('12', confirm=True)
type_text('nature documentaries')  # Focus the desired text field first.
press_key('enter')
```

Button delivery is not confirmation that the TV performed the action. The TV firmware and foreground app decide which buttons work. Inputs, tuner channels, recording, captions and picture-in-picture require corresponding hardware/app support. These commands cannot universally control an external set-top box or replace infrared-only remote features.

Wake works only if the TV keeps ADB/network access available in standby. The assistant button opens the TV assistant; it does not forward your laptop microphone. Text entry accepts 1–500 printable ASCII characters, excluding literal `%s`; Unicode input is not supported by this ADB method. Long press uses Android's `--longpress` event, rather than an arbitrary-duration physical hold.

Button definitions follow the [Android KeyEvent reference](https://developer.android.com/reference/android/view/KeyEvent).

After updating, restart `./start-tunnel.ps1` (which rebuilds the image), then refresh/reconnect the ChatGPT tool connection to discover the new tools and expanded button schema.

Rapid volume: call hold_volume(direction='up' or 'down', seconds=2). Duration accepts 0.2–10 seconds and automatically stops. Repeated Android key events simulate holding the remote. Refresh the ChatGPT tool connection after restarting the tunnel to discover the new tool.

Start the configured tunnel: `./start-tunnel.ps1` in PowerShell. It prompts securely for the runtime API key if absent. Keep the window running.

Development checks (create a disposable Python environment first): install `requirements.txt` and `pytest`, then run `python -m pytest tests` and `python tests/mcp_smoke.py`. Local Python environments and caches are generated and are not part of the project.
