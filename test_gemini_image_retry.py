#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import io
import sys
import types
from pathlib import Path
from unittest.mock import patch

import requests
from PIL import Image


if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


PLUGIN_DIR = Path(__file__).parent
sys.path.insert(0, str(PLUGIN_DIR))

from py import gemini_image_node as gemini_module


OK = "[OK]"
FAIL = "[FAIL]"


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


class FakeExecutionBlocker:
    def __init__(self, message=None):
        self.message = message


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def fake_execution_blocker_context():
    fake_graph = types.ModuleType("comfy_execution.graph")
    fake_graph.ExecutionBlocker = FakeExecutionBlocker

    fake_package = types.ModuleType("comfy_execution")
    fake_package.graph = fake_graph

    return patch.dict(
        sys.modules,
        {
            "comfy_execution": fake_package,
            "comfy_execution.graph": fake_graph,
        },
    )


def make_success_payload(text="generated text"):
    image = Image.new("RGB", (2, 2), color="blue")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": text},
                        {"inlineData": {"data": encoded}},
                    ]
                }
            }
        ]
    }


def build_node():
    node = gemini_module.HouLai_Gemini_Image_Gen()
    node.timeout = 5
    return node


def base_call_kwargs():
    return {
        "prompt": "Generate a beautiful landscape",
        "api_key": "test-key",
        "base_url": "https://example.com/generate",
        "aspect_ratio_mode": "auto",
        "custom_aspect_ratio": "1:1",
        "image_size": "2K",
        "response_modalities": "IMAGE",
    }


def test_input_types_include_retry_controls():
    required = gemini_module.HouLai_Gemini_Image_Gen.INPUT_TYPES()["required"]
    expect("enable_retry" in required, "enable_retry input is missing")
    expect("retry_count" in required, "retry_count input is missing")
    expect(required["enable_retry"][1]["default"] is False, "enable_retry default should be False")
    expect(required["retry_count"][1]["default"] == 2, "retry_count default should be 2")


def test_widget_i18n_includes_gemini_retry_labels():
    js_text = (PLUGIN_DIR / "js" / "houlai_widget_i18n.js").read_text(encoding="utf-8")
    expect("HouLai_Gemini_Image_Gen" in js_text, "widget i18n should target the Gemini node")
    expect("enable_retry" in js_text, "widget i18n should localize enable_retry")
    expect("retry_count" in js_text, "widget i18n should localize retry_count")
    expect("失败重试" in js_text, "widget i18n should include Chinese retry labels")


def test_widget_i18n_preserves_combo_values_and_normalizes_legacy_gemini_values():
    js_text = (PLUGIN_DIR / "js" / "houlai_widget_i18n.js").read_text(encoding="utf-8")
    expect(
        "widget.options.values = widget.options.values.map" not in js_text,
        "widget i18n should not overwrite combo option values anymore",
    )
    expect(
        "legacyValueMaps" in js_text,
        "widget i18n should define legacy value maps for old Chinese workflow values",
    )
    expect(
        "beforeQueued" in js_text,
        "widget i18n should normalize legacy Gemini values right before prompt queueing",
    )


def test_retry_disabled_keeps_legacy_failure_behavior():
    node = build_node()

    with patch.object(gemini_module.requests, "post", side_effect=requests.exceptions.Timeout("simulated timeout")) as mocked_post:
        image_output, response_text, info = node.generate_image(
            enable_retry=False,
            retry_count=2,
            **base_call_kwargs(),
        )

    expect(mocked_post.call_count == 1, "retry disabled should only call the API once")
    expect(hasattr(image_output, "shape"), "retry disabled should still return a blank tensor image")
    expect(response_text == "", "legacy failure behavior should keep response_text empty")
    expect("超时" in info or "timeout" in info.lower(), "timeout message should be returned in info")


