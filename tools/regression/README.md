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

The script creates temporary canvases through the API, runs 30 interaction checks, deletes the canvases, and stops the server it started.

The smart-canvas pin checks assert the composer pin model: each node remembers its own pinned state, the panel stays nailed to the pinned node instead of following a new selection, the button reflects the selected node (so another node can be pinned without unpinning the first), and 取消固定 releases only that node.

## Security checks

Run the fast backend/security checks with:

    .\python\python.exe tools\regression\security_regression.py

It covers private-network SSRF blocking, saved API key origin binding, atomic JSON writes, ZIP and request-body limits, task retention, and cross-origin API rejection.
