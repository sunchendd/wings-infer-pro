import re


_DOC_PATTERN = re.compile(r"<\|doc_start\|>(.*?)<\|doc_end\|>", re.DOTALL)
_DOC_START = "<|doc_start|>"
_DOC_END = "<|doc_end|>"


def parse_document_chunks(content):
    """Extract strictly paired document blocks and surrounding prompt text."""
    if not isinstance(content, str) or not content:
        return "", "", "", []

    matches = list(_DOC_PATTERN.finditer(content))
    if not matches:
        return content, "", "", []

    prefix = content[:matches[0].start()]
    postfix = content[matches[-1].end():]
    chunks = [match.group(1).strip() for match in matches if match.group(1).strip()]
    query = _extract_query_from_prefix_postfix(prefix, postfix)
    return prefix, postfix, query, chunks


def has_strictly_paired_document_tags(content):
    """Return true only when every document marker belongs to a valid pair."""
    if not isinstance(content, str):
        return False
    matches = list(_DOC_PATTERN.finditer(content))
    if not matches:
        return False
    return len(matches) == content.count(_DOC_START) == content.count(_DOC_END)


def _extract_query_from_prefix_postfix(prefix, postfix):
    match = re.search(
        r"(Question:|Question\uFF1A|\u95EE\u9898\uFF1A|\u95EE\u9898:)(.*)",
        prefix + postfix,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(2).strip()
    return postfix.strip()
