# zapret-web-panel

[Русская версия](README.md)

A local web control panel for [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube) (Flowseal's Windows distribution of [bol-van/zapret](https://github.com/bol-van/zapret)).

**Unofficial, independent companion tool — not affiliated with or endorsed by the zapret-discord-youtube project.**

It replaces `service.bat`'s console menu and the bundled `test zapret.ps1` with a single dashboard running as its own app window (available in English and Russian — language switcher in the UI):

- **Test** — run every (or a chosen subset of) bypass strategy against a configurable set of services, see which strategy actually gets through, and enable the winner with one click.
- **Manual launch** — start/stop any strategy directly, no test needed.
- **Service** — install/remove the autostart `zapret` Windows service, toggle game filter / ipset / auto-update settings, update the ipset list and hosts file, check for new zapret-discord-youtube releases — all without opening `service.bat`'s console.
- **Diagnostics** — the same conflict/health checks as `service.bat`'s "Run Diagnostics", plus one-click fixes: stop selected VPN services, remove conflicting bypass services, clear an orphaned WinDivert driver registration, clear Discord's cache.

## Why

`zapret-discord-youtube` ships great bypass strategies but manages them through batch-file console menus. This panel is a friendlier front end over the same mechanics — it shells out to the same `winws.exe`, reads/writes the same config files, and (for service installs) captures the exact resolved command line the official `.bat` files would produce, instead of re-parsing batch syntax.

## Requirements

- Windows 10/11 (needs the WebView2 Runtime — already bundled with Windows 10/11 alongside Edge)
- The prebuilt `.exe` needs nothing extra — otherwise Python 3.9+, `curl.exe` and PowerShell (all three ship with modern Windows) plus `pip install -r requirements.txt` to run from source
- One or more extracted [zapret-discord-youtube releases](https://github.com/Flowseal/zapret-discord-youtube/releases) (the folders that contain `bin/winws.exe`, `service.bat`, `general*.bat`, ...)

## Install

### Option 1 — prebuilt .exe (easiest)

Download `zapret-web-panel.exe` from [Releases](../../releases) and place it next to your zapret version folders (or anywhere — point it at them with `ZAPRET_BASE_DIR`, see below).

### Option 2 — from source

```
git clone https://github.com/e24x5-Fox/zapret-web-panel.git
```

It looks for `zapret-discord-youtube-*` releases (folders containing `bin/winws.exe`) in its own folder by default. If you keep this checkout separate from your zapret releases — the normal case — point it at that folder instead with the `ZAPRET_BASE_DIR` environment variable:

```
Downloads/
  zapret-discord-youtube-1.9.9d/
  zapret-discord-youtube-1.9.6/
  zapret-web-panel/          <- this repo, cloned separately
```

```
pip install -r zapret-web-panel\requirements.txt
set ZAPRET_BASE_DIR=C:\Users\you\Downloads
python zapret-web-panel\zapret_web.py
```

(PowerShell: `$env:ZAPRET_BASE_DIR = "C:\Users\you\Downloads"`)

## Run

```
python zapret_web.py
```

or just run `zapret-web-panel.exe`.

It requests admin rights via UAC (required — `winws.exe` needs the WinDivert driver), starts a local server on `127.0.0.1:8756`, and opens its own app window (no console, no browser tab — the UI renders through the system WebView2 runtime).

## Security

This server runs elevated and can install/remove Windows services and kill processes, so it's locked to localhost with two defenses beyond `bind(127.0.0.1)`:

- A random token is generated on every run, embedded into the served page, and required (via a custom `X-Zapret-Token` header) on every API call. A page from another origin cannot read it and cannot forge the header without triggering a CORS preflight the server doesn't approve — this blocks both CSRF and DNS-rebinding attempts against the local API.
- Every request's `Host` header is checked against `127.0.0.1:8756` as defense in depth.

## Configuring test targets

The list of services the "Test" tab can test against lives in `targets.json`, created next to the scripts on first run with a starter set (Discord, YouTube, Cloudflare, Telegram, Twitter/X, Instagram, Facebook, TikTok, Steam, Spotify, Twitch, Reddit). Edit it freely — format:

```json
{
  "ServiceName": [
    {"host": "example.com", "kind": "http"},
    {"host": "1.2.3.4", "kind": "tcp443"}
  ]
}
```

## Building the .exe yourself

```
pip install -r requirements.txt pyinstaller
pyinstaller zapret-web-panel.spec
```

The resulting `dist\zapret-web-panel.exe` is a single file that requests admin rights via UAC on launch (`uac_admin=True` manifest); the web UI (`web/`) is bundled inside it.

## License

MIT — see [LICENSE](LICENSE). `zapret-discord-youtube` and `zapret` are themselves MIT-licensed by bol-van and Flowseal; this project doesn't bundle or redistribute their code, only automates the release folders you point it at.
