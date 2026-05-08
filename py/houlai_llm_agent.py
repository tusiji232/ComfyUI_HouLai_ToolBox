import os
import re
import json
import asyncio
import traceback
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Union

import yaml

# ============================================
# 技能目录定义（供其他模块使用）
# ============================================
CURRENT_DIR = Path(__file__).parent.parent
SKILLS_DIR = CURRENT_DIR / "skills"

# ============================================
# 依赖检查与导入
# ============================================
DEPS_OK = True
MISSING_DEPS = []

try:
    from openai import OpenAI
except ImportError:
    DEPS_OK = False
    MISSING_DEPS.append("openai")

try:
    import torch
except ImportError:
    DEPS_OK = False
    MISSING_DEPS.append("torch")

try:
    import numpy as np
except ImportError:
    DEPS_OK = False
    MISSING_DEPS.append("numpy")

try:
    from PIL import Image as PILImage
except ImportError:
    DEPS_OK = False
    MISSING_DEPS.append("PIL")

try:
    import aiofiles
    AIOFILES_OK = True
except ImportError:
    AIOFILES_OK = False
    MISSING_DEPS.append("aiofiles")


def check_dependencies():
    """检查依赖是否满足"""
    if not DEPS_OK:
        missing = ", ".join(MISSING_DEPS)
        print(f"[HouLai ToolBox] 缺少必要依赖: {missing}")
        print("[HouLai ToolBox] 请运行: pip install openai torch numpy Pillow pyyaml aiofiles")
    return DEPS_OK


# ============================================
# 工具函数
# ============================================

def tensor_to_pil(image_tensor) -> "PILImage.Image":
    """将 ComfyUI 的图像 Tensor 转换为 PIL Image"""
    if image_tensor is None:
        return None
    
    # 处理不同的 tensor 格式
    if len(image_tensor.shape) == 4:
        # (batch, height, width, channels)
        image_tensor = image_tensor[0]
    
    # 确保值范围在 [0, 1] 或 [0, 255]
    if image_tensor.max() <= 1.0:
        image_tensor = (image_tensor * 255).numpy().astype(np.uint8)
    else:
        image_tensor = image_tensor.numpy().astype(np.uint8)
    
    # 转换为 PIL Image
    if image_tensor.shape[-1] == 3:
        return PILImage.fromarray(image_tensor, 'RGB')
    elif image_tensor.shape[-1] == 4:
        return PILImage.fromarray(image_tensor, 'RGBA')
    else:
        return PILImage.fromarray(image_tensor)


def pil_to_base64(pil_image: PILImage.Image, format: str = "PNG") -> str:
    """将 PIL Image 转换为 base64 字符串"""
    import base64
    from io import BytesIO
    
    buffered = BytesIO()
    pil_image.save(buffered, format=format)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str


def create_vision_message(pil_images: List[PILImage.Image], text_prompt: str) -> List[Dict[str, Any]]:
    """
    创建支持视觉的多模态消息
    
    Args:
        pil_images: PIL Image 列表
        text_prompt: 文本提示词
    
    Returns:
        符合 OpenAI Vision API 格式的消息列表
    """
    content = []
    
    # 添加所有图片
    for pil_img in pil_images:
        base64_img = pil_to_base64(pil_img, "PNG")
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64_img}",
                "detail": "high"
            }
        })
    
    # 添加文本
    content.append({
        "type": "text",
        "text": text_prompt
    })
    
    return [{
        "role": "user",
        "content": content
    }]


# ============================================
# 技能系统 - 异步扫描与加载 (v2.0)
# ============================================

SKILLS_CACHE = {
    "file_list": [],
    "trigger_map": {},
    "weights": {},
    "metadata_list": [],
    "skill_id_map": {},
    "last_scan": 0
}

STYLE_ONLY_SCHEMA_VERSION = "style_only_v3"
STYLE_ONLY_SCREEN_COUNT = 8


def _normalize_language_label(value: str) -> str:
    """将语言值标准化为固定标签。"""
    raw = str(value or "").strip()
    if not raw:
        return "中文"

    lower = raw.lower()
    if "english" in lower or "英文" in raw or lower in {"en", "en-us"}:
        return "English"
    if "日本" in raw or "japanese" in lower or lower in {"ja", "jp"}:
        return "日本語"
    if "한국" in raw or "korean" in lower or lower in {"ko", "kr"}:
        return "한국어"
    if "中文" in raw or "chinese" in lower or "简体" in raw or lower.startswith("zh"):
        return "中文"
    return "中文"


def _normalize_skill_payload_style_only(data: Dict[str, Any], batch_count: int, language: str) -> Dict[str, Any]:
    """
    对技能数据做最小归一化，确保满足 style-only 运行必需字段。
    """
    normalized: Dict[str, Any] = dict(data)
    legacy_mode = str(data.get("schema_version", "") or "").strip() != STYLE_ONLY_SCHEMA_VERSION

    defaults = normalized.get("defaults")
    if not isinstance(defaults, dict):
        defaults = {}
    defaults["schema_version"] = STYLE_ONLY_SCHEMA_VERSION
    defaults["screen_count"] = str(STYLE_ONLY_SCREEN_COUNT)
    defaults.setdefault("style_transfer_mode", "style_only")
    defaults.setdefault("dynamic_sequence", "true")
    defaults.setdefault("language_lock", "strict")

    resolved_language = _normalize_language_label(language or defaults.get("output_language", "中文"))
    defaults["output_language"] = resolved_language
    normalized["defaults"] = defaults
    normalized["schema_version"] = STYLE_ONLY_SCHEMA_VERSION

    variables = normalized.get("variables")
    if not isinstance(variables, dict):
        variables = {}
    variables.setdefault("product", "")
    variables.setdefault("selling_points", "")
    variables["language"] = resolved_language
    variables.setdefault("platform", "")
    variables["batch_count"] = str(batch_count)
    for idx in range(1, STYLE_ONLY_SCREEN_COUNT + 1):
        variables.setdefault(f"copy_function_language_{idx}", "")
    normalized["variables"] = variables

    shots_candidate = normalized.get("shots")
    shots_list = shots_candidate if isinstance(shots_candidate, list) else []
    template_candidate = normalized.get("template", "")
    template_text = template_candidate if isinstance(template_candidate, str) else str(template_candidate)

    invalid_prompt_codes = False
    for shot in shots_list:
        if not isinstance(shot, dict):
            continue
        guide = str(shot.get("prompt_guide", "") or "")
        if re.search(r"(?i)\bf_code\b\s*[:=：]\s*F(\s*[;,\n]|$)", guide):
            invalid_prompt_codes = True
            break
        if re.search(r"(?i)\bp_code\b\s*[:=：]\s*P(\s*[;,\n]|$)", guide):
            invalid_prompt_codes = True
            break
        if re.search(r"(?i)\bi_code\b\s*[:=：]\s*I(\s*[;,\n]|$)", guide):
            invalid_prompt_codes = True
            break

    leakage_text_parts = [template_text]
    for shot in shots_list:
        if not isinstance(shot, dict):
            continue
        leakage_text_parts.append(str(shot.get("name", "") or ""))
        leakage_text_parts.append(str(shot.get("description", "") or ""))
        leakage_text_parts.append(str(shot.get("prompt_guide", "") or ""))
    leakage_text = "\n".join(leakage_text_parts)
    leakage_mode = _has_reference_product_leak_markers(leakage_text)
    language_conflict_mode = _has_template_language_conflict(template_text, resolved_language)

    strict_rebuild = legacy_mode or invalid_prompt_codes or leakage_mode or language_conflict_mode
    if strict_rebuild:
        if invalid_prompt_codes:
            print("[SKILL 技能调用] [WARN] 检测到无效F/P/I编码，启用严格风格骨架重建")
        if leakage_mode:
            print("[SKILL 技能调用] [WARN] 检测到参考产品泄漏信号，启用严格风格骨架重建")
        if language_conflict_mode:
            print("[SKILL 技能调用] [WARN] 检测到模板语言与当前输出语言冲突，启用严格风格骨架重建")
        language_pack = _get_style_only_language_pack(resolved_language)
        normalized["shots"] = [
            {
                "id": f"screen_{idx}",
                "name": language_pack["screen_name"](idx),
                "description": language_pack["screen_desc"](idx),
                "order": idx,
                "prompt_guide": (
                    "f_code=F1/F6; p_code=P2; i_code=I5; "
                    "style_tokens=[balanced composition, clear hierarchy, controlled whitespace]; "
                    "copy_action=generate_copy; "
                    f"copy_placeholder={{{{copy_function_language_{idx}}}}}"
                ),
            }
            for idx in range(1, STYLE_ONLY_SCREEN_COUNT + 1)
        ]
        template_lines = [
            language_pack["title"],
            language_pack["rule_style_only"],
            language_pack["rule_no_product_copy"],
            f"{language_pack['language_lock']}: {{{{language}}}}",
            f"{language_pack['product_source']}: {{{{product}}}}",
            f"{language_pack['platform_source']}: {{{{platform}}}}",
            f"{language_pack['batch_source']}: {{{{batch_count}}}}",
            f"{language_pack['language_source']}: {{{{language}}}}",
        ]
        for idx in range(1, STYLE_ONLY_SCREEN_COUNT + 1):
            template_lines.append(language_pack["screen_line"](idx, f"{{{{copy_function_language_{idx}}}}}"))
        normalized["template"] = "\n".join(template_lines)
        return normalized

    template = normalized.get("template", "")
    if not isinstance(template, str):
        template = str(template)
    template = template.replace("{{copy_function_language}}", "{{copy_function_language_1}}")

    required_runtime = ["{{product}}", "{{language}}", "{{platform}}", "{{batch_count}}"]
    for placeholder in required_runtime:
        if placeholder not in template:
            template += f"\n{placeholder}"

    for idx in range(1, STYLE_ONLY_SCREEN_COUNT + 1):
        placeholder = f"{{{{copy_function_language_{idx}}}}}"
        if placeholder not in template:
            template += f"\nScreen {idx} copy slot: {placeholder}"

    normalized["template"] = template.strip()
    return normalized


def _get_style_only_language_pack(language: str) -> Dict[str, Any]:
    if language == "English":
        return {
            "title": "Style-only transfer template",
            "rule_style_only": "Keep visual style and copy-function relation only.",
            "rule_no_product_copy": "Do not inherit reference product facts.",
            "language_lock": "Output language lock",
            "product_source": "Product runtime source",
            "platform_source": "Platform runtime source",
            "batch_source": "Batch runtime source",
            "language_source": "Language runtime source",
            "screen_line": lambda idx, placeholder: f"Screen {idx} copy slot: {placeholder}",
            "screen_name": lambda idx: f"screen_{idx}",
            "screen_desc": lambda idx: f"Dynamic narrative slot; source_refs:[{idx}]",
        }
    if language == "日本語":
        return {
            "title": "スタイル転写テンプレート",
            "rule_style_only": "視覚スタイルと言語機能関係のみを継承する。",
            "rule_no_product_copy": "参照商品の事実情報は継承しない。",
            "language_lock": "出力言語ロック",
            "product_source": "商品実行時ソース",
            "platform_source": "プラットフォーム実行時ソース",
            "batch_source": "生成数実行時ソース",
            "language_source": "言語実行時ソース",
            "screen_line": lambda idx, placeholder: f"第{idx}画面 文案スロット: {placeholder}",
            "screen_name": lambda idx: f"第{idx}画面",
            "screen_desc": lambda idx: f"動的叙事スロット; source_refs:[{idx}]",
        }
    if language == "한국어":
        return {
            "title": "스타일 전이 템플릿",
            "rule_style_only": "시각 스타일과 카피 기능 관계만 계승한다.",
            "rule_no_product_copy": "참고 상품의 사실 정보는 계승하지 않는다.",
            "language_lock": "출력 언어 잠금",
            "product_source": "상품 런타임 소스",
            "platform_source": "플랫폼 런타임 소스",
            "batch_source": "생성 수 런타임 소스",
            "language_source": "언어 런타임 소스",
            "screen_line": lambda idx, placeholder: f"{idx}번 화면 카피 슬롯: {placeholder}",
            "screen_name": lambda idx: f"{idx}번 화면",
            "screen_desc": lambda idx: f"동적 서사 슬롯; source_refs:[{idx}]",
        }
    return {
        "title": "风格迁移模板",
        "rule_style_only": "仅保留视觉风格与文案功能关系。",
        "rule_no_product_copy": "禁止继承参考产品事实信息。",
        "language_lock": "输出语言锁定",
        "product_source": "产品运行时来源",
        "platform_source": "平台运行时来源",
        "batch_source": "数量运行时来源",
        "language_source": "语言运行时来源",
        "screen_line": lambda idx, placeholder: f"第{idx}屏文案占位: {placeholder}",
        "screen_name": lambda idx: f"第{idx}屏",
        "screen_desc": lambda idx: f"动态叙事功能位; source_refs:[{idx}]",
    }


