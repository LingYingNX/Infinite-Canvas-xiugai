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

    cursors = page.evaluate(
        """() => ['documentElement', 'body', 'shell', 'world'].map(key => {
            const el = key === 'documentElement' ? document.documentElement
                : key === 'body' ? document.body
                : document.getElementById(key);
            return [key, getComputedStyle(el).cursor];
        })"""
    )
    record(
        "smart canvas uses arrow cursor",
        all(cursor in {"default", "auto"} for _, cursor in cursors),
        "cursors=%s" % json.dumps(cursors),
    )

    port_source = page.evaluate(
        """() => {
            const node = createImageNodeAt({x:260, y:560}, [{url:'/static/images/logo.png', name:'port-source'}], {select:false, skipUndo:true});
            selectedId = '';
            selectedIds = [];
            selectedImage = {nodeId:'', index:-1};
            render();
            return node.id;
        }"""
    )
    page.wait_for_timeout(150)
    page.locator('.image-node[data-id="' + port_source + '"]').hover()
    port = page.locator(
        '.image-node[data-id="' + port_source + '"] .node-port.port-out'
    )
    port_box = port.bounding_box()
    shell_box = page.locator("#shell").bounding_box()
    port_ok = bool(port_box and shell_box)
    if port_ok:
        page.mouse.move(port_box["x"] + port_box["width"] / 2, port_box["y"] + port_box["height"] / 2)
        page.mouse.down()
        port_drag_down = page.evaluate("() => Boolean(portDragState)")
        page.mouse.move(shell_box["x"] + 1080, shell_box["y"] + 780, steps=10)
        port_drag_move = page.evaluate("() => portDragState ? {moved:portDragState.moved, hover:portDragState.hoverTargetId} : null")
        page.mouse.up()
        page.wait_for_timeout(180)
        port_state = page.evaluate(
            """(id) => {
                const conn = (canvas.connections || []).find(item => item.from === id && item.kind === 'input');
                const target = conn ? nodes.find(item => item.id === conn.to) : null;
                return {
                    targetId: target?.id || '',
                    targetEmpty: Boolean(target && !(target.images || []).length),
                    composerOpen: Boolean(composer?.classList.contains('open')),
                    nodeCount: nodes.length,
                    selectedId,
                };
            }""",
            port_source,
        )
        record(
            "smart port drop creates node without composer",
            bool(port_state["targetId"])
            and port_state["targetEmpty"]
            and not port_state["composerOpen"],
            "down=%s move=%s state=%s" % (port_drag_down, json.dumps(port_drag_move), json.dumps(port_state)),
        )
    else:
        record("smart port drop creates node without composer", False, "port not rendered")

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

    drag_selection = page.evaluate(
        """() => {
            const oldNode = createImageNodeAt({x:260, y:760}, [{url:'/static/images/logo.png', name:'drag-old'}], {select:false, skipUndo:true});
            const draggedNode = createImageNodeAt({x:760, y:760}, [{url:'/static/images/logo.png', name:'drag-new'}], {select:false, skipUndo:true});
            selectedId = oldNode.id;
            selectedIds = [];
            selectedImage = {nodeId:'', index:-1};
            render();
            const el = document.querySelector('.image-node[data-id="' + CSS.escape(draggedNode.id) + '"] .node-body');
            if(!el) return {ok:false};
            const r = el.getBoundingClientRect();
            return {
                ok:true,
                oldId:oldNode.id,
                draggedId:draggedNode.id,
                cx:r.x + r.width / 2,
                cy:r.y + r.height / 2,
            };
        }"""
    )
    if drag_selection.get("ok"):
        page.mouse.move(drag_selection["cx"], drag_selection["cy"])
        page.mouse.down()
        page.mouse.move(drag_selection["cx"] + 90, drag_selection["cy"] + 40, steps=8)
        page.mouse.up()
        selected_after_drag = page.evaluate(
            """(ids) => ({
                selectedId,
                selectedIds:selectedIds.slice(),
                oldExists:Boolean(nodes.find(node => node.id === ids.oldId)),
                draggedExists:Boolean(nodes.find(node => node.id === ids.draggedId)),
            })""",
            {"oldId": drag_selection["oldId"], "draggedId": drag_selection["draggedId"]},
        )
        selected_ok = (
            selected_after_drag["selectedId"] == drag_selection["draggedId"]
            and not selected_after_drag["selectedIds"]
        )
        record(
            "smart drag selects dragged node",
            selected_ok,
            "state=%s" % json.dumps(selected_after_drag),
        )
        page.keyboard.press("Delete")
        page.wait_for_timeout(120)
        delete_after_drag = page.evaluate(
            """(ids) => ({
                oldExists:Boolean(nodes.find(node => node.id === ids.oldId)),
                draggedExists:Boolean(nodes.find(node => node.id === ids.draggedId)),
            })""",
            {"oldId": drag_selection["oldId"], "draggedId": drag_selection["draggedId"]},
        )
        record(
            "smart delete after drag removes dragged node",
            delete_after_drag["oldExists"] and not delete_after_drag["draggedExists"],
            "state=%s" % json.dumps(delete_after_drag),
        )
    else:
        record("smart drag selects dragged node", False, "drag setup failed")
        record("smart delete after drag removes dragged node", False, "drag setup failed")

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

    composer_check = page.evaluate(
        """(id) => {
            const node = nodes.find(item => item.id === id);
            if (!node) return {ok:false, reason:'image node missing'};
            selectedId = id;
            selectedIds = [];
            selectedImage = {nodeId:id, index:0};
            updateComposer();
            if (!composer?.classList.contains('open')) return {ok:false, reason:'composer not open'};
            if (!composerPinned) composerPinBtn?.click();
            return {ok:Boolean(composerPinned), nodeId:id};
        }""",
        image_id,
    )
    if composer_check.get("ok"):
        image_delete = page.locator(
            '.image-node[data-id="' + image_id + '"] .image-delete'
        )
        page.locator(
            '.image-node[data-id="' + image_id + '"] .image-wrap'
        ).hover()
        image_delete.dispatch_event("click")
        page.wait_for_timeout(120)
        composer_state = page.evaluate(
            """(id) => {
                const node = nodes.find(item => item.id === id);
                return {
                    composerOpen: Boolean(composer?.classList.contains('open')),
                    pinned: Boolean(composerPinned),
                    nodeExists: Boolean(node),
                    imageCount: node ? (node.images || []).length : -1,
                };
            }""",
            image_id,
        )
        record(
            "smart delete last image closes pinned composer",
            not composer_state["composerOpen"]
            and not composer_state["pinned"]
            and composer_state["nodeExists"]
            and composer_state["imageCount"] == 0,
            "state=%s" % json.dumps(composer_state),
        )
    else:
        record(
            "smart delete last image closes pinned composer",
            False,
            "setup failed: %s" % composer_check.get("reason", "unknown"),
        )

    toolbar_image = page.evaluate(
        """() => createImageNodeAt({x: 1080, y: 420}, [{url:'/static/images/logo.png', name:'toolbar-e2e'}]).id"""
    )
    toolbar_check = page.evaluate(
        """(id) => {
            selectedId = id;
            selectedIds = [];
            selectedImage = {nodeId:id, index:0};
            updateComposer();
            if (!composer?.classList.contains('open')) return {ok:false, reason:'composer not open'};
            if (!composerPinned) composerPinBtn?.click();
            return {ok:Boolean(composerPinned)};
        }""",
        toolbar_image,
    )
    if toolbar_check.get("ok"):
        node_delete = page.locator(
            '.image-node[data-id="' + toolbar_image + '"] .node-delete'
        ).last
        node_delete.click()
        page.wait_for_timeout(120)
        toolbar_state = page.evaluate(
            """(id) => {
                const node = nodes.find(item => item.id === id);
                return {
                    composerOpen: Boolean(composer?.classList.contains('open')),
                    pinned: Boolean(composerPinned),
                    nodeExists: Boolean(node),
                    imageCount: node ? (node.images || []).length : -1,
                };
            }""",
            toolbar_image,
        )
        record(
            "smart node delete clears pinned composer",
            not toolbar_state["composerOpen"]
            and not toolbar_state["pinned"]
            and toolbar_state["nodeExists"]
            and toolbar_state["imageCount"] == 0,
            "state=%s" % json.dumps(toolbar_state),
        )
    else:
        record(
            "smart node delete clears pinned composer",
            False,
            "setup failed: %s" % toolbar_check.get("reason", "unknown"),
        )

    multi_image = page.evaluate(
        """() => createImageNodeAt({x: 1460, y: 420}, [
            {url:'/static/images/logo.png', name:'multi-a'},
            {url:'/static/images/logo.png', name:'multi-b'}
        ]).id"""
    )
    multi_check = page.evaluate(
        """(id) => {
            selectedId = id;
            selectedIds = [];
            selectedImage = {nodeId:id, index:0};
            updateComposer();
            if (!composer?.classList.contains('open')) return {ok:false, reason:'composer not open'};
            if (!composerPinned) composerPinBtn?.click();
            return {ok:Boolean(composerPinned)};
        }""",
        multi_image,
    )
    if multi_check.get("ok"):
        image_delete = page.locator(
            '.image-node[data-id="' + multi_image + '"] .image-delete'
        ).first
        page.locator(
            '.image-node[data-id="' + multi_image + '"] .thumb-item'
        ).first.hover()
        image_delete.click()
        page.wait_for_timeout(120)
        multi_state = page.evaluate(
            """(id) => {
                const node = nodes.find(item => item.id === id);
                return {
                    composerOpen: Boolean(composer?.classList.contains('open')),
                    pinned: Boolean(composerPinned),
                    nodeExists: Boolean(node),
                    imageCount: node ? (node.images || []).length : -1,
                };
            }""",
            multi_image,
        )
        record(
            "smart delete image always clears composer",
            not multi_state["composerOpen"]
            and not multi_state["pinned"]
            and multi_state["nodeExists"]
            and multi_state["imageCount"] == 1,
            "state=%s" % json.dumps(multi_state),
        )
    else:
        record(
            "smart delete image always clears composer",
            False,
            "setup failed: %s" % multi_check.get("reason", "unknown"),
        )

    wheel_image = page.evaluate(
        """() => {
            const point = screenToWorld({clientX:560, clientY:180});
            return createImageNodeAt(point, [{url:'/static/images/logo.png', name:'wheel-e2e'}], {select:false}).id;
        }"""
    )
    wheel_check = page.evaluate(
        """(id) => {
            selectedId = id;
            selectedIds = [];
            selectedImage = {nodeId:id, index:0};
            updateComposer();
            return Boolean(composer?.classList.contains('open'));
        }""",
        wheel_image,
    )
    if wheel_check:
        page.locator("#composer").hover()
        before_zoom = page.evaluate("() => viewport.scale")
        page.mouse.wheel(0, -180)
        page.wait_for_timeout(120)
        after_zoom = page.evaluate("() => viewport.scale")
        record(
            "smart composer wheel zooms canvas",
            abs(after_zoom - before_zoom) > 0.001,
            "before=%s after=%s" % (before_zoom, after_zoom),
        )
    else:
        record("smart composer wheel zooms canvas", False, "composer not open")

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


