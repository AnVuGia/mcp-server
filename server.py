import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from mcp.server.fastmcp import FastMCP
from tools import github_tools, figma_tools, notion_tools, code_graph_tools
from skills import github_skills, figma_skills, notion_skills, code_graph_skills


# ─── URL parsers (shared by tools + old prompts) ─────────────────────────────

def _parse_pr_url(github_url: str) -> tuple[str, int]:
    match = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", github_url)
    if not match:
        raise ValueError(f"Could not parse GitHub PR URL: {github_url}")
    return match.group(1), int(match.group(2))


def _parse_repo_url(github_url: str) -> str:
    match = re.search(r"github\.com/([^/]+/[^/]+?)(?:\.git|/|$)", github_url)
    if not match:
        raise ValueError(f"Could not parse GitHub repo URL: {github_url}")
    return match.group(1)


def _require_code_graph_target(repo: str, local_root: str) -> None:
    has_repo = bool(repo and repo.strip())
    has_local = bool(local_root and local_root.strip())
    if has_repo and has_local:
        raise ValueError("Pass either repo (GitHub owner/repo) or local_root, not both.")
    if not has_repo and not has_local:
        raise ValueError("Pass repo (GitHub owner/repo) or local_root (absolute path to a project directory).")


def _parse_figma_url(figma_url: str) -> tuple[str, str | None]:
    match = re.search(r"figma\.com/(?:design|file)/([^/?\s]+)", figma_url)
    if not match:
        raise ValueError(f"Could not parse Figma URL: {figma_url}")
    file_key = match.group(1)
    node_match = re.search(r"node-id=([^&\s]+)", figma_url)
    node_id = node_match.group(1).replace("-", ":") if node_match else None
    return file_key, node_id


def _parse_notion_id(url_or_id: str) -> str:
    match = re.search(r"([a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12})", url_or_id)
    if match:
        raw = match.group(1).replace("-", "")
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    raise ValueError(f"Could not parse Notion ID from: {url_or_id}")


def _isiee_env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _shorten_str(s: str, max_len: int = 160) -> str:
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _redact_tool_args(arguments: dict[str, Any]) -> dict[str, Any]:
    redact = ("token", "password", "secret", "api_key", "apikey", "credential", "authorization")
    out: dict[str, Any] = {}
    for k, v in arguments.items():
        lk = k.lower()
        if any(r in lk for r in redact):
            out[k] = "<redacted>"
        elif isinstance(v, str):
            out[k] = _shorten_str(v)
        else:
            out[k] = v
    return out


_tool_logger = logging.getLogger("isiee.tools")


class LoggingFastMCP(FastMCP):
    """FastMCP with optional stderr logging for each tools/call (ISIEE_LOG_TOOLS=1)."""

    async def call_tool(self, name: str, arguments: dict[str, Any]):  # type: ignore[override]
        log_tools = _isiee_env_flag("ISIEE_LOG_TOOLS")
        if log_tools:
            try:
                payload = json.dumps(_redact_tool_args(dict(arguments)), default=str)
            except (TypeError, ValueError):
                payload = repr(arguments)
            _tool_logger.info("tool call name=%s args=%s", name, payload)
        t0 = time.perf_counter()
        try:
            result = await super().call_tool(name, arguments)
        except Exception:
            if log_tools:
                _tool_logger.exception(
                    "tool failed name=%s elapsed_ms=%.1f",
                    name,
                    (time.perf_counter() - t0) * 1000,
                )
            raise
        if log_tools:
            _tool_logger.info(
                "tool finished name=%s elapsed_ms=%.1f",
                name,
                (time.perf_counter() - t0) * 1000,
            )
        return result


mcp = LoggingFastMCP("ISIEE MCP Server")

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


# ─── Code Graph ───────────────────────────────────────────────────────────────

@mcp.tool()
def code_graph_fetch_tree(
    repo: str = "",
    path: str = "",
    ref: str = "HEAD",
    recursive: bool = True,
    max_depth: int = 5,
    local_root: str = "",
) -> list[dict]:
    """Fetch the file tree of a GitHub repository (repo=owner/repo) or a local directory (local_root=path). Returns a flat list of files with path, type, size, and url (url is null for local)."""
    _require_code_graph_target(repo, local_root)
    if local_root and local_root.strip():
        return code_graph_tools.fetch_tree_local(
            local_root.strip(),
            path=path,
            recursive=recursive,
            max_depth=max(12, max_depth),
        )
    return code_graph_tools.fetch_tree(repo.strip(), path, ref, recursive, max_depth)


