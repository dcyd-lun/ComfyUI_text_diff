"""
HTML formatter for generating GitHub-style diff output.

Generates complete HTML documents with embedded CSS for both
unified and side-by-side diff views.
"""

import html
from typing import Dict, Optional, Union

from .diff_engine import DiffResult, DiffLine

# Theme color constants (dark theme matching ComfyUI interface)
COLOR_BG_DARK = "#1e1e1e"
COLOR_BG_HEADER = "#252526"
COLOR_BORDER = "#3c3c3c"
COLOR_TEXT = "#d4d4d4"
COLOR_TEXT_MUTED = "#9d9d9d"
COLOR_LINE_NUM = "#6e7681"
COLOR_ADDED = "#4ec9b0"
COLOR_DELETED = "#f14c4c"
COLOR_ADDED_BG = "#1e3a1e"
COLOR_DELETED_BG = "#3a1e1e"
COLOR_CHAR_ADDED_BG = "#2d5a2d"
COLOR_CHAR_DELETED_BG = "#5a2d2d"

# Dark theme CSS for diff display
DIFF_CSS = """
<style>
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 12px;
    line-height: 1.5;
    background: #1e1e1e;
    color: #d4d4d4;
}

.diff-container {
    width: 100%;
    overflow-x: auto;
}

.diff-header {
    padding: 8px 12px;
    background: #252526;
    border-bottom: 1px solid #3c3c3c;
    display: flex;
    align-items: center;
    gap: 12px;
}

.stats {
    font-size: 12px;
    color: #9d9d9d;
}

.stats .added {
    color: #4ec9b0;
    font-weight: 600;
}

.stats .deleted {
    color: #f14c4c;
    font-weight: 600;
}

.diff-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}

.diff-line {
    height: 20px;
}

.diff-line:hover {
    background-color: #2a2a2a;
}

.line-num {
    width: 50px;
    min-width: 50px;
    padding: 0 8px;
    color: #6e7681;
    text-align: right;
    border-right: 1px solid #3c3c3c;
    user-select: none;
    vertical-align: top;
    font-size: 12px;
}

.diff-content {
    padding: 0 8px;
    white-space: pre-wrap;
    word-break: break-all;
    overflow-wrap: break-word;
}

.line-added {
    background-color: #1e3a1e;
}

.line-added .line-num {
    background-color: #2d4a2d;
    border-color: #3d5a3d;
}

.line-deleted {
    background-color: #3a1e1e;
}

.line-deleted .line-num {
    background-color: #4a2d2d;
    border-color: #5a3d3d;
}

.char-added {
    background-color: #2d5a2d;
    border-radius: 2px;
    color: #98c379;
}

.char-deleted {
    background-color: #5a2d2d;
    border-radius: 2px;
    color: #e06c75;
}

/* Side-by-side specific styles */
.side-by-side .diff-table {
    table-layout: fixed;
}

.side-by-side .line-num {
    width: 40px;
    min-width: 40px;
}

.side-by-side .diff-content {
    width: calc(50% - 40px);
}

.side-by-side .diff-content.left {
    border-right: 1px solid #3c3c3c;
}

.side-by-side .line-added .diff-content.left {
    background-color: transparent;
}

.side-by-side .line-deleted .diff-content.right {
    background-color: transparent;
}

.empty-cell {
    background-color: #252526;
}

.line-unchanged .diff-content {
    color: #9d9d9d;
}

/* Prefix indicators */
.prefix {
    display: inline-block;
    width: 16px;
    text-align: center;
    color: inherit;
    user-select: none;
}

.prefix-add {
    color: #4ec9b0;
}

.prefix-del {
    color: #f14c4c;
}

/* No changes message */
.no-changes {
    padding: 24px;
    text-align: center;
    color: #9d9d9d;
    background: #252526;
}

.no-changes-icon {
    font-size: 24px;
    margin-bottom: 8px;
}
</style>
"""


