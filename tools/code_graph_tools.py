"""
Code graph tools — analyze import relationships from a GitHub repo or a local
directory tree and build a dependency graph suitable for visualization.
"""

import json
import os
import re
import subprocess
from pathlib import Path

# ─── helpers ──────────────────────────────────────────────────────────────────

_LANG_EXTENSIONS = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "jsx": "javascript",
    "go": "go",
    "rs": "rust",
    "java": "java",
    "kt": "kotlin",
    "kts": "kotlin",
    "rb": "ruby",
    "cs": "csharp",
    "php": "php",
    "c": "c",
    "cpp": "cpp",
    "h": "c",
    "hpp": "cpp",
    "hxx": "cpp",
    "cs": "csharp",
    "scala": "scala",
    "clj": "clojure",
    "ex": "elixir",
    "exs": "elixir",
    "erl": "erlang",
    "hs": "haskell",
    "lua": "lua",
    "r": "r",
    "m": "objectivec",
    "mm": "objectivec",
    "swift": "swift",
    "dart": "dart",
}

_IMPORT_RULES = {
    "python": [
        re.compile(r"^\s*(?:from\s+([\w.]+)\s+)?import\s+([\w][\w.]*)", re.MULTILINE),
        re.compile(r"^\s*import\s+([\w][\w.]*)", re.MULTILINE),
    ],
    "javascript": [
        re.compile(r'^\s*import\s+(?:.*?\s+from\s+)?"([^"]+)"', re.MULTILINE),
        re.compile(r'^\s*require\s*\(\s*"([^"]+)"\s*\)', re.MULTILINE),
        re.compile(r'^\s*import\s+"([^"]+)"', re.MULTILINE),
    ],
    "typescript": [
        re.compile(r"""^\s*import\s+(?:.*?\s+from\s+)?"([^"]+)"\s*""", re.MULTILINE),
        re.compile(r"""^\s*import\s+(?:.*?\s+from\s+)'([^']+)'\s*""", re.MULTILINE),
        re.compile(r"""^\s*import\s+"([^"]+)"\s*""", re.MULTILINE),
        re.compile(r"""^\s*import\s+'([^']+)'""", re.MULTILINE),
        re.compile(r'^\s*require\s*\(\s*"[^"]+"\s*\)', re.MULTILINE),
        re.compile(r"""^\s*require\s*\(\s*'[^']+'\s*\)""", re.MULTILINE),
    ],
    "go": [
        re.compile(r'^\s*import\s+"([^"]+)"', re.MULTILINE),
        re.compile(r'^\s*import\s+\((.*?)\)', re.MULTILINE | re.DOTALL),
    ],
    "rust": [
        re.compile(r'^\s*use\s+([\w:]+)', re.MULTILINE),
        re.compile(r'^\s*extern\s+crate\s+([\w]+)', re.MULTILINE),
    ],
    "java": [
        re.compile(r'^\s*import\s+([\w.]+)\s*;', re.MULTILINE),
    ],
    "kotlin": [
        re.compile(r'^\s*import\s+([\w.]+)', re.MULTILINE),
    ],
    "ruby": [
        re.compile(r"""^\s*require\s+[\'"]([^"\']+)\'""", re.MULTILINE),
        re.compile(r"""^\s*require_relative\s+[\'"]([^"\']+)\'""", re.MULTILINE),
        re.compile(r"""^\s*load\s+[\'"]([^"\']+)\'""", re.MULTILINE),
    ],
    "php": [
        re.compile(r'^\s*use\s+([\w\\\\]+)', re.MULTILINE),
        re.compile(r"""^\s*require\s*\([\'"]([^"\']+)\'""", re.MULTILINE),
        re.compile(r"""^\s*require_once\s*\([\'"]([^"\']+)\'""", re.MULTILINE),
        re.compile(r"""^\s*include\s*\([\'"]([^"\']+)\'""", re.MULTILINE),
    ],
    "c": [
        re.compile(r'^\s*#include\s*[<"]([^>"]+)[>"]', re.MULTILINE),
    ],
    "cpp": [
        re.compile(r'^\s*#include\s*[<"]([^>"]+)[>"]', re.MULTILINE),
    ],
    "scala": [
        re.compile(r'^\s*import\s+([\w.]+)(?:\.\w+)*', re.MULTILINE),
    ],
    "elixir": [
        re.compile(r'^\s*use\s+([\w:]+)', re.MULTILINE),
        re.compile(r'^\s*import\s+([\w:]+)', re.MULTILINE),
        re.compile(r'^\s*require\s+([\w:]+)', re.MULTILINE),
    ],
    "csharp": [
        re.compile(r'^\s*using\s+([\w.]+)\s*;', re.MULTILINE),
    ],
    "dart": [
        re.compile(r"""^\s*import\s+[\'"]([^"\']+)\'""", re.MULTILINE),
    ],
    "lua": [
        re.compile(r"""^\s*local\s+require\s*=\s*require\s*\([\'"]([^"\']+)\'""", re.MULTILINE),
        re.compile(r"""^\s*require\s*\([\'"]([^"\']+)\'""", re.MULTILINE),
    ],
    "r": [
        re.compile(r'^\s*library\s*\(([\w.]+)\)', re.MULTILINE),
        re.compile(r'^\s*require\s*\(([\w.]+)\)', re.MULTILINE),
        re.compile(r"""^\s*source\s*\([\'"]([^"\']+)\'""", re.MULTILINE),
    ],
    "swift": [
        re.compile(r'^\s*import\s+([\w]+)', re.MULTILINE),
    ],
    "objectivec": [
        re.compile(r'^\s*#import\s*[<"]([^>"]+)[>"]', re.MULTILINE),
    ],
}

