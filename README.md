# ISIEE MCP Server

A Python MCP (Model Context Protocol) server for Cursor that exposes tools to interact with GitHub, Figma, and Notion.

## Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (package manager)

## Installation

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### 2. Clone the repo and set up the environment

```bash
git clone <repo-url>
cd mcp-server

uv venv
uv pip install -r requirements.txt
```

### 3. Configure your API tokens

Copy the example env file and fill in your tokens:

```bash
cp .env.example .env
```

Edit `.env`:

```env
GITHUB_TOKEN=your_github_personal_access_token
FIGMA_TOKEN=your_figma_personal_access_token
NOTION_TOKEN=your_notion_integration_token
```

**Where to get each token:**

| Service | Where to generate |
|---------|------------------|
| GitHub  | github.com → Settings → Developer settings → Personal access tokens |
| Figma   | figma.com → Settings → Security → Personal access tokens |
| Notion  | notion.so/my-integrations → Create integration → copy Internal Integration Secret |

### 4. Connect to Cursor

Add the server to your Cursor MCP config at `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "isiee": {
      "command": "/path/to/mcp-server/.venv/bin/python",
      "args": ["/path/to/mcp-server/server.py"]
    }
  }
}
```

Replace `/path/to/mcp-server` with the absolute path to this repo. Then restart Cursor.

### 5. Start the server

```bash
.venv/bin/python server.py
```

Cursor manages the server process automatically via the MCP config, so you only need to run this manually for debugging.

---

## Available Tools

### GitHub

| Tool | Description |
|------|-------------|
| `github_list_repos` | List your repos, or all repos for a given org |
| `github_get_file` | Get the content of a file (`owner/repo`, `path`) |
| `github_list_issues` | List issues in a repo (state: `open`, `closed`, `all`) |
| `github_get_issue` | Get a specific issue by number |
| `github_list_pull_requests` | List pull requests (state: `open`, `closed`, `all`) |

### Figma

| Tool | Description |
|------|-------------|
| `figma_get_file` | Get metadata for a Figma file by its file key |
| `figma_get_nodes` | Get specific nodes by their IDs |
| `figma_list_components` | List all published components in a file |
| `figma_list_projects` | List all projects for a team |
| `figma_list_project_files` | List all files in a project |

> The file key is the string in the Figma URL: `figma.com/design/<file_key>/...`

### Notion

| Tool | Description |
|------|-------------|
| `notion_search` | Search pages and databases by keyword |
| `notion_get_page` | Get a page's properties by ID |
| `notion_get_page_content` | Get the text content (blocks) of a page |
| `notion_get_database` | Get a database's schema by ID |
| `notion_query_database` | Query all rows from a database |

---

## Skills

Skills are prompt templates that tell Cursor AI exactly what steps to follow using the tools above. Invoke them by name in Cursor chat.

### GitHub Skills

| Skill | Argument | Description |
|-------|----------|-------------|
| `review_pr` | GitHub PR URL | Fetch PR details, analyze quality, write a structured review |
| `summarize_issues` | GitHub repo URL | List open issues grouped by theme with top priorities |
| `onboard_repo` | GitHub repo URL | Overview of stack, setup steps, and current open work |

**Example:**
```
review_pr https://github.com/owner/repo/pull/42
```

### Figma Skills

| Skill | Argument | Description |
|-------|----------|-------------|
| `review_design` | Figma file URL | Review a design for consistency, completeness, and accessibility |
| `list_team_files` | Figma team ID | List all projects and files for a team |

**Example:**
```
review_design https://www.figma.com/design/abc123/MyFile?node-id=1-2
```

### Notion Skills

| Skill | Argument | Description |
|-------|----------|-------------|
| `summarize_page` | Notion page URL or ID | Fetch and summarize a page's content |
| `search_and_summarize` | Search query | Search Notion and summarize the top results |
| `summarize_database` | Notion database URL or ID | Summarize a database schema and its rows |

**Example:**
```
summarize_page https://notion.so/myworkspace/My-Page-a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
```

---

## Adding a New Skill

1. Add a function to the relevant file in `skills/` (or create a new one).
2. The function should accept string arguments and return a multi-line string with numbered steps that reference the available tools by name.
3. Register it in `server.py` with `@mcp.prompt()`.

---

## Project Structure

```
mcp-server/
├── server.py          # MCP server — tools and skills registered here
├── tools/             # API wrappers (called by Cursor via MCP tools)
│   ├── github_tools.py
│   ├── figma_tools.py
│   └── notion_tools.py
├── skills/            # Prompt templates (multi-step workflows for Cursor)
│   ├── github_skills.py
│   ├── figma_skills.py
│   └── notion_skills.py
├── requirements.txt
├── .env.example
└── .env               # your tokens (not committed)
```

## Adding More Integrations

1. Create a new file in `tools/`, e.g. `tools/slack_tools.py`
2. Implement your functions there
3. Register them in `server.py` using the `@mcp.tool()` decorator
