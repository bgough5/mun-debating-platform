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


def test_titles_match_headings_and_deep_pages_have_breadcrumbs(coord):
    """Phase 6 polish: every page's <title> is its <h1>, and every page below a section has breadcrumbs."""
    import html as H
    seen, _ = crawl(coord, limit=600)
    problems = []
    for url in sorted(seen):
        r = coord.get(url)
        if "text/html" not in r.headers.get("content-type", ""):
            continue
        t = r.text
        title = H.unescape(re.search(r"<title>(.*?)</title>", t, re.S).group(1)).split(" — SOC")[0].strip()
        h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S)
        h1 = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", h1s[0])).strip()) if h1s else None
        if h1 != title:
            problems.append(("title", url, title, h1))
        path = urlparse(url).path
        depth = len([x for x in path.split("/") if x])
        if depth >= 2 and 'class="breadcrumb"' not in t and not any(k in path for k in ("/print", "projector", "/chair/committee/")):
            problems.append(("breadcrumb", url))
    assert problems == []
