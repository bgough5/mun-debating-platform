"""Visit every page reachable by links (GET only) as each role, and fail on any server error."""
import re
from urllib.parse import urljoin, urlparse

SKIP = ("/static/", "/practice-game/solo", "/logout", ".docx", ".csv", "/admin/data/download", "javascript:")


def crawl(client, start="/", limit=400):
    seen, queue, bad = set(), [start], []
    while queue and len(seen) < limit:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        r = client.get(url)
        if r.status_code >= 500:
            bad.append((url, r.status_code, r.text[-800:]))
            continue
        if "text/html" not in r.headers.get("content-type", ""):
            continue
        for href in re.findall(r'href="([^"#]+)', r.text):
            u = urljoin(url, href.replace("&amp;", "&"))
            p = urlparse(u)
            if p.netloc not in ("", "testserver") or any(s in u for s in SKIP):
                continue
            path = p.path + (("?" + p.query) if p.query else "")
            if path not in seen:
                queue.append(path)
    return seen, bad


def test_crawl_as_coordinator(coord):
    seen, bad = crawl(coord)
    assert not bad, bad[:3]
    assert len(seen) > 40


def test_crawl_anonymous(client):
    seen, bad = crawl(client)
    assert not bad, bad[:3]
