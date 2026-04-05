"""
Notion skills — prompt templates that guide Cursor through multi-step Notion tasks.
"""

import re


def _parse_notion_id(url_or_id: str) -> str:
    """Extract a Notion page/database ID from a URL or return it as-is."""
    # Match a 32-char hex ID at the end of a URL path segment (with or without dashes)
    match = re.search(r"([a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12})", url_or_id)
    if match:
        raw = match.group(1).replace("-", "")
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    raise ValueError(f"Could not parse Notion ID from: {url_or_id}")


def summarize_page(url_or_id: str) -> str:
    page_id = _parse_notion_id(url_or_id)
    return f"""Summarize the Notion page with ID {page_id}.

Follow these steps:

1. Fetch the page properties using `notion_get_page` with page_id="{page_id}".
2. Fetch the full page content using `notion_get_page_content` with page_id="{page_id}".
3. Read through all the blocks returned.
4. Write a summary with:

   ## Page Title
   The title of the page.

   ## Summary
   A concise 2–4 sentence summary of what this page is about.

   ## Key Points
   Bullet list of the most important facts, decisions, or action items found in the page.
"""


def search_and_summarize(query: str) -> str:
    return f"""Search Notion for "{query}" and summarize the results.

Follow these steps:

1. Search using `notion_search` with query="{query}".
2. For the top 3 most relevant results, fetch their content:
   - If type is "page": use `notion_get_page_content` to read it.
   - If type is "database": use `notion_get_database` to read its schema.
3. Present the findings:

   ## Search Results for "{query}"

   For each result:
   - **Title** (type: page or database)
     Brief description of what it contains and why it's relevant to the query.

   ## Best Match
   Which result most directly answers the query, and a summary of its content.
"""


def summarize_database(url_or_id: str) -> str:
    db_id = _parse_notion_id(url_or_id)
    return f"""Summarize the Notion database with ID {db_id}.

Follow these steps:

1. Fetch the database schema using `notion_get_database` with database_id="{db_id}".
2. Query its rows using `notion_query_database` with database_id="{db_id}".
3. Analyze the structure and content:

   ## Database Overview
   Name and what this database tracks.

   ## Schema
   List of property/column names and their types.

   ## Contents Summary
   Total number of rows. Highlight any patterns, categories, or notable entries found.
"""