_SKIP_DIR_NAMES = frozenset({
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    "out",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "target",
    "bin",
    "obj",
    ".idea",
    ".vscode",
})


def _resolve_local_root(local_root: str) -> Path:
    p = Path(local_root).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"local_root is not a directory: {local_root}")
    return p


def _rel_posix_under(root: Path, file_path: Path) -> str:
    try:
        rel = file_path.relative_to(root)
    except ValueError as e:
        raise ValueError(f"Path escapes local_root: {file_path}") from e
    return rel.as_posix()


def _path_has_skip_segment(rel_posix: str) -> bool:
    return any(part in _SKIP_DIR_NAMES for part in rel_posix.split("/"))


def _scoped_scan_dir(root: Path, path: str) -> Path:
    if not path or not str(path).strip("/"):
        return root
    p = Path(path.replace("\\", "/").strip("/"))
    if ".." in p.parts:
        raise ValueError(f"Invalid path (must not contain '..'): {path}")
    scan = (root / p).resolve()
    try:
        scan.relative_to(root)
    except ValueError as e:
        raise ValueError(f"path escapes local_root: {path}") from e
    return scan


_GITATTRS_IGNORE = (
    ".git/"
    "node_modules/"
    "__pycache__/"
    ".venv/"
    "venv/"
    "dist/"
    "build/"
    "out/"
    ".next/"
    ".nuxt/"
    ".svelte-kit/"
    "target/"
    "bin/"
    "obj/"
    ".idea/"
    ".vscode/"
    "*.lock"
    "*.lockb"
    "*.lockc"
    "*.log"
    "*.pid"
    "*.pidfile"
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


def _detect_language(path: str) -> str | None:
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    return _LANG_EXTENSIONS.get(ext)


def _extract_imports(content: str, lang: str) -> list[str]:
    """Return a list of raw import strings found in *content*."""
    rules = _IMPORT_RULES.get(lang)
    if not rules:
        return []
    imports: list[str] = []
    for rule in rules:
        imports.extend(rule.findall(content))
    return imports


# ─── public tools ─────────────────────────────────────────────────────────────


def fetch_tree(
    repo: str,
    path: str = "",
    ref: str = "HEAD",
    recursive: bool = True,
    max_depth: int = 5,
) -> list[dict]:
    """
    Fetch the tree of a GitHub repository.

    Returns a flat list of entries with keys:
      path, type (blob|tree), size, url
    """
    url = f"repos/{repo}/git/trees/{ref}"
    params = []
    if recursive:
        params.append(f"recursive={max_depth}")
    if path:
        params.append(f"path={path}")
    if params:
        url += "?" + "&".join(params)
    args = ["api", url]
    raw = _gh(*args)
    data = json.loads(raw)
    return [
        {
            "path": entry["path"],
            "type": entry["type"],
            "size": entry.get("size", 0),
            "url": entry.get("url"),
        }
        for entry in data.get("tree", [])
        if entry["type"] == "blob"  # only files
    ]


def fetch_tree_local(
    local_root: str,
    path: str = "",
    recursive: bool = True,
    max_depth: int = 12,
) -> list[dict]:
    """
    List files under a local directory (same shape as fetch_tree for GitHub).

    Paths in results are POSIX-relative to *local_root*. Skips common vendor
    and build directories (node_modules, .git, etc.).
    """
    root = _resolve_local_root(local_root)
    scan = _scoped_scan_dir(root, path)
    if not scan.is_dir():
        return []

    entries: list[dict] = []

    def walk(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            it = os.scandir(current)
        except OSError:
            return
        with it:
            for dirent in it:
                if dirent.name in _SKIP_DIR_NAMES:
                    continue
                full = Path(dirent.path)
                try:
                    rel = _rel_posix_under(root, full)
                except ValueError:
                    continue
                if _path_has_skip_segment(rel):
                    continue
                if dirent.is_file(follow_symlinks=False):
                    try:
                        size = full.stat().st_size
                    except OSError:
                        size = 0
                    entries.append({
                        "path": rel,
                        "type": "blob",
                        "size": size,
                        "url": None,
                    })
                elif dirent.is_dir(follow_symlinks=False) and recursive:
                    walk(full, depth + 1)

    walk(scan, 0)
    entries.sort(key=lambda e: e["path"])
    return entries


def build_code_graph(
    repo: str,
    path: str = "",
    ref: str = "HEAD",
    language: str = "",
    max_files: int = 80,
    ignore_patterns: str = "",
    local_root: str | None = None,
) -> dict:
    """
    Build a code graph for a GitHub repository or a local checkout.

    Fetches the repo tree (GitHub) or walks the filesystem (local), reads each
    file's content, extracts imports, and returns nodes (files) and edges
    (import relationships).

    Args:
        repo: owner/repo (GitHub). Ignored when *local_root* is set.
        path: optional sub-path inside the repo or local root (default root)
        ref: git ref (GitHub only)
        language: optional language filter (e.g. "python", "typescript").
                  If empty, auto-detect from file extensions.
        max_files: cap on files to read (prevents huge responses)
        ignore_patterns: colon-separated glob-like patterns to skip (e.g. "node_modules:__pycache__")
        local_root: if set, read from this directory instead of GitHub.

    Returns:
        dict with keys:
          source ("github" | "local"), repo, ref, local_root, language_filter,
          total_files_scanned,
          nodes: [{path, language, size, line_count}]
          edges: [{source, target, type}]
          stats: {total_nodes, total_edges, language_breakdown}
    """
    use_local = bool(local_root and str(local_root).strip())
    root_path: Path | None = None

    # 1. Fetch tree
    if use_local:
        root_path = _resolve_local_root(local_root or "")
        entries = fetch_tree_local(str(root_path), path=path, recursive=True)
    else:
        entries = fetch_tree(repo, path=path, ref=ref, recursive=True)

    if not entries:
        return {
            "source": "local" if use_local else "github",
            "repo": repo or "",
            "ref": ref if not use_local else "",
            "local_root": str(root_path) if root_path else None,
            "language_filter": language or "auto",
            "total_files_scanned": 0,
            "nodes": [],
            "edges": [],
            "stats": {"total_nodes": 0, "total_edges": 0, "language_breakdown": {}},
        }

    # 2. Filter
    ignore_set = set(p.strip() for p in (ignore_patterns or "").split(":") if p.strip())

    def _should_ignore(entry_path: str) -> bool:
        for pat in ignore_set:
            if pat in entry_path:
                return True
        return False

    # Apply language filter
    filtered: list[dict] = []
    for entry in entries:
        ep = entry["path"]
        if path and ep.startswith(path + "/"):
            ep = ep[len(path) + 1:]
        if _should_ignore(ep):
            continue
        if language:
            lang = _detect_language(ep)
            if lang != language:
                continue
        filtered.append(entry)

    # Cap files
    filtered = filtered[:max_files]

    # 3. Read files and extract imports
    nodes: list[dict] = []
    # Map import specifiers to canonical paths for edge targets
    path_index: dict[str, str] = {}
    for e in filtered:
        ext_lang = _detect_language(e["path"])
        nodes.append({
            "path": e["path"],
            "language": ext_lang or "unknown",
            "size": e.get("size", 0),
            "line_count": 0,
        })
        if ext_lang:
            path_index[e["path"]] = e["path"]
            # Also index basename without extension
            base = e["path"].rsplit("/", 1)[-1] if "/" in e["path"] else e["path"]
            stem = base.rsplit(".", 1)[0]
            path_index[stem] = e["path"]

    edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()

    for entry in filtered:
        src = entry["path"]
        lang = _detect_language(src)
        if not lang:
            continue
        try:
            if use_local and root_path is not None:
                abs_file = (root_path / Path(src)).resolve()
                try:
                    abs_file.relative_to(root_path)
                except ValueError:
                    raw_lines = 0
                    content = ""
                else:
                    if not abs_file.is_file():
                        raw_lines = 0
                        content = ""
                    else:
                        content = abs_file.read_text(encoding="utf-8", errors="replace")
                        raw_lines = content.count("\n") + 1
            else:
                url = f"repos/{repo}/contents/{src}"
                if ref and ref != "HEAD":
                    url += f"?ref={ref}"
                raw = _gh("api", url)
                data = json.loads(raw)
                content = data.get("content", "")
                # base64 decode
                import base64 as _b64
                enc = data.get("encoding", "base64")
                if enc == "base64":
                    content = _b64.b64decode(content).decode("utf-8", errors="replace")
                raw_lines = content.count("\n") + 1
        except Exception:
            raw_lines = 0
            content = ""

        # Update line count on node
        for n in nodes:
            if n["path"] == src:
                n["line_count"] = raw_lines
                break

        imports = _extract_imports(content, lang)
        for imp in imports:
            if isinstance(imp, tuple):
                # Some regex groups return tuples (e.g. python "from X import Y" → ("X", "Y"))
                imp_str = imp[0] if imp[0] else imp[1] if len(imp) > 1 else ""
            else:
                imp_str = str(imp)

            # Try to resolve to a file path in the repo
            target = _resolve_import(imp_str, src, path_index, lang)
            if target and target != src:
                edge_key = (src, target)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": src,
                        "target": target,
                        "type": lang,
                    })

    # 4. Language breakdown
    lang_breakdown: dict[str, int] = {}
    for n in nodes:
        l = n["language"]
        lang_breakdown[l] = lang_breakdown.get(l, 0) + 1

    return {
        "source": "local" if use_local else "github",
        "repo": repo or "",
        "ref": ref if not use_local else "",
        "local_root": str(root_path) if root_path else None,
        "language_filter": language or "auto",
        "total_files_scanned": len(filtered),
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "language_breakdown": lang_breakdown,
        },
    }