@mcp.tool()
def code_graph_build(
    repo: str = "",
    path: str = "",
    ref: str = "HEAD",
    language: str = "",
    max_files: int = 80,
    ignore_patterns: str = "",
    local_root: str = "",
) -> dict:
    """Build a code dependency graph from GitHub (repo=owner/repo) or from a local checkout (local_root). Extracts imports and returns nodes (files) and edges (import relationships)."""
    _require_code_graph_target(repo, local_root)
    lr = local_root.strip() or None
    return code_graph_tools.build_code_graph(
        repo.strip(), path, ref, language, max_files, ignore_patterns, local_root=lr
    )


# ─── Skill Tools (actual executable tools, replacing @mcp.prompt()) ───────────

@mcp.tool()
def review_pr(github_url: str) -> str:
    """Review a GitHub pull request: fetch details, analyze quality, and write a structured review."""
    repo, number = _parse_pr_url(github_url)

    pr = github_tools.get_issue(repo, number)
    all_prs = github_tools.list_pull_requests(repo, "open")

    # Build a short summary of the PR diff if available
    body = pr.get("body", "") or ""
    title = pr.get("title", "Untitled")
    state = pr.get("state", "unknown")
    labels = [lb.get("name", "") for lb in pr.get("labels", [])]
    user = pr.get("user", {}).get("login", "unknown") if isinstance(pr.get("user"), dict) else str(pr.get("user", ""))

    lines = [f"## Summary\nPR #{number}: **{title}** by @{user} (`{state}`)\n\n"]
    lines.append(f"```{pr.get('body', '') or ''}```\n\n")

    # Check for common issues
    issues = []
    if "wip" in title.lower() or "wip" in body.lower():
        issues.append("🟡 Warning: PR title or body contains 'WIP' — not ready for merge.")
    if "fix" not in title.lower() and "feat" not in title.lower() and "refactor" not in title.lower() and "chore" not in title.lower() and "fix:" not in title.lower() and "feat:" not in title.lower():
        issues.append("🔵 Suggestion: Consider using conventional commit prefixes (fix:, feat:, refactor:) in the PR title.")
    if len(body) < 50:
        issues.append("🟡 Warning: PR description is very short (< 50 chars) — may lack context for reviewers.")
    if any("security" in lb.lower() or "vuln" in lb.lower() for lb in labels):
        issues.append("🔴 Critical: PR is tagged with a security/vulnerability label.")
    if any("breaking" in lb.lower() for lb in labels):
        issues.append("🔴 Critical: PR is tagged as breaking change — requires careful review.")

    # Check if tests are mentioned
    has_tests = any(kw in body.lower() for kw in ["test", "unit test", "integration test", "e2e", "coverage"])
    if not has_tests:
        issues.append("🔵 Suggestion: No mention of tests in the description — consider adding test coverage.")

    lines.append("## Issues Found\n")
    if issues:
        for iss in issues:
            lines.append(f"- {iss}")
    else:
        lines.append("- No critical issues found.\n")

    lines.append("\n## Positive Highlights\n")
    if has_tests:
        lines.append("- PR description mentions testing / test coverage.")
    if len(body) > 200:
        lines.append("- Detailed PR description with good context.")
    if not issues:
        lines.append("- No obvious issues detected by automated checks.")

    lines.append(f"\n## Overall Assessment\n")
    if any("Critical" in i for i in issues):
        lines.append("**Request Changes** — Critical issues need to be addressed before merge.")
    elif any("Warning" in i for i in issues):
        lines.append("**Needs Discussion** — Minor concerns; can merge with caution.")
    else:
        lines.append("**Approve** — No blocking issues found.")

    return "\n".join(lines)


