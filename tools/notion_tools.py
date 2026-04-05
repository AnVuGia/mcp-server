import os
import httpx


BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers() -> dict:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise ValueError("NOTION_TOKEN is not set")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def search(query: str, filter_type: str | None = None) -> list[dict]:
    """Search Notion pages and databases."""
    body: dict = {"query": query}
    if filter_type in ("page", "database"):
        body["filter"] = {"value": filter_type, "property": "object"}
    resp = httpx.post(f"{BASE_URL}/search", headers=_headers(), json=body)
    resp.raise_for_status()
    results = []
    for item in resp.json().get("results", []):
        title = _extract_title(item)
        results.append({"id": item["id"], "type": item["object"], "title": title, "url": item.get("url")})
    return results


def get_page(page_id: str) -> dict:
    """Get a Notion page's properties."""
    resp = httpx.get(f"{BASE_URL}/pages/{page_id}", headers=_headers())
    resp.raise_for_status()
    item = resp.json()
    return {"id": item["id"], "title": _extract_title(item), "url": item.get("url"), "properties": item.get("properties", {})}


def get_page_content(page_id: str) -> list[dict]:
    """Get the block children (content) of a Notion page."""
    resp = httpx.get(f"{BASE_URL}/blocks/{page_id}/children", headers=_headers())
    resp.raise_for_status()
    blocks = []
    for block in resp.json().get("results", []):
        btype = block["type"]
        text = _extract_rich_text(block.get(btype, {}))
        blocks.append({"type": btype, "text": text})
    return blocks


def get_database(database_id: str) -> dict:
    """Get a Notion database's schema."""
    resp = httpx.get(f"{BASE_URL}/databases/{database_id}", headers=_headers())
    resp.raise_for_status()
    item = resp.json()
    return {"id": item["id"], "title": _extract_title(item), "properties": list(item.get("properties", {}).keys())}


def query_database(database_id: str, filter: dict | None = None) -> list[dict]:
    """Query rows from a Notion database."""
    body = {}
    if filter:
        body["filter"] = filter
    resp = httpx.post(f"{BASE_URL}/databases/{database_id}/query", headers=_headers(), json=body)
    resp.raise_for_status()
    results = []
    for item in resp.json().get("results", []):
        results.append({"id": item["id"], "title": _extract_title(item), "url": item.get("url")})
    return results


def _extract_title(item: dict) -> str:
    props = item.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return _extract_rich_text(prop)
    # fallback for database titles
    title_list = item.get("title", [])
    if title_list:
        return "".join(t.get("plain_text", "") for t in title_list)
    return ""


def _extract_rich_text(block: dict) -> str:
    for key in ("rich_text", "title", "text"):
        parts = block.get(key, [])
        if parts:
            return "".join(p.get("plain_text", "") for p in parts)
    return ""
