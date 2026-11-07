# ChatGPT_is_TV_Remote

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

## Faster ChatGPT commands

ChatGPT can now use `run_actions` to execute a known sequence in one MCP call. For example, "move down five times and select" becomes:

```json
{
  "actions": [
    {"action": "key", "key": "down", "repeat": 5},
    {"action": "key", "key": "ok"}
  ]
}
```

Steps support `key` (including repeat/long_press), `text`, `open_app`, and `wait` (seconds). Use text only with a known focused text field. Add a short explicit wait when a known screen transition needs time. Unfamiliar screens still require inspection before choosing the next action; this is not a universal app-search macro.

All steps validate before any command runs. Limits are 20 steps, 120 key presses, 10 seconds of explicit waits and a 30-second execution budget. Sequences run in order without other remote requests interleaving. On failure, the result contains `ok: false`, `completed_steps`, and a one-based `failed_step`. A failed/timed-out step may already have affected the TV: inspect the current state before retrying. Commands are never automatically replayed.

The MCP server instructions encourage batching and short acknowledgments, avoiding repeated connection/status/screenshots unless needed. `get_tv_status()` now returns a compact foreground summary; use `detail=true` for the previous detailed dump. Keep the tunnel running: its stdio container and ADB server persist for the connection, rather than restarting for every button. A transport change alone does not eliminate ChatGPT processing time.

## Measuring delay

- `get_latency_stats(limit=5)` returns recent tool duration, queue time, ADB call count and ADB duration without contacting the TV.
- `measure_tv_latency(samples=3)` measures harmless ADB echo round trips without pressing buttons.
- `python tests/benchmark_latency.py` measures a fresh Docker/MCP startup, then a probe's local MCP round-trip time and server/ADB timings. Build the image first. This opens a disposable session and connects once using the existing ADB identity.

The last 100 tool timing records are kept in memory and reset when the server restarts. Timing records also go to stderr as JSON (`event: tv_tool_timing`), never MCP stdout; they contain no command arguments or typed text. Set `TV_TIMING_LOG=0` in the server environment to disable those log records. The reported receive timestamp is when the server's tool wrapper starts, after MCP parsing/validation. These measurements exclude ChatGPT processing and cloud/tunnel transit; they do not measure the full time from speaking a command to the TV visibly reacting.

Development checks (create a disposable Python environment first): install `requirements.txt` and `pytest`, then run `python -m pytest tests` and `python tests/mcp_smoke.py`. Local Python environments and caches are generated and are not part of the project.