@mcp.tool()
def summarize_issues(github_url: str) -> str:
    repo = _parse_repo_url(github_url)
    issues = github_tools.list_issues(repo, "open")

    total = len(issues)
    categories: dict[str, list[dict]] = {"bug": [], "feature": [], "docs": [], "performance": [], "other": []}

    keywords = {
        "bug": ["bug", "fix", "issue", "error", "crash", "fail", "regression"],
        "feature": ["feature", "add", "new", "implement", "support", "enable"],
        "docs": ["doc", "readme", "guide", "tutorial", "example"],
        "performance": ["perf", "slow", "optim", "fast", "speed", "bottleneck", "latency"],
    }

    for issue in issues:
        title = (issue.get("title", "") or "").lower()
        body = (issue.get("body", "") or "").lower()
        text = f"{title} {body}"
        matched = False
        for cat, kws in keywords.items():
            if any(kw in text for kw in kws):
                categories[cat].append(issue)
                matched = True
                break
        if not matched:
            categories["other"].append(issue)

    # Top 3 by number of reactions if available, otherwise first 3
    scored: list[dict] = []
    for issue in issues:
        score = 0
        if isinstance(issue.get("reactions"), dict):
            score = issue["reactions"].get("+1", 0) + issue["reactions"].get("heart", 0)
        elif isinstance(issue.get("reactions"), (int, float)):
            score = issue["reactions"]
        scored.append((score, issue))
    scored.sort(key=lambda x: x[0], reverse=True)
    top3 = scored[:3]

    lines = [f"## Open Issues Overview\nTotal: **{total}** open issues.\n\n"]
    for cat, lst in categories.items():
        if lst:
            lines.append(f"- **{cat}**: {len(lst)}")
    lines.append("\n## Top Priority Issues\n")
    for score, issue in top3:
        num = issue.get("number", "?")
        title = issue.get("title", "Untitled")
        lines.append(f"- **#{num}: {title}** (reactions: {score})")
    lines.append("\n## Themes & Patterns\n")
    if categories["other"]:
        lines.append(f"- {len(categories['other'])} issue(s) don't fit standard categories — may need manual triage.")
    if categories["bug"]:
        lines.append(f"- Bugs make up {len(categories['bug'])}/{total} issues — consider prioritizing fixes.")
    return "\n".join(lines)


@mcp.tool()
def onboard_repo(github_url: str) -> str:
    repo = _parse_repo_url(github_url)

    # Try common entry-point files
    entry_files = ["README.md", "README.rst", "README"]
    stack_files = ["package.json", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "setup.py"]
    all_entries = entry_files + stack_files

    readme = ""
    stack_info = ""
    for fname in all_entries:
        try:
            content = github_tools.get_file(repo, fname)
            if fname in entry_files:
                readme = content
            else:
                stack_info = content
        except Exception:
            pass

    issues = github_tools.list_issues(repo, "open")
    prs = github_tools.list_pull_requests(repo, "open")

    lines = [f"## What This Project Does\n"]
    if readme:
        first_lines = "\n".join(readme.split("\n")[:15])
        lines.append(first_lines)
    else:
        lines.append("No README found.")

    lines.append("\n## Tech Stack\n")
    if stack_info:
        lines.append(f"```\n{stack_info[:1000]}\n```")
    else:
        lines.append("No standard manifest file found.")

    lines.append(f"\n## How to Get Started\n")
    if readme:
        setup_lines = [l.strip() for l in readme.split("\n") if l.strip().startswith(("```", "$", "pip", "npm", "cargo", "go ", "docker", "gradle", "make"))]
        if setup_lines:
            lines.extend(setup_lines[:10])
        else:
            lines.append("See the README for setup instructions.")
    else:
        lines.append("No README found — check the repo for setup instructions.")

    lines.append(f"\n## Current State\nOpen issues: **{len(issues)}** | Open PRs: **{len(prs)}**\n")
    if issues:
        lines.append("\n### Open Issues\n")
        for iss in issues[:10]:
            lines.append(f"- **#{iss.get('number', '?')}**: {iss.get('title', 'Untitled')}")
    if prs:
        lines.append("\n### Open PRs\n")
        for pr in prs[:10]:
            lines.append(f"- **#{pr.get('number', '?')}**: {pr.get('title', 'Untitled')}")

    return "\n".join(lines)


