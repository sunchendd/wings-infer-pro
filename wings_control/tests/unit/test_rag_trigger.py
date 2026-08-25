import asyncio
import json
from types import SimpleNamespace

from wings_ctl.rag_acc.document_processor import (
    has_strictly_paired_document_tags,
    parse_document_chunks,
)
from wings_ctl.rag_acc.extract_dify_info import extract_dify_info, is_dify_scenario
from wings_ctl.rag_acc.rag_app import (
    detect_rag_scenario,
    is_no_rag_scenario,
    is_rag_scenario,
    is_warmup_scenario,
)


def _chat(*messages):
    return SimpleNamespace(messages=list(messages))


def _msg(role, content):
    return {"role": role, "content": content}


def _large_chunks():
    return ["a" * 700, "b" * 700, "c" * 700]


def _tagged_prompt(chunks, postfix="Question: what is the answer?"):
    documents = "".join(
        f"<|doc_start|>{chunk}<|doc_end|>" for chunk in chunks
    )
    return documents + postfix


def test_valid_generic_rag_is_detected():
    chat = _chat(_msg("user", _tagged_prompt(_large_chunks())))

    detection = detect_rag_scenario(chat)

    assert detection is not None
    assert detection.kind == "generic"
    assert detection.query == "what is the answer?"
    assert len(detection.chunks) == 3
    assert is_rag_scenario(chat)


def test_unbalanced_or_out_of_order_tags_do_not_trigger():
    content = (
        "<|doc_start|>" * 3
        + "x" * 2100
        + "<|doc_end|>" * 3
        + "Question: q"
    )
    chat = _chat(_msg("user", content))

    assert not has_strictly_paired_document_tags(content)
    assert detect_rag_scenario(chat) is None


def test_short_documents_do_not_trigger_even_with_long_prompt_prefix():
    content = "prefix" * 500 + _tagged_prompt(["a", "b", "c"])

    assert detect_rag_scenario(_chat(_msg("user", content))) is None


def test_system_documents_use_latest_user_message_as_query():
    system_content = _tagged_prompt(_large_chunks(), postfix="")
    chat = _chat(
        _msg("system", system_content),
        _msg("user", "Use the supplied documents to answer this question"),
    )

    detection = detect_rag_scenario(chat)

    assert detection is not None
    assert detection.kind == "generic"
    assert detection.query == "Use the supplied documents to answer this question"


def test_system_documents_with_trailing_instruction_use_latest_user_question():
    system_content = _tagged_prompt(
        _large_chunks(),
        postfix="Only answer from the supplied documents.",
    )
    chat = _chat(
        _msg("system", system_content),
        _msg("user", "What is the actual answer?"),
    )

    detection = detect_rag_scenario(chat)

    assert detection is not None
    assert detection.kind == "generic"
    assert detection.query == "What is the actual answer?"


def test_empty_or_missing_messages_are_safe():
    assert detect_rag_scenario(_chat()) is None
    assert detect_rag_scenario(SimpleNamespace(messages=None)) is None
    assert detect_rag_scenario(SimpleNamespace()) is None


def test_dify_detection_and_extraction_share_the_same_parser():
    content = "prefix <context>one</context> suffix"
    chat = _chat(_msg("system", content), _msg("user", "q"))

    extracted = extract_dify_info(chat)

    assert extracted is not None
    assert extracted["rag_documents"] == ["one"]
    assert is_dify_scenario(chat)
    assert detect_rag_scenario(chat) is None


def test_large_dify_context_triggers_only_after_successful_extraction():
    context = "\n".join(_large_chunks())
    chat = _chat(
        _msg("system", f"prefix\n<context>{context}</context>\nsuffix"),
        _msg("user", "question"),
    )

    detection = detect_rag_scenario(chat)

    assert detection is not None
    assert detection.kind == "dify"
    assert detection.query == "question"
    assert len(detection.chunks) == 3


