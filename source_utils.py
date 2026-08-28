"""Collect and render trusted HTTP(S) source links from agent tool results."""

from urllib.parse import urlparse


def _valid_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def collect_sources(value):
    """Recursively collect titled URLs from parsed tool output."""
    collected = []

    def visit(item):
        if isinstance(item, dict):
            for key in ("source_url", "url"):
                url = item.get(key)
                if _valid_url(url):
                    title = (
                        item.get("source_title")
                        or item.get("title")
                        or item.get("name")
                        or item.get("ticker")
                        or urlparse(url).netloc
                    )
                    collected.append({"title": str(title)[:160], "url": url})
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    seen = set()
    unique = []
    for source in collected:
        if source["url"] in seen:
            continue
        seen.add(source["url"])
        unique.append(source)
    return unique


def append_sources(answer, sources, limit=15):
    """Append a consistent Markdown Sources section to an agent answer."""
    answer = (answer or "").rstrip()
    unique = []
    seen = set()
    for source in sources:
        url = source.get("url") if isinstance(source, dict) else None
        if not _valid_url(url) or url in seen:
            continue
        seen.add(url)
        unique.append(source)

    if not unique:
        return answer + "\n\n## Sources\n\nNo external sources were used."

    # News and primary web pages are usually more useful to readers than a
    # long run of quote pages; preserve order within each group.
    unique.sort(key=lambda source: "finance.yahoo.com/quote/" in source["url"])
    shown = unique[:limit]
    lines = []
    for source in shown:
        title = str(source.get("title") or urlparse(source["url"]).netloc)
        title = title.replace("[", "").replace("]", "")
        lines.append(f"- [{title}]({source['url']})")
    if len(unique) > limit:
        lines.append(f"- {len(unique) - limit} additional source link(s) were omitted for readability.")
    return answer + "\n\n## Sources\n\n" + "\n".join(lines)
