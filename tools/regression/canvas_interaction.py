#!/usr/bin/env python3
"""Repeatable Playwright regression for classic and smart canvases.

Usage:
    python tools/regression/canvas_interaction.py [--no-server] [--base-url URL]

Starts main.py on 127.0.0.1:3000 when the endpoint is not reachable and
cleans up test canvases afterwards.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    sys.exit("playwright is required: pip install playwright && playwright install chromium")

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:3000"
KNOWN_404 = "runninghub/workflows"
results = []
server_proc = None


def api(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {}


def record(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL") + " | " + name + " | " + detail)


def endpoint_ready(timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            api("GET", "/api/config")
            return True
        except Exception:
            time.sleep(0.5)
    return False


def start_server():
    global server_proc
    if endpoint_ready(2):
        return None
    exe = os.environ.get("CANVAS_TEST_PYTHON")
    if not exe:
        bundled = ROOT / "python" / "python.exe"
        exe = str(bundled) if bundled.exists() else sys.executable
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    server_proc = subprocess.Popen(
        [exe, str(ROOT / "main.py")],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )
    if not endpoint_ready(30):
        stop_server()
        raise RuntimeError("main.py did not start on " + BASE)
    return server_proc


def stop_server():
    global server_proc
    if server_proc and server_proc.poll() is None:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
    server_proc = None


def create_canvas(kind):
    data = api(
        "POST",
        "/api/canvases",
        {"title": "e2e-refactor-check", "icon": "layers", "kind": kind},
    )
    return data["canvas"]["id"]


def cleanup_canvas(cid):
    try:
        api("DELETE", "/api/canvases/" + cid)
    except Exception:
        pass
    try:
        api("DELETE", "/api/canvases/" + cid + "/purge")
    except Exception as exc:
        print("cleanup warning:", exc)


def attach_errors(page):
    errors = []

    def on_pageerror(exc):
        errors.append("pageerror: " + str(exc))

    def on_console(msg):
        if msg.type == "error":
            text = msg.text or ""
            if "Failed to load resource" in text:
                return
            errors.append("console: " + text)

    def on_response(resp):
        if resp.status >= 400 and KNOWN_404 not in resp.url:
            errors.append("http %d: %s" % (resp.status, resp.url))

    page.on("pageerror", on_pageerror)
    page.on("console", on_console)
    page.on("response", on_response)
    return errors


def classic_flow(page, cid):
    errors = attach_errors(page)
    page.goto(BASE + "/static/canvas.html?id=" + cid, wait_until="domcontentloaded")
    page.wait_for_function(
        "cid => { const s = document.getElementById('shell'); return s && !s.classList.contains('no-canvas') && typeof canvas !== 'undefined' && !!canvas && canvas.id === cid; }",
        arg=cid,
        timeout=20000,
    )

    added = page.evaluate(
        """() => {
            const fns = ['addPromptNode','addImageNode','addLoopNode','addLLMNode','addGeneratorNode','addMsGenNode','addVideoNode','addMiniMaxNode','addRhNode','addComfyNode','addLTXDirectorNode','addOutputNode'];
            const out = {ok: [], errors: []};
            for (const fn of fns) {
                try {
                    const n = window[fn]();
                    if (n && n.id) out.ok.push(n.id);
                } catch (e) {
                    out.errors.push(fn + ': ' + (e && e.message ? e.message : e));
                }
            }
            try {
                const extra = window.addPromptNode();
                if (extra && extra.id) out.ok.push(extra.id);
            } catch (e) {
                out.errors.push('prompt-extra: ' + (e && e.message ? e.message : e));
            }
            return out;
        }"""
    )
    record(
        "classic add all node types",
        len(added["ok"]) >= 10 and not added["errors"],
        "ok=%d errors=%s" % (len(added["ok"]), json.dumps(added["errors"])),
    )
    page.wait_for_timeout(250)
    dom_count = page.locator(".node").count()
    record("classic node DOM rendered", dom_count >= 10, "dom=%d" % dom_count)

    layout = page.evaluate(
        """() => {
            const prompts = nodes.filter(n => n.type === 'prompt').slice(0, 2);
            if (prompts.length < 2) return {ok:false};
            const p1 = screenToWorld(260, 280);
            const p2 = screenToWorld(700, 280);
            prompts[0].x = p1.x; prompts[0].y = p1.y;
            prompts[1].x = p2.x; prompts[1].y = p2.y;
            render();
            return {ok:true, ids: prompts.map(n => n.id)};
        }"""
    )
    if layout.get("ok"):
        page.wait_for_timeout(150)
        drag_id = layout["ids"][0]
        before_node = page.evaluate(
            "id => { const n = nodes.find(x => x.id === id); return n ? {x:n.x, y:n.y} : null; }",
            drag_id,
        )
        head = page.locator('.node[data-id="' + drag_id + '"] .node-head')
        r = head.bounding_box()
        d = {
            "id": drag_id,
            "x": before_node["x"] if before_node else 0,
            "y": before_node["y"] if before_node else 0,
            "cx": r["x"] + r["width"] / 2,
            "cy": r["y"] + r["height"] / 2,
        }
        page.mouse.move(d["cx"], d["cy"])
        page.mouse.down()
        page.mouse.move(d["cx"] + 90, d["cy"] + 60, steps=8)
        page.mouse.up()
        after = page.evaluate(
            "id => { const n = nodes.find(x => x.id === id); return n ? {x:n.x, y:n.y} : null; }",
            drag_id,
        )
        moved = bool(after) and (
            abs(after["x"] - d["x"]) > 20 or abs(after["y"] - d["y"]) > 20
        )
        record("classic drag node", moved, "before=%s after=%s" % (d, after))

        b1 = page.locator('.node[data-id="' + layout["ids"][0] + '"]').bounding_box()
        b2 = page.locator('.node[data-id="' + layout["ids"][1] + '"]').bounding_box()
        sx = min(b1["x"], b2["x"]) - 50
        sy = min(b1["y"], b2["y"]) - 50
        ex = max(b1["x"] + b1["width"], b2["x"] + b2["width"]) + 50
        ey = max(b1["y"] + b1["height"], b2["y"] + b2["height"]) + 50
        page.mouse.move(sx, sy)
        page.mouse.down()
        page.mouse.move(ex, ey, steps=10)
        page.mouse.up()
        sel_count = page.evaluate("() => selected.size")
        record(
            "classic box select",
            sel_count >= 2,
            "selected=%d" % sel_count,
        )
    else:
        record("classic drag node", False, "not enough prompt nodes")
        record("classic box select", False, "not enough prompt nodes")

    before_pan = page.evaluate("() => ({x: viewport.x, y: viewport.y})")
    board_box = page.locator("#board").bounding_box()
    px = board_box["x"] + 60
    py = board_box["y"] + 90
    page.mouse.move(px, py)
    page.mouse.down(button="middle")
    page.mouse.move(px + 110, py + 70, steps=8)
    page.mouse.up(button="middle")
    after_pan = page.evaluate("() => ({x: viewport.x, y: viewport.y})")
    pan_moved = abs(after_pan["x"] - before_pan["x"]) > 10 or abs(
        after_pan["y"] - before_pan["y"]
    ) > 10
    record("classic middle-button pan", pan_moved, "before=%s after=%s" % (before_pan, after_pan))

    image_id = page.evaluate(
        """() => {
            const n = {id: uid('img'), type:'image', x: 700, y: 500, url:'/static/images/logo.png', name:'e2e'};
            nodes.push(n);
            render();
            return n.id;
        }"""
    )
    page.evaluate("id => openImageEditor(id)", image_id)
    page.wait_for_selector("#imageEditModal.open", timeout=8000)
    page.wait_for_function(
        "() => { const im = document.getElementById('cropImage'); return im && im.getAttribute('src') && im.naturalWidth > 0; }",
        timeout=12000,
    )
    page.evaluate("() => setImageEditMode('grid')")
    page.evaluate("() => resetCropBox()")
    page.evaluate("() => closeImageEditor()")
    page.evaluate("id => openImageEditor(id)", image_id)
    page.wait_for_selector("#imageEditModal.open", timeout=8000)
    page.wait_for_function(
        "() => { const im = document.getElementById('cropImage'); return im && im.getAttribute('src') && im.naturalWidth > 0; }",
        timeout=12000,
    )
    page.evaluate("() => closeImageEditor()")
    record("classic image editor open/close twice", True, "logo.png loaded")

    page.wait_for_timeout(400)
    real_errors = [e for e in errors if "runninghub/workflows" not in e]
    record("classic no page/console errors", not real_errors, "; ".join(real_errors[:5]))


def smart_flow(page, cid):
    errors = attach_errors(page)
    page.goto(BASE + "/static/smart-canvas.html?id=" + cid, wait_until="domcontentloaded")
    page.wait_for_function(
        "cid => typeof canvas !== 'undefined' && !!canvas && canvas.id === cid",
        arg=cid,
        timeout=25000,
    )

    created = page.evaluate(
        """() => {
            const out = {ids: [], errors: []};
            try {
                const p1 = createNodeFromMenu('prompt');
                if (p1 && p1.id) out.ids.push(p1.id);
                const p2 = createNodeFromMenu('prompt');
                if (p2 && p2.id) out.ids.push(p2.id);
            } catch (e) { out.errors.push('prompt: ' + e.message); }
            try {
                const l = createNodeFromMenu('loop');
                if (l && l.id) out.ids.push(l.id);
            } catch (e) { out.errors.push('loop: ' + e.message); }
            try {
                const im = createImageNodeAt({x: 860, y: 420}, [{url:'/static/images/logo.png', name:'e2e'}]);
                if (im && im.id) out.ids.push(im.id);
            } catch (e) { out.errors.push('image: ' + e.message); }
            return out;
        }"""
    )
    record(
        "smart create prompt/loop/image",
        len(created["ids"]) >= 3 and not created["errors"],
        "ids=%s errors=%s" % (json.dumps(created["ids"]), json.dumps(created["errors"])),
    )
    page.wait_for_timeout(250)
    dom_count = page.locator(".image-node").count()
    record("smart node DOM rendered", dom_count >= 3, "dom=%d" % dom_count)

    drag = page.evaluate(
        """(id) => {
            const n = nodes.find(x => x.id === id);
            if (!n || !(n.images || []).length) return {ok:false};
            const p = screenToWorld({clientX:620, clientY:420});
            n.x = p.x; n.y = p.y;
            render();
            const el = document.querySelector('.image-node[data-id="' + CSS.escape(n.id) + '"] .node-body');
            if (!el) return {ok:false};
            const r = el.getBoundingClientRect();
            window.__smartDrag = {id:n.id, x:n.x, y:n.y, cx:r.x + r.width / 2, cy:r.y + r.height / 2};
            return {ok:true};
        }""",
        created["ids"][-1],
    )
    if drag.get("ok"):
        d = page.evaluate("() => window.__smartDrag")
        page.mouse.move(d["cx"], d["cy"])
        page.mouse.down()
        page.mouse.move(d["cx"] + 80, d["cy"] + 50, steps=8)
        page.mouse.up()
        after = page.evaluate(
            """() => {
                const d = window.__smartDrag;
                const n = nodes.find(x => x.id === d.id);
                return n ? {x:n.x, y:n.y} : null;
            }"""
        )
        moved = bool(after) and (
            abs(after["x"] - d["x"]) > 20 or abs(after["y"] - d["y"]) > 20
        )
        record("smart drag node", moved, "before=%s after=%s" % (d, after))
    else:
        record("smart drag node", False, "no smart image node")

    sel_setup = page.evaluate(
        """() => {
            const prompts = nodes.filter(n => n.type === 'smart-prompt').slice(0, 2);
            if (prompts.length < 2) return {ok:false};
            const p1 = screenToWorld({clientX:260, clientY:280});
            const p2 = screenToWorld({clientX:700, clientY:280});
            prompts[0].x = p1.x; prompts[0].y = p1.y;
            prompts[1].x = p2.x; prompts[1].y = p2.y;
            render();
            return {ok:true, ids: prompts.map(n => n.id)};
        }"""
    )
    if sel_setup.get("ok"):
        page.wait_for_timeout(150)
        b1 = page.locator('.image-node[data-id="' + sel_setup["ids"][0] + '"]').bounding_box()
        b2 = page.locator('.image-node[data-id="' + sel_setup["ids"][1] + '"]').bounding_box()
        sx = min(b1["x"], b2["x"]) - 60
        sy = min(b1["y"], b2["y"]) - 60
        ex = max(b1["x"] + b1["width"], b2["x"] + b2["width"]) + 60
        ey = max(b1["y"] + b1["height"], b2["y"] + b2["height"]) + 60
        page.mouse.move(sx, sy)
        page.mouse.down()
        page.mouse.move(ex, ey, steps=10)
        page.mouse.up()
        sel_count = page.evaluate("() => selectedNodeIds().length")
        record("smart box select", sel_count >= 2, "selected=%d" % sel_count)
    else:
        record("smart box select", False, "not enough smart prompt nodes")

    before_pan = page.evaluate("() => ({x: viewport.x, y: viewport.y})")
    world_box = page.locator("#world").bounding_box()
    px = world_box["x"] + 80
    py = world_box["y"] + 120
    page.mouse.move(px, py)
    page.mouse.down(button="middle")
    page.mouse.move(px + 100, py + 60, steps=8)
    page.mouse.up(button="middle")
    after_pan = page.evaluate("() => ({x: viewport.x, y: viewport.y})")
    pan_moved = abs(after_pan["x"] - before_pan["x"]) > 10 or abs(
        after_pan["y"] - before_pan["y"]
    ) > 10
    record("smart middle-button pan", pan_moved, "before=%s after=%s" % (before_pan, after_pan))

    image_id = created["ids"][-1]
    page.evaluate("id => openImageEditor(id, 0)", image_id)
    page.wait_for_selector("#imageEditModal.open", timeout=8000)
    page.wait_for_function(
        "() => { const im = document.getElementById('cropImage'); return im && im.getAttribute('src') && im.naturalWidth > 0; }",
        timeout=12000,
    )
    page.evaluate("() => closeImageEditor()")
    record("smart image editor open/close", True, "logo.png loaded")

    comfy = page.evaluate(
        """async () => {
            const origText = smartRequestJsonText;
            const origRun = runQueuedSmartComfyGenerate;
            try {
                const fields = [
                    {id:'p0', node:'KPrompt', input:'text', type:'textarea', name:'prompt'},
                    {id:'img0', node:'LoadImage', input:'image', type:'image', name:'image'},
                    {id:'seed0', node:'KSampler', input:'seed', type:'number', name:'seed', random_enabled:true, min:1, max:100, step:1},
                    {id:'steps0', node:'KSampler', input:'steps', type:'number', name:'steps', default:20}
                ];
                smartRequestJsonText = async () => ({config:{fields}});
                runQueuedSmartComfyGenerate = async payload => {
                    window.__comfyPayload = payload;
                    return {urls:['/output/e2e.png'], videos:[], audios:[], texts:[]};
                };
                const result = await runComfyCustomWorkflow(
                    {comfyWorkflow:'e2e-workflow.json', comfyParams:{steps0:25}},
                    'hello world',
                    [],
                    id => true
                );
                const p = window.__comfyPayload || {};
                const params = p.params || {};
                const ok = p.type === 'workflow-custom'
                    && params.KPrompt?.text === 'hello world'
                    && typeof params.KSampler?.seed === 'number'
                    && params.KSampler?.steps === 25
                    && (result.urls || []).includes('/output/e2e.png');
                return {ok, payload:p};
            } finally {
                smartRequestJsonText = origText;
                runQueuedSmartComfyGenerate = origRun;
            }
        }"""
    )
    record(
        "smart runComfyCustomWorkflow mock",
        bool(comfy.get("ok")),
        json.dumps(comfy.get("payload", {}), ensure_ascii=False)[:500],
    )

    page.wait_for_timeout(400)
    real_errors = [e for e in errors if "runninghub/workflows" not in e]
    record("smart no page/console errors", not real_errors, "; ".join(real_errors[:5]))


def main():
    global BASE
    parser = argparse.ArgumentParser(description="Classic and smart canvas interaction regression")
    parser.add_argument("--no-server", action="store_true", help="do not start main.py automatically")
    parser.add_argument("--base-url", default=BASE, help="server base URL")
    args = parser.parse_args()
    BASE = args.base_url.rstrip("/")
    try:
        if not args.no_server:
            start_server()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            cids = []
            try:
                classic_id = create_canvas("classic")
                cids.append(classic_id)
                classic_flow(context.new_page(), classic_id)

                smart_id = create_canvas("smart")
                cids.append(smart_id)
                smart_flow(context.new_page(), smart_id)
            finally:
                for cid in cids:
                    cleanup_canvas(cid)
            browser.close()
    finally:
        stop_server()

    failed = [r for r in results if not r["ok"]]
    print("SUMMARY total=%d pass=%d fail=%d" % (len(results), len(results) - len(failed), len(failed)))
    if failed:
        print("FAILURES " + json.dumps(failed, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
