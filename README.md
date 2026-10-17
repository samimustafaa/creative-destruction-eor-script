# Creative Destruction — Quick Edit

Windows edit helper by **sg0hann**. Current version: **1.10**.

Press **G**, move to an edit shape, and the helper selects and applies it. Auto reset chooses the top/default shape and starts enabled.

## Download

Open the [latest release](https://github.com/samimustafaa/creative-destruction-eor-script/releases/latest).

- **QuickEdit.exe** — standalone Windows app.
- **QuickEdit-Windows.zip** — app and short README.
- **QuickEdit-source.zip** — complete source, assets, and build instructions.
- **creative_destruction_edit.py** — Python script only (needs dependencies and the `assets` folder).

No Python installation is needed for the built app. Close older helper instances before opening the new one.

## Controls

| Key | Action |
| --- | --- |
| F6 | Start / pause |
| F10 | Exit |
| G | Open / cancel an edit |
| Esc | Cancel |

Use windowed or borderless mode with `client.exe`. Keep **Select shape only** unchecked for automatic apply. **Auto reset (top/default)** can be turned ON or OFF. Green button and dot mean the helper is enabled.

## Wallpapers and performance

- Fixed bundled background; custom wallpaper controls have been removed.
- Black Windows title bar with light text (supported Windows versions).
- Settings-applied confirmations are larger, bold, and green.
- Fixed window size, transparent settings panel, and no wallpaper animation loop.
- Mouse tracking runs only during edits; hooks run separately from the UI.
- Workers sleep while idle. High-resolution timers are requested only during editing/clicks.
- **360 Hz is a scan target**, not a guaranteed detection rate. Start with Fast; use Balanced or a longer click hold if inputs are missed.

## Run from source (Windows, Python 3.12)

```powershell
py -3.12 -m pip install -r requirements.txt
py -3.12 creative_destruction_edit.py
```

## Build an EXE (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Output: `dist/QuickEdit/QuickEdit.exe`. The script uses PyInstaller; the app and assets are bundled together. GitHub Actions runs the same build on Windows.

## Checks

```powershell
py -3.12 tests/engine_check.py
```

Hook lifecycle, timer cleanup, settings confirmations, and UI behavior were checked locally. Windows taskbar responsiveness and in-game timing still need testing on a Windows PC. This helper does not change game files or read game memory. Disable pre-edit is not implemented.

