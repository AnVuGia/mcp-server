import os
from github import Github, GithubException


def get_client() -> Github:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN is not set")
    return Github(token)


def list_repos(org: str | None = None) -> list[dict]:
    """List repositories for the authenticated user or a given org."""
    g = get_client()
    if org:
        repos = g.get_organization(org).get_repos()
    else:
        repos = g.get_user().get_repos()
    return [
        {"name": r.full_name, "description": r.description, "url": r.html_url, "private": r.private}
        for r in repos
    ]


def get_file(repo: str, path: str, ref: str = "HEAD") -> str:
    """Get the content of a file in a repository."""
    g = get_client()
    content = g.get_repo(repo).get_contents(path, ref=ref)
    if isinstance(content, list):
        raise ValueError(f"'{path}' is a directory, not a file")
    return content.decoded_content.decode("utf-8")


def list_issues(repo: str, state: str = "open") -> list[dict]:
    """List issues in a repository."""
    g = get_client()
    issues = g.get_repo(repo).get_issues(state=state)
    return [
        {"number": i.number, "title": i.title, "state": i.state, "url": i.html_url, "body": i.body}
        for i in issues
    ]


def get_issue(repo: str, number: int) -> dict:
    """Get a specific issue by number."""
    g = get_client()
    i = g.get_repo(repo).get_issue(number)
    return {"number": i.number, "title": i.title, "state": i.state, "url": i.html_url, "body": i.body}


def list_pull_requests(repo: str, state: str = "open") -> list[dict]:
    """List pull requests in a repository."""
    g = get_client()
    prs = g.get_repo(repo).get_pulls(state=state)
    return [
        {"number": pr.number, "title": pr.title, "state": pr.state, "url": pr.html_url, "body": pr.body}
        for pr in prs
    ]