def smart_cross_canvas_copy_flow(page, source_cid, target_cid):
    errors = attach_errors(page)
    page.goto(BASE + "/static/smart-canvas.html?id=" + source_cid, wait_until="domcontentloaded")
    page.wait_for_function(
        "cid => typeof canvas !== 'undefined' && !!canvas && canvas.id === cid",
        arg=source_cid,
        timeout=25000,
    )
    source = page.evaluate(
        """() => {
            const a = createPromptNode(220, 220, {select:false, skipUndo:true});
            const b = createPromptNode(620, 220, {select:false, skipUndo:true});
            connectInputNode(a.id, b.id);
            selectedId = '';
            selectedIds = [a.id, b.id];
            selectedImage = {nodeId:'', index:-1};
            render();
            return {ids:[a.id, b.id], connectionCount:(canvas.connections || []).length};
        }"""
    )
    page.keyboard.press("Control+C")
    page.wait_for_timeout(150)
    page.goto(BASE + "/static/smart-canvas.html?id=" + target_cid, wait_until="domcontentloaded")
    page.wait_for_function(
        "cid => typeof canvas !== 'undefined' && !!canvas && canvas.id === cid",
        arg=target_cid,
        timeout=25000,
    )
    page.keyboard.press("Control+V")
    page.wait_for_timeout(260)
    state = page.evaluate(
        """() => {
            const copied = nodes.filter(node => node.type === 'smart-prompt');
            const ids = new Set(copied.map(node => node.id));
            const internal = (canvas.connections || []).filter(conn => ids.has(conn.from) && ids.has(conn.to));
            return {promptCount:copied.length, internalConnections:internal.length};
        }"""
    )
    record(
        "smart copy/paste works across canvases",
        state["promptCount"] >= 2 and state["internalConnections"] >= 1,
        "source=%s target=%s state=%s" % (json.dumps(source), target_cid, json.dumps(state)),
    )
    page.wait_for_timeout(300)
    real_errors = [e for e in errors if "runninghub/workflows" not in e]
    record("smart cross-canvas copy no page/console errors", not real_errors, "; ".join(real_errors[:5]))


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

                smart_target_id = create_canvas("smart")
                cids.append(smart_target_id)
                smart_cross_canvas_copy_flow(context.new_page(), smart_id, smart_target_id)
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