@mcp.tool()
def read_github_project(scope: str, owner: str = "", repo: str = "", project_number: int = 0) -> str:
    """Read a GitHub Project v2 board: list projects if no number given, otherwise fetch items and fields."""
    projects = github_tools.list_projects_v2(scope, owner or None, repo or None, 30)

    if project_number == 0:
        lines = ["## GitHub Projects (v2)\n"]
        if not projects:
            lines.append("No projects found for the given scope.")
        else:
            for p in projects:
                num = p.get("number", "?")
                title = p.get("title", "Untitled")
                url = p.get("url", "")
                state = p.get("state", "")
                lines.append(f"- **#{num}**: {title} (`{state}`) — [{url}]({url})")
        return "\n".join(lines)

    project = github_tools.get_project_v2(scope, owner, project_number, repo or "", 50)

    lines = [f"## Project #{project_number}: {project.get('title', 'Untitled')}\n"]
    if project.get("short_description"):
        lines.append(project["short_description"] + "\n")

    # Show field schema
    fields = project.get("fields", [])
    if fields:
        lines.append("### Field Schema\n")
        for f in fields:
            lines.append(f"- **{f.get('name', '?')}**: {f.get('type', '?')}")

    # Show items
    items = project.get("items", [])
    if items:
        lines.append(f"\n### Items ({len(items)})\n")
        lines.append("| Title | Type | State |")
        lines.append("|-------|------|-------|")
        for item in items[:50]:
            title = item.get("title", "Untitled")
            type_ = item.get("type", "?")
            fields = item.get("fields", [])
            state_val = ""
            for f in fields:
                if f.get("type") == "status":
                    state_val = f.get("value", {}).get("name", "") or f.get("value", "")
                    break
            lines.append(f"| {title} | {type_} | {state_val} |")

        if len(items) > 50:
            lines.append(f"\n*... and {len(items) - 50} more items.*")
    else:
        lines.append("\nNo items found in this project.")

    return "\n".join(lines)


@mcp.tool()
def review_design(figma_url: str) -> str:
    file_key, node_id = _parse_figma_url(figma_url)

    file_meta = figma_tools.get_file(file_key)
    components = figma_tools.list_components(file_key)

    node_data = None
    if node_id:
        try:
            node_data = figma_tools.get_file_nodes(file_key, [node_id])
        except Exception:
            pass

    lines = ["## Design Overview\n"]
    name = file_meta.get("name", "Untitled")
    role = file_meta.get("role", "")
    lines.append(f"**{name}**" + (f" (role: {role})" if role else "") + "\n")

    lines.append("## Component Inventory\n")
    if components:
        for comp in components[:30]:
            comp_name = comp.get("name", "?")
            comp_id = comp.get("node_id", "?")
            lines.append(f"- `{comp_name}` (`{comp_id}`)")
        if len(components) > 30:
            lines.append(f"\n*... and {len(components) - 30} more components.*")
    else:
        lines.append("No published components found.\n")

    # Node-level analysis
    if node_data and isinstance(node_data.get("nodes"), dict):
        for nid, node in node_data["nodes"].items():
            if node:
                lines.append(f"\n## Node: {nid}\n")
                lines.append(f"- **Type**: {node.get('type', '?')}\n")
                lines.append(f"- **Name**: {node.get('name', '?')}\n")
                if node.get("absoluteBoundingBox"):
                    bb = node["absoluteBoundingBox"]
                    lines.append(f"- **Bounds**: {bb.get('width', '?')}×{bb.get('height', '?')} at ({bb.get('x', '?')}, {bb.get('y', '?')})\n")

    issues = []
    if not components:
        issues.append("🔵 Suggestion: No published components found — consider extracting reusable elements into components.")
    if len(issues) > 2:
        issues.append("🔵 Suggestion: Consider adding loading, empty, and error states.")

    lines.append("## Issues Found\n")
    if issues:
        for iss in issues:
            lines.append(f"- {iss}")
    else:
        lines.append("- No critical issues found.\n")

    lines.append("\n## Overall Assessment\n")
    if node_data:
        lines.append("Ready for development — node-level details available.")
    else:
        lines.append("Review file-level overview; link a specific node for detailed analysis.")

    return "\n".join(lines)


