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
    ) -> dict | None:
        """Create a branch and open a PR. Returns commit metadata on success, None on failure."""
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

        commit_meta = self._commit_patch(
            branch_name=branch_name,
            proposed_patch=proposed_patch,
            incident_id=incident_id,
        )
        if commit_meta is None:
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
            result = {
                "pr_url": pr.html_url,
                "pr_number": pr.number,
                "branch_name": branch_name,
            }
            if commit_meta:
                result.update(commit_meta)
            return result
        except GithubException as exc:
            logger.error("Failed to open PR: %s", exc)
            return None

    def _commit_patch(
        self,
        branch_name: str,
        proposed_patch: str,
        incident_id: str,
    ) -> dict | None:
        """Parse unified diff, apply to live file, commit to branch.

        Derives the target file path from the diff's own header instead of
        requiring a separate patch_file argument. Returns commit metadata
        (patch_file, before_sha) on success, None on skip/failure.
        """
        if not proposed_patch:
            logger.debug("No proposed_patch — skipping file commit")
            return None
        try:
            patch_set = unidiff.PatchSet(proposed_patch)
        except Exception as exc:
            logger.warning("Failed to parse unified diff: %s", exc)
            return None

        if len(patch_set) == 0:
            logger.warning("Diff parsed but contains no file entries")
            return None
        if len(patch_set) > 1:
            logger.warning(
                "Diff touches %d files — only single-file patches are auto-committed",
                len(patch_set),
            )
            return None

        patched_file = patch_set[0]
        patch_file = patched_file.path
        if patch_file.startswith(("a/", "b/")):
            patch_file = patch_file[2:]

        try:
            gh_file = self._repo.get_contents(patch_file, ref=branch_name)
            original = base64.b64decode(gh_file.content).decode("utf-8")
            file_sha = gh_file.sha
        except GithubException as exc:
            logger.warning("Could not fetch %s from GitHub: %s", patch_file, exc)
            return None

        try:
            patched = self._apply_patch(original, patch_set)
        except Exception as exc:
            logger.warning("Patch application failed: %s", exc)
            return None

        if patched == original:
            logger.info("Patch produced no changes — skipping commit")
            return None

        try:
            self._repo.update_file(
                path=patch_file,
                message=f"[SentinAI] auto-patch for incident {incident_id[:8]}",
                content=patched,
                sha=file_sha,
                branch=branch_name,
            )
            logger.info("Committed patch to %s on %s", patch_file, branch_name)
            return {"patch_file": patch_file, "before_sha": file_sha}
        except GithubException as exc:
            logger.warning("Failed to commit patch: %s", exc)
            return None

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

    def check_pr_merged(self, pr_number: int) -> dict | None:
        """Poll a PR's merge status. Returns merge metadata if merged, else None."""
        try:
            pr = self._repo.get_pull(pr_number)
        except GithubException as exc:
            logger.warning("Could not fetch PR #%s: %s", pr_number, exc)
            return None
        if not pr.merged:
            return None
        return {"merge_commit_sha": pr.merge_commit_sha, "merged_at": pr.merged_at}

    def get_current_file_sha(self, patch_file: str, ref: str | None = None) -> str | None:
        """Return the current blob sha for a file on the given ref (default branch if omitted)."""
        try:
            ref = ref or self._repo.default_branch
            gh_file = self._repo.get_contents(patch_file, ref=ref)
            return gh_file.sha
        except GithubException as exc:
            logger.warning("Could not fetch current sha for %s: %s", patch_file, exc)
            return None

    def revert_patch(
        self,
        patch_file: str,
        before_sha: str,
        current_sha: str,
        incident_id: str,
        branch: str | None = None,
    ) -> str | None:
        """Restore patch_file to its pre-patch content by fetching the before_sha blob
        and committing it back on top of current_sha. Returns the new commit sha, or None."""
        try:
            branch = branch or self._repo.default_branch
            blob = self._repo.get_git_blob(before_sha)
            original_content = base64.b64decode(blob.content).decode("utf-8")
        except GithubException as exc:
            logger.warning("Could not fetch before_sha blob %s: %s", before_sha, exc)
            return None

        try:
            result = self._repo.update_file(
                path=patch_file,
                message=f"[SentinAI] rollback for incident {incident_id[:8]}",
                content=original_content,
                sha=current_sha,
                branch=branch,
            )
            new_sha = result["commit"].sha
            logger.info("Reverted %s on %s (commit %s)", patch_file, branch, new_sha)
            return new_sha
        except GithubException as exc:
            logger.warning("Failed to revert %s: %s", patch_file, exc)
            return None
