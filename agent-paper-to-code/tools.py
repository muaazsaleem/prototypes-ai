import base64

import requests

from config import GITHUB_TOKEN


def _headers() -> dict:
    """Build GitHub API request headers, adding a Bearer token when GITHUB_TOKEN is set.

    Without a token, requests are unauthenticated and subject to 60 req/hour rate limits.
    With a token, the limit rises to 5,000 req/hour and code search becomes available.
    """
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def search_github_repositories(query: str, language: str = "python") -> dict:
    """
    Search GitHub for public repositories that implement a specific algorithm or method.

    Args:
        query: Keywords describing the algorithm, e.g. "self-attention transformer"
        language: Programming language to filter by (default: python)

    Returns:
        A dict with a "repos" list. Each item has name, description, stars, url.
    """
    # Sort by stars so the most battle-tested implementations appear first
    resp = requests.get(
        "https://api.github.com/search/repositories",
        params={"q": f"{query} language:{language}", "sort": "stars", "per_page": 5},
        headers=_headers(),
        timeout=10,
    )
    if resp.status_code != 200:
        return {"error": f"GitHub API returned {resp.status_code}", "repos": []}

    return {
        "repos": [
            {
                "name": r["full_name"],
                "description": r.get("description") or "",  # description can be null
                "stars": r["stargazers_count"],
                "url": r["html_url"],
            }
            for r in resp.json().get("items", [])
        ]
    }


def fetch_github_file(owner: str, repo: str, path: str) -> dict:
    """
    Fetch the raw content of a specific file from a GitHub repository.

    Args:
        owner: GitHub username or organisation, e.g. "huggingface"
        repo: Repository name, e.g. "transformers"
        path: Path to the file within the repo, e.g. "src/model.py"

    Returns:
        A dict with "content" (first 5000 chars) or "error" on failure.
    """
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        headers=_headers(),
        timeout=10,
    )
    if resp.status_code != 200:
        return {"error": f"Cannot fetch {owner}/{repo}/{path}: HTTP {resp.status_code}"}

    data = resp.json()
    if data.get("encoding") == "base64":
        # GitHub always returns small files base64-encoded via the contents API
        content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return {"content": content[:5000]}  # cap at 5000 chars to keep prompts short

    return {"error": "Unsupported file encoding"}


def search_github_code(query: str, language: str = "python") -> dict:
    """
    Search GitHub's code index for files that contain a specific implementation pattern.

    Note: GitHub code search requires GITHUB_TOKEN to be set in the environment.

    Args:
        query: Code pattern or function name, e.g. "def scaled_dot_product_attention"
        language: Language filter (default: python)

    Returns:
        A dict with an "items" list of matching files, each with repo, path, url.
    """
    if not GITHUB_TOKEN:
        return {
            "error": "GitHub code search requires GITHUB_TOKEN env var",
            "items": [],
        }

    resp = requests.get(
        "https://api.github.com/search/code",
        params={"q": f"{query} language:{language}", "per_page": 5},
        headers=_headers(),
        timeout=10,
    )
    if resp.status_code != 200:
        return {"error": f"Code search returned HTTP {resp.status_code}", "items": []}

    return {
        "items": [
            {
                "repo": item["repository"]["full_name"],
                "path": item["path"],
                "url": item["html_url"],
            }
            for item in resp.json().get("items", [])
        ]
    }


# Registry used by the agent to dispatch tool calls by name
TOOL_REGISTRY = {
    fn.__name__: fn
    for fn in [
        search_github_repositories,
        fetch_github_file,
        search_github_code,
    ]
}

# Passed directly to GenerateContentConfig — the SDK infers schemas from type hints
TOOLS = list(TOOL_REGISTRY.values())