@mcp.tool()
def list_team_files(team_id: str) -> str:
    projects = figma_tools.list_projects(team_id)

    lines = [f"## Figma Projects & Files for Team {team_id}\n"]
    if not projects:
        lines.append("No projects found for this team.")
        return "\n".join(lines)

    for proj in projects:
        proj_id = proj.get("id", "?")
        proj_name = proj.get("name", "Untitled")
        lines.append(f"### {proj_name} (`{proj_id}`)\n")

        files = figma_tools.list_project_files(proj_id)
        if files:
            for f in files:
                fname = f.get("name", "?")
                fkey = f.get("key", "?")
                updated = f.get("last_modified", "?")
                lines.append(f"- **{fname}** — `{fkey}` — last modified: {updated}")
        else:
            lines.append("- No files in this project.\n")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def summarize_page(url_or_id: str) -> str:
    page_id = _parse_notion_id(url_or_id)

    props = notion_tools.get_page(page_id)
    content = notion_tools.get_page_content(page_id)

    # Extract title from properties
    title = ""
    props_data = props.get("properties", {})
    for prop_name, prop_val in props_data.items():
        if prop_val.get("type") == "title" and isinstance(prop_val.get("title"), list):
            title = "".join(t.get("plain_text", "") for t in prop_val["title"])
            break
    if not title:
        title = props.get("title", props.get("name", "Untitled"))

    # Extract text content
    text_blocks = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                text = block.get("plain_text", "") or block.get("text", {}).get("content", "") or ""
                if text:
                    text_blocks.append(text)
    elif isinstance(content, str):
        text_blocks.append(content)

    full_text = "\n".join(text_blocks)

    lines = [f"## Page Title\n**{title}**\n"]

    # Summary (first 3-4 sentences)
    sentences = full_text.split(". ")
    summary_parts = sentences[:min(4, len(sentences))]
    summary = ". ".join(summary_parts)
    if summary and not summary.endswith("."):
        summary += "."
    lines.append(f"## Summary\n{summary}\n")

    # Key points
    lines.append("## Key Points\n")
    if text_blocks:
        for block in text_blocks[:15]:
            block = block.strip()
            if block and len(block) > 10:
                lines.append(f"- {block}")
    else:
        lines.append("- No text content found.")

    return "\n".join(lines)


@mcp.tool()
def search_and_summarize(query: str) -> str:
    results = notion_tools.search(query)

    lines = [f"## Search Results for \"{query}\"\n"]
    if not results:
        lines.append("No results found.")
        return "\n".join(lines)

    best_match = None
    best_score = 0

    for i, result in enumerate(results[:5]):
        rtype = result.get("object", "page")
        title = result.get("properties", {}).get("title", [{}])
        if isinstance(title, list):
            title_text = "".join(t.get("plain_text", "") for t in title) if title else "Untitled"
        elif isinstance(title, dict):
            title_text = title.get("title", [{}])[0].get("plain_text", "Untitled") if title.get("title") else "Untitled"
        else:
            title_text = str(result.get("title", result.get("name", "Untitled")))

        lines.append(f"### {i + 1}. {title_text} (**{rtype}**)\n")
        lines.append(f"- **ID**: `{result.get('id', '?')}`\n")

        # Fetch content for pages
        if rtype == "page":
            try:
                content = notion_tools.get_page_content(result["id"])
                text_parts = []
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            t = block.get("plain_text", "") or block.get("text", {}).get("content", "") or ""
                            if t:
                                text_parts.append(t)
                summary = " ".join(text_parts[:3])
                lines.append(f"_Summary_: {summary}\n")
                score = len(text_parts)
            except Exception:
                lines.append("_Could not fetch content._\n")
                score = 0
        elif rtype == "database":
            try:
                schema = notion_tools.get_database(result["id"])
                prop_names = [p.get("name", "?") for p in schema.get("properties", {}).values()]
                lines.append(f"_Schema_: {', '.join(prop_names[:10])}\n")
                score = len(prop_names)
            except Exception:
                lines.append("_Could not fetch schema._\n")
                score = 0
        else:
            score = 0

        if score > best_score:
            best_score = score
            best_match = title_text

    lines.append("\n## Best Match\n")
    if best_match:
        lines.append(f"**{best_match}** — most relevant result for the query.")
    else:
        lines.append("No clear best match.")

    return "\n".join(lines)


