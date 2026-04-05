from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from mcp.server.fastmcp import FastMCP
from tools import github_tools, figma_tools, notion_tools
from skills import github_skills, figma_skills, notion_skills

mcp = FastMCP("ISIEE MCP Server")

# ─── GitHub ───────────────────────────────────────────────────────────────────

@mcp.tool()
def github_list_repos(org: str = "") -> list[dict]:
    """List GitHub repositories. Pass an org name to list org repos, or leave empty for your own repos."""
    return github_tools.list_repos(org or None)


@mcp.tool()
def github_get_file(repo: str, path: str, ref: str = "HEAD") -> str:
    """Get the content of a file in a GitHub repository. repo format: owner/repo"""
    return github_tools.get_file(repo, path, ref)


@mcp.tool()
def github_list_issues(repo: str, state: str = "open") -> list[dict]:
    """List issues in a GitHub repository. state: open | closed | all"""
    return github_tools.list_issues(repo, state)


@mcp.tool()
def github_get_issue(repo: str, number: int) -> dict:
    """Get a specific GitHub issue by number."""
    return github_tools.get_issue(repo, number)


@mcp.tool()
def github_list_pull_requests(repo: str, state: str = "open") -> list[dict]:
    """List pull requests in a GitHub repository. state: open | closed | all"""
    return github_tools.list_pull_requests(repo, state)


@mcp.tool()
def github_list_projects_v2(
    scope: str,
    owner: str = "",
    repo: str = "",
    first: int = 30,
) -> list[dict]:
    """List GitHub Projects v2 boards. scope: viewer | user | org | repository. For user/org, set owner to login; for repository, set owner and repo name."""
    return github_tools.list_projects_v2(scope, owner, repo, first)


@mcp.tool()
def github_get_project_v2(
    scope: str,
    owner: str,
    project_number: int,
    repo: str = "",
    items_first: int = 50,
    items_after: str = "",
) -> dict:
    """Read one GitHub Project v2: items, Status and other field columns, linked issues/PRs. scope: viewer | org | user | repository. items_after: cursor from items_page_info.end_cursor for pagination."""
    after = items_after or None
    return github_tools.get_project_v2(scope, owner, project_number, repo, items_first, after)


@mcp.tool()
def github_add_project_v2_draft_issue(project_node_id: str, title: str, body: str = "") -> str:
    """Add a draft issue to a GitHub Project v2 board. project_node_id is the GraphQL node ID (e.g. PVT_kwHOBj4MN84BTxbG) — get it from github_get_project_v2 or github_list_projects_v2. Returns the new item's node ID."""
    return github_tools.add_project_v2_draft_issue(project_node_id, title, body)


# ─── Figma ────────────────────────────────────────────────────────────────────

@mcp.tool()
def figma_get_file(file_key: str) -> dict:
    """Get metadata for a Figma file by its file key (from the URL)."""
    return figma_tools.get_file(file_key)


@mcp.tool()
def figma_get_nodes(file_key: str, node_ids: list[str]) -> dict:
    """Get specific nodes from a Figma file by their IDs."""
    return figma_tools.get_file_nodes(file_key, node_ids)


@mcp.tool()
def figma_list_components(file_key: str) -> list[dict]:
    """List all published components in a Figma file."""
    return figma_tools.list_components(file_key)


@mcp.tool()
def figma_list_projects(team_id: str) -> list[dict]:
    """List all projects for a Figma team."""
    return figma_tools.list_projects(team_id)


@mcp.tool()
def figma_list_project_files(project_id: str) -> list[dict]:
    """List all files in a Figma project."""
    return figma_tools.list_project_files(project_id)


# ─── Notion ───────────────────────────────────────────────────────────────────

@mcp.tool()
def notion_search(query: str, filter_type: str = "") -> list[dict]:
    """Search Notion for pages and databases. filter_type: page | database | (empty for both)"""
    return notion_tools.search(query, filter_type or None)


@mcp.tool()
def notion_get_page(page_id: str) -> dict:
    """Get a Notion page's properties by its ID."""
    return notion_tools.get_page(page_id)


@mcp.tool()
def notion_get_page_content(page_id: str) -> list[dict]:
    """Get the text content (blocks) of a Notion page."""
    return notion_tools.get_page_content(page_id)


@mcp.tool()
def notion_get_database(database_id: str) -> dict:
    """Get a Notion database schema by its ID."""
    return notion_tools.get_database(database_id)


@mcp.tool()
def notion_query_database(database_id: str) -> list[dict]:
    """Query all rows from a Notion database."""
    return notion_tools.query_database(database_id)


# ─── Skills (prompts) ─────────────────────────────────────────────────────────

@mcp.prompt()
def review_pr(github_url: str) -> str:
    """Review a GitHub pull request: fetch details, analyze quality, and write a structured review."""
    return github_skills.review_pr(github_url)


@mcp.prompt()
def summarize_issues(github_url: str) -> str:
    """Summarize open GitHub issues for a repository, grouped by theme with top priorities highlighted."""
    return github_skills.summarize_issues(github_url)


@mcp.prompt()
def onboard_repo(github_url: str) -> str:
    """Give a developer onboarding overview of a GitHub repo: stack, setup steps, and current work."""
    return github_skills.onboard_repo(github_url)


@mcp.prompt()
def read_github_project(
    scope: str,
    owner: str = "",
    repo: str = "",
    project_number: int = 0,
) -> str:
    """Read a GitHub Project v2 board: list projects if no number given, otherwise fetch items and fields."""
    return github_skills.read_github_project(scope, owner, repo, project_number)


@mcp.prompt()
def review_design(figma_url: str) -> str:
    """Review a Figma design file for consistency, completeness, accessibility, and component reuse."""
    return figma_skills.review_design(figma_url)


@mcp.prompt()
def list_team_files(team_id: str) -> str:
    """List all Figma projects and files for a given team ID."""
    return figma_skills.list_team_files(team_id)


@mcp.prompt()
def summarize_page(url_or_id: str) -> str:
    """Fetch and summarize a Notion page by its URL or ID."""
    return notion_skills.summarize_page(url_or_id)


@mcp.prompt()
def search_and_summarize(query: str) -> str:
    """Search Notion for a query and summarize the top matching pages and databases."""
    return notion_skills.search_and_summarize(query)


@mcp.prompt()
def summarize_database(url_or_id: str) -> str:
    """Summarize a Notion database schema and its contents by URL or ID."""
    return notion_skills.summarize_database(url_or_id)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
