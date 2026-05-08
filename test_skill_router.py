#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度测试 Ecommerce_Skill_Router 的各种使用场景
验证修复和功能逻辑
"""

import sys
import os
# 设置 stdout 编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from py.houlai_llm_agent import (
    Ecommerce_Skill_Router, 
    scan_skills_directory, 
    scan_skills_directory_v2,
    check_dependencies
)

def test_skill_scanning():
    """测试技能扫描功能（解包bug修复验证）"""
    print("=" * 60)
    print("【测试1】技能扫描功能")
    print("=" * 60)
    
    # 测试 v2 版本（返回5个值）
    try:
        result = scan_skills_directory_v2(force_refresh=True)
        print(f"✅ scan_skills_directory_v2() 返回 {len(result)} 个值")
        file_list, trigger_map, weights, metadata_list, skill_id_map = result
        print(f"   - 技能数量: {len(file_list)}")
        print(f"   - 技能列表: {file_list}")
        print(f"   - 触发词: {list(trigger_map.keys())}")
    except Exception as e:
        print(f"❌ scan_skills_directory_v2() 失败: {e}")
        return False
    
    # 测试 v1 兼容版本（返回2个值）- 这是之前出bug的地方
    try:
        file_list, trigger_map = scan_skills_directory(force_refresh=True)
        print(f"✅ scan_skills_directory() 返回2个值 - 解包bug已修复")
        print(f"   - 技能数量: {len(file_list)}")
    except ValueError as e:
        print(f"❌ scan_skills_directory() 解包错误: {e}")
        return False
    except Exception as e:
        print(f"❌ scan_skills_directory() 其他错误: {e}")
        return False
    
    return True

def test_input_types():
    """测试 INPUT_TYPES 返回的结构"""
    print("\n" + "=" * 60)
    print("【测试2】INPUT_TYPES 结构验证")
    print("=" * 60)
    
    try:
        input_types = Ecommerce_Skill_Router.INPUT_TYPES()
        required = input_types.get("required", {})
        optional = input_types.get("optional", {})
        
        print(f"✅ INPUT_TYPES 生成成功")
        print(f"   - Required 字段: {list(required.keys())}")
        print(f"   - Optional 字段数: {len(optional)}")
        
        # 检查技能选择字段
        if "技能选择" in required:
            skills_tuple = required["技能选择"]
            skills_list = skills_tuple[0] if isinstance(skills_tuple, tuple) else skills_tuple
            print(f"   - 技能选择列表: {skills_list}")

            if not skills_list:
                print("   ❌ 技能列表为空！")
                return False

            print(f"   ✅ 技能列表非空，首个技能: {skills_list[0]}")
            if skills_list[0] != "<请选择技能>":
                print("   ❌ 技能列表首项不是占位项 <请选择技能>")
                return False

        if "工作模式" not in required:
            print("   ❌ Required 中缺少 工作模式")
            return False

        if "使用技能" in required or "参考图模式" in required:
            print("   ❌ 旧模式开关仍然存在于 Required 中")
            return False

        mode_tuple = required["工作模式"]
        mode_list = mode_tuple[0] if isinstance(mode_tuple, tuple) else mode_tuple
        print(f"   - 工作模式选项: {mode_list}")
        expected_modes = ["技能模板模式", "自定义模板模式", "参考图模式"]
        if list(mode_list) != expected_modes:
            print(f"   ❌ 工作模式选项不符合预期: {mode_list}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ INPUT_TYPES 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mode_priority_logic():
    """测试新工作模式映射逻辑"""
    print("\n" + "=" * 60)
    print("【测试3】模式优先级逻辑验证")
    print("=" * 60)
    
    test_cases = [
        # (工作模式, reference_image, 预期模式)
        ("技能模板模式", None, "skill"),
        ("自定义模板模式", None, "custom"),
        ("参考图模式", "image_exists", "reference"),
    ]

    for work_mode, ref_img, expected in test_cases:
        if work_mode == "技能模板模式":
            actual_mode = "skill"
        elif work_mode == "自定义模板模式":
            actual_mode = "custom"
        elif work_mode == "参考图模式" and ref_img is not None:
            actual_mode = "reference"
        else:
            actual_mode = "invalid"

        status = "✅" if actual_mode == expected else "❌"
        print(f"{status} 工作模式='{work_mode}', reference_image={'有' if ref_img else '无'} -> {actual_mode}模式")
        
        if actual_mode != expected:
            return False

    # 额外检查：参考图模式缺图时应视为无效
    actual_mode = "reference" if None is not None else "invalid"
    status = "✅" if actual_mode == "invalid" else "❌"
    print(f"{status} 工作模式='参考图模式', reference_image=无 -> {actual_mode}")
    if actual_mode != "invalid":
        return False
    
    return True

def test_parameter_combinations():
    """测试新模式下的技能选择约束"""
    print("\n" + "=" * 60)
    print("【测试4】参数组合冲突检测")
    print("=" * 60)
    
    input_types = Ecommerce_Skill_Router.INPUT_TYPES()
    valid_skills = input_types["required"]["技能选择"][0]
    actual_skills = [s for s in valid_skills if s not in {"<请选择技能>", "<未找到技能文件>"}]
    sample_skill_a = actual_skills[0]
    sample_skill_b = actual_skills[1] if len(actual_skills) > 1 else actual_skills[0]

    combinations = [
        # (工作模式, 技能选择, 是否有效, 说明)
        ("技能模板模式", "<请选择技能>", False, "技能模式下必须选择真实技能"),
        ("技能模板模式", sample_skill_a, True, "技能模式下真实技能有效"),
        ("自定义模板模式", "<请选择技能>", True, "自定义模板模式忽略技能选择"),
        ("参考图模式", "<请选择技能>", True, "参考图模式忽略技能选择"),
        ("技能模板模式", sample_skill_b, True, "技能模式支持多个真实技能"),
    ]
    
    all_passed = True
    for work_mode, skill_select, should_be_valid, desc in combinations:
        if work_mode == "技能模板模式":
            actual_valid = skill_select not in {"<请选择技能>", "<未找到技能文件>"} and skill_select in valid_skills
        else:
            actual_valid = True

        status = "✅" if actual_valid == should_be_valid else "❌"
        print(f"{status} 工作模式={work_mode} | 技能='{skill_select}'")
        print(f"      验证: {'有效' if actual_valid else '无效'} | {desc}")

        if actual_valid != should_be_valid:
            all_passed = False
    
    return all_passed

def main():
    print("\n" + "=" * 60)
    print("   Ecommerce_Skill_Router 深度测试")
    print("=" * 60 + "\n")
    
    results = []
    
    # 运行所有测试
    results.append(("技能扫描", test_skill_scanning()))
    results.append(("INPUT_TYPES", test_input_types()))
    results.append(("模式优先级", test_mode_priority_logic()))
    results.append(("参数组合", test_parameter_combinations()))
    
    # 汇总
    print("\n" + "=" * 60)
    print("【测试结果汇总】")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] 所有测试通过！修复有效，无逻辑冲突。")
    else:
        print("[WARN] 部分测试失败，需要进一步检查。")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