@mcp.tool()
def summarize_database(url_or_id: str) -> str:
    db_id = _parse_notion_id(url_or_id)

    schema = notion_tools.get_database(db_id)
    rows = notion_tools.query_database(db_id)

    name = schema.get("title", [{}])[0].get("plain_text", "Untitled") if schema.get("title") else "Untitled"

    lines = [f"## Database Overview\n**{name}**\n"]

    lines.append("## Schema\n")
    for prop_name, prop_data in schema.get("properties", {}).items():
        ptype = prop_data.get("type", "?")
        lines.append(f"- **{prop_name}**: `{ptype}`")

    lines.append(f"\n## Contents Summary\nTotal rows: **{len(rows)}**\n")
    if rows:
        # Show first few rows as a summary
        sample = rows[:5]
        prop_names = list(schema.get("properties", {}).keys())
        for i, row in enumerate(sample):
            props = row.get("properties", {})
            vals = []
            for pn in prop_names[:5]:
                pv = props.get(pn, {})
                if isinstance(pv, dict):
                    if pv.get("type") == "title":
                        parts = pv.get("title", [])
                        val = parts[0].get("plain_text", "") if parts else ""
                    elif pv.get("type") == "rich_text":
                        parts = pv.get("rich_text", [])
                        val = parts[0].get("plain_text", "") if parts else ""
                    else:
                        val = str(pv.get(pv.get("type", ""), pv))
                else:
                    val = str(pv)
                vals.append(f"{pn}: {val}")
            lines.append(f"- Row {i + 1}: {', '.join(vals)}")
        if len(rows) > 5:
            lines.append(f"\n*... and {len(rows) - 5} more rows.*")

    return "\n".join(lines)


@mcp.tool()
def code_graph(
    github_url: str = "",
    path: str = "",
    language: str = "",
    max_files: int = 80,
    ignore_patterns: str = "",
    local_root: str = "",
) -> str:
    """Generate a code dependency graph from a GitHub repository (github_url) or a local project directory (local_root)."""
    if local_root.strip() and github_url.strip():
        raise ValueError("Pass either github_url or local_root, not both.")
    lr = local_root.strip() or None
    if lr:
        graph = code_graph_tools.build_code_graph("", path, "HEAD", language, max_files, ignore_patterns, local_root=lr)
    else:
        if not github_url.strip():
            raise ValueError("Provide github_url or local_root.")
        repo = _parse_repo_url(github_url)
        graph = code_graph_tools.build_code_graph(repo, path, "HEAD", language, max_files, ignore_patterns)

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    lang_breakdown = graph.get("stats", {}).get("language_breakdown", {})

    lines = ["## Code Graph Summary\n"]
    if graph.get("source") == "local":
        lines.append(f"- **Source**: local — `{graph.get('local_root', local_root)}`")
    else:
        lines.append(f"- **Repository**: `{graph.get('repo', '')}`")
    lines.append(f"- **Total files analyzed**: {len(nodes)}")
    lines.append(f"- **Total dependency edges**: {len(edges)}")
    if lang_breakdown:
        lines.append(f"- **Languages**: {', '.join(f'{k}: {v}' for k, v in lang_breakdown.items())}")

    # Hub detection: files with most edges
    edge_counts: dict[str, int] = {}
    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        edge_counts[src] = edge_counts.get(src, 0) + 1
        edge_counts[tgt] = edge_counts.get(tgt, 0) + 1

    sorted_edges = sorted(edge_counts.items(), key=lambda x: x[1], reverse=True)
    hubs = sorted_edges[:10]

    lines.append("\n## Key Modules (Hub Detection)\n")
    if hubs:
        for path, count in hubs:
            lines.append(f"- **{path}**: {count} edges")
    else:
        lines.append("- No hub files detected.")

    # Isolated files
    connected = set(e.get("source") for e in edges) | set(e.get("target") for e in edges)
    isolated = [n.get("path", "") for n in nodes if n.get("path", "") not in connected]

    lines.append("\n## Isolated Files\n")
    if isolated:
        for f in isolated[:15]:
            lines.append(f"- `{f}`")
        if len(isolated) > 15:
            lines.append(f"\n*... and {len(isolated) - 15} more isolated files.*")
    else:
        lines.append("- No isolated files found.")

    # Circular dependencies
    circular = []
    edge_set = {(e.get("source"), e.get("target")) for e in edges}
    for src, tgt in edge_set:
        if (tgt, src) in edge_set and src < tgt:
            circular.append((src, tgt))

    lines.append("\n## Architecture Observations\n")
    if circular:
        lines.append(f"- **Circular dependencies found**: {len(circular)}")
        for a, b in circular[:5]:
            lines.append(f"  - `{a}` ↔ `{b}`")
    else:
        lines.append("- No circular dependencies detected.")

    if hubs:
        top_hub = hubs[0][0]
        lines.append(f"- **Core module**: `{top_hub}` ({hubs[0][1]} edges)")

    # Mermaid visualization
    lines.append("\n## Graph Visualization (Mermaid)\n```mermaid\ngraph TD\n")
    top_edges = sorted(edges, key=lambda e: edge_counts.get(e.get("source", ""), 0) + edge_counts.get(e.get("target", ""), 0), reverse=True)[:30]
    for edge in top_edges:
        src = edge.get("source", "?").replace(".", "_").replace("/", "_")
        tgt = edge.get("target", "?").replace(".", "_").replace("/", "_")
        lines.append(f"    {src} --> {tgt}\n")
    lines.append("```\n")

    if len(edges) > 30:
        lines.append(f"*Top 30 edges shown. {len(edges) - 30} more edges omitted.*")

    return "\n".join(lines)


