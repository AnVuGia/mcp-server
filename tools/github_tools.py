import base64
import json
import subprocess

# GitHub Projects (classic) are deprecated; these calls target Projects v2 (GraphQL).

_PROJECT_V2_BODY = """
fragment ProjectV2ReadBody on ProjectV2 {
  title
  url
  shortDescription
  items(first: $itemsFirst, after: $itemsAfter) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      content {
        __typename
        ... on Issue {
          title
          number
          url
          state
          repository {
            nameWithOwner
          }
        }
        ... on PullRequest {
          title
          number
          url
          state
          repository {
            nameWithOwner
          }
        }
        ... on DraftIssue {
          title
          body
        }
      }
      fieldValues(first: 24) {
        nodes {
          __typename
          ... on ProjectV2ItemFieldSingleSelectValue {
            name
            field {
              ... on ProjectV2SingleSelectField {
                name
              }
            }
          }
          ... on ProjectV2ItemFieldTextValue {
            text
            field {
              ... on ProjectV2FieldCommon {
                name
              }
            }
          }
          ... on ProjectV2ItemFieldNumberValue {
            number
            field {
              ... on ProjectV2FieldCommon {
                name
              }
            }
          }
          ... on ProjectV2ItemFieldDateValue {
            date
            field {
              ... on ProjectV2FieldCommon {
                name
              }
            }
          }
        }
      }
    }
  }
}
"""

_QUERY_LIST_VIEWER = """
query ListViewerProjects($first: Int!) {
  viewer {
    projectsV2(first: $first) {
      nodes {
        number
        title
        url
      }
    }
  }
}
"""

_QUERY_LIST_USER = """
query ListUserProjects($login: String!, $first: Int!) {
  user(login: $login) {
    projectsV2(first: $first) {
      nodes {
        number
        title
        url
      }
    }
  }
}
"""

_QUERY_LIST_ORG = """
query ListOrgProjects($login: String!, $first: Int!) {
  organization(login: $login) {
    projectsV2(first: $first) {
      nodes {
        number
        title
        url
      }
    }
  }
}
"""

_QUERY_LIST_REPO = """
query ListRepoProjects($owner: String!, $name: String!, $first: Int!) {
  repository(owner: $owner, name: $name) {
    projectsV2(first: $first) {
      nodes {
        number
        title
        url
      }
    }
  }
}
"""

_QUERY_GET_ORG_PROJECT = (
    """
query GetOrgProject($login: String!, $number: Int!, $itemsFirst: Int!, $itemsAfter: String) {
  organization(login: $login) {
    projectV2(number: $number) {
      ...ProjectV2ReadBody
    }
  }
}
"""
    + _PROJECT_V2_BODY
)

_QUERY_GET_USER_PROJECT = (
    """
query GetUserProject($login: String!, $number: Int!, $itemsFirst: Int!, $itemsAfter: String) {
  user(login: $login) {
    projectV2(number: $number) {
      ...ProjectV2ReadBody
    }
  }
}
"""
    + _PROJECT_V2_BODY
)

_QUERY_GET_REPO_PROJECT = (
    """
query GetRepoProject($owner: String!, $name: String!, $number: Int!, $itemsFirst: Int!, $itemsAfter: String) {
  repository(owner: $owner, name: $name) {
    projectV2(number: $number) {
      ...ProjectV2ReadBody
    }
  }
}
"""
    + _PROJECT_V2_BODY
)

_QUERY_GET_VIEWER_PROJECT = (
    """
query GetViewerProject($number: Int!, $itemsFirst: Int!, $itemsAfter: String) {
  viewer {
    projectV2(number: $number) {
      ...ProjectV2ReadBody
    }
  }
}
"""
    + _PROJECT_V2_BODY
)


def _gh(*args: str, input: str | None = None) -> str:
    """Run a gh CLI command and return stdout. Raises on non-zero exit."""
    result = subprocess.run(
        ["gh", *args],
        input=input,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"gh error: {result.stderr.strip()}")
    return result.stdout


def _graphql(query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables})
    raw = _gh("api", "graphql", "--input", "-", input=payload)
    data = json.loads(raw)
    if data.get("errors"):
        msgs = "; ".join(e.get("message", str(e)) for e in data["errors"])
        raise ValueError(f"GitHub GraphQL error: {msgs}")
    return data.get("data") or {}


