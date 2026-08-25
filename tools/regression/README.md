# Canvas Interaction Regression

Repeatable Playwright smoke test for classic and smart canvases.

## Requirements

- Python with Playwright installed: `pip install playwright && playwright install chromium`
- Port 3000 must be free, or pass `--no-server` when the app is already running.

## Run

From the repository root:

    python tools/regression/canvas_interaction.py

On this Windows machine, use the RTK wrapper:

    rtk proxy python tools\regression\canvas_interaction.py

To reuse an already running server:

    python tools/regression/canvas_interaction.py --no-server

The script creates temporary canvases through the API, runs 15 interaction checks, deletes the canvases, and stops the server it started.
