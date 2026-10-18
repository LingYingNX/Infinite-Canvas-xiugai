#!/usr/bin/env python3
"""Fast security/data-integrity checks for the local application."""

import json
import os
import tempfile
import time
import zipfile
from io import BytesIO
from pathlib import Path
import sys

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import main


def check(name, fn):
    try:
        fn()
    except Exception as exc:
        print(f"FAIL | {name} | {exc}")
        raise
    print(f"PASS | {name}")


def check_private_urls_blocked():
    for url in ("http://127.0.0.1:3000/", "http://169.254.169.254/latest/meta-data/"):
        try:
            main.ensure_public_http_url(url)
        except HTTPException as exc:
            assert exc.status_code == 403, (url, exc.status_code)
        else:
            raise AssertionError(f"private URL was accepted: {url}")


def check_saved_key_requires_same_origin():
    provider = {"id": "test-provider", "base_url": "https://api.example.com/v1", "protocol": "openai"}
    old_load = main.load_api_providers
    old_key = main.provider_env_key_value
    try:
        main.load_api_providers = lambda: [provider]
        main.provider_env_key_value = lambda provider_id: "saved-secret" if provider_id == "test-provider" else ""
        payload = main.TestConnectionPayload(provider_id="test-provider", base_url="https://evil.example")
        assert main.api_key_from_payload(payload, "openai", payload.base_url) == ""
        payload.base_url = "https://api.example.com/other-path"
        assert main.api_key_from_payload(payload, "openai", payload.base_url) == "saved-secret"
    finally:
        main.load_api_providers = old_load
        main.provider_env_key_value = old_key


def check_atomic_json_replace():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "state.json")
        main.atomic_write_json(path, {"step": 1})
        main.atomic_write_json(path, {"step": 2})
        with open(path, "r", encoding="utf-8") as handle:
            assert json.load(handle) == {"step": 2}
        assert not [name for name in os.listdir(temp_dir) if name.endswith(".tmp")]


def check_zip_limits():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("large.bin", b"x" * 128)
    with zipfile.ZipFile(BytesIO(buffer.getvalue())) as archive:
        try:
            main.validate_zip_limits(archive, max_entries=10, max_bytes=64)
        except HTTPException as exc:
            assert exc.status_code == 413
        else:
            raise AssertionError("oversized archive was accepted")


def check_task_pruning():
    old_retention = main.CANVAS_TASK_RETENTION_SECONDS
    old_max = main.CANVAS_TASK_MAX_ENTRIES
    try:
        main.CANVAS_TASK_RETENTION_SECONDS = 60
        main.CANVAS_TASK_MAX_ENTRIES = 20
        with main.CANVAS_TASK_LOCK:
            main.CANVAS_TASKS.clear()
            main.CANVAS_TASKS["old"] = {"status": "succeeded", "updated_at": time.time() - 3600}
            main.prune_canvas_tasks_locked()
            assert "old" not in main.CANVAS_TASKS
    finally:
        main.CANVAS_TASK_RETENTION_SECONDS = old_retention
        main.CANVAS_TASK_MAX_ENTRIES = old_max
        with main.CANVAS_TASK_LOCK:
            main.CANVAS_TASKS.clear()


def check_cross_origin_api_rejected():
    client = TestClient(main.app, base_url="http://127.0.0.1:3000")
    response = client.get("/api/config", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403, response.text
    response = client.get("/api/config", headers={"Origin": "http://127.0.0.1:3000"})
    assert response.status_code == 200, response.text
    response = client.get("/api/config")
    assert response.status_code == 200, response.text


def check_lan_client_needs_page_token():
    client = TestClient(
        main.app,
        base_url="http://192.168.1.10:3000",
        client=("192.168.1.50", 50000),
    )
    response = client.get("/api/config")
    assert response.status_code == 403, response.text
    response = client.get("/api/config", headers={"Origin": "http://192.168.1.10:3000"})
    assert response.status_code == 403, response.text
    response = client.get("/")
    assert response.status_code == 200, response.text
    assert main.ACCESS_COOKIE_NAME in client.cookies
    response = client.get("/api/config", headers={"Origin": "http://192.168.1.10:3000"})
    assert response.status_code == 200, response.text


def check_dns_rebinding_needs_token():
    client = TestClient(
        main.app,
        base_url="http://rebind.example:3000",
        client=("127.0.0.1", 50001),
    )
    headers = {"Origin": "http://rebind.example:3000"}
    response = client.get("/api/config", headers=headers)
    assert response.status_code == 403, response.text
    response = client.get("/")
    assert response.status_code == 200, response.text
    response = client.get("/api/config", headers=headers)
    assert response.status_code == 200, response.text


def check_request_body_limit():
    old_limit = main.MAX_REQUEST_BODY_BYTES
    try:
        main.MAX_REQUEST_BODY_BYTES = 32
        client = TestClient(main.app)
        response = client.post("/api/config", content=b"x" * 64)
        assert response.status_code == 413, response.text
    finally:
        main.MAX_REQUEST_BODY_BYTES = old_limit


def check_websocket_origin_auth():
    client = TestClient(main.app, base_url="http://127.0.0.1:3000")
    with client.websocket_connect(
        "/ws/stats?client_id=security-regression",
        headers={"Host": "127.0.0.1:3000", "Origin": "http://127.0.0.1:3000"},
    ) as websocket:
        websocket.send_text("ping")
        messages = [websocket.receive_text() for _ in range(2)]
        assert any('"type": "pong"' in message for message in messages)
    try:
        with client.websocket_connect(
            "/ws/stats?client_id=security-evil",
            headers={"Origin": "https://evil.example"},
        ):
            raise AssertionError("cross-origin WebSocket was accepted")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008


def main_check():
    checks = [
        ("private URL blocked", check_private_urls_blocked),
        ("saved key bound to provider origin", check_saved_key_requires_same_origin),
        ("atomic JSON replacement", check_atomic_json_replace),
        ("ZIP bombs rejected by metadata limit", check_zip_limits),
        ("old canvas tasks pruned", check_task_pruning),
        ("cross-origin API rejected", check_cross_origin_api_rejected),
        ("LAN API requires page token", check_lan_client_needs_page_token),
        ("DNS rebinding requires page token", check_dns_rebinding_needs_token),
        ("oversized request body rejected", check_request_body_limit),
        ("WebSocket origin auth", check_websocket_origin_auth),
    ]
    for name, fn in checks:
        check(name, fn)
    print(f"SUMMARY {len(checks)}/{len(checks)} passed")


if __name__ == "__main__":
    main_check()
