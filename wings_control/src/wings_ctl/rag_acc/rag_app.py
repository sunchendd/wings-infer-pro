from dataclasses import dataclass
from typing import List, Optional

from fastapi import Request
from fastapi.responses import StreamingResponse

from wings_ctl.proxy.proxy_config import logger
from wings_ctl.rag_acc.document_processor import (
    has_strictly_paired_document_tags,
    parse_document_chunks,
)
from wings_ctl.rag_acc.extract_dify_info import extract_dify_info
from wings_ctl.rag_acc.request_handlers import (
    create_chunk_request,
    create_combine_request,
    create_simple_request,
)
from wings_ctl.rag_acc.stream_collector import StreamCollector


MIN_CONTENT_LENGTH = 2048
MIN_DOC_BLOCKS = 3
_WARMUP_MARKER = "/rag_acc_warm_up"
_NO_RAG_MARKER = "/no_rag_acc"


@dataclass(frozen=True)
class RagDetection:
    kind: str
    query: str
    chunks: List[str]
    content: str = ""


def _get_messages(chat_input):
    messages = getattr(chat_input, "messages", None)
    return messages if isinstance(messages, (list, tuple)) else []


def _get_message_field(msg, field: str, default=""):
    if isinstance(msg, dict):
        return msg.get(field, default)
    return getattr(msg, field, default)


def _message_content(msg) -> str:
    """Return textual message content without stringifying arbitrary objects."""
    content = _get_message_field(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
            elif isinstance(getattr(part, "text", None), str):
                text_parts.append(part.text)
        return "\n".join(text_parts)
    return ""


def is_warmup_scenario(content: str) -> bool:
    return isinstance(content, str) and content.strip() == _WARMUP_MARKER


def is_no_rag_scenario(chat_input) -> bool:
    """Recognize the legacy opt-out marker only as an exact message value."""
    return any(_message_content(msg).strip() == _NO_RAG_MARKER for msg in _get_messages(chat_input))


def _latest_user_content(messages) -> str:
    for msg in reversed(messages):
        if _get_message_field(msg, "role", "") == "user":
            content = _message_content(msg).strip()
            if content:
                return content
    return ""


def _generic_candidates(messages):
    if not messages:
        return []
    candidates = [messages[-1]]
    candidates.extend(
        msg for msg in reversed(messages[:-1])
        if _get_message_field(msg, "role", "") == "system"
    )
    return candidates


def _documents_are_accelerable(chunks, scenario: str) -> bool:
    if len(chunks) < MIN_DOC_BLOCKS:
        logger.info(
            "%s RAG scenario detected, but document count is too small: %d",
            scenario,
            len(chunks),
        )
        return False
    document_length = sum(len(chunk) for chunk in chunks)
    if document_length < MIN_CONTENT_LENGTH:
        logger.info(
            "%s RAG scenario detected, but document content is shorter than 2K: %d",
            scenario,
            document_length,
        )
        return False
    return True


def detect_rag_scenario(chat_input) -> Optional[RagDetection]:
    """Detect and fully validate a RAG request before acceleration starts."""
    messages = _get_messages(chat_input)
    if not messages:
        return None

    last_content = _message_content(messages[-1])
    if is_warmup_scenario(last_content):
        return RagDetection(
            kind="warmup",
            query="<query_warm_up>",
            chunks=["<query_warm_up>"],
            content=last_content,
        )

    latest_user_content = _latest_user_content(messages)
    for msg in _generic_candidates(messages):
        role = _get_message_field(msg, "role", "")
        content = _message_content(msg)
        if "<|doc_start|>" not in content and "<|doc_end|>" not in content:
            continue
        if not has_strictly_paired_document_tags(content):
            logger.info("RAG document markers are unbalanced or out of order")
            continue

        prefix, postfix, query, chunks = parse_document_chunks(content)
        if role == "system" and latest_user_content:
            query = latest_user_content
        elif not query and content != latest_user_content:
            query = latest_user_content
        query = query.strip()
        if not query:
            logger.info("RAG scenario detected, but no user query could be extracted")
            continue
        if not _documents_are_accelerable(chunks, "generic"):
            continue

        logger.debug(
            "RAG prompt lengths: prefix=%d postfix=%d query=%d",
            len(prefix),
            len(postfix),
            len(query),
        )
        return RagDetection(kind="generic", query=query, chunks=chunks, content=content)

    dify = extract_dify_info(chat_input)
    if dify is not None:
        chunks = dify["rag_documents"]
        query = dify["user_question"].strip()
        if query and _documents_are_accelerable(chunks, "Dify"):
            return RagDetection(kind="dify", query=query, chunks=chunks)

    return None


def is_rag_scenario(chat_input, request: Request = None) -> bool:
    detection = detect_rag_scenario(chat_input)
    return detection is not None and detection.kind in {"generic", "warmup"}


def extract_last_message_and_log(chat_input):
    logger.debug("input: %s", chat_input)
    messages = _get_messages(chat_input)
    if not messages:
        return [], None, "", ""

    previous_messages = list(messages[:-1])
    msg = messages[-1]
    role = str(_get_message_field(msg, "role", "user") or "user")
    content = _message_content(msg)
    logger.debug("msg content: %s, %s, %s", content, previous_messages, role)
    return previous_messages, msg, role, content


async def rag_acc_chat(
    chat_input,
    request: Request,
    backend_url: str = "",
    detection: Optional[RagDetection] = None,
):
    detection = detection or detect_rag_scenario(chat_input)
    if detection is None:
        simple_request = create_simple_request(chat_input, {}, backend_url)
        return StreamingResponse(simple_request())

    query = detection.query
    chunks = sorted(detection.chunks, key=len)
    for i, chunk in enumerate(chunks):
        logger.debug("chunk[%d] length: %d", i, len(chunk))

    chunk_request = create_chunk_request(chat_input, query, chunks, {}, backend_url)
    combine_request = create_combine_request(chat_input, query, chunks, {}, backend_url)
    collector = StreamCollector(len(chunks), chunk_request, combine_request)
    return StreamingResponse(collector.collect_and_stream(), media_type="text/event-stream")
