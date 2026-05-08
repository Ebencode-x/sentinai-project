"""GitHub integration -- opens auto-patch pull requests for SentinAI incidents."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
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
    ) -> "str | None":
        """Create a branch and open a PR. Returns PR URL on success, None on failure."""
        branch_name = f"sentinai/fix-{incident_id[:8]}"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

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