@mcp.tool()
def code_graph_for_language(
    github_url: str = "",
    language: str = "",
    path: str = "",
    max_files: int = 60,
    local_root: str = "",
) -> str:
    """Generate a code dependency graph filtered to a single language. Set github_url or local_root (not both); language is required."""
    if not language.strip():
        raise ValueError("language is required (e.g. typescript, python).")
    if local_root.strip() and github_url.strip():
        raise ValueError("Pass either github_url or local_root, not both.")
    lr = local_root.strip() or None
    if lr:
        graph = code_graph_tools.build_code_graph("", path, "HEAD", language.strip(), max_files, "", local_root=lr)
    else:
        if not github_url.strip():
            raise ValueError("Provide github_url or local_root.")
        repo = _parse_repo_url(github_url)
        graph = code_graph_tools.build_code_graph(repo, path, "HEAD", language.strip(), max_files, "")

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    lines = [f"## {language.strip().title()} Dependency Graph\n"]
    if graph.get("source") == "local":
        lines.append(f"- **Source**: local — `{graph.get('local_root', local_root)}`\n")
    else:
        lines.append(f"- **Repository**: `{graph.get('repo', '')}`\n")
    lines.append(f"- **{language} files analyzed**: {len(nodes)}")
    lines.append(f"- **Dependency edges**: {len(edges)}\n")

    # Group by directory
    dirs: dict[str, list[str]] = {}
    for node in nodes:
        npath = node.get("path", "")
        d = npath.rsplit("/", 1)[0] if "/" in npath else "(root)"
        dirs.setdefault(d, []).append(npath)

    lines.append("## Module Map\n")
    for d, files in sorted(dirs.items()):
        lines.append(f"### `{d}`\n")
        for f in files[:10]:
            lines.append(f"- `{f}`")
        if len(files) > 10:
            lines.append(f"\n*... and {len(files) - 10} more.*")

    # Entry points and core libs
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    for edge in edges:
        tgt = edge.get("target", "")
        src = edge.get("source", "")
        incoming[tgt] = incoming.get(tgt, 0) + 1
        outgoing[src] = outgoing.get(src, 0) + 1

    lines.append("\n## Key Insights\n")
    core = sorted(incoming.items(), key=lambda x: x[1], reverse=True)[:5]
    if core:
        lines.append("### Core libraries (most imported)")
        for path, count in core:
            lines.append(f"- `{path}` ({count} imports)")

    entries = [(p, c) for p, c in outgoing.items() if p not in incoming]
    if entries:
        lines.append("\n### Entry points (import others but not imported)")
        for path, count in entries[:5]:
            lines.append(f"- `{path}` ({count} outgoing)")

    all_paths = {n.get("path", "") for n in nodes}
    orphans = [p for p in all_paths if p not in incoming and p not in outgoing]
    if orphans:
        lines.append(f"\n### Orphan modules ({len(orphans)})")
        for p in orphans[:10]:
            lines.append(f"- `{p}`")

    lines.append("\n```mermaid\ngraph TD\n")
    for edge in edges[:25]:
        src = edge.get("source", "?").replace(".", "_").replace("/", "_")
        tgt = edge.get("target", "?").replace(".", "_").replace("/", "_")
        lines.append(f"    {src} --> {tgt}\n")
    lines.append("```\n")

    return "\n".join(lines)


