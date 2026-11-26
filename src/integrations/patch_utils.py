"""Pure helpers that validate and apply a single file unified diff.

Nothing here talks to GitHub, so a bad diff can be rejected before any
branch is created.
"""

import re

import unidiff


class PatchRejected(ValueError):
    """The proposed diff cannot be applied safely."""


def _strip_diff_prefix(name: str) -> str:
    return name[2:] if name.startswith(("a/", "b/")) else name


def normalize_repo_path(raw: str) -> str:
    """Return raw as a clean repo-relative POSIX path, or raise PatchRejected.

    Empty, absolute, backslash and NUL paths and any empty, "." or ".." segment
    are rejected, so the policy and the GitHub API always see the same plain path.
    """
    path = raw.strip()
    if not path or "\x00" in path or "\\" in path or path.startswith("/"):
        raise PatchRejected(f"unsafe patch path: {raw!r}")
    if any(part in ("", ".", "..") for part in path.split("/")):
        raise PatchRejected(f"unsafe patch path: {raw!r}")
    return path


_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$")


def _is_blank(line: str) -> bool:
    return line.strip("\r") == ""


def _starts_new_file(lines: list[str], i: int) -> bool:
    if lines[i].startswith("diff --git "):
        return True
    return lines[i].startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ ")


def canonicalize_patch(diff_text: str) -> str:
    """Return the diff with every hunk header recomputed from the hunk body.

    LLMs often write hunk headers whose counts do not match the body, and unidiff
    then quietly ignores the extra lines. Counting the body itself removes that
    risk: what is checked is exactly what is applied. A body line without a valid
    marker is rejected, never guessed. A blank line inside a hunk is a blank
    context line that lost its leading space, and blank lines that end a hunk
    or the diff are dropped.
    """
    if not diff_text or not diff_text.strip():
        raise PatchRejected("empty diff")
    raw = diff_text.split("\n")
    while raw and _is_blank(raw[-1]):
        raw.pop()
    out: list[str] = []
    hunks = 0
    i = 0
    while i < len(raw):
        line = raw[i]
        match = _HUNK_HEADER.match(line)
        if match is None:
            if line.startswith("@@"):
                raise PatchRejected(f"malformed hunk header: {line[:60]!r}")
            out.append(line)
            i += 1
            continue
        i += 1
        body: list[str] = []
        while i < len(raw) and not raw[i].startswith("@@") and not _starts_new_file(raw, i):
            body.append(raw[i])
            i += 1
        while body and _is_blank(body[-1]):
            body.pop()
        old_count = 0
        new_count = 0
        fixed: list[str] = []
        for body_line in body:
            if _is_blank(body_line):
                body_line = " " + body_line
            marker = body_line[0]
            if marker == " ":
                old_count += 1
                new_count += 1
            elif marker == "-":
                old_count += 1
            elif marker == "+":
                new_count += 1
            elif marker != "\\":
                raise PatchRejected(f"hunk line has no valid marker: {body_line[:60]!r}")
            fixed.append(body_line)
        if old_count == 0 and new_count == 0:
            raise PatchRejected("diff has an empty hunk")
        hunks += 1
        out.append(
            f"@@ -{match.group(1)},{old_count} +{match.group(2)},{new_count} @@{match.group(3)}"
        )
        out.extend(fixed)
    if hunks == 0:
        raise PatchRejected("diff has no hunks")
    return "\n".join(out) + "\n"


def parse_single_file_patch(diff_text: str) -> tuple[str, unidiff.PatchSet]:
    """Return (repo-relative path, PatchSet) for a diff that edits exactly one file."""
    if not diff_text or not diff_text.strip():
        raise PatchRejected("empty diff")
    diff_text = canonicalize_patch(diff_text)
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
    source = _strip_diff_prefix(patched_file.source_file)
    target = _strip_diff_prefix(patched_file.target_file)
    if source != target:
        raise PatchRejected(f"diff headers name different files: {source} and {target}")
    return normalize_repo_path(source), patch_set


def _same_line(left: str, right: str) -> bool:
    return left.rstrip("\r\n") == right.rstrip("\r\n")


def _block_matches(lines: list[str], start: int, old: list[str]) -> bool:
    return all(_same_line(lines[start + k], want) for k, want in enumerate(old))


def _locate_hunk(lines: list[str], old: list[str], declared: int, cursor: int, line_no: int) -> int:
    """Return the index in lines where the old block of a hunk starts.

    The declared position wins when it matches. Otherwise the old block must
    match exactly one place at or after cursor, so a wrong line number is
    repaired but a guess is never made.
    """
    last = len(lines) - len(old)
    if cursor <= declared <= last and _block_matches(lines, declared, old):
        return declared
    found = [i for i in range(cursor, last + 1) if _block_matches(lines, i, old)]
    if not found:
        raise PatchRejected(f"hunk at line {line_no} does not match the current file")
    if len(found) > 1:
        raise PatchRejected(
            f"hunk at line {line_no} is ambiguous: its lines match {len(found)} places"
        )
    return found[0]


def apply_verified(original: str, patch_set: unidiff.PatchSet) -> str:
    """Apply a PatchSet, refusing any hunk whose old lines differ from the file."""
    lines = original.splitlines(keepends=True)
    old_types = (unidiff.LINE_TYPE_REMOVED, unidiff.LINE_TYPE_CONTEXT)
    new_types = (unidiff.LINE_TYPE_ADDED, unidiff.LINE_TYPE_CONTEXT)
    edits: list[tuple[int, int, list[str]]] = []
    for patched_file in patch_set:
        cursor = 0
        for hunk in patched_file:
            old = [ln.value for ln in hunk if ln.line_type in old_types]
            new = [ln.value for ln in hunk if ln.line_type in new_types]
            if old:
                start = _locate_hunk(lines, old, hunk.source_start - 1, cursor, hunk.source_start)
            else:
                start = hunk.source_start
                if start not in (0, len(lines)) or start < cursor:
                    raise PatchRejected(
                        f"hunk at line {hunk.source_start} has no context lines "
                        "and is not at the start or end of the file"
                    )
            edits.append((start, len(old), new))
            cursor = start + len(old)
    # Hunks go in reverse so earlier positions stay valid
    for start, length, new in reversed(edits):
        lines[start : start + length] = new
    return "".join(lines)