def _resolve_import(specifier: str, source_path: str, path_index: dict[str, str], lang: str) -> str | None:
    """Try to resolve an import specifier to a file path in the repo."""
    # Direct match
    if specifier in path_index:
        return path_index[specifier]

    # Handle relative imports (start with . or ..)
    if specifier.startswith("."):
        # Get the directory of the source file
        if "/" in source_path:
            source_dir = source_path.rsplit("/", 1)[0]
        else:
            source_dir = ""
        # Strip leading dots and slashes
        rel = specifier.lstrip("./")
        if rel:
            # Build candidate by joining source dir with relative path
            if source_dir:
                candidate = source_dir + "/" + rel
            else:
                candidate = rel
            # Normalize: collapse double slashes
            while "//" in candidate:
                candidate = candidate.replace("//", "/")

            # Try direct match
            if candidate in path_index:
                return path_index[candidate]

            # Try with extensions
            for ext in [".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".java", ".kt", ".rb"]:
                c = candidate + ext
                if c in path_index:
                    return path_index[c]

            # Try as directory (index file)
            for idx_ext in ["/index.ts", "/index.tsx", "/index.js", "/index.jsx"]:
                c = candidate + idx_ext
                if c in path_index:
                    return path_index[c]

            # Try progressively shorter prefixes (for nested imports like ./a/b/c → try ./a/b, ./a)
            parts = candidate.split("/")
            for i in range(len(parts) - 1, 0, -1):
                prefix = "/".join(parts[:i])
                for ext in [".ts", ".tsx", ".js", ".jsx", ".py"]:
                    c = prefix + ext
                    if c in path_index:
                        return path_index[c]

    # Strip leading dots for non-relative imports
    clean = specifier.lstrip(".")

    # Strip trailing module names (e.g. "package.module.sub" → try progressively)
    parts = clean.split(".") if "." in clean and lang == "python" else clean.split("/")
    current = ""
    for i, part in enumerate(parts):
        if not part:
            continue
        if current:
            current += "." if lang == "python" else "/"
        current += part
        if current in path_index:
            return path_index[current]

    # Try as directory/module pattern (Python: "package.module" → "package/module.py")
    if lang == "python" and "." in clean:
        dotted = clean
        slash = dotted.replace(".", "/")
        if slash in path_index:
            return path_index[slash]
        candidate = slash + ".py"
        if candidate in path_index:
            return path_index[candidate]
        candidate = slash + "/__init__.py"
        if candidate in path_index:
            return path_index[candidate]

    # Try with common extensions
    for ext in [".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".rb"]:
        candidate = clean + ext
        if candidate in path_index:
            return path_index[candidate]

    return None
