#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from py import aliyun_translate as translate_module


OK = "[OK]"
FAIL = "[FAIL]"


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


class FakeCredentialConfig:
    def __init__(self, type=None, access_key_id=None, access_key_secret=None):
        self.type = type
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret


class FakeCredentialClient:
    instances = []

    def __init__(self, config=None):
        self.config = config
        FakeCredentialClient.instances.append(self)


class FakeOpenApiConfig:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.credential = getattr(self, "credential", None)


class FakeRuntimeOptions:
    instances = []

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        FakeRuntimeOptions.instances.append(self)


class FakeTranslateGeneralRequest:
    def __init__(
        self,
        context=None,
        format_type=None,
        scene=None,
        source_language=None,
        source_text=None,
        target_language=None,
    ):
        self.context = context
        self.format_type = format_type
        self.scene = scene
        self.source_language = source_language
        self.source_text = source_text
        self.target_language = target_language


class FakeTranslateData:
    def __init__(self, translated, detected_language, word_count):
        self.translated = translated
        self.detected_language = detected_language
        self.word_count = word_count

    def to_map(self):
        return {
            "Translated": self.translated,
            "DetectedLanguage": self.detected_language,
            "WordCount": self.word_count,
        }


class FakeTranslateBody:
    def __init__(self, translated, source_language, code=200, message="OK"):
        self.code = code
        self.data = FakeTranslateData(
            translated=translated,
            detected_language=source_language,
            word_count=str(len(translated)),
        )
        self.message = message
        self.request_id = "req-test"

    def to_map(self):
        return {
            "Code": self.code,
            "Message": self.message,
            "RequestId": self.request_id,
            "Data": self.data.to_map(),
        }


class FakeTranslateResponse:
    def __init__(self, translated, source_language):
        self.body = FakeTranslateBody(translated, source_language)
        self.status_code = 200

    def to_map(self):
        return {
            "statusCode": self.status_code,
            "body": self.body.to_map(),
        }


class FakeAlimtClient:
    instances = []
    fail_message = None

    def __init__(self, config):
        self.config = config
        self.calls = []
        FakeAlimtClient.instances.append(self)

    def translate_general_with_options(self, request, runtime):
        self.calls.append((request, runtime))
        if FakeAlimtClient.fail_message:
            raise RuntimeError(FakeAlimtClient.fail_message)
        return FakeTranslateResponse(
            translated=f"EN:{request.source_text}",
            source_language=request.source_language,
        )


class FakeService:
    def __init__(self):
        self.calls = []

    def translate_texts(self, **kwargs):
        self.calls.append(kwargs)
        texts = kwargs["texts"]
        translations = [
            {
                "source_text": text,
                "translated_text": f"EN:{text}",
                "detected_language": kwargs["source_language"],
                "word_count": "1",
                "request_id": f"req-{idx}",
                "code": 200,
                "message": "OK",
                "raw_response": {"index": idx},
            }
            for idx, text in enumerate(texts)
        ]
        return {
            "success": True,
            "source_language": kwargs["source_language"],
            "target_language": kwargs["target_language"],
            "format_type": kwargs.get("format_type", "text"),
            "scene": kwargs.get("scene", "general"),
            "region_id": kwargs.get("region_id", "cn-hangzhou"),
            "credential_mode": kwargs.get("credential_mode", "default_chain"),
            "count": len(translations),
            "translations": translations,
        }


def fake_sdk_context():
    FakeCredentialClient.instances.clear()
    FakeRuntimeOptions.instances.clear()
    FakeAlimtClient.instances.clear()
    FakeAlimtClient.fail_message = None

    return patch.multiple(
        translate_module,
        ALIYUN_SDK_AVAILABLE=True,
        ALIYUN_SDK_IMPORT_ERROR=None,
        credential_models=SimpleNamespace(Config=FakeCredentialConfig),
        CredentialClient=FakeCredentialClient,
        open_api_models=SimpleNamespace(Config=FakeOpenApiConfig),
        tea_util_models=SimpleNamespace(RuntimeOptions=FakeRuntimeOptions),
        alimt_models=SimpleNamespace(TranslateGeneralRequest=FakeTranslateGeneralRequest),
        AlimtClient=FakeAlimtClient,
    )


def test_node_registration():
    init_text = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    expect(
        '"HouLai_Aliyun_Translate": HouLai_Aliyun_Translate' in init_text,
        "Main __init__.py is missing the node class mapping",
    )
    expect(
        '"HouLai_Aliyun_Translate": "后来_阿里云翻译 (Aliyun Translate)"' in init_text,
        "Main __init__.py is missing the display name mapping",
    )
    expect(
        '"/houlai/translate/aliyun"' in init_text,
        "Main __init__.py is missing the HTTP route",
    )


def test_input_types():
    input_types = translate_module.HouLai_Aliyun_Translate.INPUT_TYPES()
    required = input_types["required"]
    expect(required["翻译模式"][1]["default"] == "单条翻译", "翻译模式默认值不正确")
    expect(
        required["凭证模式"][1]["default"] == "默认凭证链",
        "凭证模式默认值不正确",
    )
    expect(required["源语言"][1]["default"] == "zh", "源语言默认值不正确")
    expect(required["目标语言"][1]["default"] == "en", "目标语言默认值不正确")
    expect(required["格式类型"][1]["default"] == "纯文本", "格式类型默认值不正确")