def _field_entry(node: dict) -> tuple[str, str] | None:
    if not node:
        return None
    t = node.get("__typename", "")
    field = (node.get("field") or {}) if isinstance(node.get("field"), dict) else {}
    fname = field.get("name") or ""
    if t == "ProjectV2ItemFieldSingleSelectValue":
        val = node.get("name") or ""
    elif t == "ProjectV2ItemFieldTextValue":
        val = node.get("text") or ""
    elif t == "ProjectV2ItemFieldNumberValue":
        val = str(node.get("number")) if node.get("number") is not None else ""
    elif t == "ProjectV2ItemFieldDateValue":
        val = str(node.get("date") or "")
    else:
        return None
    return (fname or t, val)


def _parse_content(content: dict | None) -> dict:
    if not content:
        return {"type": "Unknown", "title": None, "number": None, "url": None, "repository": None, "state": None, "body": None}
    t = content.get("__typename", "Unknown")
    repo = content.get("repository") if isinstance(content.get("repository"), dict) else {}
    name_with_owner = repo.get("nameWithOwner") if repo else None
    if t == "DraftIssue":
        return {
            "type": "DraftIssue",
            "title": content.get("title"),
            "number": None,
            "url": None,
            "repository": None,
            "state": None,
            "body": content.get("body"),
        }
    return {
        "type": t,
        "title": content.get("title"),
        "number": content.get("number"),
        "url": content.get("url"),
        "repository": name_with_owner,
        "state": content.get("state"),
        "body": None,
    }


def list_projects_v2(
    scope: str,
    owner: str = "",
    repo: str = "",
    first: int = 30,
) -> list[dict]:
    """
    List GitHub Projects v2 boards.

    scope:
      - viewer: projects for the authenticated user (owner ignored)
      - user: projects for user login `owner`
      - org: projects for organization login `owner`
      - repository: projects linked to repo `owner`/`repo`
    """
    scope = scope.lower().strip()
    first = max(1, min(first, 100))
    if scope == "viewer":
        data = _graphql(_QUERY_LIST_VIEWER, {"first": first})
        viewer = data.get("viewer") or {}
        nodes = (viewer.get("projectsV2") or {}).get("nodes") or []
        return [{"number": n["number"], "title": n["title"], "url": n["url"]} for n in nodes if n]
    if scope == "user":
        if not owner:
            raise ValueError("owner must be the GitHub username when scope is user")
        data = _graphql(_QUERY_LIST_USER, {"login": owner, "first": first})
        user = data.get("user")
        if not user:
            raise ValueError(f"User not found or not visible: {owner}")
        nodes = (user.get("projectsV2") or {}).get("nodes") or []
        return [{"number": n["number"], "title": n["title"], "url": n["url"]} for n in nodes if n]
    if scope == "org":
        if not owner:
            raise ValueError("owner must be the organization login when scope is org")
        data = _graphql(_QUERY_LIST_ORG, {"login": owner, "first": first})
        org = data.get("organization")
        if not org:
            raise ValueError(f"Organization not found or not visible: {owner}")
        nodes = (org.get("projectsV2") or {}).get("nodes") or []
        return [{"number": n["number"], "title": n["title"], "url": n["url"]} for n in nodes if n]
    if scope == "repository":
        if not owner or not repo:
            raise ValueError("owner and repo are required when scope is repository (owner/repo name)")
        data = _graphql(_QUERY_LIST_REPO, {"owner": owner, "name": repo, "first": first})
        r = data.get("repository")
        if not r:
            raise ValueError(f"Repository not found or not visible: {owner}/{repo}")
        nodes = (r.get("projectsV2") or {}).get("nodes") or []
        return [{"number": n["number"], "title": n["title"], "url": n["url"]} for n in nodes if n]
    raise ValueError("scope must be viewer, user, org, or repository")


