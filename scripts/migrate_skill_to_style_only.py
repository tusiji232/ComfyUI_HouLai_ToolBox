#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将旧版详情页技能迁移为“风格骨架型”技能（style_only_v3）。

特点：
1. 保留技能元信息（name/description/category/trigger/weight）
2. 强制生成8屏结构（S1~S8）
3. 每屏包含独立 copy_function_language 占位符
4. 不复用旧模板中的产品细节文本，避免参考产品泄漏
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List

import yaml


DEFAULT_F_CODES = [
    "F1+F6",
    "F2+F5",
    "F4",
    "F3",
    "F4+F6",
    "F6",
    "F3+F6",
    "F2+F3",
]

DEFAULT_P_CODES = ["P2", "P1+P2", "P5", "P4", "P5", "P4", "P4", "P4"]
DEFAULT_I_CODES = ["I5", "I5", "I1", "I4", "I1", "I4", "I2", "I3"]


def action_from_f_code(f_code: str) -> str:
    if f_code in {"F4", "F5", "F4+F5"}:
        return "reserve_space"
    if f_code in {"F3", "F3+F6", "F2+F3", "F4+F6"}:
        return "conditional"
    return "generate_copy"


def extract_f_codes(template: str) -> List[str]:
    if not template:
        return []
    return re.findall(r"文案功能类型:\s*([F\d\+]+)", template)


def build_screens(f_codes: List[str]) -> List[Dict[str, str]]:
    result = []
    merged = (f_codes + DEFAULT_F_CODES)[:8]
    for i in range(8):
        f_code = merged[i]
        result.append(
            {
                "screen_id": f"S{i + 1}",
                "screen_name": f"通用模块{i + 1}",
                "f_code": f_code,
                "p_code": DEFAULT_P_CODES[i],
                "i_code": DEFAULT_I_CODES[i],
                "copy_action": action_from_f_code(f_code),
                "copy_function_language_placeholder": f"{{{{copy_function_language_{i + 1}}}}}",
            }
        )
    return result


def build_template_text() -> str:
    blocks = []
    block_names = [
        "首屏主视觉",
        "材质/特性表达",
        "尺码信息区",
        "细节标注区",
        "信息卡片区",
        "多图组合展示",
        "场景标注展示",
        "工艺特写展示",
    ]
    for i, name in enumerate(block_names, start=1):
        blocks.append(
            f"""========================================
【S{i} - {name}】
文案功能类型: {DEFAULT_F_CODES[i - 1]}
文案位置: {DEFAULT_P_CODES[i - 1]}
图文互动方式: {DEFAULT_I_CODES[i - 1]}
文案决策: {action_from_f_code(DEFAULT_F_CODES[i - 1])}
文案区域自然语言描述: "{{{{copy_function_language_{i}}}}}"
style_tokens:
  color_palette: "统一色彩策略"
  lighting: "统一光影方向"
  background: "简洁背景表达"
  composition: "明确主体与文案区关系"
  whitespace_ratio: "按模块预留必要留白"
  module_layout: "信息层级清晰"
prompt:
  详情页第{i}屏，主体为{{{{product}}}}，遵循以上style_tokens，
  文案区域用于{{{{copy_function_language_{i}}}}}，
  仅迁移视觉风格，不迁移参考产品细节。"""
        )

    footer = """【输出要求】
1. 生成{{batch_count}}条提示词，按S1~S8顺序取前{{batch_count}}屏
2. 输出语言严格使用{{language}}
3. 产品事实只来自{{product}}与{{selling_points}}
4. 严禁保留参考产品细节词"""

    head = """【模板定位】
本模板是“风格骨架模板”，只迁移视觉风格与图文关系。
禁止迁移参考产品的款式、面料、颜色细节、品牌词、产品名与类目词。
"""
    return head + "\n\n" + "\n\n".join(blocks) + "\n\n" + footer


def migrate(data: Dict) -> Dict:
    template = data.get("template", "")
    f_codes = extract_f_codes(template)
    screens = build_screens(f_codes)

    out = {
        "name": data.get("name", "可迁移详情页风格骨架模板"),
        "description": "仅保留视觉风格与图文关系的8屏模板，不包含参考产品细节，可复用于新产品",
        "category": data.get("category", "详情页模板"),
        "trigger": data.get("trigger", "详情页"),
        "weight": float(data.get("weight", 1.0)),
        "schema_version": "style_only_v3",
        "screens": screens,
        "template": build_template_text(),
        "variables": {
            "product": "",
            "selling_points": "",
            "language": "中文",
            "batch_count": 4,
        },
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移旧技能到 style_only_v3")
    parser.add_argument("input", help="输入 YAML 文件路径")
    parser.add_argument("-o", "--output", help="输出 YAML 文件路径，默认覆盖 input")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path

    if not input_path.exists():
        print(f"[ERROR] 输入文件不存在: {input_path}")
        return 1

    with input_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        print("[ERROR] 输入 YAML 顶层必须是字典")
        return 1

    migrated = migrate(data)

    # 基础校验
    screens = migrated.get("screens", [])
    if len(screens) != 8:
        print("[ERROR] 迁移后屏数不为8，已中止")
        return 1

    with output_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            migrated,
            f,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )

    print(f"[OK] 迁移完成: {input_path} -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
