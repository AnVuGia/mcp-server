"""
GitHub skills — prompt templates that guide Cursor through multi-step GitHub tasks.
"""

import re


def _parse_pr_url(github_url: str) -> tuple[str, int]:
    """Extract owner/repo and PR number from a GitHub PR URL."""
    match = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", github_url)
    if not match:
        raise ValueError(f"Could not parse GitHub PR URL: {github_url}")
    return match.group(1), int(match.group(2))


def _parse_repo_url(github_url: str) -> str:
    """Extract owner/repo from a GitHub repo URL."""
    match = re.search(r"github\.com/([^/]+/[^/]+?)(?:\.git|/|$)", github_url)
    if not match:
        raise ValueError(f"Could not parse GitHub repo URL: {github_url}")
    return match.group(1)


def review_pr(github_url: str) -> str:
    repo, number = _parse_pr_url(github_url)
    return f"""Review the GitHub pull request #{number} in {repo}.

Follow these steps:

1. Fetch the PR using the `github_get_issue` tool with repo="{repo}" and number={number}.
2. Read the PR title, description, and body carefully to understand the intent.
3. Fetch the list of open PRs with `github_list_pull_requests` (repo="{repo}") to understand the broader context.
4. Analyze the PR based on the information retrieved. Focus on:
   - **Purpose**: Does the description clearly explain what and why?
   - **Correctness**: Are there any obvious bugs or logic errors?
   - **Security**: Any potential vulnerabilities (injection, auth bypass, secrets exposed)?
   - **Code quality**: Readability, naming, duplication, unnecessary complexity.
   - **Tests**: Does the PR mention or include test coverage?
   - **Breaking changes**: Could this break existing functionality?

5. Write a structured review with these sections:
   ## Summary
   One paragraph describing what this PR does.

   ## Issues Found
   Bullet list of bugs, risks, or concerns (label each as 🔴 Critical / 🟡 Warning / 🔵 Suggestion).

   ## Positive Highlights
   What is done well.

   ## Overall Assessment
   Approve / Request Changes / Needs Discussion — with a one-line rationale.
"""


def summarize_issues(github_url: str) -> str:
    repo = _parse_repo_url(github_url)
    return f"""Summarize the open issues for the GitHub repository {repo}.

Follow these steps:

1. Fetch all open issues using `github_list_issues` with repo="{repo}" and state="open".
2. Group the issues by theme or category (e.g. bug, feature request, documentation, performance).
3. Identify the top 3 most critical or impactful issues based on their titles and descriptions.
4. Write a summary with these sections:

   ## Open Issues Overview
   Total count and a brief breakdown by category.

   ## Top Priority Issues
   The 3 most important issues with title, number, and one-line explanation of why they matter.

   ## Themes & Patterns
   Any recurring problems or feature gaps you notice across the issues.
"""


def read_github_project(scope: str, owner: str = "", repo: str = "", project_number: int = 0) -> str:
    """
    Prompt template: list GitHub Projects v2 or read one board with items and custom fields.
    project_number 0 means list only; otherwise fetch that project.
    """
    list_hint = (
        'Call `github_list_projects_v2` with scope, owner, repo, and first=30 (scope "viewer" ignores owner). '
        "Summarize number, title, and url for each project."
    )
    if project_number == 0:
        return f"""Read the user's GitHub Projects (v2) boards.

1. {list_hint}
2. If the user asked for a specific project by name or number, pick the matching entry from the list (or ask which one if ambiguous).
3. If they only wanted a catalog, stop after the summary.

Scope reference:
- **viewer**: authenticated user's projects (empty owner)
- **user**: another user's login in owner (rare)
- **org**: organization login in owner
- **repository**: owner = repo owner, repo = repository name
"""

    get_steps = (
        f"Call `github_get_project_v2` with scope={scope!r}, owner={owner!r}, project_number={project_number}, "
        f"repo={repo!r}, items_first=50. "
    )
    return f"""Read GitHub Project v2 #{project_number} for the given scope.

1. {get_steps}
2. Present a concise report:
   - **Project**: title, url, short_description if present
   - **Items table**: each row = title, type (Issue / PullRequest / DraftIssue), repository (if any), state, and **custom fields** (especially Status / iteration / priority when present in `fields`)
3. If `items_page_info.has_next_page` is true, say how many items were shown and offer to call again with `items_after` set to `items_page_info.end_cursor` to load more.

If the call fails with access errors, remind the user that `GITHUB_TOKEN` needs read access to GitHub Projects (classic PAT: `read:project`; fine-grained: Projects read).
"""


def onboard_repo(github_url: str) -> str:
    repo = _parse_repo_url(github_url)
    return f"""Give a developer onboarding overview of the GitHub repository {repo}.

Follow these steps:

1. List the repository's files using `github_get_file` for common entry points:
   - Try "README.md", then "README.rst" if not found.
   - Try "package.json", "pyproject.toml", "Cargo.toml", or "go.mod" to identify the stack.
2. Read the README content fully.
3. Fetch open issues with `github_list_issues` (repo="{repo}", state="open") to understand current work.
4. Fetch open PRs with `github_list_pull_requests` (repo="{repo}", state="open").

5. Write an onboarding guide with:

   ## What This Project Does
   A plain-language description.

   ## Tech Stack
   Languages, frameworks, and key dependencies identified.

   ## How to Get Started
   Key setup steps inferred from the README.

   ## Current State
   Summary of open issues and PRs — what is the team working on right now?
"""