def test_retry_enabled_retries_until_success():
    node = build_node()
    success_response = FakeResponse(payload=make_success_payload())

    with patch.object(
        gemini_module.requests,
        "post",
        side_effect=[
            requests.exceptions.Timeout("first timeout"),
            requests.exceptions.Timeout("second timeout"),
            success_response,
        ],
    ) as mocked_post:
        image_output, response_text, info = node.generate_image(
            enable_retry=True,
            retry_count=2,
            **base_call_kwargs(),
        )

    expect(mocked_post.call_count == 3, "retry enabled should keep trying until success")
    expect(hasattr(image_output, "shape"), "successful retry should return an image tensor")
    expect(response_text == "generated text", "successful retry should preserve response_text")
    expect("成功" in info, "successful retry should still return success info")


def test_localized_widget_values_are_accepted():
    node = build_node()
    success_response = FakeResponse(payload=make_success_payload("localized success"))
    call_kwargs = base_call_kwargs()
    call_kwargs["aspect_ratio_mode"] = "自动"
    call_kwargs["response_modalities"] = "仅图片"

    with patch.object(gemini_module.requests, "post", return_value=success_response) as mocked_post:
        image_output, response_text, info = node.generate_image(
            enable_retry=False,
            retry_count=2,
            **call_kwargs,
        )

    expect(mocked_post.call_count == 1, "localized widget values should still make one successful request")
    payload = mocked_post.call_args.kwargs["json"]
    expect(
        payload["generationConfig"]["responseModalities"] == ["IMAGE"],
        "localized response modal should normalize back to IMAGE before the API call",
    )
    expect(
        "aspectRatio" not in payload["generationConfig"]["imageConfig"],
        "localized auto aspect ratio should normalize back to the API auto mode",
    )
    expect(hasattr(image_output, "shape"), "localized widget values should still return an image tensor")
    expect(response_text == "localized success", "localized widget values should be normalized before parsing")
    expect("宽高比" in info, "localized widget values should still produce the normal success info")


def test_retry_enabled_blocks_image_chain_and_reports_timeout_after_exhaustion():
    node = build_node()

    with fake_execution_blocker_context():
        with patch.object(
            gemini_module.requests,
            "post",
            side_effect=requests.exceptions.Timeout("persistent timeout"),
        ) as mocked_post:
            image_output, response_text, info = node.generate_image(
                enable_retry=True,
                retry_count=2,
                **base_call_kwargs(),
            )

    expect(mocked_post.call_count == 3, "retry enabled should exhaust 1 initial try + 2 retries")
    expect(isinstance(image_output, FakeExecutionBlocker), "image output should block downstream execution")
    expect(isinstance(response_text, FakeExecutionBlocker), "response_text should also block downstream execution")
    expect("超时" in info or "timeout" in info.lower(), "info output should include timeout failure reason")
    expect("3" in info, "info output should mention the exhausted attempt count")


def run_test(name, func):
    try:
        func()
        print(f"{OK} {name}")
        return True
    except Exception as exc:
        print(f"{FAIL} {name}: {exc}")
        return False


def main():
    tests = [
        ("INPUT_TYPES include retry controls", test_input_types_include_retry_controls),
        ("Widget i18n includes Gemini retry labels", test_widget_i18n_includes_gemini_retry_labels),
        ("Widget i18n preserves combo values", test_widget_i18n_preserves_combo_values_and_normalizes_legacy_gemini_values),
        ("Retry disabled keeps legacy failure behavior", test_retry_disabled_keeps_legacy_failure_behavior),
        ("Retry enabled retries until success", test_retry_enabled_retries_until_success),
        ("Localized widget values are accepted", test_localized_widget_values_are_accepted),
        ("Retry enabled blocks after timeout exhaustion", test_retry_enabled_blocks_image_chain_and_reports_timeout_after_exhaustion),
    ]
    results = [run_test(name, func) for name, func in tests]
    print("")
    print(f"Passed: {sum(results)}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
