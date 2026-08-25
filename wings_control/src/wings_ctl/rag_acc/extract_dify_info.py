import re

from wings_ctl.proxy.proxy_config import logger


_CONTEXT_PATTERN = re.compile(r"<context>\s*(.*?)\s*</context>", re.DOTALL | re.IGNORECASE)


def _get_msg_field(msg, field: str, default=""):
    """Extract a field from either a Pydantic-style object or a dict."""
    if isinstance(msg, dict):
        return msg.get(field, default)
    return getattr(msg, field, default)


def _get_messages(chat_input):
    messages = getattr(chat_input, "messages", None)
    return messages if isinstance(messages, (list, tuple)) else []


def _text_content(msg) -> str:
    content = _get_msg_field(msg, "content", "")
    return content if isinstance(content, str) else ""


def extract_dify_info(chat_input):
    """Extract Dify context and the latest user question.

    Detection and extraction intentionally share this implementation so a
    request cannot be classified as Dify RAG while yielding zero documents.
    """
    messages = _get_messages(chat_input)
    if not messages:
        return None

    system_prompt = ""
    context_content = None
    user_question = ""

    for msg in messages:
        role = _get_msg_field(msg, "role", "")
        content = _text_content(msg)
        if role == "system" and context_content is None:
            match = _CONTEXT_PATTERN.search(content)
            if match:
                system_prompt = content
                context_content = match.group(1)
        elif role == "user" and content.strip():
            user_question = content.strip()

    if context_content is None or not user_question:
        return None

    logger.debug("Dify system prompt length: %d", len(system_prompt))
    rag_documents = [item.strip() for item in context_content.splitlines() if item.strip()]
    logger.debug("Extracted context chunks: %d", len(rag_documents))
    if not rag_documents:
        return None

    return {
        "rag_documents": rag_documents,
        "system_prompt": system_prompt,
        "user_question": user_question,
    }


def is_dify_scenario(chat_input) -> bool:
    return extract_dify_info(chat_input) is not None
