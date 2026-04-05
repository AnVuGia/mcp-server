"""
Figma skills — prompt templates that guide Cursor through multi-step Figma tasks.
"""

import re


def _parse_figma_url(figma_url: str) -> tuple[str, str | None]:
    """Extract file_key and optional node_id from a Figma URL."""
    match = re.search(r"figma\.com/(?:design|file)/([^/?\s]+)", figma_url)
    if not match:
        raise ValueError(f"Could not parse Figma URL: {figma_url}")
    file_key = match.group(1)
    node_match = re.search(r"node-id=([^&\s]+)", figma_url)
    node_id = node_match.group(1).replace("-", ":") if node_match else None
    return file_key, node_id


def review_design(figma_url: str) -> str:
    file_key, node_id = _parse_figma_url(figma_url)
    node_step = (
        f'2. Since a specific node is linked, also fetch it with `figma_get_nodes` (file_key="{file_key}", node_ids=["{node_id}"]).'
        if node_id
        else "2. No specific node is linked — review the file-level overview."
    )
    return f"""Review the Figma design at {figma_url}.

Follow these steps:

1. Fetch the file metadata using `figma_get_file` with file_key="{file_key}".
{node_step}
3. List all components with `figma_list_components` (file_key="{file_key}") to understand the design system.
4. Analyze the design based on the information retrieved. Consider:
   - **Consistency**: Are components and styles used consistently?
   - **Completeness**: Are all necessary states covered (empty, loading, error)?
   - **Accessibility**: Sufficient contrast, legible type sizes, clear affordances?
   - **Responsiveness**: Are mobile/tablet breakpoints addressed?
   - **Component reuse**: Are one-off elements that should be components?

5. Write a structured design review:

   ## Design Overview
   What this design represents and its purpose.

   ## Component Inventory
   List of key components found.

   ## Issues Found
   Bullet list labeled 🔴 Critical / 🟡 Warning / 🔵 Suggestion.

   ## Overall Assessment
   Ready for development / Needs revisions — with rationale.
"""


def list_team_files(team_id: str) -> str:
    return f"""List all Figma files available for team {team_id}.

Follow these steps:

1. Fetch all projects for the team using `figma_list_projects` with team_id="{team_id}".
2. For each project returned, fetch its files using `figma_list_project_files` with the project's id.
3. Present the results as a structured list:

   ## Figma Projects & Files for Team {team_id}

   For each project:
   - **Project name** (project id)
     - File name — last modified date — file key
"""
