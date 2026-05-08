#!/usr/bin/env python3
"""Validate and optionally fix style_only_v3 skill YAML files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

TARGET_SCREEN_COUNT = 8
STYLE_SCHEMA_VERSION = "style_only_v3"
LEAK_MARKERS = [
    "黑檀",
    "印尼",
    "报关",
    "海关",
    "梳齿",
    "100年",
    "成材",
    "木梳",
    "羊毛",
    "盘扣",
    "french skirt",
]


def normalize_language(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "中文"
    low = raw.lower()
    if "english" in low or low in {"en", "en-us", "en-gb"} or "英文" in raw:
        return "English"
    if "日本" in raw or "japanese" in low or low in {"ja", "jp"}:
        return "日本語"
    if "한국" in raw or "korean" in low or low in {"ko", "kr"}:
        return "한국어"
    return "中文"


def language_pack(language: str) -> Dict[str, Any]:
    if language == "English":
        return {
            "title": "Style-only transfer template",
            "rule_style_only": "Keep visual style and copy-function relation only.",
            "rule_no_product": "Do not inherit reference product facts.",
            "language_lock": "Output language lock",
            "product_source": "Product runtime source",
            "platform_source": "Platform runtime source",
            "batch_source": "Batch runtime source",
            "language_source": "Language runtime source",
            "screen_line": lambda i, ph: f"Screen {i} copy slot: {ph}",
            "screen_name": lambda i: f"screen_{i}",
            "screen_desc": lambda i: f"Dynamic narrative slot; source_refs:[{i}]",
        }
    if language == "日本語":
        return {
            "title": "スタイル転写テンプレート",
            "rule_style_only": "視覚スタイルと言語機能関係のみを継承する。",
            "rule_no_product": "参照商品の事実情報は継承しない。",
            "language_lock": "出力言語ロック",
            "product_source": "商品実行時ソース",
            "platform_source": "プラットフォーム実行時ソース",
            "batch_source": "生成数実行時ソース",
            "language_source": "言語実行時ソース",
            "screen_line": lambda i, ph: f"第{i}画面 文案スロット: {ph}",
            "screen_name": lambda i: f"第{i}画面",
            "screen_desc": lambda i: f"動的叙事スロット; source_refs:[{i}]",
        }
    if language == "한국어":
        return {
            "title": "스타일 전이 템플릿",
            "rule_style_only": "시각 스타일과 카피 기능 관계만 계승한다.",
            "rule_no_product": "참고 상품의 사실 정보는 계승하지 않는다.",
            "language_lock": "출력 언어 잠금",
            "product_source": "상품 런타임 소스",
            "platform_source": "플랫폼 런타임 소스",
            "batch_source": "생성 수 런타임 소스",
            "language_source": "언어 런타임 소스",
            "screen_line": lambda i, ph: f"{i}번 화면 카피 슬롯: {ph}",
            "screen_name": lambda i: f"{i}번 화면",
            "screen_desc": lambda i: f"동적 서사 슬롯; source_refs:[{i}]",
        }
    return {
        "title": "风格迁移模板",
        "rule_style_only": "仅保留视觉风格与文案功能关系。",
        "rule_no_product": "禁止继承参考产品事实信息。",
        "language_lock": "输出语言锁定",
        "product_source": "产品运行时来源",
        "platform_source": "平台运行时来源",
        "batch_source": "数量运行时来源",
        "language_source": "语言运行时来源",
        "screen_line": lambda i, ph: f"第{i}屏文案占位: {ph}",
        "screen_name": lambda i: f"第{i}屏",
        "screen_desc": lambda i: f"动态叙事功能位; source_refs:[{i}]",
    }


def default_prompt_guide(index: int) -> str:
    return (
        "f_code=F1/F6; p_code=P2; i_code=I5; "
        "style_tokens=[balanced composition, clear hierarchy, controlled whitespace]; "
        "copy_action=generate_copy; "
        f"copy_placeholder={{{{copy_function_language_{index}}}}}"
    )


def has_reference_product_leak_markers(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(token.lower() in lower for token in LEAK_MARKERS)


def normalize_skill(data: Dict[str, Any], strict_rebuild: bool = False) -> Dict[str, Any]:
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    language = normalize_language(str(defaults.get("output_language") or data.get("output_language") or data.get("language") or "中文"))
    pack = language_pack(language)

    defaults["schema_version"] = STYLE_SCHEMA_VERSION
    defaults["screen_count"] = str(TARGET_SCREEN_COUNT)
    defaults.setdefault("style_transfer_mode", "style_only")
    defaults.setdefault("dynamic_sequence", "true")
    defaults.setdefault("language_lock", "strict")
    defaults["output_language"] = language

    variables = data.get("variables") if isinstance(data.get("variables"), dict) else {}
    variables.setdefault("product", "")
    variables.setdefault("selling_points", "")
    variables["language"] = language
    variables.setdefault("platform", "")
    variables.setdefault("batch_count", str(TARGET_SCREEN_COUNT))
    for i in range(1, TARGET_SCREEN_COUNT + 1):
        variables.setdefault(f"copy_function_language_{i}", "")

    shots_raw = data.get("shots") if isinstance(data.get("shots"), list) else []
    shots_sorted = [item for item in shots_raw if isinstance(item, dict)]
    shots_sorted.sort(key=lambda x: int(x.get("order", 10**9)) if str(x.get("order", "")).isdigit() else 10**9)

    shots: List[Dict[str, Any]] = []
    if strict_rebuild:
        for i in range(1, TARGET_SCREEN_COUNT + 1):
            shots.append(
                {
                    "id": f"screen_{i}",
                    "name": pack["screen_name"](i),
                    "description": pack["screen_desc"](i),
                    "order": i,
                    "prompt_guide": default_prompt_guide(i),
                }
            )
    else:
        for i in range(1, TARGET_SCREEN_COUNT + 1):
            src = shots_sorted[i - 1] if i - 1 < len(shots_sorted) else {}
            prompt_guide = str(src.get("prompt_guide", "")).replace("：", ":").replace("{{copy_function_language}}", f"{{{{copy_function_language_{i}}}}}")
            if not prompt_guide.strip():
                prompt_guide = default_prompt_guide(i)
            if f"{{{{copy_function_language_{i}}}}}" not in prompt_guide:
                prompt_guide = f"{prompt_guide}; copy_placeholder={{{{copy_function_language_{i}}}}}"
            if "f_code=" not in prompt_guide and "f_code:" not in prompt_guide:
                prompt_guide = f"f_code=F1/F6; {prompt_guide}"
            if "p_code=" not in prompt_guide and "p_code:" not in prompt_guide:
                prompt_guide = f"{prompt_guide}; p_code=P2"
            if "i_code=" not in prompt_guide and "i_code:" not in prompt_guide:
                prompt_guide = f"{prompt_guide}; i_code=I5"
            if "style_tokens=" not in prompt_guide and "style_tokens:" not in prompt_guide:
                prompt_guide = f"{prompt_guide}; style_tokens=[balanced composition, clear hierarchy, controlled whitespace]"
            prompt_guide = prompt_guide.replace("f_code=F;", "f_code=F1/F6;").replace("f_code:F;", "f_code=F1/F6;")
            prompt_guide = prompt_guide.replace("p_code=P;", "p_code=P2;").replace("p_code:P;", "p_code=P2;")
            prompt_guide = prompt_guide.replace("i_code=I;", "i_code=I5;").replace("i_code:I;", "i_code=I5;")

            shots.append(
                {
                    "id": str(src.get("id") or f"screen_{i}"),
                    "name": str(src.get("name") or pack["screen_name"](i)),
                    "description": str(src.get("description") or pack["screen_desc"](i)),
                    "order": i,
                    "prompt_guide": prompt_guide.strip(),
                }
            )

    template = str(data.get("template") or "").strip()
    if strict_rebuild or not template:
        template_lines = [
            pack["title"],
            pack["rule_style_only"],
            pack["rule_no_product"],
            f"{pack['language_lock']}: {{{{language}}}}",
            f"{pack['product_source']}: {{{{product}}}}",
            f"{pack['platform_source']}: {{{{platform}}}}",
            f"{pack['batch_source']}: {{{{batch_count}}}}",
            f"{pack['language_source']}: {{{{language}}}}",
        ]
        for i in range(1, TARGET_SCREEN_COUNT + 1):
            template_lines.append(pack["screen_line"](i, f"{{{{copy_function_language_{i}}}}}"))
        template = "\n".join(template_lines)
    else:
        must_have = ["{{product}}", "{{language}}", "{{platform}}", "{{batch_count}}"]
        for ph in must_have:
            if ph not in template:
                template += f"\n{ph}"
        template = re.sub(
            r"(输出语言锁定|Output language lock|出力言語ロック|출력 언어 잠금)\s*:\s*[^\n]+",
            r"\1: {{language}}",
            template,
            flags=re.IGNORECASE,
        )
        for i in range(1, TARGET_SCREEN_COUNT + 1):
            ph = f"{{{{copy_function_language_{i}}}}}"
            if ph not in template:
                template += f"\n{pack['screen_line'](i, ph)}"

    trigger_words = data.get("trigger_words") if isinstance(data.get("trigger_words"), list) else []
    trigger_words = [str(item).strip() for item in trigger_words if str(item).strip()]
    if not trigger_words:
        trigger_words = [str(data.get("trigger") or "style_only_detail_template")]

    normalized = {
        "name": str(data.get("name") or "style_only_detail_template"),
        "description": str(data.get("description") or ""),
        "category": str(data.get("category") or "detail_page_template"),
        "schema_version": STYLE_SCHEMA_VERSION,
        "version": str(data.get("version") or "1.0.0"),
        "trigger_words": trigger_words,
        "trigger": str(data.get("trigger") or trigger_words[0]),
        "tags": data.get("tags") if isinstance(data.get("tags"), list) else [{"name": trigger_words[0], "weight": 1.0}],
        "shots": shots,
        "template": template,
        "defaults": defaults,
        "variables": variables,
    }
    if isinstance(data.get("weight"), (int, float)):
        normalized["weight"] = float(data["weight"])
    else:
        normalized["weight"] = 1.0
    return normalized


def validate_skill(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    if data.get("schema_version") != STYLE_SCHEMA_VERSION:
        errors.append("missing top-level schema_version=style_only_v3")

    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    for key in ["schema_version", "screen_count", "style_transfer_mode", "dynamic_sequence", "language_lock", "output_language"]:
        if key not in defaults:
            errors.append(f"defaults missing: {key}")

    variables = data.get("variables") if isinstance(data.get("variables"), dict) else {}
    for key in ["product", "selling_points", "language", "platform", "batch_count"]:
        if key not in variables:
            errors.append(f"variables missing: {key}")
    for i in range(1, TARGET_SCREEN_COUNT + 1):
        if f"copy_function_language_{i}" not in variables:
            errors.append(f"variables missing: copy_function_language_{i}")

    shots = data.get("shots") if isinstance(data.get("shots"), list) else []
    if len(shots) != TARGET_SCREEN_COUNT:
        errors.append(f"shots count is {len(shots)} not {TARGET_SCREEN_COUNT}")
    else:
        orders = [item.get("order") for item in shots if isinstance(item, dict)]
        if orders != list(range(1, TARGET_SCREEN_COUNT + 1)):
            errors.append("shot order is not 1..8")
        for i, shot in enumerate(shots, 1):
            guide = str(shot.get("prompt_guide", "")) if isinstance(shot, dict) else ""
            if "f_code=F;" in guide or "f_code:F;" in guide:
                errors.append(f"shot {i} uses invalid generic f_code=F")
            if "p_code=P;" in guide or "p_code:P;" in guide:
                errors.append(f"shot {i} uses invalid generic p_code=P")
            if "i_code=I;" in guide or "i_code:I;" in guide:
                errors.append(f"shot {i} uses invalid generic i_code=I")
            if f"{{{{copy_function_language_{i}}}}}" not in guide:
                errors.append(f"shot {i} prompt_guide missing copy_function_language_{i}")

    template = str(data.get("template") or "")
    for ph in ["{{product}}", "{{language}}", "{{platform}}", "{{batch_count}}"]:
        if ph not in template:
            errors.append(f"template missing placeholder: {ph}")
    for i in range(1, TARGET_SCREEN_COUNT + 1):
        ph = f"{{{{copy_function_language_{i}}}}}"
        if ph not in template:
            errors.append(f"template missing placeholder: {ph}")
    if not re.search(r"(输出语言锁定|Output language lock|出力言語ロック|출력 언어 잠금)\s*:\s*\{\{language\}\}", template, flags=re.IGNORECASE):
        errors.append("language lock line is hardcoded; must use {{language}}")
    leakage_text_parts = [template]
    for shot in shots:
        if isinstance(shot, dict):
            leakage_text_parts.append(str(shot.get("name", "")))
            leakage_text_parts.append(str(shot.get("description", "")))
            leakage_text_parts.append(str(shot.get("prompt_guide", "")))
    if has_reference_product_leak_markers("\n".join(leakage_text_parts)):
        errors.append("reference product leak markers detected")

    return len(errors) == 0, errors


def process_file(path: Path, fix: bool) -> int:
    if not path.exists():
        print(f"[validate] missing file: {path}")
        return 2

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        print(f"[validate] read error: {path} -> {exc}")
        return 2

    if not isinstance(data, dict):
        print(f"[validate] invalid yaml root: {path}")
        return 2

    ok, errors = validate_skill(data)
    if ok:
        print(f"[validate] PASS: {path}")
        return 0

    print(f"[validate] FAIL: {path}")
    for item in errors:
        print(f"  - {item}")

    if not fix:
        return 1

    strict_rebuild = any(
        ("invalid generic" in item) or ("leak markers" in item) for item in errors
    )
    normalized = normalize_skill(data, strict_rebuild=strict_rebuild)
    ok2, errors2 = validate_skill(normalized)
    if not ok2:
        print(f"[validate] FIX failed: {path}")
        for item in errors2:
            print(f"  - {item}")
        return 1

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(normalized, f, allow_unicode=True, sort_keys=False)
    print(f"[validate] FIXED: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/fix style_only_v3 skill files")
    parser.add_argument("target", help="YAML file path or directory")
    parser.add_argument("--fix", action="store_true", help="Auto-fix invalid files")
    args = parser.parse_args()

    target = Path(args.target)
    if target.is_dir():
        codes = []
        for file in sorted(target.glob("*.y*ml")):
            codes.append(process_file(file, args.fix))
        return 0 if all(code == 0 for code in codes) else 1

    return process_file(target, args.fix)


if __name__ == "__main__":
    raise SystemExit(main())
