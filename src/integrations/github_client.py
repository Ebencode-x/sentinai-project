"""GitHub integration -- opens auto-patch pull requests for SentinAI incidents."""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime

import unidiff
from github import Github, GithubException

from src.core.config import settings

logger = logging.getLogger(__name__)


class GitHubClient:
    """Opens a pull request containing the LLM-proposed patch for a given incident."""

    def __init__(self) -> None:
        self._client = Github(settings.github_token)
        self._repo = self._client.get_repo(settings.github_repo)

    def open_patch_pr(
        self,
        incident_id: str,
        trigger_line: str,
        summary: str,
        proposed_patch: str,
        test_guidance: str,
        confidence: float,
        patch_file: str | None = None,
    ) -> str | None:
        """Create a branch and open a PR. Returns PR URL on success, None on failure."""
        branch_name = f"sentinai/fix-{incident_id[:8]}"
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        try:
            default_branch = self._repo.default_branch
            source = self._repo.get_branch(default_branch)
            self._repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=source.commit.sha,
            )
            logger.info("Created branch: %s", branch_name)
        except GithubException as exc:
            if exc.status == 422:
                logger.warning("Branch already exists: %s", branch_name)
            else:
                logger.error("Failed to create branch: %s", exc)
                return None

        committed = self._commit_patch(
            branch_name=branch_name,
            proposed_patch=proposed_patch,
            patch_file=patch_file,
            incident_id=incident_id,
        )
        if not committed:
            logger.warning("Patch commit skipped — PR will be description-only")

        pr_body = self._build_pr_body(
            incident_id=incident_id,
            trigger_line=trigger_line,
            summary=summary,
            proposed_patch=proposed_patch,
            test_guidance=test_guidance,
            confidence=confidence,
            timestamp=timestamp,
        )

        try:
            pr = self._repo.create_pull(
                title=f"[SentinAI] Incident {incident_id[:8]} -- auto-patch proposal",
                body=pr_body,
                head=branch_name,
                base=default_branch,
            )
            logger.info("Opened PR #%s: %s", pr.number, pr.html_url)
            return pr.html_url
        except GithubException as exc:
            logger.error("Failed to open PR: %s", exc)
            return None

    def _commit_patch(
        self,
        branch_name: str,
        proposed_patch: str,
        patch_file: str | None,
        incident_id: str,
    ) -> bool:
        """Parse unified diff, apply to live file, commit to branch. Returns True on success."""
        if not proposed_patch or not patch_file:
            logger.debug("No patch_file provided — skipping file commit")
            return False
        try:
            patch_set = unidiff.PatchSet(proposed_patch)
        except Exception as exc:
            logger.warning("Failed to parse unified diff: %s", exc)
            return False

        try:
            gh_file = self._repo.get_contents(patch_file, ref=branch_name)
            original = base64.b64decode(gh_file.content).decode("utf-8")
            file_sha = gh_file.sha
        except GithubException as exc:
            logger.warning("Could not fetch %s from GitHub: %s", patch_file, exc)
            return False

        try:
            patched = self._apply_patch(original, patch_set)
        except Exception as exc:
            logger.warning("Patch application failed: %s", exc)
            return False

        if patched == original:
            logger.info("Patch produced no changes — skipping commit")
            return False

        try:
            self._repo.update_file(
                path=patch_file,
                message=f"[SentinAI] auto-patch for incident {incident_id[:8]}",
                content=patched,
                sha=file_sha,
                branch=branch_name,
            )
            logger.info("Committed patch to %s on %s", patch_file, branch_name)
            return True
        except GithubException as exc:
            logger.warning("Failed to commit patch: %s", exc)
            return False

    def _apply_patch(self, original: str, patch_set: unidiff.PatchSet) -> str:
        """Apply a parsed unidiff PatchSet to original file content."""
        lines = original.splitlines(keepends=True)
        # Work through hunks in reverse so line offsets stay valid
        for patched_file in patch_set:
            for hunk in reversed(list(patched_file)):
                start = hunk.source_start - 1  # unidiff is 1-indexed
                length = hunk.source_length
                new_lines = [
                    line.value
                    for line in hunk
                    if line.line_type in (unidiff.LINE_TYPE_ADDED, unidiff.LINE_TYPE_CONTEXT)
                ]
                lines[start : start + length] = new_lines
        return "".join(lines)

    def _build_pr_body(
        self,
        incident_id: str,
        trigger_line: str,
        summary: str,
        proposed_patch: str,
        test_guidance: str,
        confidence: float,
        timestamp: str,
    ) -> str:
        confidence_pct = int(confidence * 100)
        bar_filled = int(confidence_pct / 10)
        bar = "[" + "#" * bar_filled + "-" * (10 - bar_filled) + "]"
        parts = [
            "## SentinAI -- Auto-Patch Proposal",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Incident ID | `{incident_id}` |",
            f"| Detected | {timestamp} |",
            f"| Trigger | `{trigger_line[:120]}` |",
            f"| Confidence | {bar} {confidence_pct}% |",
            "",
            "---",
            "",
            "### Summary",
            "",
            f"{summary}",
            "",
            "---",
            "",
            "### Proposed Patch",
            "",
            "```python",
            f"{proposed_patch}",
            "```",
            "",
            "---",
            "",
            "### Test Guidance",
            "",
            f"{test_guidance}",
            "",
            "---",
            "",
            "> This PR was opened automatically by SentinAI.",
            "> Review the patch, apply manually if appropriate, then merge or close.",
            "> Never merge without human review.",
        ]
        return "\n".join(parts) + "\n"
