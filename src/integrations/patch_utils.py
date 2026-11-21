"""Pure helpers that validate and apply a single file unified diff.

Nothing here talks to GitHub, so a bad diff can be rejected before any
branch is created.
"""

import unidiff


class PatchRejected(ValueError):
    """The proposed diff cannot be applied safely."""


def parse_single_file_patch(diff_text: str) -> tuple[str, unidiff.PatchSet]:
    """Return (repo-relative path, PatchSet) for a diff that edits exactly one file."""
    if not diff_text or not diff_text.strip():
        raise PatchRejected("empty diff")
    try:
        patch_set = unidiff.PatchSet(diff_text)
    except Exception as exc:
        raise PatchRejected(f"diff does not parse: {exc}") from exc
    if len(patch_set) == 0:
        raise PatchRejected("diff has no file entries")
    if len(patch_set) > 1:
        raise PatchRejected(f"diff touches {len(patch_set)} files, only one is allowed")
    patched_file = patch_set[0]
    if patched_file.is_added_file or patched_file.is_removed_file:
        raise PatchRejected("creating or deleting files is not allowed")
    path = patched_file.path
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return path, patch_set


def _same_line(left: str, right: str) -> bool:
    return left.rstrip("\r\n") == right.rstrip("\r\n")


def apply_verified(original: str, patch_set: unidiff.PatchSet) -> str:
    """Apply a PatchSet, refusing any hunk whose old lines differ from the file."""
    lines = original.splitlines(keepends=True)
    old_types = (unidiff.LINE_TYPE_REMOVED, unidiff.LINE_TYPE_CONTEXT)
    new_types = (unidiff.LINE_TYPE_ADDED, unidiff.LINE_TYPE_CONTEXT)
    for patched_file in patch_set:
        # Hunks go in reverse so earlier line numbers stay valid
        for hunk in reversed(list(patched_file)):
            old = [ln.value for ln in hunk if ln.line_type in old_types]
            new = [ln.value for ln in hunk if ln.line_type in new_types]
            start = hunk.source_start if not old else hunk.source_start - 1
            current = lines[start : start + len(old)]
            matches = (
                start >= 0
                and len(current) == len(old)
                and all(_same_line(a, b) for a, b in zip(current, old, strict=True))
            )
            if not matches:
                raise PatchRejected(
                    f"hunk at line {hunk.source_start} does not match the current file"
                )
            lines[start : start + len(old)] = new
    return "".join(lines)
