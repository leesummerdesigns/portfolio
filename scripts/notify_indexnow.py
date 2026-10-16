"""Notify IndexNow about changed canonical pages after their deployment is visible."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://api.indexnow.org/indexnow"
HEADERS = {"User-Agent": "LouisHenrichPortfolioIndexNow/1.0 (https://louishenrich.com/)"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def canonical_pages(xml, host):
    pages = {}
    for node in ET.fromstring(xml).findall("{*}url/{*}loc"):
        url = (node.text or "").strip()
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != host or parsed.query or parsed.fragment:
            raise ValueError("Sitemap contains a noncanonical or foreign URL")
        path = unquote(parsed.path).lstrip("/") or "index.html"
        if ".." in Path(path).parts:
            raise ValueError("Invalid sitemap path")
        pages[path] = url
    return pages


def fetch(url):
    try:
        with urlopen(Request(url, headers={**HEADERS, "Cache-Control": "no-cache"}), timeout=15) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, b""


def wait_for_publication(resources, timeout):
    deadline = time.monotonic() + timeout

    def matches(resource):
        url, expected = resource
        try:
            status, body = fetch(url)
        except OSError:
            return False
        return status in (404, 410) if expected is None else status == 200 and body == expected

    while True:
        with ThreadPoolExecutor(max_workers=8) as pool:
            ready = all(pool.map(matches, resources))
        if ready:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("Published files did not match this commit; no notification was sent")
        print("Waiting for GitHub Pages to publish the changed files...", flush=True)
        time.sleep(15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", default=os.environ.get("INDEXNOW_BEFORE", ""))
    parser.add_argument("--after", default=os.environ.get("INDEXNOW_AFTER", "HEAD"))
    parser.add_argument("--paths", nargs="+", help="Explicit recently changed paths for initial setup")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--publication-timeout", type=int, default=300)
    args = parser.parse_args()

    config = json.loads((ROOT / ".github/indexnow.json").read_text())
    host, key_file = config["host"], config["key_file"]
    if host != "louishenrich.com" or not re.fullmatch(r"[a-f0-9]{32}\.txt", key_file):
        raise ValueError("Unexpected IndexNow site configuration")
    key_bytes = (ROOT / key_file).read_bytes()
    key = key_bytes.decode().strip()
    if key_file != key + ".txt":
        raise ValueError("Site verification file does not match its key")

    before = args.before
    if not before or set(before) == {"0"}:
        before = git("rev-parse", args.after + "^").decode().strip()
    pages = canonical_pages((ROOT / "sitemap.xml").read_bytes(), host)
    previous_pages = canonical_pages(git("show", before + ":sitemap.xml"), host)
    known_pages = {**previous_pages, **pages}
    changed = args.paths or git("diff", "--no-renames", "--name-only", "-z", before, args.after).decode().split("\0")
    paths = sorted({path for path in changed if path in known_pages})
    if not paths:
        print("No canonical HTML pages changed; no notification needed.")
        return

    urls = [known_pages[path] for path in paths]
    payload = {"host": host, "key": key, "keyLocation": f"https://{host}/{key_file}", "urlList": urls}
    print(json.dumps({"host": host, "urlList": urls}, indent=2))
    if args.dry_run:
        print("Dry run: no request sent.")
        return

    resources = [(payload["keyLocation"], key_bytes)]
    resources.extend((known_pages[path], (ROOT / path).read_bytes() if (ROOT / path).is_file() else None) for path in paths)
    wait_for_publication(resources, args.publication_timeout)
    request = Request(ENDPOINT, data=json.dumps(payload).encode(), method="POST", headers={**HEADERS, "Content-Type": "application/json; charset=utf-8"})
    with urlopen(request, timeout=30) as response:
        status = response.status
    if status not in (200, 202):
        raise RuntimeError(f"Unexpected IndexNow response: {status}")
    result = "received" if status == 200 else "received; key validation pending"
    print(f"IndexNow HTTP {status}: {len(urls)} URLs {result}. This does not confirm crawling or indexing.")


if __name__ == "__main__":
    main()