@mcp.tool()
def code_graph_subpath(
    github_url: str = "",
    subpath: str = "",
    language: str = "",
    max_files: int = 40,
    local_root: str = "",
) -> str:
    """Generate a code dependency graph for a subdirectory. Set github_url or local_root (not both); subpath is required."""
    if not subpath.strip():
        raise ValueError("subpath is required (e.g. src/components).")
    if local_root.strip() and github_url.strip():
        raise ValueError("Pass either github_url or local_root, not both.")
    lr = local_root.strip() or None
    if lr:
        graph = code_graph_tools.build_code_graph("", subpath, "HEAD", language, max_files, "", local_root=lr)
    else:
        if not github_url.strip():
            raise ValueError("Provide github_url or local_root.")
        repo = _parse_repo_url(github_url)
        graph = code_graph_tools.build_code_graph(repo, subpath, "HEAD", language, max_files, "")

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    lines = [f"## Subdirectory Graph: `{subpath}`\n"]
    if graph.get("source") == "local":
        lines.append(f"- **Source**: local — `{graph.get('local_root', local_root)}`\n")
    lines.append(f"- **Files analyzed**: {len(nodes)}")

    internal_edges = [e for e in edges if subpath in e.get("source", "") and subpath in e.get("target", "")]
    external_edges = [e for e in edges if subpath not in e.get("source", "") or subpath not in e.get("target", "")]
    lines.append(f"- **Internal edges**: {len(internal_edges)}")
    lines.append(f"- **External edges**: {len(external_edges)}")

    # External dependencies
    external_deps = set()
    for e in external_edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if subpath in src:
            external_deps.add(tgt)
        if subpath in tgt:
            external_deps.add(src)

    lines.append(f"\n## Mermaid Graph\n```mermaid\ngraph TD\n")
    for edge in edges[:20]:
        src = edge.get("source", "?").replace(".", "_").replace("/", "_")
        tgt = edge.get("target", "?").replace(".", "_").replace("/", "_")
        lines.append(f"    {src} --> {tgt}\n")
    lines.append("```\n")

    lines.append("## Boundary Analysis\n")
    if external_deps:
        lines.append(f"### External dependencies ({len(external_deps)})")
        for d in sorted(external_deps)[:10]:
            lines.append(f"- `{d}`")
    else:
        lines.append("- No external dependencies detected.")

    if not external_edges:
        lines.append("\nThis subdirectory appears to be **self-contained** with no external connections.")

    return "\n".join(lines)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Stderr only — stdout/stdin are the MCP wire protocol.
    sys.stderr.write(
        "ISIEE MCP: stdio server running (waiting on stdin). "
        "This is normal. Cursor launches this for you via mcp.json — "
        "you usually do not run server.py in a terminal. "
        "Exit: Ctrl+C once.\n"
    )
    if _isiee_env_flag("ISIEE_LOG_TOOLS"):
        sys.stderr.write(
            "ISIEE MCP: ISIEE_LOG_TOOLS=1 — each tools/call is logged to stderr "
            "(set FASTMCP_LOG_LEVEL=DEBUG for more MCP noise).\n"
        )
    sys.stderr.flush()
    try:
        mcp.run()
    except KeyboardInterrupt:
        sys.stderr.write("ISIEE MCP: stopped.\n")
        sys.stderr.flush()
        raise SystemExit(0) from None