def get_project_v2(
    scope: str,
    owner: str,
    project_number: int,
    repo: str = "",
    items_first: int = 50,
    items_after: str | None = None,
) -> dict:
    """
    Read a single GitHub Project v2: metadata, board field values per item, linked issues/PRs.

    scope: viewer | org | user | repository — viewer uses the authenticated user.
    project_number: the project number from the project URL or list_projects_v2.
    items_after: GraphQL cursor for the next page when items_page_info.has_next_page is true.
    """
    scope = scope.lower().strip()
    items_first = max(1, min(items_first, 100))
    vars_base = {
        "number": project_number,
        "itemsFirst": items_first,
        "itemsAfter": items_after,
    }
    if scope == "viewer":
        data = _graphql(_QUERY_GET_VIEWER_PROJECT, vars_base)
        proj = ((data.get("viewer") or {}).get("projectV2")) or None
    elif scope == "org":
        if not owner:
            raise ValueError("owner must be the organization login when scope is org")
        data = _graphql(_QUERY_GET_ORG_PROJECT, {**vars_base, "login": owner})
        proj = ((data.get("organization") or {}).get("projectV2")) or None
    elif scope == "user":
        if not owner:
            raise ValueError("owner must be the GitHub username when scope is user")
        data = _graphql(_QUERY_GET_USER_PROJECT, {**vars_base, "login": owner})
        proj = ((data.get("user") or {}).get("projectV2")) or None
    elif scope == "repository":
        if not owner or not repo:
            raise ValueError("owner and repo are required when scope is repository")
        data = _graphql(
            _QUERY_GET_REPO_PROJECT,
            {"owner": owner, "name": repo, "number": project_number, "itemsFirst": items_first, "itemsAfter": items_after},
        )
        proj = ((data.get("repository") or {}).get("projectV2")) or None
    else:
        raise ValueError("scope must be viewer, org, user, or repository")

    if not proj:
        raise ValueError("Project not found, or gh CLI lacks read access to projects")

    items_conn = proj.get("items") or {}
    page_info = items_conn.get("pageInfo") or {}
    out_items: list[dict] = []
    for node in items_conn.get("nodes") or []:
        if not node:
            continue
        base = _parse_content(node.get("content") if isinstance(node.get("content"), dict) else None)
        fields: list[dict] = []
        for fv in (node.get("fieldValues") or {}).get("nodes") or []:
            if not isinstance(fv, dict):
                continue
            pair = _field_entry(fv)
            if pair:
                fields.append({"name": pair[0], "value": pair[1]})
        base["fields"] = fields
        out_items.append(base)

    return {
        "title": proj.get("title"),
        "url": proj.get("url"),
        "short_description": proj.get("shortDescription"),
        "items": out_items,
        "items_page_info": {
            "has_next_page": page_info.get("hasNextPage", False),
            "end_cursor": page_info.get("endCursor"),
        },
    }


def list_repos(org: str | None = None) -> list[dict]:
    """List repositories for the authenticated user or a given org."""
    args = ["repo", "list", "--json", "nameWithOwner,description,url,isPrivate", "--limit", "100"]
    if org:
        args.insert(2, org)
    raw = _gh(*args)
    repos = json.loads(raw)
    return [
        {
            "name": r["nameWithOwner"],
            "description": r.get("description"),
            "url": r["url"],
            "private": r["isPrivate"],
        }
        for r in repos
    ]


def get_file(repo: str, path: str, ref: str = "HEAD") -> str:
    """Get the content of a file in a repository."""
    raw = _gh("api", f"repos/{repo}/contents/{path}?ref={ref}")
    data = json.loads(raw)
    if isinstance(data, list):
        raise ValueError(f"'{path}' is a directory, not a file")
    content = data.get("content", "")
    encoding = data.get("encoding", "base64")
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8")
    return content


def list_issues(repo: str, state: str = "open") -> list[dict]:
    """List issues in a repository."""
    raw = _gh(
        "issue", "list",
        "--repo", repo,
        "--state", state,
        "--json", "number,title,state,url,body",
        "--limit", "100",
    )
    return json.loads(raw)


def get_issue(repo: str, number: int) -> dict:
    """Get a specific issue by number."""
    raw = _gh("issue", "view", str(number), "--repo", repo, "--json", "number,title,state,url,body")
    return json.loads(raw)


def list_pull_requests(repo: str, state: str = "open") -> list[dict]:
    """List pull requests in a repository."""
    raw = _gh(
        "pr", "list",
        "--repo", repo,
        "--state", state,
        "--json", "number,title,state,url,body",
        "--limit", "100",
    )
    return json.loads(raw)


def add_project_v2_draft_issue(project_node_id: str, title: str, body: str = "") -> str:
    """
    Add a draft issue to a GitHub Project v2 board.

    project_node_id: the GraphQL node ID of the project (e.g. PVT_kwHOBj4MN84BTxbG).
                     Obtain it via get_project_v2 or list_projects_v2 (the 'id' field).
    Returns the new project item's node ID.
    """
    query = """
mutation AddDraft($projectId: ID!, $title: String!, $body: String!) {
  addProjectV2DraftIssue(input: {projectId: $projectId, title: $title, body: $body}) {
    projectItem { id }
  }
}
"""
    data = _graphql(query, {"projectId": project_node_id, "title": title, "body": body})
    return data["addProjectV2DraftIssue"]["projectItem"]["id"]