def format_diff_html(diff_result: DiffResult, view_mode: str = "unified") -> str:
    """
    Generate complete HTML for diff display.

    Args:
        diff_result: The computed diff result
        view_mode: 'unified' or 'side_by_side'

    Returns:
        Complete HTML document string
    """
    if view_mode == "side_by_side":
        return format_side_by_side_view(diff_result)
    return format_unified_view(diff_result)


def format_unified_view(diff_result: DiffResult) -> str:
    """
    Generate unified diff view (similar to git diff).

    Shows all lines in a single column with +/- prefixes.
    """
    stats = diff_result.stats
    header = _generate_header(stats)

    # Check for no changes
    if stats["additions"] == 0 and stats["deletions"] == 0:
        return _generate_html_document(
            f"""
            {header}
            <div class="no-changes">
                <div class="no-changes-icon">&#10003;</div>
                <div>No differences found</div>
            </div>
            """,
            "unified",
        )

    rows = []
    for line in diff_result.lines:
        row_class = _get_row_class(line.change_type)
        line_num_a = line.line_num_a if line.line_num_a is not None else ""
        line_num_b = line.line_num_b if line.line_num_b is not None else ""
        content = _format_content_with_char_diffs(line)
        prefix = _get_prefix(line.change_type)

        rows.append(
            f"""<tr class="diff-line {row_class}">
                <td class="line-num">{line_num_a}</td>
                <td class="line-num">{line_num_b}</td>
                <td class="diff-content">{prefix}{content}</td>
            </tr>"""
        )

    table = f"""
        <table class="diff-table">
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    """

    return _generate_html_document(f"{header}{table}", "unified")


def format_side_by_side_view(diff_result: DiffResult) -> str:
    """
    Generate side-by-side diff view.

    Shows original and modified text in two columns.
    """
    stats = diff_result.stats
    header = _generate_header(stats)

    # Check for no changes
    if stats["additions"] == 0 and stats["deletions"] == 0:
        return _generate_html_document(
            f"""
            {header}
            <div class="no-changes">
                <div class="no-changes-icon">&#10003;</div>
                <div>No differences found</div>
            </div>
            """,
            "side-by-side",
        )

    # Group lines for side-by-side display
    rows = []
    i = 0
    lines = diff_result.lines

    while i < len(lines):
        line = lines[i]

        if line.change_type == "unchanged":
            # Unchanged line - show on both sides
            content = _format_content_with_char_diffs(line)
            rows.append(_create_side_by_side_row(
                line.line_num_a, content,
                line.line_num_b, content,
                "line-unchanged"
            ))
            i += 1

        elif line.change_type == "deleted":
            # Check if this is a paired line from a replace opcode AND next line is its pair
            if (line.is_paired and
                i + 1 < len(lines) and
                lines[i + 1].change_type == "added" and
                lines[i + 1].is_paired):
                # Paired deletion and addition from same replace opcode
                del_line = line
                add_line = lines[i + 1]
                left_content = _format_content_with_char_diffs(del_line, for_deleted=True)
                right_content = _format_content_with_char_diffs(add_line, for_added=True)
                rows.append(_create_side_by_side_row(
                    del_line.line_num_a, left_content,
                    add_line.line_num_b, right_content,
                    "line-modified"
                ))
                i += 2
            else:
                # Deletion only
                content = _format_content_with_char_diffs(line, for_deleted=True)
                rows.append(_create_side_by_side_row(
                    line.line_num_a, content,
                    "", "",
                    "line-deleted"
                ))
                i += 1

        elif line.change_type == "added":
            # Addition only (no paired deletion)
            content = _format_content_with_char_diffs(line, for_added=True)
            rows.append(_create_side_by_side_row(
                "", "",
                line.line_num_b, content,
                "line-added"
            ))
            i += 1

        else:
            i += 1

    table = f"""
        <table class="diff-table">
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    """

    return _generate_html_document(f"{header}{table}", "side-by-side")


