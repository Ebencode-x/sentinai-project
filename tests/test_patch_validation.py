import base64
from unittest.mock import MagicMock

from github import GithubException

from src.integrations.github_client import GitHubClient

ORIGINAL = "def handler(x):\n    return x / 0\n\nprint('done')\n"

GOOD = (
    "--- a/src/handler.py\n"
    "+++ b/src/handler.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def handler(x):\n"
    "-    return x / 0\n"
    "+    return x\n"
)
WRONG_CONTEXT = (
    "--- a/src/handler.py\n"
    "+++ b/src/handler.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def other(x):\n"
    "-    return x / 1\n"
    "+    return x\n"
)
PSEUDOCODE = "# Before\nold()\n# After\nnew()\n"
TWO_FILES = (
    "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n-x\n+y\n"
)
NEW_FILE = "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+x\n"

INCIDENT = "abcd1234efgh"


def make_client(original=ORIGINAL, sha="abc123"):
    repo = MagicMock()
    repo.default_branch = "main"
    repo.get_branch.return_value.commit.sha = "deadbeef"
    gh_file = MagicMock()
    gh_file.content = base64.b64encode(original.encode()).decode()
    gh_file.sha = sha
    repo.get_contents.return_value = gh_file
    repo.create_pull.return_value = MagicMock(number=7, html_url="https://example.test/pr/7")
    client = GitHubClient.__new__(GitHubClient)
    client._repo = repo
    return client, repo


def open_pr(client, diff):
    return client.open_patch_pr(
        incident_id=INCIDENT,
        trigger_line="boom",
        summary="s",
        proposed_patch=diff,
        test_guidance="t",
        confidence=0.9,
    )


def test_rejected_diffs_create_no_branch():
    for bad in (PSEUDOCODE, TWO_FILES, NEW_FILE, WRONG_CONTEXT, ""):
        client, repo = make_client()
        assert open_pr(client, bad) is None
        repo.create_git_ref.assert_not_called()
        repo.update_file.assert_not_called()
        repo.create_pull.assert_not_called()


def test_valid_diff_commits_and_opens_pr():
    client, repo = make_client()
    result = open_pr(client, GOOD)
    repo.create_git_ref.assert_called_once()
    repo.update_file.assert_called_once()
    kwargs = repo.update_file.call_args.kwargs
    assert kwargs["content"] == "def handler(x):\n    return x\n\nprint('done')\n"
    assert kwargs["sha"] == "abc123"
    assert result["pr_number"] == 7
    assert result["patch_file"] == "src/handler.py"
    assert result["before_sha"] == "abc123"


def test_branch_we_created_is_deleted_when_commit_fails():
    client, repo = make_client()
    repo.update_file.side_effect = GithubException(500, {"message": "boom"}, {})
    assert open_pr(client, GOOD) is None
    repo.get_git_ref.assert_called_once_with("heads/sentinai/fix-abcd1234")
    repo.get_git_ref.return_value.delete.assert_called_once()
    repo.create_pull.assert_not_called()


def test_existing_branch_is_never_deleted():
    client, repo = make_client()
    repo.create_git_ref.side_effect = GithubException(422, {"message": "exists"}, {})
    repo.update_file.side_effect = GithubException(500, {"message": "boom"}, {})
    assert open_pr(client, GOOD) is None
    repo.get_git_ref.assert_not_called()
