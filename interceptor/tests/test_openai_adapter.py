from uuid import uuid4

import pytest

from app.cascade import PolicyHit
from app.enums import Action, PolicyLayer
from app.openai_adapter import (
    OPENAI_CHAT_COMPLETIONS_PATH,
    ChatCompletionsRequest,
    extract_openai_text_parts,
    openai_upstream_path,
    redact_openai_chat_body,
    synthesize_openai_block_message,
    synthesize_openai_block_sse,
)


def hit(matched_text: str = "SECRET=abc") -> PolicyHit:
    return PolicyHit(
        policy_id=str(uuid4()),
        slug="secret-token",
        layer=PolicyLayer.regex,
        action=Action.BLOCK,
        rule="no secrets",
        matched_text=matched_text,
    )


def test_chat_completions_schema_is_permissive_and_preserves_extra_fields():
    req = ChatCompletionsRequest.model_validate(
        {
            "model": "gpt-5.1-codex",
            "stream": True,
            "messages": [{"role": "user", "content": "hello", "name": "dev"}],
            "tools": [{"type": "function", "function": {"name": "x"}}],
            "temperature": 0.2,
            "vendor_extra": {"kept": True},
        }
    )

    dumped = req.model_dump()
    assert req.model == "gpt-5.1-codex"
    assert req.stream is True
    assert dumped["tools"][0]["function"]["name"] == "x"
    assert dumped["temperature"] == 0.2
    assert dumped["vendor_extra"] == {"kept": True}


def test_extract_openai_text_parts_only_evaluable_roles_and_text_blocks():
    req = ChatCompletionsRequest.model_validate(
        {
            "model": "gpt-5.1-codex",
            "messages": [
                {"role": "system", "content": "sys SECRET=abc"},
                {"role": "developer", "content": [{"type": "text", "text": "dev"}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "file://x"}},
                        {"type": "text", "text": "user"},
                    ],
                },
                {"role": "assistant", "content": "assistant SECRET=skip"},
                {"role": "tool", "content": "tool SECRET=skip"},
            ],
        }
    )

    parts = extract_openai_text_parts(req)

    assert [(part.path, part.role, part.text) for part in parts] == [
        ("messages[0].content", "system", "sys SECRET=abc"),
        ("messages[1].content[0].text", "developer", "dev"),
        ("messages[2].content[1].text", "user", "user"),
    ]


def test_synthesize_openai_block_message_shape():
    body = synthesize_openai_block_message("gpt-5.1-codex", "01TRACE", hit())

    assert body["id"] == "chatcmpl_tranquera_blocked_01TRACE"
    assert body["object"] == "chat.completion"
    assert body["model"] == "gpt-5.1-codex"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert "secret-token" in body["choices"][0]["message"]["content"]
    assert body["choices"][0]["finish_reason"] == "content_filter"
    assert body["usage"] == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


@pytest.mark.asyncio
async def test_synthesize_openai_block_sse_order_and_done():
    chunks = [
        chunk async for chunk in synthesize_openai_block_sse("gpt-5.1-codex", "01TRACE", hit())
    ]
    decoded = [chunk.decode() for chunk in chunks]

    assert decoded[0].startswith("data: ")
    assert '"delta":{"role":"assistant"}' in decoded[0]
    assert '"delta":{"content":' in decoded[1]
    assert '"finish_reason":"content_filter"' in decoded[2]
    assert decoded[-1] == "data: [DONE]\n\n"


def test_redact_openai_chat_body_only_strings_and_text_blocks_preserving_extra_fields():
    original = {
        "model": "gpt-5.1-codex",
        "stream": False,
        "messages": [
            {"role": "system", "content": "sys SECRET=abc", "cache_control": {"type": "ephemeral"}},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello SECRET=abc", "extra": 1},
                    {"type": "image_url", "image_url": {"url": "SECRET=abc"}},
                ],
            },
            {"role": "assistant", "content": "assistant SECRET=abc"},
            {"role": "tool", "content": "tool SECRET=abc"},
        ],
        "temperature": 0.1,
    }

    redacted, skipped = redact_openai_chat_body(original, [hit()])

    assert redacted is not original
    assert redacted["messages"][0]["content"] == "sys [REDACTED]"
    assert redacted["messages"][0]["cache_control"] == {"type": "ephemeral"}
    assert redacted["messages"][1]["content"][0] == {
        "type": "text",
        "text": "hello [REDACTED]",
        "extra": 1,
    }
    assert redacted["messages"][1]["content"][1]["image_url"]["url"] == "SECRET=abc"
    assert redacted["messages"][2]["content"] == "assistant SECRET=abc"
    assert redacted["messages"][3]["content"] == "tool SECRET=abc"
    assert redacted["temperature"] == 0.1
    assert skipped is True


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://api.openai.com/v1", "/v1/chat/completions"),
        ("https://litellm.example.com", "/v1/chat/completions"),
    ],
)
def test_openai_upstream_path_avoids_double_v1(base_url, expected):
    assert openai_upstream_path(base_url) == expected
    assert OPENAI_CHAT_COMPLETIONS_PATH == "/v1/chat/completions"