def test_control_markers_require_exact_message_match():
    assert is_warmup_scenario(" /rag_acc_warm_up ")
    assert not is_warmup_scenario("please explain /rag_acc_warm_up")
    assert is_no_rag_scenario(_chat(_msg("user", " /no_rag_acc ")))
    assert not is_no_rag_scenario(_chat(_msg("user", "please explain /no_rag_acc")))


def test_document_parser_returns_only_paired_blocks():
    content = "prefix<|doc_start|>doc1<|doc_end|><|doc_start|>doc2<|doc_end|>Question: q"

    prefix, postfix, query, chunks = parse_document_chunks(content)

    assert prefix == "prefix"
    assert postfix == "Question: q"
    assert query == "q"
    assert chunks == ["doc1", "doc2"]


class _FakeRequest:
    def __init__(self, payload, headers=None):
        self._body = json.dumps(payload).encode("utf-8")
        self.headers = headers or {}

    async def body(self):
        return self._body


def test_gateway_falls_back_for_missing_messages(monkeypatch):
    from wings_ctl.proxy import gateway

    async def fake_forward(request, path):
        return "forwarded"

    monkeypatch.setattr(gateway, "_forward_stream", fake_forward)
    request = _FakeRequest({"model": "test", "stream": True})

    result = asyncio.run(gateway.handle_rag_scenario(request, "/v1/chat/completions"))

    assert result == "forwarded"


def test_gateway_no_rag_marker_requires_exact_message(monkeypatch):
    from wings_ctl.proxy import gateway

    async def fake_forward(request, path):
        return "forwarded"

    async def fake_rag(chat_input, request, backend_url, detection):
        return detection.kind

    monkeypatch.setattr(gateway, "_forward_stream", fake_forward)
    monkeypatch.setattr(gateway, "rag_acc_chat", fake_rag)

    content = _tagged_prompt(
        _large_chunks(),
        postfix="Question: please explain /no_rag_acc",
    )
    request = _FakeRequest(
        {"model": "test", "stream": True, "messages": [_msg("user", content)]}
    )

    result = asyncio.run(gateway.handle_rag_scenario(request, "/v1/chat/completions"))

    assert result == "generic"


def test_gateway_exact_no_rag_marker_forces_fallback(monkeypatch):
    from wings_ctl.proxy import gateway

    async def fake_forward(request, path):
        return "forwarded"

    monkeypatch.setattr(gateway, "_forward_stream", fake_forward)
    request = _FakeRequest(
        {
            "model": "test",
            "stream": True,
            "messages": [
                _msg("system", _tagged_prompt(_large_chunks(), postfix="")),
                _msg("user", "/no_rag_acc"),
            ],
        }
    )

    result = asyncio.run(gateway.handle_rag_scenario(request, "/v1/chat/completions"))

    assert result == "forwarded"

def test_backend_failure_is_info_while_engine_is_starting(monkeypatch):
    from wings_ctl.proxy import gateway

    infos = []
    errors = []
    monkeypatch.setattr(gateway, "jlog", lambda event, **fields: infos.append((event, fields)))
    monkeypatch.setattr(gateway, "elog", lambda event, **fields: errors.append((event, fields)))
    monkeypatch.setattr(gateway, "map_http_code_from_state", lambda health: 201)
    monkeypatch.setattr(gateway.app.state, "health", {"ever_ready": False}, raising=False)

    gateway._log_backend_failure("retry_exception", detail="connection refused")

    assert infos == [
        ("retry_exception", {"phase": "starting", "detail": "connection refused"})
    ]
    assert errors == []


def test_backend_failure_remains_error_after_engine_was_ready(monkeypatch):
    from wings_ctl.proxy import gateway

    infos = []
    errors = []
    monkeypatch.setattr(gateway, "jlog", lambda event, **fields: infos.append((event, fields)))
    monkeypatch.setattr(gateway, "elog", lambda event, **fields: errors.append((event, fields)))
    monkeypatch.setattr(gateway.app.state, "health", {"ever_ready": True}, raising=False)

    gateway._log_backend_failure("retry_exception", detail="connection refused")

    assert infos == []
    assert errors == [("retry_exception", {"detail": "connection refused"})]