def test_http_payload_parsing_and_unified_service():
    fake_service = FakeService()
    response = translate_module.handle_aliyun_translate_http_payload(
        {
            "text": "第一行\n\n第二行",
            "mode": "line_by_line",
            "source_language": "zh",
            "target_language": "en",
        },
        service=fake_service,
    )
    expect(
        fake_service.calls[0]["texts"] == ["第一行", "第二行"],
        "line_by_line mode should split non-empty lines",
    )
    expect(response["count"] == 2, "response count should match translated lines")

    fake_service = FakeService()
    response = translate_module.handle_aliyun_translate_http_payload(
        {
            "texts": ["开心", "难过"],
            "source_language": "zh",
            "target_language": "en",
        },
        service=fake_service,
    )
    expect(
        fake_service.calls[0]["texts"] == ["开心", "难过"],
        "texts list should pass straight through to the service layer",
    )
    expect(
        "translated_text" not in response,
        "batch responses should not include a single translated_text field",
    )


def test_localized_node_call():
    fake_service = FakeService()
    node = translate_module.HouLai_Aliyun_Translate()
    with patch.object(translate_module, "AliyunTranslateService", return_value=fake_service):
        translated_text, info, _raw = node.translate(
            **{
                "翻译文本": "第一行\n\n第二行",
                "翻译模式": "逐行翻译",
                "源语言": "zh",
                "目标语言": "en",
                "格式类型": "纯文本",
                "翻译场景": "general",
                "地域": "cn-hangzhou",
                "凭证模式": "默认凭证链",
                "访问密钥ID": "",
                "访问密钥Secret": "",
                "超时时间(秒)": 60,
            }
        )

    expect(
        fake_service.calls[0]["texts"] == ["第一行", "第二行"],
        "中文节点参数应正确映射到服务层",
    )
    expect(translated_text == "EN:第一行\nEN:第二行", "节点返回的翻译文本不正确")
    expect("阿里云翻译成功" in info, "节点状态信息应为中文")


def test_batch_order_and_timeout_with_fake_sdk():
    with fake_sdk_context():
        service = translate_module.AliyunTranslateService()
        result = service.translate_texts(
            texts=["我开心", "我难过"],
            source_language="zh",
            target_language="en",
            credential_mode="default_chain",
            timeout_seconds=30,
        )

    expect(
        [item["translated_text"] for item in result["translations"]]
        == ["EN:我开心", "EN:我难过"],
        "translations should preserve input order",
    )
    expect(
        FakeRuntimeOptions.instances[-1].read_timeout == 30000,
        "timeout_seconds should be converted to milliseconds",
    )
    expect(
        FakeAlimtClient.instances[-1].config.endpoint == "mt.cn-hangzhou.aliyuncs.com",
        "client endpoint should follow the configured region",
    )


def test_length_limit():
    service = translate_module.AliyunTranslateService()
    too_long = "a" * 5000
    try:
        service.translate_texts(texts=[too_long])
    except translate_module.AliyunTranslateValidationError as exc:
        expect("shorter than 5000" in str(exc), "length validation message mismatch")
        return
    raise AssertionError("Expected a validation error for 5000-character input")


def test_credential_modes():
    with fake_sdk_context():
        service = translate_module.AliyunTranslateService()
        service.translate_texts(
            texts=["你好"],
            credential_mode="explicit",
            access_key_id="ak-test",
            access_key_secret="sk-test",
        )
        explicit_credential = FakeCredentialClient.instances[-1]
        expect(
            explicit_credential.config.type == "access_key",
            "explicit mode should build an access_key credential",
        )
        expect(
            explicit_credential.config.access_key_id == "ak-test",
            "explicit mode should forward access_key_id",
        )

    with fake_sdk_context():
        service = translate_module.AliyunTranslateService()
        service.translate_texts(texts=["你好"], credential_mode="default_chain")
        default_chain_credential = FakeCredentialClient.instances[-1]
        expect(
            default_chain_credential.config is None,
            "default_chain mode should initialize CredentialClient without explicit config",
        )


def test_error_mapping_and_secret_redaction():
    status, payload = translate_module.build_aliyun_translate_error_payload(
        translate_module.AliyunTranslateValidationError("bad request")
    )
    expect(status == 400 and payload["error"] == "bad request", "validation errors should map to 400")

    status, payload = translate_module.build_aliyun_translate_error_payload(
        translate_module.AliyunTranslateUpstreamError(
            "upstream failed", raw_response={"Code": 500}, upstream_code=500
        )
    )
    expect(status == 502, "upstream errors should map to 502")
    expect(payload["upstream_code"] == 500, "upstream_code should be forwarded")

    status, payload = translate_module.build_aliyun_translate_error_payload(
        translate_module.AliyunTranslateDependencyError("deps missing")
    )
    expect(status == 500 and payload["error"] == "deps missing", "dependency errors should map to 500")

    with fake_sdk_context():
        FakeAlimtClient.fail_message = "bad access key ak-test and secret sk-test"
        service = translate_module.AliyunTranslateService()
        try:
            service.translate_texts(
                texts=["你好"],
                credential_mode="explicit",
                access_key_id="ak-test",
                access_key_secret="sk-test",
            )
        except translate_module.AliyunTranslateUpstreamError as exc:
            message = str(exc)
            expect("ak-test" not in message, "access_key_id should be redacted")
            expect("sk-test" not in message, "access_key_secret should be redacted")
            return
    raise AssertionError("Expected an upstream error from the fake client")


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
        ("Node registration", test_node_registration),
        ("INPUT_TYPES defaults", test_input_types),
        ("HTTP payload parsing", test_http_payload_parsing_and_unified_service),
        ("Localized node call", test_localized_node_call),
        ("Batch order and timeout", test_batch_order_and_timeout_with_fake_sdk),
        ("Length limit", test_length_limit),
        ("Credential modes", test_credential_modes),
        ("Error mapping and redaction", test_error_mapping_and_secret_redaction),
    ]
    results = [run_test(name, func) for name, func in tests]
    print("")
    print(f"Passed: {sum(results)}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
