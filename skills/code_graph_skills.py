"""
Code graph skills — prompt templates for generating code dependency graphs.
"""

import re


def _parse_repo_url(github_url: str) -> str:
    """Extract owner/repo from a GitHub URL."""
    match = re.search(r"github\.com/([^/]+/[^/]+?)(?:\.git|/|$)", github_url)
    if not match:
        raise ValueError(f"Could not parse GitHub repo URL: {github_url}")
    return match.group(1)


def code_graph(
    github_url: str = "",
    path: str = "",
    language: str = "",
    max_files: int = 80,
    ignore_patterns: str = "",
    local_root: str = "",
) -> str:
    """
    Generate a code dependency graph for a GitHub repository or a local directory.

    Shows files as nodes and import/dependency relationships as edges.
    """
    if local_root.strip():
        args = f"local_root={local_root.strip()!r}"
        if path:
            args += f", path={path!r}"
        if language:
            args += f", language={language!r}"
        args += f", max_files={max_files}"
        if ignore_patterns:
            args += f", ignore_patterns={ignore_patterns!r}"
        source_label = f"local project `{local_root.strip()}`"
        step1 = f"""1. Call `build_code_graph` with {args} (local_root selects the filesystem; do not pass a GitHub repo).
   - This walks the directory tree (skipping node_modules, .git, build outputs, etc.), reads each file,
     extracts import statements, and returns nodes (files) and edges (import relationships)."""
    else:
        repo = _parse_repo_url(github_url)
        args = f"repo={repo!r}"
        if path:
            args += f", path={path!r}"
        if language:
            args += f", language={language!r}"
        args += f", max_files={max_files}"
        if ignore_patterns:
            args += f", ignore_patterns={ignore_patterns!r}"
        source_label = f"GitHub repository `{repo}`"
        step1 = f"""1. Call `build_code_graph` with {args}.
   - This fetches the repository tree from GitHub, reads each file, extracts import statements,
     and returns a graph with nodes (files) and edges (import relationships)."""

    return f"""Generate a code dependency graph for the {source_label}.

Follow these steps:

{step1}

2. If the result has very few edges relative to nodes, try calling again with a higher
   max_files value or a narrower path/language filter to get a more focused graph.

3. Analyze the graph and present:

   ## Code Graph Summary
   - Total files analyzed
   - Total dependency edges found
   - Language breakdown

   ## Key Modules (Hub Detection)
   Files with the most incoming + outgoing edges — these are the core modules
   that many other files depend on or that depend on many others.

   ## Isolated Files
   Files with no import edges at all — likely standalone scripts, data files,
   or entry points (e.g. main.py, index.js).

   ## Dependency Clusters
   Groups of files that import each other but have few external connections —
   these are natural module boundaries or subsystems.

   ## Graph Visualization (Mermaid)
   Generate a Mermaid flowgraph using the nodes and edges:
   ```mermaid
   graph TD
   [Use the edges from the result to build edges like: A --> B]
   ```
   (If there are too many edges for a readable graph, show only the top ~30
   by edge weight and label the rest as "and N more edges".)

   ## Architecture Observations
   - Any suspicious circular dependencies (A imports B, B imports A)
   - Single points of failure (one file imported by many)
   - Potential areas for refactoring (overly coupled clusters)
"""


def code_graph_for_language(
    github_url: str = "",
    language: str = "",
    path: str = "",
    max_files: int = 60,
    local_root: str = "",
) -> str:
    """
    Generate a code dependency graph filtered to a single language.

    Useful for understanding a specific subsystem (e.g. just the Python backend
    or just the TypeScript frontend).
    """
    if local_root.strip():
        src = f"local `{local_root.strip()}`"
        call = f"local_root={local_root.strip()!r}, language={language!r}, path={path!r}, max_files={max_files}"
    else:
        repo = _parse_repo_url(github_url)
        src = repo
        call = f"repo={repo!r}, language={language!r}, path={path!r}, max_files={max_files}"
    return f"""Generate a code dependency graph for {src}, filtered to {language} files only.

Follow these steps:

1. Call `build_code_graph` with {call}.
   - The language filter restricts the graph to files matching the given language's
     common extensions (e.g. .py for python, .ts/.tsx for typescript).

2. Present:

   ## {language.title()} Dependency Graph
   - Number of {language} files analyzed
   - Dependency edges between {language} modules

   ## Module Map
   How the {language} files relate: which modules import which.
   Group by top-level directory/package.

   ## Mermaid Graph
   ```mermaid
   graph TD
   [Build a Mermaid graph from the edges]
   ```

   ## Key Insights
   - Entry points (files that import others but are not imported)
   - Core libraries (files imported by many others)
   - Orphan modules (files with no imports in or out)
"""


def code_graph_subpath(
    github_url: str = "",
    subpath: str = "",
    language: str = "",
    max_files: int = 40,
    local_root: str = "",
) -> str:
    """
    Generate a code dependency graph for a specific subdirectory.

    Useful for deep-diving into one module or feature area.
    """
    if local_root.strip():
        src = f"local `{local_root.strip()}`"
        call = f"local_root={local_root.strip()!r}, path={subpath!r}, max_files={max_files}"
    else:
        repo = _parse_repo_url(github_url)
        src = repo
        call = f"repo={repo!r}, path={subpath!r}, max_files={max_files}"
    lang_hint = f"\n   - If a language filter is desired, add language={language!r}." if language else ""
    return f"""Generate a code dependency graph for the subdirectory "{subpath}" in {src}.

Follow these steps:

1. Call `build_code_graph` with {call}.{lang_hint}

2. Present:

   ## Subdirectory Graph: {subpath}
   - Files analyzed within this subdirectory
   - Internal edges (imports within the subdirectory)
   - External edges (imports reaching outside the subdirectory)

   ## Mermaid Graph
   ```mermaid
   graph TD
   [Build a Mermaid graph from the edges]
   ```

   ## Boundary Analysis
   - What external modules does this subdirectory depend on?
   - What other parts of the codebase depend on this subdirectory?
   - Is this subdirectory a self-contained module or does it leak dependencies?
"""
