#!/usr/bin/env python3
"""Re-run main.py's static cache-busting without restarting the server.

Usage:
    python tools/sync_static_versions.py
"""
import os
import re
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(ROOT, "static")
PATTERN = re.compile(
    r'(?P<prefix>(?:src|href)=["\']|@import\s+url\(["\'])'
    r'(?P<url>/static/[^"\')?#]+(?:\.(?:js|css|html)))'
    r'(?:\?v=[^"\')#]*)?',
    re.I,
)


def app_version():
    with open(os.path.join(ROOT, "VERSION"), "r", encoding="utf-8") as f:
        return (f.read().strip().splitlines() or [""])[0].strip()


def versioned(html, version):
    safe = urllib.parse.quote(version, safe="._-")

    def repl(match):
        url = match.group("url")
        cache_version = safe
        rel = urllib.parse.unquote(url[len("/static/"):]).replace("/", os.sep)
        path = os.path.abspath(os.path.join(STATIC_DIR, rel))
        if path.startswith(os.path.abspath(STATIC_DIR) + os.sep) and os.path.isfile(path):
            cache_version = "%s.%d" % (safe, int(os.path.getmtime(path)))
        return "%s%s?v=%s" % (match.group("prefix"), url, cache_version)

    return PATTERN.sub(repl, html)


def main():
    version = app_version()
    changed = []
    for name in os.listdir(STATIC_DIR):
        if name.startswith("._") or not name.lower().endswith(".html"):
            continue
        path = os.path.join(STATIC_DIR, name)
        with open(path, "r", encoding="utf-8") as f:
            old = f.read()
        new = versioned(
            re.sub(r'([?&]v=)[^"\'`\s<>)]*', r"\g<1>%s" % urllib.parse.quote(version, safe="._-"), old),
            version,
        )
        if new != old:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            changed.append(name)
    print("version:", version)
    print("updated:", changed)


if __name__ == "__main__":
    main()
