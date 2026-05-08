import json
from typing import Any, Dict, List, Optional, Sequence, Tuple


ALIYUN_SDK_AVAILABLE = False
ALIYUN_SDK_IMPORT_ERROR: Optional[Exception] = None

try:
    from alibabacloud_alimt20181012 import models as alimt_models
    from alibabacloud_alimt20181012.client import Client as AlimtClient
    from alibabacloud_credentials import models as credential_models
    from alibabacloud_credentials.client import Client as CredentialClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_tea_util import models as tea_util_models

    ALIYUN_SDK_AVAILABLE = True
except Exception as exc:  # pragma: no cover - exercised in runtime when deps are missing
    ALIYUN_SDK_IMPORT_ERROR = exc
    alimt_models = None
    AlimtClient = None
    credential_models = None
    CredentialClient = None
    open_api_models = None
    tea_util_models = None


class AliyunTranslateError(Exception):
    """Base exception for Aliyun Translate integration."""


class AliyunTranslateValidationError(AliyunTranslateError):
    """Raised for invalid user input."""


class AliyunTranslateDependencyError(AliyunTranslateError):
    """Raised when the Alibaba Cloud SDK is unavailable."""


class AliyunTranslateUpstreamError(AliyunTranslateError):
    """Raised when Alibaba Cloud returns an error or malformed payload."""

    def __init__(
        self,
        message: str,
        raw_response: Optional[Dict[str, Any]] = None,
        upstream_code: Optional[Any] = None,
    ):
        super().__init__(message)
        self.raw_response = raw_response or {}
        self.upstream_code = upstream_code


def split_non_empty_lines(text: str) -> List[str]:
    return [line for line in text.splitlines() if line.strip()]


def _redact_text(value: str, secrets: Sequence[str]) -> str:
    redacted = value or ""
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _safe_error_message(exc: Exception, secrets: Sequence[str]) -> str:
    message = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
    return _redact_text(message, secrets)


