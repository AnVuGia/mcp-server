import os
import httpx


BASE_URL = "https://api.figma.com/v1"


def _headers() -> dict:
    token = os.getenv("FIGMA_TOKEN")
    if not token:
        raise ValueError("FIGMA_TOKEN is not set")
    return {"X-Figma-Token": token}


def get_file(file_key: str) -> dict:
    """Get metadata and document structure of a Figma file."""
    resp = httpx.get(f"{BASE_URL}/files/{file_key}", headers=_headers())
    resp.raise_for_status()
    data = resp.json()
    return {
        "name": data["name"],
        "last_modified": data["lastModified"],
        "thumbnail_url": data.get("thumbnailUrl"),
        "version": data["version"],
    }


def get_file_nodes(file_key: str, node_ids: list[str]) -> dict:
    """Get specific nodes from a Figma file by their IDs."""
    ids = ",".join(node_ids)
    resp = httpx.get(f"{BASE_URL}/files/{file_key}/nodes", headers=_headers(), params={"ids": ids})
    resp.raise_for_status()
    return resp.json().get("nodes", {})


def list_components(file_key: str) -> list[dict]:
    """List all components in a Figma file."""
    resp = httpx.get(f"{BASE_URL}/files/{file_key}/components", headers=_headers())
    resp.raise_for_status()
    meta = resp.json().get("meta", {})
    return [
        {"key": c["key"], "name": c["name"], "description": c.get("description", "")}
        for c in meta.get("components", [])
    ]


def list_projects(team_id: str) -> list[dict]:
    """List projects for a Figma team."""
    resp = httpx.get(f"{BASE_URL}/teams/{team_id}/projects", headers=_headers())
    resp.raise_for_status()
    return [
        {"id": p["id"], "name": p["name"]}
        for p in resp.json().get("projects", [])
    ]


def list_project_files(project_id: str) -> list[dict]:
    """List files in a Figma project."""
    resp = httpx.get(f"{BASE_URL}/projects/{project_id}/files", headers=_headers())
    resp.raise_for_status()
    return [
        {"key": f["key"], "name": f["name"], "last_modified": f["last_modified"], "thumbnail_url": f.get("thumbnail_url")}
        for f in resp.json().get("files", [])
    ]