def _has_reference_product_leak_markers(text: str) -> bool:
    """
    粗粒度泄漏检测：识别明显“参考产品细节”词，命中则触发严格重建。
    """
    if not text:
        return False
    tokens = [
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
    lower = text.lower()
    return any(token.lower() in lower for token in tokens)


def _has_template_language_conflict(template_text: str, language: str) -> bool:
    """
    粗粒度语言冲突检测：
    - English 目标下不应包含大量 CJK 模板静态文本
    - 中文目标下不应包含明显英文骨架标题
    """
    if not template_text:
        return False

    text = str(template_text)
    cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))
    latin_word_count = len(re.findall(r"\b[A-Za-z]{3,}\b", text))

    if language == "English":
        return cjk_count >= 12
    if language == "中文":
        return ("Style-only transfer template" in text) or ("Output language lock" in text) or (latin_word_count >= 24 and cjk_count < 6)
    if language == "日本語":
        return cjk_count < 6 and latin_word_count >= 12
    if language == "한국어":
        return cjk_count < 6 and latin_word_count >= 12
    return False


async def scan_skills_directory_v2_async(force_refresh: bool = False, custom_path: str = "") -> Tuple[List[str], Dict[str, str], Dict[str, float], List[Dict]]:
    """
    异步扫描技能目录 (v2.0版本 - 支持权重和分类元数据)
    
    Args:
        force_refresh: 是否强制刷新缓存
        custom_path: 自定义技能目录路径
    
    Returns:
        Tuple[List[str], Dict[str, str], Dict[str, float], List[Dict]]:
            (技能文件列表, 触发词映射, 权重映射, 元数据列表)
    """
    import time
    current_time = time.time()
    
    # 检查缓存（30秒，减少缓存时间以提高实时性）
    if not force_refresh and (current_time - SKILLS_CACHE["last_scan"] < 30) and SKILLS_CACHE["file_list"]:
        return (SKILLS_CACHE["file_list"], SKILLS_CACHE["trigger_map"],
                SKILLS_CACHE["weights"], SKILLS_CACHE["metadata_list"])
    
    # 确定技能目录
    if custom_path and Path(custom_path).exists():
        skills_dir = Path(custom_path)
    else:
        current_dir = Path(__file__).parent.parent
        skills_dir = current_dir / "skills"
    
    if not skills_dir.exists():
        return ([], {}, {}, [])
    
    # 异步扫描
    file_list = []
    trigger_map = {}
    weights = {}
    metadata_list = []
    
    yaml_files = list(skills_dir.glob("*.yaml"))
    
    for yaml_file in yaml_files:
        # 跳过隐藏文件
        if yaml_file.name.startswith('_'):
            continue
            
        skill_name = yaml_file.stem
        file_list.append(skill_name)
        
        try:
            if AIOFILES_OK:
                import aiofiles
                async with aiofiles.open(yaml_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
            else:
                # 如果 aiofiles 不可用，使用同步读取
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            data = yaml.safe_load(content)
            
            if data and isinstance(data, dict):
                # 提取触发词
                trigger = data.get("trigger", "")
                if trigger:
                    trigger_map[trigger.lower()] = skill_name
                
                # 提取权重
                weight = data.get("weight", 1.0)
                weights[skill_name] = float(weight)
                
                # 提取元数据
                metadata = {
                    "name": skill_name,
                    "trigger": trigger,
                    "weight": weight,
                    "category": data.get("category", ""),
                    "description": data.get("description", ""),
                    "tags": data.get("tags", []),
                    "variables": list(data.get("variables", {}).keys())
                }
                metadata_list.append(metadata)
                    
        except Exception as e:
            print(f"[Skill Scanner] 读取技能文件失败 {yaml_file}: {e}")
    
    # 更新缓存
    SKILLS_CACHE["file_list"] = file_list
    SKILLS_CACHE["trigger_map"] = trigger_map
    SKILLS_CACHE["weights"] = weights
    SKILLS_CACHE["metadata_list"] = metadata_list
    SKILLS_CACHE["last_scan"] = current_time
    
    return (file_list, trigger_map, weights, metadata_list)


def scan_skills_directory_v2(force_refresh: bool = False, custom_path: str = "") -> Tuple[List[str], Dict[str, str], Dict[str, float], List[Dict], Dict[str, str]]:
    """
    同步版本的技能目录扫描 (v2.0)
    """
    import time
    current_time = time.time()
    
    if not force_refresh and (current_time - SKILLS_CACHE["last_scan"] < 60) and SKILLS_CACHE["file_list"]:
        return (SKILLS_CACHE["file_list"], SKILLS_CACHE["trigger_map"],
                SKILLS_CACHE["weights"], SKILLS_CACHE["metadata_list"],
                SKILLS_CACHE.get("skill_id_map", {}))
    
    if custom_path and Path(custom_path).exists():
        skills_dir = Path(custom_path)
    else:
        current_dir = Path(__file__).parent.parent
        skills_dir = current_dir / "skills"
    
    if not skills_dir.exists():
        return ([], {}, {}, [], {})
    
    return _scan_skills_sync(skills_dir)


def _scan_skills_sync(skills_dir: Path) -> Tuple[List[str], Dict[str, str], Dict[str, float], List[Dict], Dict[str, str]]:
    """同步扫描技能文件 (内部实现)"""
    import time
    
    file_list = []
    trigger_map = {}
    weights = {}
    metadata_list = []
    skill_id_map = {}  # 显示名到文件名的映射
    
    try:
        yaml_files = list(skills_dir.glob("*.yaml"))
    except Exception as e:
        print(f"[Skill Scanner] 扫描目录失败: {e}")
        return ([], {}, {}, [], {})
    
    for yaml_file in yaml_files:
        if yaml_file.name.startswith('_'):
            continue
            
        skill_name = yaml_file.stem
        
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                
                if data and isinstance(data, dict):
                    # 获取中文显示名称（从YAML的name字段，如果没有则使用文件名）
                    display_name = data.get("name", skill_name)
                    file_list.append(display_name)
                    
                    # 建立显示名到文件名的映射
                    skill_id_map[display_name] = skill_name
                    
                    # 触发词
                    trigger = data.get("trigger", "")
                    if trigger:
                        trigger_map[trigger.lower()] = display_name
                    
                    # 权重
                    weight = data.get("weight", 1.0)
                    weights[display_name] = float(weight)
                    
                    # 元数据
                    metadata = {
                        "name": display_name,
                        "skill_id": skill_name,
                        "trigger": trigger,
                        "weight": weight,
                        "category": data.get("category", ""),
                        "description": data.get("description", ""),
                        "tags": data.get("tags", []),
                        "variables": list(data.get("variables", {}).keys())
                    }
                    metadata_list.append(metadata)
                else:
                    # YAML格式错误，使用文件名
                    file_list.append(skill_name)
                    skill_id_map[skill_name] = skill_name
                    
        except Exception as e:
            print(f"[Skill Scanner] 读取技能文件失败 {yaml_file}: {e}")
            file_list.append(skill_name)
            skill_id_map[skill_name] = skill_name
    
    # 更新缓存
    SKILLS_CACHE["file_list"] = file_list
    SKILLS_CACHE["trigger_map"] = trigger_map
    SKILLS_CACHE["weights"] = weights
    SKILLS_CACHE["metadata_list"] = metadata_list
    SKILLS_CACHE["skill_id_map"] = skill_id_map
    SKILLS_CACHE["last_scan"] = time.time()
    
    return (file_list, trigger_map, weights, metadata_list, skill_id_map)


def scan_skills_directory(force_refresh: bool = False, custom_path: str = "") -> Tuple[List[str], Dict[str, str]]:
    """
    向后兼容的 v1.0 技能扫描接口
    
    Returns:
        Tuple[List[str], Dict[str, str]]: (技能文件列表, 触发词映射)
    """
    file_list, trigger_map, _, _, _ = scan_skills_directory_v2(force_refresh, custom_path)
    return (file_list, trigger_map)


def search_skill_by_trigger(text: str) -> Optional[str]:
    """
    根据触发词搜索技能 (v2.0支持权重排序和标签匹配)
    
    Args:
        text: 用户输入的文本
    
    Returns:
        匹配的技能名称，未匹配则返回 None
    """
    if not text:
        return None
    
    text = text.lower().strip()
    file_list, trigger_map, weights, metadata_list, skill_id_map = scan_skills_directory_v2()
    
    # 精确匹配触发词
    if text in trigger_map:
        return trigger_map[text]
    
    # 构建技能元数据字典便于查找
    metadata_dict = {meta['name']: meta for meta in metadata_list}
    
    # 匹配技能（按权重排序）
    matched_skills = []
    
    for skill_name in file_list:
        score = 0.0
        weight = weights.get(skill_name, 1.0)
        metadata = metadata_dict.get(skill_name, {})
        
        # 1. 触发词包含匹配
        trigger = metadata.get('trigger', '').lower()
        if trigger:
            if trigger == text:
                score += 100 * weight  # 精确匹配触发词，最高权重
            elif trigger in text:
                score += 50 * weight   # 触发词在文本中
            elif text in trigger:
                score += 30 * weight   # 文本在触发词中
        
        # 2. 标签匹配
        tags = metadata.get('tags', [])
        for tag in tags:
            if isinstance(tag, dict):
                tag_name = tag.get('name', '').lower()
                tag_weight = tag.get('weight', 1.0)
            else:
                tag_name = str(tag).lower()
                tag_weight = 1.0
            
            if tag_name == text:
                score += 40 * tag_weight * weight
            elif tag_name in text or text in tag_name:
                score += 20 * tag_weight * weight
        
        # 3. 类别匹配
        category = metadata.get('category', '').lower()
        if category and (category in text or text in category):
            score += 25 * weight
        
        # 4. 描述匹配
        description = metadata.get('description', '').lower()
        if description and text in description:
            score += 10 * weight
        
        # 5. 技能名称匹配
        if skill_name.lower() == text:
            score += 80 * weight
        elif text in skill_name.lower():
            score += 20 * weight
        
        if score > 0:
            matched_skills.append((skill_name, score))
    
    if matched_skills:
        # 按分数降序排序，返回分数最高的
        matched_skills.sort(key=lambda x: x[1], reverse=True)
        selected_skill = matched_skills[0][0]
        
        # 获取技能文件名（skill_id）
        skill_id = skill_id_map.get(selected_skill, selected_skill)
        
        # 显示技能调用记录
        print("=" * 60)
        print(f"[SKILL 技能调用] 关键词 '{text}' 触发技能匹配")
        print(f"[SKILL 技能调用] 匹配技能: {selected_skill}")
        print(f"[SKILL 技能调用] 技能文件: {skill_id}.yaml")
        print(f"[SKILL 技能调用] 匹配分数: {matched_skills[0][1]:.1f}")
        print("=" * 60)
        
        return selected_skill
    
    print(f"[SKILL 技能调用] 关键词 '{text}' 未匹配到任何技能")
    return None


def load_skill_template(skill_selection: str, custom_path: str = "", batch_count: int = 4, language: str = "") -> Optional[str]:
    """
    加载技能模板文件并填充变量（增强版 - 兼容多种变量格式）

    Args:
        skill_selection: 技能显示名称（中文）或文件名（英文）
        custom_path: 自定义技能目录路径
        batch_count: 生成图片的数量
        language: 指定语言，如 "中文"、"English" 等，为空则使用技能文件中的设置
    
    Returns:
        填充变量后的模板字符串，失败则返回 None
    """
    if not DEPS_OK:
        return None

    # 构建技能文件路径
    if custom_path and Path(custom_path).exists():
        skills_dir = Path(custom_path)
    else:
        current_dir = Path(__file__).parent.parent
        skills_dir = current_dir / "skills"
    
    # 尝试直接使用 skill_selection 作为文件名
    yaml_file = skills_dir / f"{skill_selection}.yaml"
    
    # 如果文件不存在，尝试通过显示名称查找对应的文件名
    if not yaml_file.exists():
        _, _, _, _, skill_id_map = scan_skills_directory_v2()
        if skill_selection in skill_id_map:
            skill_id = skill_id_map[skill_selection]
            yaml_file = skills_dir / f"{skill_id}.yaml"
    
    if not yaml_file.exists():
        print(f"[SKILL 技能调用] 技能文件不存在: {yaml_file}")
        return None

    try:
        print(f"[SKILL 技能调用] 正在加载技能文件: {yaml_file.name}")
        print(f"[SKILL 技能调用] 完整路径: {yaml_file}")
        
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # 增强：验证技能文件格式
        if not data:
            print(f"[SKILL 技能调用] 技能文件为空或解析失败: {yaml_file}")
            return None
            
        if not isinstance(data, dict):
            print(f"[SKILL 技能调用] 技能文件格式错误，应为字典类型: {yaml_file}")
            return None
            
        if "template" not in data:
            print(f"[SKILL 技能调用] 技能文件格式错误，缺少 template 字段: {yaml_file}")
            print(f"[SKILL 技能调用] 可用字段: {list(data.keys())}")
            return None

        schema_version = str(data.get("schema_version", "") or "").strip()
        if schema_version != STYLE_ONLY_SCHEMA_VERSION:
            print(
                f"[SKILL 技能调用] [WARN] 技能schema_version={schema_version or 'missing'}，"
                f"运行时自动归一化为 {STYLE_ONLY_SCHEMA_VERSION}"
            )

        data = _normalize_skill_payload_style_only(data, batch_count=batch_count, language=language)

        template = data["template"]
        variables = data.get("variables", {})
        
        # 增强：验证 template 类型
        if not isinstance(template, str):
            print(f"[SKILL 技能调用] template 字段类型错误，应为字符串: {type(template)}")
            return None
            
        # 增强：验证 variables 类型
        if not isinstance(variables, dict):
            print(f"[SKILL 技能调用] variables 字段类型错误，应为字典: {type(variables)}")
            variables = {}

        # 增强：定义统一的变量值提取函数
        def get_variable_value(var_value, var_name: str = "", default: str = "") -> str:
            """
            统一处理变量值，支持简单值和字典格式
            
            Args:
                var_value: 变量值（可能是 str/int/float/dict）
                var_name: 变量名（用于日志）
                default: 默认值
            
            Returns:
                str: 处理后的字符串值
            """
            if var_value is None:
                return default
                
            if isinstance(var_value, dict):
                # 字典格式：提取 default 字段
                actual = var_value.get("default", default)
                if actual is None:
                    actual = default
                print(f"[SKILL 技能调用] 变量 {var_name}: dict 格式 -> {actual}")
                return str(actual)
            elif isinstance(var_value, (str, int, float)):
                # 简单值格式
                return str(var_value)
            else:
                # 其他类型，转为字符串
                print(f"[SKILL 技能调用] 变量 {var_name}: 未知类型 {type(var_value)}，转为字符串")
                return str(var_value)

        # 注入默认变量（增强：统一使用 get_variable_value）
        filled_template = template
        
        # platform 变量
        platform_val = get_variable_value(
            variables.get("platform"),
            "platform",
            "电商平台"
        )
        filled_template = filled_template.replace("{{platform}}", platform_val)
        
        # selling_points 变量
        selling_val = get_variable_value(
            variables.get("selling_points"),
            "selling_points",
            "高品质、实用"
        )
        filled_template = filled_template.replace("{{selling_points}}", selling_val)
        
        # batch_count 变量（优先使用传入的参数）
        filled_template = filled_template.replace("{{batch_count}}", str(batch_count))
        
        # language 变量（优先使用传入的参数）
        effective_language = language if language else get_variable_value(
            variables.get("language"),
            "language",
            "中文"
        )
        filled_template = filled_template.replace("{{language}}", effective_language)
        language = effective_language
        
        # 运行时变量应保留到 process 阶段再注入，避免过早清空占位符
        runtime_keep_names = {"product", "platform", "selling_points", "product_info", "batch_count", "language"}
        
        # 处理 copy_function_language - 根据F代码和语言预生成对应语言的自然语言描述
        # 确保中文输入一定输出中文，不会泄露英文
        import re
        f_code_matches = _extract_f_codes_from_skill(filled_template, data)
        
        safe_language = str(language).encode("unicode_escape").decode("ascii")
        print(f"[SKILL 技能调用] 语言设置: {safe_language}")
        print(f"[SKILL 技能调用] 检测到F代码: {f_code_matches}")
        
        has_indexed_copy_placeholder = bool(re.search(r'\{\{copy_function_language_\d+\}\}', filled_template))
        has_generic_copy_placeholder = "{{copy_function_language}}" in filled_template
        indexed_ids = sorted({
            int(m) for m in re.findall(r'\{\{copy_function_language_(\d+)\}\}', filled_template)
        })

        if has_indexed_copy_placeholder:
            # 按占位符序号替换，避免“第N屏占位符”与“第N个F码”错位
            if f_code_matches:
                for idx, placeholder_id in enumerate(indexed_ids):
                    f_codes = f_code_matches[idx] if idx < len(f_code_matches) else f_code_matches[-1]
                    copy_desc = _get_copy_function_language(f_codes, language)
                    placeholder = f"{{{{copy_function_language_{placeholder_id}}}}}"
                    filled_template = filled_template.replace(placeholder, copy_desc)
                    print(f"[SKILL 技能调用] 替换 {placeholder} ({f_codes})")
            else:
                # 新格式未显式写F码时，给每屏占位符统一兜底，避免被清空
                default_desc = _get_copy_function_language("F1+F6", language)
                for placeholder_id in indexed_ids:
                    placeholder = f"{{{{copy_function_language_{placeholder_id}}}}}"
                    filled_template = filled_template.replace(placeholder, default_desc)
                    print(f"[SKILL 技能调用] 兜底替换 {placeholder}")

        if has_generic_copy_placeholder:
            default_f_code = f_code_matches[0] if f_code_matches else "F1+F6"
            default_desc = _get_copy_function_language(default_f_code, language)
            filled_template = filled_template.replace("{{copy_function_language}}", default_desc)
            print("[SKILL 技能调用] 默认替换: {{copy_function_language}}")
        
        # 【关键调试】输出替换后的模板片段，验证占位符是否正确替换
        remaining_placeholders = re.findall(r'\{\{\w+\}\}', filled_template)
        if remaining_placeholders:
            print(f"[SKILL 技能调用] [WARN] 仍有未替换的占位符: {remaining_placeholders}")
            # 增强：尝试替换剩余的占位符
            for placeholder_name in remaining_placeholders:
                var_name = placeholder_name.strip('{}')
                if var_name in runtime_keep_names:
                    continue
                if var_name in variables:
                    var_value = get_variable_value(variables[var_name], var_name, "")
                    filled_template = filled_template.replace(placeholder_name, var_value)
                    print(f"[SKILL 技能调用] 自动替换 {placeholder_name} -> {var_value}")
        else:
            print(f"[SKILL 技能调用] OK 所有占位符已替换")
        
        # 输出包含"reserved for"的片段，验证语言
        reserved_matches = re.findall(r'reserved for (.+?) text', filled_template)
        print(f"[SKILL 技能调用] 'reserved for' 片段数量: {len(reserved_matches)}")

        # 注入用户定义的其他变量（增强：使用统一的 get_variable_value）
        for var_name, var_value in variables.items():
            if var_name in runtime_keep_names:
                continue
            placeholder = f"{{{{{var_name}}}}}"
            if placeholder in filled_template:
                actual_value = get_variable_value(var_value, var_name, "")
                filled_template = filled_template.replace(placeholder, actual_value)
        
        # 最终检查：是否还有未替换的占位符
        final_check = re.findall(r'\{\{\w+\}\}', filled_template)
        if final_check:
            print(f"[SKILL 技能调用] [WARN] 最终仍有未替换的占位符: {final_check}")
            for ph in final_check:
                ph_name = ph.strip("{}")
                if ph_name in runtime_keep_names:
                    continue
                filled_template = filled_template.replace(ph, "")
        
        # 显示技能加载成功信息
        skill_name = data.get("name", yaml_file.stem)
        trigger = data.get("trigger", "无")
        print("=" * 60)
        print(f"[OK 技能调用] 技能文件加载成功!")
        print(f"[OK 技能调用] 技能名称: {skill_name}")
        print(f"[OK 技能调用] 技能文件: {yaml_file.name}")
        print(f"[OK 技能调用] 触发词: {trigger}")
        print("=" * 60)

        return filled_template

    except yaml.YAMLError as e:
        print(f"[SKILL 技能调用] YAML解析错误: {e}")
        return None
    except Exception as e:
        print(f"[SKILL 技能调用] 加载技能文件失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def _get_copy_function_language(f_codes: str, language: str) -> str:
    """
    根据F代码和语言生成对应的自然语言描述
    
    Args:
        f_codes: F代码组合，如 "F1+F6", "F2+F5" 等
        language: 目标语言，如 "中文", "English", "日本語", "한국어"
    
    Returns:
        对应语言的自然语言描述
    """
    f_codes = _normalize_f_code_pattern(f_codes)

    # F代码映射表
    f_code_mapping = {
        "F1": {
            "中文": "产品标题和主标题",
            "English": "product title and main headline",
            "日本語": "商品タイトルとメインヘッドライン",
            "한국어": "제품 제목 및 메인 헤드라인"
        },
        "F2": {
            "中文": "产品特性和面料描述",
            "English": "product features and fabric description",
            "日本語": "製品特徴と生地の説明",
            "한국어": "제품 특징 및 원단 설명"
        },
        "F3": {
            "中文": "标注标签和特性标记",
            "English": "annotated callout labels and feature markers",
            "日本語": "注釈ラベルと特徴マーカー",
            "한국어": "주석 라벨 및 특징 마커"
        },
        "F4": {
            "中文": "尺码表和测量信息",
            "English": "size chart and measurement information",
            "日本語": "サイズチャートと測定情報",
            "한국어": "사이즈 차트 및 측정 정보"
        },
        "F5": {
            "中文": "护理说明和使用指南",
            "English": "care instructions and usage guide",
            "日本語": "お手入れ説明と使用ガイド",
            "한국어": "관리 설명 및 사용 가이드"
        },
        "F6": {
            "中文": "场景描述和搭配建议",
            "English": "scene description and styling suggestions",
            "日本語": "シーン説明とスタイリング提案",
            "한국어": "시장 설명 및 스타일링 제안"
        },
        # 组合代码
        "F1+F6": {
            "中文": "产品标题和场景描述",
            "English": "product title and scene description",
            "日本語": "商品タイトルとシーン説明",
            "한국어": "제품 제목 및 시장 설명"
        },
        "F2+F5": {
            "中文": "产品特性和护理说明",
            "English": "product features and care instructions",
            "日本語": "製品特徴とお手入れ説明",
            "한국어": "제품 특징 및 관리 설명"
        },
        "F3+F6": {
            "中文": "特性标注和场景说明",
            "English": "feature annotations and styling notes",
            "日本語": "特徴注釈とスタイリングノート",
            "한국어": "특징 주석 및 스타일링 노트"
        },
        "F1+F2": {
            "中文": "产品标题和特性描述",
            "English": "product title and feature description",
            "日本語": "商品タイトルと特徴説明",
            "한국어": "제품 제목 및 특징 설명"
        },
        "F4+F5": {
            "中文": "尺码信息和护理说明",
            "English": "size information and care instructions",
            "日本語": "サイズ情報とお手入れ説明",
            "한국어": "사이즈 정보 및 관리 설명"
        }
    }
    
    # 标准化语言参数
    lang_key = "中文"  # 默认中文
    if "english" in language.lower() or "英文" in language:
        lang_key = "English"
    elif "日本" in language or "japanese" in language.lower():
        lang_key = "日本語"
    elif "한국" in language or "korean" in language.lower():
        lang_key = "한국어"
    elif "中文" in language or "chinese" in language.lower():
        lang_key = "中文"
    
    # 返回对应描述，如果不存在则返回默认描述
    if f_codes in f_code_mapping and lang_key in f_code_mapping[f_codes]:
        return f_code_mapping[f_codes][lang_key]
    
    # 如果是组合代码但没有预定义，尝试拆分组合
    if "+" in f_codes:
        parts = f_codes.split("+")
        descriptions = []
        for part in parts:
            part = part.strip()
            if part in f_code_mapping and lang_key in f_code_mapping[part]:
                descriptions.append(f_code_mapping[part][lang_key])
        if descriptions:
            if lang_key == "中文":
                return "和".join(descriptions)
            else:
                return " and ".join(descriptions)
    
    # 默认返回英文描述（最通用）
    default_mapping = {
        "中文": "产品标题和场景描述",
        "English": "product title and scene description",
        "日本語": "商品タイトルとシーン説明",
        "한국어": "제품 제목 및 시장 설명"
    }
    return default_mapping.get(lang_key, default_mapping["English"])


def _normalize_f_code_pattern(raw: str) -> str:
    """
    统一 F 码格式，兼容 F1+F6 / F1/F6 / f1,f6 / f1 f6 等写法
    """
    if not raw:
        return "F1+F6"
    parts = re.findall(r'F\s*([1-6])', str(raw).upper())
    if not parts:
        return "F1+F6"
    ordered = []
    for p in parts:
        code = f"F{p}"
        if code not in ordered:
            ordered.append(code)
    return "+".join(ordered)


def _extract_f_codes_from_skill(template_text: str, skill_data: Dict[str, Any]) -> List[str]:
    """
    从 template / shots 中提取 F 码，兼容旧模板与 style-only 新模板
    """
    patterns = [
        r'文案功能类型:\s*([Ff0-9\+\s/、,]+)',
        r'(?im)\bf_code\b\s*[:=：]\s*["\']?([Ff0-9\+\s/、,]+)',
    ]

    raw_codes: List[str] = []
    for pattern in patterns:
        raw_codes.extend(re.findall(pattern, template_text))

    # 若 template 中未提取到，回退读取 shots 的 prompt_guide/description
    if not raw_codes:
        shots = skill_data.get("shots", [])
        if isinstance(shots, list):
            for shot in shots:
                if not isinstance(shot, dict):
                    continue
                for key in ("prompt_guide", "description"):
                    content = str(shot.get(key, "") or "")
                    m = re.search(r'(?i)\bf_code\b\s*[:=：]\s*([Ff0-9\+\s/、,]+)', content)
                    if m:
                        raw_codes.append(m.group(1))
                        break

    normalized = [_normalize_f_code_pattern(item) for item in raw_codes if str(item).strip()]
    return normalized


def build_holistic_skill_template(data: dict, batch_count: int) -> str:
    """
    将 skill yaml 数据转换为 holistic prompt template
    
    Args:
        data: skill yaml 解析后的字典
        batch_count: 生成图片数量
    
    Returns:
        完整的 holistic prompt template 字符串
    """
    skill_name = data.get("name", "Unknown Skill")
    description = data.get("description", "")
    template = data.get("template", "")
    variables = data.get("variables", {})
    
    # 替换变量
    # 支持简单值和元数据格式（含type/description/default）
    filled_template = template
    for var_name, var_value in variables.items():
        placeholder = f"{{{{{var_name}}}}}"
        # 解析变量值：如果 var_value 是字典，提取 default 值
        if isinstance(var_value, dict):
            actual_value = var_value.get("default", "")
        else:
            actual_value = var_value
        filled_template = filled_template.replace(placeholder, str(actual_value))
    
    # 确保 batch_count 被替换
    filled_template = filled_template.replace("{{batch_count}}", str(batch_count))
    
    # 构建 holistic template
    holistic = f"""【技能名称】{skill_name}
【描述】{description}

【模板】
{filled_template}

【任务】
请根据以上模板，生成{batch_count}条独立的电商详情页视觉提示词。"""
    
    return holistic


# ============================================
# 详情页参考模式系统提示词模板
# ============================================

REFERENCE_MODE_LEGACY_SYSTEM_PROMPT_TEMPLATE = """你是一位专业的电商详情页视觉设计分析师和AI绘图提示词专家。

【角色定位】
你擅长分析电商详情页的设计结构、视觉风格和排版布局，并能根据参考详情页的设计语言，为新产品生成适配的详情页视觉提示词。

【分析维度】
1. 构图布局：页面结构、图片位置、留白比例、模块分布
2. 排版风格：标题层级、文字区域、信息密度、视觉动线
3. 视觉风格：配色方案、光影效果、整体调性、质感表现
4. 结构模块：首屏海报、产品展示、卖点说明、场景图、细节展示等

【任务要求】
- 深度分析参考详情页的设计要素
- 结合产品图的特点和属性
- 生成{batch_count}条独立、完整的AI绘图提示词
- 每条提示词应体现参考页的设计风格，但适配当前产品
- 提示词使用{language}语言输出

【风格迁移硬约束】
1. 只迁移参考页的视觉风格：配色、光影、构图、版式、图文关系、模块组织
2. 严禁复用参考页产品细节：款式细节、面料细节、颜色细节、五金、品牌词、产品名、类目词
3. 若参考页信息与当前产品冲突，必须以当前产品为准
4. 输出前执行泄漏检查：若残留参考产品细节词，必须重写

【语言锁定】
输出必须严格使用 {language}，禁止中英混杂或多语言混杂

【输出格式】
请直接输出{batch_count}行提示词，每行一个完整的prompt，不要添加序号或其他说明文字。"""


# ============================================
# 节点类定义
# ============================================

class Universal_LLM_Config:
    """
    通用LLM配置节点
    用于配置Base URL、API Key、模型名称等参数
    """
    
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {
            "required": {
                "base_url": ("STRING", {"default": "https://api.openai.com/v1", "tooltip": "API基础URL"}),
                "api_key": ("STRING", {"default": "", "tooltip": "API密钥"}),
                "model_name": ("STRING", {"default": "gpt-4o", "tooltip": "模型名称，如gpt-4o、claude-3-opus等"}),
            },
            "optional": {
                "system_prompt": ("STRING", {
                    "default": "", 
                    "multiline": True,
                    "tooltip": "系统提示词，定义AI助手的角色和行为"
                }),
            }
        }
    
    RETURN_TYPES = ("DICT",)
    RETURN_NAMES = ("LLM配置",)
    FUNCTION = "create_config"
    CATEGORY = "后来工具箱/AI AI智能"
    DESCRIPTION = "配置LLM API参数，包括Base URL、API Key和模型名称"

    def create_config(self, base_url: str, api_key: str, 
                      model_name: str, system_prompt: str = "") -> Tuple[Dict[str, Any]]:
        """创建LLM配置字典"""
        config = {
            "base_url": base_url.strip(),
            "api_key": api_key.strip(),
            "model_name": model_name.strip(),
            "system_prompt": system_prompt.strip()
        }
        print(f"[Universal_LLM_Config] 配置已创建: {model_name} @ {base_url}")
        return (config,)


class Ecommerce_Skill_Router:
    """
    电商技能路由节点
    支持通过技能模板生成批量提示词，或分析上传的图片内容
    """
    
    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        # 获取技能列表 - 确保始终有可用技能
        skills = []
        try:
            # 直接扫描技能目录，不检查依赖
            file_list, trigger_map, weights, metadata_list, skill_id_map = scan_skills_directory_v2(force_refresh=False)
            # 使用显示名称（中文）作为选项
            skills = file_list if file_list else []
        except Exception as e:
            print(f"[Ecommerce_Skill_Router] 获取技能列表失败: {e}")
            skills = []

        if skills:
            skills = ["<请选择技能>"] + skills
        else:
            skills = ["<请选择技能>", "<未找到技能文件>"]
        
        return {
            "required": {
                "技能选择": (skills, {"default": "<请选择技能>", "tooltip": "仅在“技能模板模式”下生效；其他模式会忽略此项"}),
                "LLM配置": ("DICT", {"tooltip": "从通用LLM配置节点传入的配置"}),
                "工作模式": ([
                    "技能模板模式",
                    "自定义模板模式",
                    "参考图模式"
                ], {
                    "default": "自定义模板模式",
                    "tooltip": "推荐优先使用这个下拉明确控制模式"
                }),
                "输出模式": (["分批输出", "合并输出"], {"tooltip": "分批输出每行一个prompt，合并输出为完整文本"}),
                "生图数量": ("INT", {"default": 4, "min": 1, "max": 20, "tooltip": "要生成的提示词数量"}),
                "产品图数量": ("INT", {"default": 3, "min": 1, "max": 3, "tooltip": "选择要上传的产品图片数量(1-3张)"}),
            },
            "optional": {
                "image1": ("IMAGE", {"tooltip": "产品图1"}),
                "image2": ("IMAGE", {"tooltip": "产品图2"}),
                "image3": ("IMAGE", {"tooltip": "产品图3"}),
                "reference_image": ("IMAGE", {"tooltip": "详情页参考图"}),
                "关键词搜索": ("STRING", {"default": "", "tooltip": "输入关键词自动匹配技能（支持触发词）"}),
                "自定义技能目录": ("STRING", {"default": "", "tooltip": "自定义技能文件夹路径，留空使用默认"}),
                "产品名称": ("STRING", {"default": "", "tooltip": "产品名称，用于提示词生成"}),
                "目标人群": ("STRING", {"default": "", "tooltip": "目标用户群体描述"}),
                "产品参数": ("STRING", {"default": "", "multiline": True, "tooltip": "产品规格参数"}),
                "卖点": ("STRING", {"default": "", "multiline": True, "tooltip": "产品核心卖点"}),
                "平台": ("STRING", {"default": "", "tooltip": "电商平台类型，如淘宝、天猫、京东、亚马逊等"}),
                "语言": ("STRING", {"default": "", "tooltip": "输出语言，如中文、English、日本語等"}),
                "自定义模板": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "【Skill模式】关闭技能时使用此模板"
                }),
                "参考页系统提示词": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "【详情页参考模式】留空使用默认提示词，自定义时以此为准"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("batch_prompts", "formatted_summary")
    FUNCTION = "process"
    OUTPUT_IS_LIST = (True, False)
    CATEGORY = "后来工具箱/AI AI智能"
    DESCRIPTION = "电商详情页智能生成器：支持技能模板或自定义模板，可分析上传的图片生成提示词"

    def _normalize_language(self, language: str) -> str:
        """将用户输入的语言归一化到系统支持集合。"""
        if not language:
            return ""
        lang = str(language).strip()
        low = lang.lower()

        if ("english" in low) or (low in {"en", "en-us", "en-gb"}) or ("英文" in lang):
            return "English"
        if ("中文" in lang) or ("chinese" in low) or (low in {"zh", "zh-cn", "zh-hans", "zh-tw"}):
            return "中文"
        if ("日本" in lang) or ("japanese" in low) or (low in {"ja", "jp"}):
            return "日本語"
        if ("한국" in lang) or ("korean" in low) or (low in {"ko", "kr"}):
            return "한국어"
        return ""

    def _detect_language_from_text(self, text: str) -> str:
        """从文本中粗略检测语言（仅在用户未显式指定时使用）。"""
        if not text:
            return ""
        # 日文优先于中文，避免汉字重叠导致误判
        if re.search(r"[\u3040-\u30ff\u31f0-\u31ff]", text):
            return "日本語"
        if re.search(r"[\uac00-\ud7af]", text):
            return "한국어"
        if re.search(r"[\u4e00-\u9fff]", text):
            return "中文"
        if re.search(r"[A-Za-z]", text):
            return "English"
        return ""

    def _resolve_effective_language(self, explicit_language: str, *sources: str) -> str:
        """
        语言优先级：
        1) 节点显式输入 2) 文本自动检测 3) 默认中文
        """
        normalized = self._normalize_language(explicit_language)
        if normalized:
            return normalized

        joined = "\n".join([s for s in sources if s])
        detected = self._detect_language_from_text(joined)
        if detected:
            return detected
        return "中文"

    def _inject_prompt_variables(self, template: str, variables: Dict[str, Any]) -> str:
        """
        兼容两种占位符风格：
        - {{language}}
        - {language}
        未匹配字段保持原样，不抛异常。
        """
        if not template:
            return template

        result = template
        safe_vars = {k: "" if v is None else str(v) for k, v in variables.items()}

        # 先替换双大括号变量
        for k, v in safe_vars.items():
            result = result.replace(f"{{{{{k}}}}}", v)

        # 再尝试替换单大括号变量，未知键保持原样
        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        try:
            result = result.format_map(_SafeDict(safe_vars))
        except Exception:
            pass

        return result

    def _build_generation_line(self, language: str, batch_count: int) -> str:
        """根据语言生成最终数量约束句。"""
        if language == "English":
            return f"\n\nPlease strictly generate {batch_count} standalone prompts, one complete prompt per line."
        if language == "日本語":
            return f"\n\n{batch_count}行の独立したプロンプトを厳密に生成してください。1行につき1つの完全なpromptにしてください。"
        if language == "한국어":
            return f"\n\n반드시 {batch_count}개의 독립 프롬프트를 생성하세요. 각 줄에 완전한 prompt를 1개씩 작성하세요."
        return f"\n\n请严格生成{batch_count}行独立的提示词，每行一个完整的prompt。"

    def _build_reference_mode_extraction_system_prompt(self, language: str, batch_count: int) -> str:
        """构建参考模式的第一阶段：参考页骨架抽取系统提示词。"""
        return f"""你是一位电商详情页骨架提取专家。

你的任务不是直接写最终出图 prompt，而是先把参考详情页抽象成可运行的动态骨架模板。

【核心目标】
- 只继承参考页的视觉骨架：模块顺序、镜头节奏、主体与文案区关系、留白、拼版方式、画面氛围
- 严禁继承参考产品事实：品类词、品牌词、参数、配件、颜色、材质细节、文案原句
- 最终必须输出严格等于 {batch_count} 屏的骨架，不多不少
- 输出语言目标为：{language}

【动态屏数规则】
- 如果参考页可见模块多于 {batch_count}，合并相邻且叙事接近的模块，优先保留 hero / feature / scene / macro / proof / closure 的差异
- 如果参考页可见模块少于 {batch_count}，允许把强模块拆成更细的镜头节奏，例如 hero 拆成 opening 与主视觉，detail 拆成结构页与局部页，scene 拆成氛围页与使用页
- 不允许为了凑数而输出多张只是改标题位置的重复海报
- 每屏都要在 camera、layout、subject、text_zone 或 text_density 上形成可见差异

【安全约束】
- 只在参考图确实体现时才保留 multi-panel、compare、evidence、scene-collage 等结构
- 如果后续只有 1 张产品图，也必须让骨架能安全退回单产品重复、裁切、局部或同主体重组，而不是强依赖额外 SKU
- 不要把业务判断、真假验证、文案创作逻辑写进骨架

【字段要求】
每个 screen line 必须包含以下字段，顺序固定：
kind, bg, camera, layout, subject, accent, text_mode, text_zone, text_align, text_density, copy_role, slot, negative

【字段约束】
- kind / bg / camera / layout / subject / accent / negative 尽量使用简洁的 ASCII token 或短语
- text_mode 只能是 strong / weak / placeholder
- text_align 只能是 left / center / right
- copy_role 优先从这些词中选择：hero-benefit, hero-feature, feature-callout, scene-note, material-note, comfort-proof, proof-data, choice-recap
- slot 必须是简短的文案功能提示，使用 {language}

【输出格式】
只允许输出一个模板块，不要解释，不要 Markdown，不要序号：
BEGIN_TEMPLATE
sv=style_only_v3
cn=参考页动态骨架
pd={{product}}
pi={{product_info}}
sp={{selling_points}}
pf={{platform}}
lg={{language}}
bc={{batch_count}}
arch=skeleton-only
brain=system-prompt-only
s1|kind=...|bg=...|camera=...|layout=...|subject=...|accent=...|text_mode=...|text_zone=...|text_align=...|text_density=...|copy_role=...|slot=...|negative=...
...
END_TEMPLATE"""

    def _build_reference_mode_extraction_user_prompt(
        self,
        language: str,
        product_info: str,
        product_image_count: int,
        batch_count: int,
        platform: str,
    ) -> str:
        """构建参考模式第一阶段的用户提示词。"""
        return f"""【任务类型】
参考详情页骨架抽取

【输出语言】
{language}

【产品信息】
{product_info}

【运行时约束】
- 最终详情页数量：{batch_count}
- 当前上传的产品图数量：{product_image_count}
- 平台：{platform or '淘宝'}

【参考图说明】
你现在只需要分析这 1 张参考详情页长图，抽取它的叙事节奏和屏位骨架。

【抽取要求】
1. 先识别这张参考页里可见的模块节奏，例如开场、主视觉、卖点拆解、细节特写、场景、证明、对比、收尾
2. 再按照 {batch_count} 屏重组为动态骨架
3. 只保留结构，不要带入参考商品事实
4. 输出必须严格是模板块，且只有 s1 到 s{batch_count}
5. slot 请写成简短的文案功能提示，便于后续生成最终 prompt

开始抽取。"""

    def _build_reference_mode_screen_plan(self, batch_count: int, product_image_count: int, language: str) -> List[str]:
        """根据屏数生成本次详情页设计任务清单。"""
        chinese_plan_map = {
            1: ["第1屏：首屏主视觉页，聚焦整体产品形象、主标题和视觉气质。"],
            2: [
                "第1屏：首屏主视觉页，聚焦整体产品形象、主标题和视觉气质。",
                "第2屏：补充卖点页，基于已提供卖点或产品图可见结构做单一重点说明。",
            ],
            3: [
                "第1屏：首屏主视觉页。",
                "第2屏：核心卖点页，从真实输入里选一个最强卖点展开。",
                "第3屏：收口页，做场景适配或选择理由总结。",
            ],
            4: [
                "第1屏：首屏主视觉页。",
                "第2屏：核心卖点页。",
                "第3屏：局部细节页，只能写产品图可见的部位或材质。",
                "第4屏：收口页。",
            ],
            5: [
                "第1屏：首屏主视觉页。",
                "第2屏：核心卖点页。",
                "第3屏：第二卖点页，不能与上一屏重复同一功能。",
                "第4屏：参数/尺寸/结构信息页，只能用真实参数。",
                "第5屏：收口页。",
            ],
            6: [
                "第1屏：首屏主视觉页。",
                "第2屏：核心卖点页。",
                "第3屏：第二卖点页。",
                "第4屏：局部细节/材质页。",
                "第5屏：场景适配页，但仍保持参考图同一审美体系。",
                "第6屏：收口页。",
            ],
            7: [
                "第1屏：首屏主视觉页。",
                "第2屏：核心卖点页。",
                "第3屏：第二卖点页。",
                "第4屏：局部细节/材质页。",
                "第5屏：参数/尺寸/结构信息页。",
                "第6屏：多视角汇总页；只有1张产品图时可以重复同一主体做裁切/镜像/局部。",
                "第7屏：收口页。",
            ],
            8: [
                "第1屏：首屏主视觉页。",
                "第2屏：核心卖点页。",
                "第3屏：第二卖点页。",
                "第4屏：局部细节/材质页。",
                "第5屏：参数/尺寸/结构信息页。",
                "第6屏：场景适配页，但不能脱离参考图的色调和版式家族。",
                "第7屏：多视角/亮点汇总页；只有1张产品图时只能复用同一主体做不同构图。",
                "第8屏：最终收口页，承担购买引导、信任感或总结性文案。",
            ],
        }
        default_plan = chinese_plan_map.get(max(1, min(8, batch_count)), chinese_plan_map[8])
        if language != "中文":
            return default_plan

        plan = list(default_plan)
        if product_image_count <= 1:
            plan.append("补充约束：本次只有1张产品图，禁止发明额外 SKU、额外配件、多人场景或产品未出现的结构。")
        return plan

    def _build_reference_mode_designer_system_prompt(self, language: str, batch_count: int) -> str:
        """参考模式默认系统提示词：让模型担任详情页提示词设计师。"""
        if language == "English":
            return f"""You are an e-commerce detail-page prompt designer.

Your job is to design exactly {batch_count} ready-to-render detail-page prompts based on:
- uploaded product image(s)
- product name / audience / specs / selling points
- one reference image that provides only the visual style DNA

Hard rules:
- The reference image only transfers palette, background mood, typography hierarchy, layout rhythm, whitespace, frame feeling, and text-to-subject relationship.
- Never transfer reference product facts, product category facts, copy text, parameters, or functional claims from the reference.
- Never invent features, certifications, angles, weights, materials, footrests, adjustable structures, or performance numbers unless they are explicitly provided in the inputs or clearly visible in the product image.
- Output exactly {batch_count} standalone prompts, one prompt per line.
- No numbering, no markdown, no explanations, no skeleton DSL, no JSON.
- Each line must be a complete prompt paragraph that can be sent directly to an image model.
- The {batch_count} prompts must belong to the same reference-inspired visual family, not {batch_count} unrelated styles.
- Keep the prompts aesthetically suitable for e-commerce detail pages."""
        return f"""你是电商详情页提示词设计师。

你的任务是根据：
- 上传的产品图
- 产品名称 / 目标人群 / 产品参数 / 卖点
- 1 张只提供视觉风格的参考图

设计出严格等于 {batch_count} 条、可直接用于出图的详情页 prompt。

硬性规则：
- 参考图只负责迁移颜色、背景气质、排版层级、留白、边框/画框感、标题区位置、主体摆位、字体气质、图文关系。
- 严禁迁移参考图里的商品事实、标题原文、品类词、功能点、参数、认证、场景故事。
- 严禁发明输入里没有提供的功能、结构、认证、角度、数值、配件、脚踏、人体姿势、多人场景。
- 只允许使用用户真实输入的信息，以及产品图里肉眼可见的结构和材质。
- 你输出的不是方案说明，而是最终 prompt 列表。
- 严格输出 {batch_count} 条 prompt，每条单独一行。
- 不要编号，不要 Markdown，不要 JSON，不要骨架 DSL，不要任何解释文字。
- 每条都必须是完整可出图的 prompt 段落。
- 这 {batch_count} 条 prompt 必须属于同一个参考图审美家族，不是 {batch_count} 种完全不同风格。
- 要符合电商详情页审美，可以润色文案，但不能越权杜撰事实。"""

    def _build_reference_mode_designer_user_prompt(
        self,
        product_info: str,
        language: str,
        product_image_count: int,
        batch_count: int,
        platform: str,
    ) -> str:
        """参考模式单阶段设计师用户提示词。"""
        screen_plan = self._build_reference_mode_screen_plan(batch_count, product_image_count, language)
        screen_plan_text = "\n".join(screen_plan)
        return f"""【工作模式】
详情页 prompt 设计模式

【语言】
{language}

【平台】
{platform or '淘宝'}

【图片说明】
前 {product_image_count} 张是产品图，最后 1 张是参考图。

【产品信息】
{product_info}

【你必须如何理解参考图】
1. 只学习它的颜色体系、背景质感、排版气质、留白比例、标题区位置、边框/画框感、主体摆位、整体审美。
2. 不要照搬参考图里的产品、标题、功能、卖点、家具类型或故事。
3. 如果参考图是法式、暖米色、墙板、画框式海报排版，你要把这种视觉语言迁移到当前产品，而不是把“法式雕花扶手椅”的内容迁移过来。

【你必须如何使用产品信息】
1. 只允许使用产品名称、目标人群、产品参数、卖点，以及产品图可见特征。
2. 未写明的功能、认证、承重、角度、脚踏、3D 扶手、SGS 等信息，禁止自行补写。
3. 单张产品图时，只能复用同一产品做全景、局部、裁切、镜像、排版重组，不得凭空出现别的产品或多人复杂场景。

【本次需要设计的屏位任务】
{screen_plan_text}

【输出规范】
1. 严格输出 {batch_count} 条最终 prompt。
2. 每条 prompt 独占一行，不要空行，不要编号，不要项目符号。
3. 每条 prompt 都要包含：画面风格、背景、主体摆位、版式关系、文案气质、文案位置。
4. 文案要像电商详情页设计师写的，精炼、有审美、可出图。
5. 不要输出任何解释或前后缀。"""

    def _build_reference_mode_generation_overlay(self, language: str, batch_count: int) -> str:
        """给 style-only 系统提示词追加参考模式专用的动态骨架规则。"""
        if language == "English":
            return f"""

## Reference Skeleton Runtime Overlay

- You are now in dynamic reference-skeleton mode, not fixed 8-screen skill mode.
- Respect the provided template lines s1..s{batch_count} exactly. Output exactly {batch_count} prompt lines.
- Do not pad to 8 screens and do not merge into fewer screens.
- Each screen must preserve visible differences in camera, layout, text relation, or module function.
- Treat the reference image only as visual skeleton evidence. Product facts must come from the uploaded product images and product info."""
        if language == "日本語":
            return f"""

## 参照骨格ランタイム補足

- 現在は固定8画面の skill モードではなく、動的な参照骨格モードです。
- 与えられた s1..s{batch_count} をそのまま実行し、必ず {batch_count} 行を出力してください。
- 8画面に補完したり、より少ない画面数に統合したりしないでください。
- 各画面は camera、layout、text relation、module function の差異を保ってください。
- 参照画像は視覚骨格の根拠としてのみ使い、商品事実は商品画像と product info を優先してください。"""
        if language == "한국어":
            return f"""

## 참고 골격 런타임 보강 규칙

- 현재는 고정 8스크린 skill 모드가 아니라 동적 참고 골격 모드입니다.
- 제공된 s1..s{batch_count} 템플릿을 그대로 따르고 반드시 {batch_count}줄을 출력하세요.
- 8스크린으로 보정하거나 더 적은 화면으로 합치지 마세요.
- 각 화면은 camera, layout, text relation, module function 차이를 유지해야 합니다.
- 참고 이미지는 시각 골격 근거로만 사용하고, 상품 사실은 업로드된 상품 이미지와 product info를 우선하세요。"""
        return f"""

## 参考骨架运行补充规则

- 你现在运行在“动态参考骨架模式”，不是固定 8 屏的 skill 模式。
- 严格执行提供的 s1..s{batch_count} 骨架行，只输出 {batch_count} 行最终 prompt。
- 不要补齐成 8 屏，也不要合并成更少屏。
- 每一屏都必须保留 camera、layout、text relation 或 module function 的可见差异。
- 参考图只作为视觉骨架来源，商品事实一律以产品图和 product info 为准。"""

    def _build_reference_mode_template_header(self, language: str) -> List[str]:
        """构建动态骨架模板头部。"""
        label_map = {
            "English": "reference skeleton",
            "日本語": "参照骨格",
            "한국어": "참고 골격",
            "中文": "参考页动态骨架",
        }
        label = label_map.get(language, "参考页动态骨架")
        return [
            "sv=style_only_v3",
            f"cn={label}",
            "pd={{product}}",
            "pi={{product_info}}",
            "sp={{selling_points}}",
            "pf={{platform}}",
            "lg={{language}}",
            "bc={{batch_count}}",
            "arch=skeleton-only",
            "brain=system-prompt-only",
        ]

    def _get_reference_mode_slot_hint(self, copy_role: str, language: str) -> str:
        """根据 copy_role 返回多语言的简短 slot 提示。"""
        mapping = {
            "hero-benefit": {
                "中文": "主标题与核心利益点",
                "English": "main headline and key benefit",
                "日本語": "主見出しと核となる利点",
                "한국어": "메인 헤드라인과 핵심 이점",
            },
            "hero-feature": {
                "中文": "主视觉标题与核心特征",
                "English": "hero title and core feature",
                "日本語": "主ビジュアル見出しと主特徴",
                "한국어": "메인 비주얼 제목과 핵심 특징",
            },
            "feature-callout": {
                "中文": "卖点标注与功能说明",
                "English": "feature labels and callouts",
                "日本語": "特徴ラベルと機能説明",
                "한국어": "특징 라벨과 기능 설명",
            },
            "scene-note": {
                "中文": "场景氛围与使用感受",
                "English": "scene mood and usage feel",
                "日本語": "シーン雰囲気と使用感",
                "한국어": "장면 분위기와 사용감",
            },
            "material-note": {
                "中文": "材质细节与触感说明",
                "English": "material detail and texture note",
                "日本語": "素材ディテールと質感説明",
                "한국어": "소재 디테일과 질감 설명",
            },
            "comfort-proof": {
                "中文": "结构支撑与体验说明",
                "English": "support structure and comfort note",
                "日本語": "構造サポートと体感説明",
                "한국어": "구조 지지와 체감 설명",
            },
            "proof-data": {
                "中文": "结构证据与说明信息",
                "English": "proof point and evidence note",
                "日本語": "根拠情報と証明要素",
                "한국어": "증거 정보와 설명 포인트",
            },
            "choice-recap": {
                "中文": "总结收口与选择理由",
                "English": "closing recap and choice reason",
                "日本語": "締めまとめと選ぶ理由",
                "한국어": "마무리 요약과 선택 이유",
            },
        }
        pack = mapping.get(copy_role, mapping["hero-feature"])
        return pack.get(language, pack["中文"])

    def _get_reference_mode_default_screen_fields(self, idx: int, batch_count: int, language: str) -> Dict[str, str]:
        """为缺失或不规范的 screen line 提供兜底字段。"""
        base_presets = [
            {
                "kind": "hero-opening",
                "bg": "styled-gradient-opening",
                "camera": "partial-or-angled-product-teaser",
                "layout": "top-copy_bottom-subject",
                "subject": "one-dominant-product-teaser",
                "accent": "opening-light-ribbon",
                "text_mode": "strong",
                "text_zone": "top-left",
                "text_align": "left",
                "text_density": "two-line",
                "copy_role": "hero-benefit",
                "negative": "plain-white-packshot",
            },
            {
                "kind": "scene-hero",
                "bg": "reference-led-main-scene",
                "camera": "front-or-three-quarter-hero-view",
                "layout": "top-title_bottom-hero-subject",
                "subject": "single-dominant-product",
                "accent": "reference-style-lighting",
                "text_mode": "strong",
                "text_zone": "top-center",
                "text_align": "center",
                "text_density": "two-line",
                "copy_role": "hero-feature",
                "negative": "headline-only",
            },
            {
                "kind": "detail-grid",
                "bg": "clean-detail-board",
                "camera": "multi-panel-feature-view",
                "layout": "top-title_bottom-grid",
                "subject": "product-feature-breakdown",
                "accent": "detail-crops-and-callouts",
                "text_mode": "strong",
                "text_zone": "top-left_and_grid",
                "text_align": "left",
                "text_density": "caption-grid",
                "copy_role": "feature-callout",
                "negative": "single-image-only",
            },
            {
                "kind": "evidence-panel",
                "bg": "technical-explainer-panel",
                "camera": "structure-or-side-view",
                "layout": "top-title_bottom-explainer",
                "subject": "support-structure-overview",
                "accent": "callout-lines-and-insets",
                "text_mode": "strong",
                "text_zone": "top-left",
                "text_align": "left",
                "text_density": "short-paragraph",
                "copy_role": "comfort-proof",
                "negative": "single-centered-packshot",
            },
            {
                "kind": "macro-closeup",
                "bg": "neutral-texture-stage",
                "camera": "tight-material-closeup",
                "layout": "top-copy_bottom-closeup",
                "subject": "material-or-contact-detail",
                "accent": "micro-texture-and-badges",
                "text_mode": "strong",
                "text_zone": "top-right",
                "text_align": "right",
                "text_density": "short-paragraph",
                "copy_role": "material-note",
                "negative": "single-image-only",
            },
            {
                "kind": "scene-collage",
                "bg": "reference-led-scene-collage",
                "camera": "full-product-in-scene",
                "layout": "top-title_bottom-scene",
                "subject": "product-in-usage-scene",
                "accent": "ambient-props-and-lighting",
                "text_mode": "strong",
                "text_zone": "top-left",
                "text_align": "left",
                "text_density": "two-line",
                "copy_role": "scene-note",
                "negative": "single-centered-packshot",
            },
            {
                "kind": "compare-proof",
                "bg": "clean-proof-layout",
                "camera": "multi-view-compare-board",
                "layout": "top-title_middle-main_bottom-secondary",
                "subject": "structure-and-choice-overview",
                "accent": "labels-pointers-and-compare-cards",
                "text_mode": "strong",
                "text_zone": "top-center_and_bottom-cards",
                "text_align": "center",
                "text_density": "data-callout",
                "copy_role": "proof-data",
                "negative": "no-compare-layout",
            },
            {
                "kind": "choice-closure",
                "bg": "bright-reference-finish",
                "camera": "final-hero-or-usage-view",
                "layout": "top-title_side-copy_bottom-subject",
                "subject": "final-product-choice-scene",
                "accent": "closing-light-and-props",
                "text_mode": "strong",
                "text_zone": "top-right",
                "text_align": "right",
                "text_density": "short-paragraph",
                "copy_role": "choice-recap",
                "negative": "headline-only",
            },
        ]

        extra_cycle = [
            {
                "kind": "detail-breakdown",
                "bg": "structured-detail-panel",
                "camera": "cropped-feature-explainer",
                "layout": "left-copy_right-feature",
                "subject": "product-structure-detail",
                "accent": "feature-markers",
                "text_mode": "strong",
                "text_zone": "left-column",
                "text_align": "left",
                "text_density": "list",
                "copy_role": "feature-callout",
                "negative": "single-image-only",
            },
            {
                "kind": "macro-proof",
                "bg": "clean-macro-evidence",
                "camera": "extreme-closeup-with-inset",
                "layout": "top-copy_bottom-macro",
                "subject": "texture-or-contact-proof",
                "accent": "micro-badges",
                "text_mode": "strong",
                "text_zone": "top-left",
                "text_align": "left",
                "text_density": "short-paragraph",
                "copy_role": "material-note",
                "negative": "full-packshot-only",
            },
            {
                "kind": "lifestyle-scene",
                "bg": "soft-usage-atmosphere",
                "camera": "wide-or-three-quarter-scene",
                "layout": "top-copy_bottom-scene",
                "subject": "product-in-lifestyle-setup",
                "accent": "scene-props",
                "text_mode": "weak",
                "text_zone": "top-left",
                "text_align": "left",
                "text_density": "two-line",
                "copy_role": "scene-note",
                "negative": "single-centered-packshot",
            },
            {
                "kind": "closure-recap",
                "bg": "clean-summary-board",
                "camera": "hero-plus-secondary-view",
                "layout": "top-title_bottom-summary",
                "subject": "product-summary-overview",
                "accent": "summary-labels",
                "text_mode": "strong",
                "text_zone": "top-center",
                "text_align": "center",
                "text_density": "short-paragraph",
                "copy_role": "choice-recap",
                "negative": "headline-only",
            },
        ]

        if batch_count <= len(base_presets):
            if batch_count == 1:
                preset = base_presets[1]
            else:
                mapped_idx = round((idx - 1) * (len(base_presets) - 1) / (batch_count - 1))
                preset = base_presets[mapped_idx]
        else:
            if idx <= len(base_presets):
                preset = base_presets[idx - 1]
            else:
                preset = extra_cycle[(idx - len(base_presets) - 1) % len(extra_cycle)]

        fields = dict(preset)
        fields["slot"] = self._get_reference_mode_slot_hint(fields["copy_role"], language)
        return fields

    def _sanitize_reference_screen_line(self, line: str, idx: int, batch_count: int, language: str) -> str:
        """将抽取结果中的 screen line 规范化为稳定的 DSL 行。"""
        cleaned = str(line or "").strip().strip("`").strip()
        cleaned = re.sub(r"^[\-\*\d\.\)\s]+", "", cleaned)
        defaults = self._get_reference_mode_default_screen_fields(idx, batch_count, language)
        allowed_copy_roles = {
            "hero-benefit",
            "hero-feature",
            "feature-callout",
            "scene-note",
            "material-note",
            "comfort-proof",
            "proof-data",
            "choice-recap",
        }

        parts = [part.strip() for part in cleaned.split("|") if part.strip()]
        kv_pairs: Dict[str, str] = {}
        for part in parts[1:]:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'").strip()
            value = value.replace("|", "/")
            value = re.sub(r"\s+", " ", value)
            if value:
                kv_pairs[key] = value

        for key in ("text_mode", "text_align", "copy_role"):
            if key in kv_pairs:
                kv_pairs[key] = kv_pairs[key].strip()

        if kv_pairs.get("text_mode") not in {"strong", "weak", "placeholder"}:
            kv_pairs["text_mode"] = defaults["text_mode"]
        if kv_pairs.get("text_align") not in {"left", "center", "right"}:
            kv_pairs["text_align"] = defaults["text_align"]
        if kv_pairs.get("copy_role") not in allowed_copy_roles:
            kv_pairs["copy_role"] = defaults["copy_role"]
        if not kv_pairs.get("slot"):
            kv_pairs["slot"] = self._get_reference_mode_slot_hint(kv_pairs["copy_role"], language)

        fields = dict(defaults)
        fields.update(kv_pairs)
        ordered_keys = [
            "kind", "bg", "camera", "layout", "subject", "accent",
            "text_mode", "text_zone", "text_align", "text_density",
            "copy_role", "slot", "negative"
        ]
        field_str = "|".join(f"{key}={fields[key]}" for key in ordered_keys)
        return f"s{idx}|{field_str}"

    def _build_reference_mode_template_from_response(self, raw_text: str, batch_count: int, language: str) -> str:
        """从第一阶段响应中抽取动态骨架模板。"""
        text = str(raw_text or "").replace("\r\n", "\n").strip()
        if not text:
            return ""

        block_match = re.search(r"BEGIN_TEMPLATE\s*(.*?)\s*END_TEMPLATE", text, re.IGNORECASE | re.DOTALL)
        candidate = block_match.group(1) if block_match else text
        candidate = candidate.strip().strip("`").strip()

        screen_map: Dict[int, str] = {}

        for raw_line in candidate.splitlines():
            line = raw_line.strip().strip("`").strip()
            if not line:
                continue
            screen_match = re.match(r"^s(\d+)\|", line)
            if screen_match:
                screen_idx = int(screen_match.group(1))
                if 1 <= screen_idx <= batch_count and screen_idx not in screen_map:
                    screen_map[screen_idx] = self._sanitize_reference_screen_line(
                        line, screen_idx, batch_count, language
                    )

        header_lines = []
        for default_line in self._build_reference_mode_template_header(language):
            if default_line.startswith("bc="):
                header_lines.append(f"bc={batch_count}")
            else:
                header_lines.append(default_line)

        if not screen_map:
            return ""

        screen_lines = []
        for idx in range(1, batch_count + 1):
            if idx in screen_map:
                screen_lines.append(screen_map[idx])
            else:
                screen_lines.append(
                    self._sanitize_reference_screen_line(
                        f"s{idx}|",
                        idx,
                        batch_count,
                        language,
                    )
                )

        return "\n".join(header_lines + screen_lines)

    def _build_reference_mode_generation_user_prompt(
        self,
        dynamic_template: str,
        product_info: str,
        language: str,
        product_image_count: int,
        batch_count: int,
    ) -> str:
        """构建参考模式第二阶段：根据动态骨架生成最终 prompt。"""
        return f"""【语言要求】
最终输出必须严格使用：{language}

【产品信息】
{product_info}

【图片说明】
前 {product_image_count} 张图片是产品图，最后 1 张图片是详情页参考图。

【动态骨架模板】
{dynamic_template}

【执行任务】
1. 严格按照上面的 s1 到 s{batch_count} 顺序生成最终 prompt
2. 每一行对应一屏，总共只输出 {batch_count} 行
3. 继承参考图的版式节奏、镜头关系、图文关系和模块组织
4. 商品事实只能来自产品图和产品信息，严禁复用参考商品文案或参数
5. 不要输出任何模板字段名、解释文字、序号、BEGIN_TEMPLATE、END_TEMPLATE 或 s1| 这类 DSL 内容

请直接输出 {batch_count} 行独立的最终 prompt。"""

    def _split_reference_mode_prompts(self, response_text: str) -> List[str]:
        """将参考模式最终响应切成干净的 prompt 列表。"""
        text = str(response_text or "").replace("\r\n", "\n").strip()
        chunks = []
        if "\n\n" in text:
            chunks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        else:
            chunks = [line.strip() for line in text.splitlines() if line.strip()]

        lines = []
        for raw_line in chunks:
            line = raw_line.strip()
            if not line:
                continue
            if line.upper() in {"BEGIN_TEMPLATE", "END_TEMPLATE"}:
                continue
            if re.match(r"^(sv|cn|pd|pi|sp|pf|lg|bc|arch|brain)=", line):
                continue
            if re.match(r"^s\d+\|", line):
                continue
            line = re.sub(r"^\d+[\.\)、\s]+", "", line).strip()
            if line:
                lines.append(line)
        return lines

    def _run_reference_mode_legacy(
        self,
        llm_config: Dict[str, Any],
        product_images: List["PILImage.Image"],
        reference_pil: "PILImage.Image",
        product_info: str,
        effective_language: str,
        platform: str,
        batch_count: int,
        custom_system_prompt: str = "",
    ) -> Tuple[Optional[str], str]:
        """参考模式旧逻辑兜底：直接分析参考页并输出 prompt。"""
        if custom_system_prompt and custom_system_prompt.strip():
            final_system_prompt = self._inject_prompt_variables(custom_system_prompt.strip(), {
                "language": effective_language,
                "platform": platform or "淘宝",
                "product_info": product_info,
                "batch_count": batch_count,
            })
        else:
            final_system_prompt = REFERENCE_MODE_LEGACY_SYSTEM_PROMPT_TEMPLATE.format(
                language=effective_language,
                platform=platform or "淘宝",
                product_info=product_info,
                batch_count=batch_count,
            )

        user_prompt = f"""【语言要求】
最终输出必须严格使用：{effective_language}

【产品信息】
{product_info}

【任务说明】
前{len(product_images)}张图片是产品图，最后1张是详情页参考图。

请分析参考图的以下设计要素：
1. 构图布局：页面结构、图片位置、留白处理
2. 排版风格：文字区域分布、标题样式、信息层级
3. 视觉风格：配色方案、光影效果、整体调性
4. 结构模块：包含哪些功能区块

然后结合产品特点，生成{batch_count}条AI绘图提示词，
体现参考图的设计风格，但适配当前产品。

请生成{batch_count}行独立的提示词，每行一个完整的prompt。"""

        response_text = self._call_llm_reference_mode(
            llm_config,
            final_system_prompt,
            user_prompt,
            product_images + [reference_pil],
        )
        return response_text, user_prompt

    def _process_reference_mode(
        self,
        llm_config: Dict[str, Any],
        product_images: List["PILImage.Image"],
        reference_pil: "PILImage.Image",
        product_info: str,
        effective_language: str,
        platform: str,
        batch_count: int,
        custom_reference_system_prompt: str = "",
    ) -> Tuple[List[str], str]:
        """参考模式：单阶段生成纯净的详情页 prompt 列表。"""
        if custom_reference_system_prompt and custom_reference_system_prompt.strip():
            final_system_prompt = self._inject_prompt_variables(
                custom_reference_system_prompt.strip(),
                {
                    "language": effective_language,
                    "platform": platform or "淘宝",
                    "product_info": product_info,
                    "batch_count": batch_count,
                    "product_image_count": len(product_images),
                },
            )
        else:
            final_system_prompt = self._build_reference_mode_designer_system_prompt(
                effective_language,
                batch_count,
            )

        final_user_prompt = self._build_reference_mode_designer_user_prompt(
            product_info,
            effective_language,
            len(product_images),
            batch_count,
            platform,
        )

        response_text = self._call_llm_reference_mode(
            llm_config,
            final_system_prompt,
            final_user_prompt,
            product_images + [reference_pil],
        )
        if response_text is None:
            return (["API调用失败"], "请检查网络或API Key")

        lines = self._split_reference_mode_prompts(response_text)
        if not lines:
            print("[Ecommerce_Skill_Router] [WARN] 设计师模式未解析出有效 prompt，回退到旧版参考模式")
            legacy_response, _ = self._run_reference_mode_legacy(
                llm_config=llm_config,
                product_images=product_images,
                reference_pil=reference_pil,
                product_info=product_info,
                effective_language=effective_language,
                platform=platform,
                batch_count=batch_count,
                custom_system_prompt=custom_reference_system_prompt,
            )
            if legacy_response is None:
                return (["API调用失败"], "请检查网络或API Key")
            legacy_lines = self._split_reference_mode_prompts(legacy_response)
            return (legacy_lines, "\n".join(legacy_lines))

        if len(lines) > batch_count:
            lines = lines[:batch_count]
        if len(lines) < batch_count:
            print(f"[Ecommerce_Skill_Router] [WARN] 设计师模式返回 {len(lines)} 条，少于目标 {batch_count} 条，回退到旧版参考模式")
            legacy_response, _ = self._run_reference_mode_legacy(
                llm_config=llm_config,
                product_images=product_images,
                reference_pil=reference_pil,
                product_info=product_info,
                effective_language=effective_language,
                platform=platform,
                batch_count=batch_count,
                custom_system_prompt=custom_reference_system_prompt,
            )
            if legacy_response is None:
                return (["API调用失败"], "请检查网络或API Key")
            legacy_lines = self._split_reference_mode_prompts(legacy_response)
            return (legacy_lines, "\n".join(legacy_lines))

        formatted_summary = "\n".join(lines)
        return (lines, formatted_summary)

    def process(self, 技能选择: str, LLM配置: Dict[str, Any],
                工作模式: str, 输出模式: str, 生图数量: int,
                产品图数量: int,
                关键词搜索: str = "",
                自定义技能目录: str = "",
                image1: Optional[torch.Tensor] = None,
                image2: Optional[torch.Tensor] = None,
                image3: Optional[torch.Tensor] = None,
                reference_image: Optional[torch.Tensor] = None,
                产品名称: str = "", 目标人群: str = "",
                产品参数: str = "", 卖点: str = "",
                平台: str = "", 语言: str = "",
                自定义模板: str = "",
                参考页系统提示词: str = "") -> Tuple[List[str], str]:
        
        if not DEPS_OK:
            return (["依赖缺失"], "请安装必要的Python库")

        try:
            # ===== 第0步：判断工作模式 =====
            selected_work_mode = (工作模式 or "").strip()
            if selected_work_mode == "技能模板模式":
                resolved_mode = "skill"
            elif selected_work_mode == "自定义模板模式":
                resolved_mode = "custom"
            elif selected_work_mode == "参考图模式":
                if reference_image is None:
                    return (["请提供参考图"], "工作模式已选择“参考图模式”，但未连接 reference_image")
                resolved_mode = "reference"
            else:
                return (["无效工作模式"], f"不支持的工作模式: {selected_work_mode}")
            is_reference_mode = (resolved_mode == "reference")
            
            # 限制产品图数量在1-3范围内
            产品图数量 = max(1, min(3, 产品图数量))

            # 语言策略：显式输入 > 自动检测 > 默认中文
            effective_language = self._resolve_effective_language(
                语言,
                关键词搜索,
                产品名称,
                目标人群,
                产品参数,
                卖点,
                平台,
                自定义模板,
                参考页系统提示词
            )
            print(f"[Ecommerce_Skill_Router] 语言解析: 输入='{语言}' -> 生效='{effective_language}'")
            print(f"[Ecommerce_Skill_Router] 工作模式: 输入='{工作模式}' -> 生效='{resolved_mode}'")
            
            # ===== 第1步：处理产品图片（根据数量选择）=====
            product_images = []
            if 产品图数量 >= 1 and image1 is not None:
                product_images.append(tensor_to_pil(image1))
            if 产品图数量 >= 2 and image2 is not None:
                product_images.append(tensor_to_pil(image2))
            if 产品图数量 >= 3 and image3 is not None:
                product_images.append(tensor_to_pil(image3))
            
            # 构建产品信息上下文
            context_parts = []
            if 产品名称:
                context_parts.append(f"产品名称: {产品名称}")
            if 目标人群:
                context_parts.append(f"目标人群: {目标人群}")
            if 产品参数:
                context_parts.append(f"产品参数: {产品参数}")
            if 卖点:
                context_parts.append(f"卖点: {卖点}")
            if 平台:
                context_parts.append(f"平台: {平台}")
            context_parts.append(f"语言: {effective_language}")
            
            product_context = "\n".join(context_parts) if context_parts else "请根据图片内容进行分析"
            product_info = product_context
            
            if is_reference_mode:
                # ==========================================
                # 详情页参考模式
                # ==========================================
                print(f"[Ecommerce_Skill_Router] 进入【详情页参考模式】产品图:{len(product_images)}张")
                
                # 处理参考图
                reference_pil = tensor_to_pil(reference_image)
                lines, formatted_summary = self._process_reference_mode(
                    llm_config=LLM配置,
                    product_images=product_images,
                    reference_pil=reference_pil,
                    product_info=product_info,
                    effective_language=effective_language,
                    platform=平台 or "淘宝",
                    batch_count=生图数量,
                    custom_reference_system_prompt=参考页系统提示词,
                )

                print(f"[Ecommerce_Skill_Router] 【详情页参考模式】成功生成 {len(lines)} 条提示词")
                return (lines, formatted_summary)
                
            else:
                # ==========================================
                # 非参考图模式：技能模板 / 自定义模板
                # ==========================================
                mode_title = "技能模板模式" if resolved_mode == "skill" else "自定义模板模式"
                print(f"[Ecommerce_Skill_Router] 进入【{mode_title}】")
                
                final_skill = 技能选择
                search_text = 关键词搜索.strip() if 关键词搜索 else ""

                # 只有技能模板模式才处理关键词搜索与技能匹配
                if resolved_mode == "skill" and search_text:
                    print(f"[SKILL 技能调用] 用户输入关键词: '{search_text}'")
                    print(f"[SKILL 技能调用] 默认选择技能: {final_skill}")
                    
                    # 先尝试触发词匹配
                    triggered_skill = search_skill_by_trigger(search_text)
                    if triggered_skill:
                        final_skill = triggered_skill
                        print(f"[SKILL 技能调用] OK 触发词匹配成功，切换到技能: {final_skill}")
                    else:
                        # 触发词未匹配，尝试常规关键词搜索
                        skills, _ = scan_skills_directory(force_refresh=True, custom_path=自定义技能目录)
                        for skill in skills:
                            if search_text.lower() in skill.lower():
                                final_skill = skill
                                print(f"[SKILL 技能调用] OK 关键词匹配成功，切换到技能: {final_skill}")
                                break
                        else:
                            print(f"[SKILL 技能调用] [WARN] 未找到匹配'{关键词搜索}'的技能，使用默认选择: {final_skill}")
                
                # 1. 构建产品信息上下文
                context_parts = []
                if 产品名称:
                    context_parts.append(f"产品名称: {产品名称}")
                if 目标人群:
                    context_parts.append(f"目标人群: {目标人群}")
                if 产品参数:
                    context_parts.append(f"产品参数: {产品参数}")
                if 卖点:
                    context_parts.append(f"卖点: {卖点}")
                if 平台:
                    context_parts.append(f"平台: {平台}")
                context_parts.append(f"语言: {effective_language}")
                
                product_context = "\n".join(context_parts) if context_parts else "请根据图片内容进行分析"
                
                # 2. 加载模板逻辑：根据解析后的工作模式决定
                if resolved_mode == "skill":
                    if final_skill == "<请选择技能>":
                        return (["请选择具体技能"], "当前处于“技能模板模式”，请先在“技能选择”里选择一个真实技能。")
                    # 检查是否选择了有效的技能
                    if final_skill == "<未找到技能文件>":
                        return (["未找到技能文件"], "请检查 skills 目录是否存在 yaml 技能文件，或切换到“自定义模板模式”")
                    
                    print("=" * 60)
                    print(f"[SKILL 技能调用] 最终使用技能: {final_skill}")
                    print("=" * 60)
                    
                    template = load_skill_template(final_skill, 自定义技能目录, 生图数量, effective_language)
                    if not template:
                        return (["技能模板加载失败"], f"无法加载技能 '{final_skill}'，请检查技能文件是否存在，或使用自定义模板")
                else:
                    if not 自定义模板 or not 自定义模板.strip():
                        return (["请提供自定义模板内容"], "关闭技能后必须填写自定义模板")
                    template = 自定义模板.strip()
                    print("=" * 60)
                    print("[SKILL 技能调用] 使用自定义模板模式（未使用技能文件）")
                    print("=" * 60)
                
                # 3. 构建最终提示词，明确告知LLM生成指定数量的提示词
                # 支持 {{var}} 和 {var} 两种格式，同时补充细粒度字段变量
                # 构建产品信息文本
                product_info_parts = []
                if 产品名称:
                    product_info_parts.append(f"产品名称: {产品名称}")
                if 目标人群:
                    product_info_parts.append(f"目标人群: {目标人群}")
                if 产品参数:
                    product_info_parts.append(f"产品参数: {产品参数}")
                if 卖点:
                    product_info_parts.append(f"卖点: {卖点}")
                if 平台:
                    product_info_parts.append(f"平台: {平台}")
                product_info_parts.append(f"语言: {effective_language}")
                product_info = "\n".join(product_info_parts) if product_info_parts else product_context

                product_runtime = 产品名称.strip() if 产品名称 and 产品名称.strip() else product_context.replace("\n", "；")

                runtime_vars = {
                    # 兼容旧模板
                    "platform": 平台 or "电商平台",
                    "selling_points": product_context,
                    "product_info": product_info,
                    "batch_count": 生图数量,
                    "language": effective_language,
                    "product": product_runtime,
                    # 细粒度英文变量
                    "product_name": 产品名称.strip(),
                    "target_audience": 目标人群.strip(),
                    "audience": 目标人群.strip(),
                    "product_params": 产品参数.strip(),
                    "product_specs": 产品参数.strip(),
                    "specs": 产品参数.strip(),
                    "selling_point_text": 卖点.strip(),
                    "selling_points_raw": 卖点.strip(),
                    "product_context": product_context,
                    "product_image_count": 产品图数量,
                    # 细粒度中文变量
                    "产品名称": 产品名称.strip(),
                    "目标人群": 目标人群.strip(),
                    "目标用户": 目标人群.strip(),
                    "产品参数": 产品参数.strip(),
                    "卖点": 卖点.strip(),
                    "卖点原文": 卖点.strip(),
                    "平台": 平台 or "电商平台",
                    "语言": effective_language,
                    "产品": product_runtime,
                    "产品信息": product_info,
                    "产品上下文": product_context,
                    "生成数量": 生图数量,
                    "产品图数量": 产品图数量,
                }
                final_prompt = self._inject_prompt_variables(template, runtime_vars)
                final_prompt += self._build_generation_line(effective_language, 生图数量)

                # 4. 处理图片（非参考图模式下只传产品图，不混入 reference_image）
                pil_images = []
                for img_tensor in [image1, image2, image3]:
                    if img_tensor is not None:
                        pil_images.append(tensor_to_pil(img_tensor))

                # 5. 调用 LLM (传递所有参数用于注入 system_prompt)
                response_text = self._call_llm(
                    LLM配置, final_prompt, pil_images,
                    language=effective_language,
                    platform=平台 or "淘宝",
                    product_info=product_info,
                    batch_count=生图数量
                )
                
                if response_text is None:
                    return (["API调用失败"], "请检查网络或API Key")

                # 6. 将文本按行切分为列表
                # 过滤掉空行，确保每一行都是一个独立的 Prompt
                lines = [line.strip() for line in response_text.split('\n') if line.strip()]
                
                # 完整的原始文本作为总结输出
                formatted_summary = response_text.strip()

                print(f"[Ecommerce_Skill_Router] 成功生成 {len(lines)} 条独立提示词")
                
                return (lines, formatted_summary)

        except Exception as e:
            traceback.print_exc()
            return ([f"错误: {str(e)}"], str(e))

    # ========================================
    # 动态系统提示词生成
    # ========================================
    def _build_system_prompt(self,
                             language: str = "",
                             base_prompt: str = "",
                             platform: str = "",
                             product_info: str = "",
                             batch_count: int = 4) -> str:
        """
        根据语言参数构建动态系统提示词
        
        Args:
            language: 目标语言 (中文/English/日本語/한국어/...)
            base_prompt: 用户在Universal_LLM_Config中设置的系统提示词
            platform: 平台
            product_info: 产品信息
            batch_count: 生成数量
        
        Returns:
            str: 组合后的系统提示词
        """
        # 语言指令映射
        language_instructions = {
            "中文": {
                "role": "你是一位电商视觉提示词专家",
                "instruction": "请使用中文输出所有内容",
                "requirement": "生成的提示词中所有文字内容必须使用中文，包括产品名称、卖点描述、标题区域等"
            },
            "English": {
                "role": "You are an expert in e-commerce visual prompt engineering",
                "instruction": "Please output all content in English",
                "requirement": "All text content in the generated prompts must be in English, including product names, selling points, title areas, etc."
            },
            "日本語": {
                "role": "あなたはEコマースビジュアルプロンプトの専門家です",
                "instruction": "すべてのコンテンツを日本語で出力してください",
                "requirement": "生成されたプロンプトのすべてのテキストコンテンツは日本語でなければなりません。製品名、セリングポイント、タイトルエリアなども含みます"
            },
            "한국어": {
                "role": "당신은 전자상거래 시각 프롬프트 전문가입니다",
                "instruction": "모든 콘텐츠를 한국어로 출력해주세요",
                "requirement": "생성된 프롬프트의 모든 텍스트 콘텐츠는 한국어여야 합니다. 제품명, 판매 포인트, 제목 영역 등도 포함됩니다"
            }
        }
        
        # 默认使用中文
        lang = self._normalize_language(language) or "中文"
        lang_config = language_instructions.get(lang, language_instructions["中文"])
        runtime_vars = {
            "language": lang,
            "platform": platform or "淘宝",
            "product_info": product_info or "",
            "batch_count": batch_count,
            "role": lang_config["role"],
            "instruction": lang_config["instruction"],
            "requirement": lang_config["requirement"],
        }
        
        # 基础系统提示词（从文件加载或使用默认）
        if base_prompt and base_prompt.strip():
            base = self._inject_prompt_variables(base_prompt.strip(), runtime_vars)
        else:
            # 优先读取更适配 style-only skeleton DSL 的系统提示词，再回退到旧默认文件
            from pathlib import Path
            current_dir = Path(__file__).parent.parent
            prompt_candidates = [
                current_dir / "default_system_prompt_skeleton_brain_split.md",
                current_dir / "default_system_prompt.md",
                current_dir / "prompts" / "default_system_prompt.md",
            ]
            prompt_file = next((p for p in prompt_candidates if p.exists()), None)
            if prompt_file is not None:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    template = f.read()
                base = self._inject_prompt_variables(template, runtime_vars)
            else:
                # 极简 fallback
                base = f"""{lang_config['role']}。{lang_config['instruction']}。{lang_config['requirement']}"""
        
        return base

    def _call_llm(self,
                  llm_config: Dict[str, Any],
                  user_prompt: str,
                  pil_images: List[PILImage.Image],
                  language: str = "中文",
                  platform: str = "淘宝",
                  product_info: str = "",
                  batch_count: int = 4) -> Optional[str]:
        """
        调用 LLM API
        
        Args:
            llm_config: LLM配置字典
            user_prompt: 用户提示词
            pil_images: PIL Image 列表
            language: 语言参数
            platform: 平台参数
            product_info: 产品信息
            batch_count: 生成数量
        
        Returns:
            Optional[str]: LLM响应文本，失败则返回 None
        """
        system_prompt = self._build_system_prompt(
            language=language,
            base_prompt=llm_config.get("system_prompt", ""),
            platform=platform,
            product_info=product_info,
            batch_count=batch_count,
        )

        # 构建消息
        messages = []
        messages.append({
            "role": "system",
            "content": system_prompt
        })

        content = []
        for pil_img in pil_images:
            base64_img = pil_to_base64(pil_img, "PNG")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_img}",
                    "detail": "high"
                }
            })

        content.append({
            "type": "text",
            "text": user_prompt
        })

        messages.append({
            "role": "user",
            "content": content
        })

        print(f"[Ecommerce_Skill_Router] 调用模型: {llm_config['model_name']}, 图片数: {len(pil_images)}")

        last_error = None
        for attempt in range(2):
            try:
                client = OpenAI(
                    base_url=llm_config["base_url"],
                    api_key=llm_config["api_key"],
                )
                response = client.chat.completions.create(
                    model=llm_config["model_name"],
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                )
                result = response.choices[0].message.content
                print(f"[Ecommerce_Skill_Router] API调用成功，响应长度: {len(result)} 字符")
                return result
            except Exception as e:
                last_error = e
                if attempt == 0:
                    print(f"[Ecommerce_Skill_Router] [WARN] LLM调用首次失败，准备自动重试: {type(e).__name__}: {e}")
                    continue

        print("=" * 60)
        print("[Ecommerce_Skill_Router] LLM API调用失败:")
        if last_error is not None:
            traceback.print_exception(type(last_error), last_error, last_error.__traceback__)
        print("=" * 60)
        return None

    def _call_llm_reference_mode(self, llm_config: Dict[str, Any],
                                  system_prompt: str,
                                  user_prompt: str,
                                  images: List) -> Optional[str]:
        """
        详情页参考模式专用LLM调用
        
        Args:
            llm_config: LLM配置
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            images: 图片列表（产品图 + 参考图）
        
        Returns:
            Optional[str]: LLM响应文本
        """
        messages = []
        messages.append({
            "role": "system",
            "content": system_prompt
        })

        content = []
        for pil_img in images:
            base64_img = pil_to_base64(pil_img, "PNG")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_img}",
                    "detail": "high"
                }
            })

        content.append({
            "type": "text",
            "text": user_prompt
        })

        messages.append({
            "role": "user",
            "content": content
        })

        print(f"[Ecommerce_Skill_Router] 调用模型 (参考模式): {llm_config['model_name']}")

        last_error = None
        for attempt in range(2):
            try:
                client = OpenAI(
                    base_url=llm_config["base_url"],
                    api_key=llm_config["api_key"],
                )
                response = client.chat.completions.create(
                    model=llm_config["model_name"],
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                )
                result = response.choices[0].message.content
                print(f"[Ecommerce_Skill_Router] API调用成功，响应长度: {len(result)} 字符")
                return result
            except Exception as e:
                last_error = e
                if attempt == 0:
                    print(f"[Ecommerce_Skill_Router] [WARN] 参考模式首次调用失败，准备自动重试: {type(e).__name__}: {e}")
                    continue

        print("=" * 60)
        print("[Ecommerce_Skill_Router] LLM API调用失败 (参考模式):")
        if last_error is not None:
            traceback.print_exception(type(last_error), last_error, last_error.__traceback__)
        print("=" * 60)
        return None


# ============================================
# 节点映射 (供ComfyUI加载使用)
# ============================================
NODE_CLASS_MAPPINGS = {
    "Universal_LLM_Config": Universal_LLM_Config,
    "Ecommerce_Skill_Router": Ecommerce_Skill_Router,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Universal_LLM_Config": "后来_通用LLM配置 (LLM Config)",
    "Ecommerce_Skill_Router": "后来_电商技能路由 (Skill Router)",
}