def _create_side_by_side_row(
    left_num: Union[int, str],
    left_content: str,
    right_num: Union[int, str],
    right_content: str,
    row_class: str
) -> str:
    """
    Create a side-by-side table row with left and right columns.

    Args:
        left_num: Line number for left side (or empty string)
        left_content: HTML content for left side
        right_num: Line number for right side (or empty string)
        right_content: HTML content for right side
        row_class: CSS class for the row (line-unchanged, line-modified, etc.)

    Returns:
        HTML string for the table row
    """
    left_cell_class = "diff-content left"
    right_cell_class = "diff-content right"

    if not left_content and left_num == "":
        left_cell_class += " empty-cell"
    if not right_content and right_num == "":
        right_cell_class += " empty-cell"

    # Add background colors for modified rows (dark theme)
    left_bg = ""
    right_bg = ""
    if row_class == "line-deleted" or row_class == "line-modified":
        left_bg = ' style="background-color: #3a1e1e;"'
    if row_class == "line-added" or row_class == "line-modified":
        right_bg = ' style="background-color: #1e3a1e;"'

    return f"""<tr class="diff-line {row_class}">
        <td class="line-num">{left_num}</td>
        <td class="{left_cell_class}"{left_bg}>{left_content}</td>
        <td class="line-num">{right_num}</td>
        <td class="{right_cell_class}"{right_bg}>{right_content}</td>
    </tr>"""


def _generate_header(stats: Dict[str, int]) -> str:
    """
    Generate the diff header with addition/deletion statistics.

    Args:
        stats: Dictionary with 'additions' and 'deletions' counts

    Returns:
        HTML string for the header section
    """
    additions = stats.get("additions", 0)
    deletions = stats.get("deletions", 0)

    return f"""
        <div class="diff-header">
            <span class="stats">
                <span class="added">+{additions}</span>
                &nbsp;
                <span class="deleted">-{deletions}</span>
            </span>
        </div>
    """


def _generate_html_document(body_content: str, view_class: str) -> str:
    """
    Generate a complete HTML document with embedded CSS.

    Args:
        body_content: HTML content for the body
        view_class: CSS class for the view mode ('unified' or 'side-by-side')

    Returns:
        Complete HTML document string
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {DIFF_CSS}
</head>
<body>
    <div class="diff-container {view_class}">
        {body_content}
    </div>
</body>
</html>"""


def _get_row_class(change_type: str) -> str:
    """Get the CSS class for a row based on change type."""
    return {
        "added": "line-added",
        "deleted": "line-deleted",
        "unchanged": "line-unchanged",
    }.get(change_type, "")


def _get_prefix(change_type: str) -> str:
    """Get the prefix indicator for unified view."""
    if change_type == "added":
        return '<span class="prefix prefix-add">+</span>'
    elif change_type == "deleted":
        return '<span class="prefix prefix-del">-</span>'
    return '<span class="prefix">&nbsp;</span>'


def _format_content_with_char_diffs(
    line: DiffLine,
    for_deleted: bool = False,
    for_added: bool = False
) -> str:
    """
    Format line content with character-level highlighting.

    Args:
        line: The DiffLine to format
        for_deleted: If True, format for left side of side-by-side (show deletions only)
        for_added: If True, format for right side of side-by-side (show additions only)

    Returns:
        HTML string with highlighted character differences
    """
    content = line.content.rstrip("\n\r")

    if not line.char_diffs:
        return html.escape(content)

    # Determine what to show based on context:
    # - Side-by-side mode: for_deleted or for_added will be True
    # - Unified mode: both are False, determine from line.change_type
    # Each line should only show its own content (deleted lines show deletions, added lines show additions)
    show_deletions = for_deleted or (not for_added and line.change_type == "deleted")
    show_additions = for_added or (not for_deleted and line.change_type == "added")

    parts = []
    for change_type, text in line.char_diffs:
        escaped = html.escape(text.rstrip("\n\r"))

        if change_type == "equal":
            parts.append(escaped)
        elif change_type == "delete" and show_deletions:
            parts.append(f'<span class="char-deleted">{escaped}</span>')
        elif change_type == "insert" and show_additions:
            parts.append(f'<span class="char-added">{escaped}</span>')
        # Skip insert on deleted lines, skip delete on added lines

    return "".join(parts)