def _model_to_plain_dict(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_map") and callable(value.to_map):
        try:
            return _model_to_plain_dict(value.to_map())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _model_to_plain_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_model_to_plain_dict(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _normalize_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise AliyunTranslateValidationError(f"{field_name} must be a string")
    return value


def _normalize_http_texts(payload: Dict[str, Any], mode: str) -> List[str]:
    has_text = "text" in payload
    has_texts = "texts" in payload
    if has_text == has_texts:
        raise AliyunTranslateValidationError("Provide exactly one of text or texts")

    if has_text:
        text = _normalize_string(payload.get("text"), "text")
        if mode == "line_by_line":
            texts = split_non_empty_lines(text)
            if not texts:
                raise AliyunTranslateValidationError(
                    "text must contain at least one non-empty line"
                )
            return texts
        return [text]

    texts = payload.get("texts")
    if not isinstance(texts, list) or not texts:
        raise AliyunTranslateValidationError("texts must be a non-empty list of strings")
    normalized: List[str] = []
    for index, item in enumerate(texts):
        normalized.append(_normalize_string(item, f"texts[{index}]"))
    return normalized


def parse_aliyun_translate_http_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise AliyunTranslateValidationError("JSON body must be an object")

    mode = payload.get("mode", "single")
    if mode not in ("single", "line_by_line"):
        raise AliyunTranslateValidationError("mode must be one of: single, line_by_line")

    texts = _normalize_http_texts(payload, mode)
    return {
        "texts": texts,
        "source_language": str(payload.get("source_language", "zh")),
        "target_language": str(payload.get("target_language", "en")),
        "format_type": str(payload.get("format_type", "text")),
        "scene": str(payload.get("scene", "general")),
        "region_id": str(payload.get("region_id", "cn-hangzhou")),
        "credential_mode": str(payload.get("credential_mode", "default_chain")),
        "access_key_id": str(payload.get("access_key_id", "")),
        "access_key_secret": str(payload.get("access_key_secret", "")),
        "timeout_seconds": payload.get("timeout_seconds", 60),
    }


def build_aliyun_translate_error_payload(
    exc: Exception,
) -> Tuple[int, Dict[str, Any]]:
    if isinstance(exc, AliyunTranslateValidationError):
        return 400, {"success": False, "error": str(exc)}
    if isinstance(exc, AliyunTranslateUpstreamError):
        payload: Dict[str, Any] = {"success": False, "error": str(exc)}
        if exc.upstream_code is not None:
            payload["upstream_code"] = exc.upstream_code
        if exc.raw_response:
            payload["raw_response"] = exc.raw_response
        return 502, payload
    if isinstance(exc, AliyunTranslateDependencyError):
        return 500, {"success": False, "error": str(exc)}
    return 500, {"success": False, "error": "Internal server error"}


def build_aliyun_translate_http_response(result: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "success": True,
        "source_language": result["source_language"],
        "target_language": result["target_language"],
        "count": result["count"],
        "translations": result["translations"],
    }
    if result["count"] == 1:
        payload["translated_text"] = result["translations"][0]["translated_text"]
    return payload


def handle_aliyun_translate_http_payload(
    payload: Dict[str, Any],
    service: Optional["AliyunTranslateService"] = None,
) -> Dict[str, Any]:
    request_args = parse_aliyun_translate_http_payload(payload)
    active_service = service or AliyunTranslateService()
    result = active_service.translate_texts(**request_args)
    return build_aliyun_translate_http_response(result)


class AliyunTranslateService:
    DEFAULT_REGION_ID = "cn-hangzhou"
    DEFAULT_SOURCE_LANGUAGE = "zh"
    DEFAULT_TARGET_LANGUAGE = "en"
    DEFAULT_FORMAT_TYPE = "text"
    DEFAULT_SCENE = "general"
    DEFAULT_TIMEOUT_SECONDS = 60
    MAX_TEXT_LENGTH = 4999

    def _ensure_sdk_available(self) -> None:
        if not ALIYUN_SDK_AVAILABLE:
            detail = ""
            if ALIYUN_SDK_IMPORT_ERROR is not None:
                detail = f": {ALIYUN_SDK_IMPORT_ERROR}"
            raise AliyunTranslateDependencyError(
                "Alibaba Cloud translation SDK is not installed. "
                "Run pip install -r requirements.txt"
                f"{detail}"
            )

    @staticmethod
    def _build_endpoint(region_id: str) -> str:
        region = (region_id or AliyunTranslateService.DEFAULT_REGION_ID).strip()
        if not region:
            region = AliyunTranslateService.DEFAULT_REGION_ID
        return f"mt.{region}.aliyuncs.com"

    @staticmethod
    def _normalize_timeout_seconds(timeout_seconds: Any) -> int:
        try:
            value = int(timeout_seconds)
        except (TypeError, ValueError):
            raise AliyunTranslateValidationError("timeout_seconds must be an integer")
        if value < 1 or value > 600:
            raise AliyunTranslateValidationError(
                "timeout_seconds must be between 1 and 600"
            )
        return value

    def _build_client(
        self,
        credential_mode: str,
        access_key_id: str,
        access_key_secret: str,
        region_id: str,
        timeout_seconds: int,
    ):
        self._ensure_sdk_available()

        region = (region_id or self.DEFAULT_REGION_ID).strip() or self.DEFAULT_REGION_ID
        timeout_ms = timeout_seconds * 1000
        config = open_api_models.Config(
            region_id=region,
            endpoint=self._build_endpoint(region),
            protocol="HTTPS",
            read_timeout=timeout_ms,
            connect_timeout=timeout_ms,
            user_agent="ComfyUI_HouLai_ToolBox/AliyunTranslate",
        )

        if credential_mode == "explicit":
            ak = (access_key_id or "").strip()
            sk = (access_key_secret or "").strip()
            if not ak or not sk:
                raise AliyunTranslateValidationError(
                    "access_key_id and access_key_secret are required when "
                    "credential_mode is explicit"
                )
            credential_config = credential_models.Config(
                type="access_key",
                access_key_id=ak,
                access_key_secret=sk,
            )
            config.credential = CredentialClient(credential_config)
        elif credential_mode == "default_chain":
            config.credential = CredentialClient()
        else:
            raise AliyunTranslateValidationError(
                "credential_mode must be one of: explicit, default_chain"
            )

        return AlimtClient(config)

    def _build_runtime(self, timeout_seconds: int):
        timeout_ms = timeout_seconds * 1000
        return tea_util_models.RuntimeOptions(
            autoretry=False,
            read_timeout=timeout_ms,
            connect_timeout=timeout_ms,
        )

    def _validate_texts(self, texts: Sequence[str]) -> List[str]:
        if not isinstance(texts, (list, tuple)) or not texts:
            raise AliyunTranslateValidationError(
                "texts must contain at least one string"
            )

        normalized: List[str] = []
        for index, text in enumerate(texts):
            if not isinstance(text, str):
                raise AliyunTranslateValidationError(f"texts[{index}] must be a string")
            if not text.strip():
                raise AliyunTranslateValidationError(f"texts[{index}] cannot be empty")
            if len(text) > self.MAX_TEXT_LENGTH:
                raise AliyunTranslateValidationError(
                    f"texts[{index}] must be shorter than 5000 characters"
                )
            normalized.append(text)
        return normalized

    def _translate_single(
        self,
        client: Any,
        runtime: Any,
        text: str,
        source_language: str,
        target_language: str,
        format_type: str,
        scene: str,
        secrets: Sequence[str],
    ) -> Dict[str, Any]:
        request = alimt_models.TranslateGeneralRequest(
            format_type=format_type,
            scene=scene,
            source_language=source_language,
            source_text=text,
            target_language=target_language,
        )

        try:
            response = client.translate_general_with_options(request, runtime)
        except Exception as exc:
            raise AliyunTranslateUpstreamError(
                _safe_error_message(exc, secrets),
                raw_response={
                    "error_type": exc.__class__.__name__,
                    "message": _safe_error_message(exc, secrets),
                },
            ) from exc

        response_map = _model_to_plain_dict(response)
        body = getattr(response, "body", None)
        body_map = _model_to_plain_dict(body) if body is not None else {}
        data = getattr(body, "data", None)

        translated_text = getattr(data, "translated", None) if data is not None else None
        detected_language = (
            getattr(data, "detected_language", None) if data is not None else None
        )
        word_count = getattr(data, "word_count", None) if data is not None else None
        code = getattr(body, "code", None)
        message = getattr(body, "message", None)
        request_id = getattr(body, "request_id", None)

        if code not in (None, 200, "200"):
            raise AliyunTranslateUpstreamError(
                message or "Alibaba Cloud translation request failed",
                raw_response=response_map,
                upstream_code=code,
            )

        if translated_text is None:
            raise AliyunTranslateUpstreamError(
                "Alibaba Cloud translation response did not include translated text",
                raw_response=response_map,
                upstream_code=code,
            )

        return {
            "source_text": text,
            "translated_text": translated_text,
            "detected_language": detected_language or source_language,
            "word_count": word_count,
            "request_id": request_id,
            "code": code if code is not None else 200,
            "message": message or "OK",
            "raw_response": response_map or body_map,
        }

    def translate_texts(
        self,
        texts: Sequence[str],
        source_language: str = DEFAULT_SOURCE_LANGUAGE,
        target_language: str = DEFAULT_TARGET_LANGUAGE,
        format_type: str = DEFAULT_FORMAT_TYPE,
        scene: str = DEFAULT_SCENE,
        region_id: str = DEFAULT_REGION_ID,
        credential_mode: str = "default_chain",
        access_key_id: str = "",
        access_key_secret: str = "",
        timeout_seconds: Any = DEFAULT_TIMEOUT_SECONDS,
    ) -> Dict[str, Any]:
        timeout_value = self._normalize_timeout_seconds(timeout_seconds)
        normalized_texts = self._validate_texts(texts)
        source = (source_language or self.DEFAULT_SOURCE_LANGUAGE).strip()
        target = (target_language or self.DEFAULT_TARGET_LANGUAGE).strip()
        format_name = (format_type or self.DEFAULT_FORMAT_TYPE).strip()
        scene_name = (scene or self.DEFAULT_SCENE).strip()
        region = (region_id or self.DEFAULT_REGION_ID).strip()
        credential_name = (credential_mode or "default_chain").strip()

        secrets = [
            (access_key_id or "").strip(),
            (access_key_secret or "").strip(),
        ]
        client = self._build_client(
            credential_name,
            access_key_id,
            access_key_secret,
            region,
            timeout_value,
        )
        runtime = self._build_runtime(timeout_value)

        translations = [
            self._translate_single(
                client=client,
                runtime=runtime,
                text=text,
                source_language=source,
                target_language=target,
                format_type=format_name,
                scene=scene_name,
                secrets=secrets,
            )
            for text in normalized_texts
        ]

        return {
            "success": True,
            "source_language": source,
            "target_language": target,
            "format_type": format_name,
            "scene": scene_name,
            "region_id": region or self.DEFAULT_REGION_ID,
            "credential_mode": credential_name,
            "count": len(translations),
            "translations": translations,
        }


class HouLai_Aliyun_Translate:
    NODE_MODE_MAP = {
        "单条翻译": "single",
        "逐行翻译": "line_by_line",
        "single": "single",
        "line_by_line": "line_by_line",
    }
    NODE_FORMAT_TYPE_MAP = {
        "纯文本": "text",
        "HTML": "html",
        "text": "text",
        "html": "html",
    }
    NODE_CREDENTIAL_MODE_MAP = {
        "默认凭证链": "default_chain",
        "显式AK/SK": "explicit",
        "default_chain": "default_chain",
        "explicit": "explicit",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "翻译文本": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "你好，世界",
                        "placeholder": "请输入要翻译的文本",
                    },
                ),
                "翻译模式": (["单条翻译", "逐行翻译"], {"default": "单条翻译"}),
                "源语言": (
                    "STRING",
                    {
                        "default": "zh",
                        "multiline": False,
                        "placeholder": "例如 zh 或 auto",
                    },
                ),
                "目标语言": (
                    "STRING",
                    {
                        "default": "en",
                        "multiline": False,
                        "placeholder": "例如 en",
                    },
                ),
                "格式类型": (["纯文本", "HTML"], {"default": "纯文本"}),
                "翻译场景": (
                    "STRING",
                    {"default": "general", "multiline": False, "placeholder": "general"},
                ),
                "地域": (
                    "STRING",
                    {
                        "default": "cn-hangzhou",
                        "multiline": False,
                        "placeholder": "cn-hangzhou",
                    },
                ),
                "凭证模式": (
                    ["默认凭证链", "显式AK/SK"],
                    {"default": "默认凭证链"},
                ),
                "访问密钥ID": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "仅在显式AK/SK模式下填写",
                    },
                ),
                "访问密钥Secret": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "仅在显式AK/SK模式下填写",
                    },
                ),
                "超时时间(秒)": (
                    "INT",
                    {"default": 60, "min": 1, "max": 600, "step": 1},
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("翻译结果", "状态信息", "原始响应JSON")
    FUNCTION = "translate"
    CATEGORY = "后来/API工具"

    def translate(self, **kwargs):
        service = AliyunTranslateService()
        try:
            text = kwargs.get("翻译文本", kwargs.get("text", ""))
            mode_value = kwargs.get("翻译模式", kwargs.get("mode", "单条翻译"))
            source_language = kwargs.get("源语言", kwargs.get("source_language", "zh"))
            target_language = kwargs.get("目标语言", kwargs.get("target_language", "en"))
            format_value = kwargs.get("格式类型", kwargs.get("format_type", "纯文本"))
            scene = kwargs.get("翻译场景", kwargs.get("scene", "general"))
            region_id = kwargs.get("地域", kwargs.get("region_id", "cn-hangzhou"))
            credential_value = kwargs.get(
                "凭证模式", kwargs.get("credential_mode", "默认凭证链")
            )
            access_key_id = kwargs.get("访问密钥ID", kwargs.get("access_key_id", ""))
            access_key_secret = kwargs.get(
                "访问密钥Secret", kwargs.get("access_key_secret", "")
            )
            timeout_seconds = kwargs.get("超时时间(秒)", kwargs.get("timeout_seconds", 60))

            normalized_mode = self.NODE_MODE_MAP.get(mode_value, str(mode_value))
            normalized_format_type = self.NODE_FORMAT_TYPE_MAP.get(
                format_value, str(format_value)
            )
            normalized_credential_mode = self.NODE_CREDENTIAL_MODE_MAP.get(
                credential_value, str(credential_value)
            )

            texts = split_non_empty_lines(text) if normalized_mode == "line_by_line" else [text]
            result = service.translate_texts(
                texts=texts,
                source_language=source_language,
                target_language=target_language,
                format_type=normalized_format_type,
                scene=scene,
                region_id=region_id,
                credential_mode=normalized_credential_mode,
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                timeout_seconds=timeout_seconds,
            )
            translated_text = "\n".join(
                item["translated_text"] for item in result["translations"]
            )
            info = "\n".join(
                [
                    "阿里云翻译成功",
                    f"翻译模式: {mode_value}",
                    f"源语言 -> 目标语言: {result['source_language']} -> {result['target_language']}",
                    f"翻译条数: {result['count']}",
                    f"格式类型: {format_value}",
                    f"翻译场景: {result['scene']}",
                    f"地域: {result['region_id']}",
                    f"凭证模式: {credential_value}",
                ]
            )
            return translated_text, info, json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            error_payload = {
                "success": False,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            }
            return "", f"阿里云翻译失败: {exc}", json.dumps(
                error_payload, ensure_ascii=False
            )


NODE_CLASS_MAPPINGS = {
    "HouLai_Aliyun_Translate": HouLai_Aliyun_Translate,
}


NODE_DISPLAY_NAME_MAPPINGS = {
    "HouLai_Aliyun_Translate": "后来_阿里云翻译 (Aliyun Translate)",
}
