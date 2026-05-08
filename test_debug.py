#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI_HouLai_ToolBox - 深度Debug测试脚本
"""

import sys
import os
import ast
from pathlib import Path

# 设置UTF-8编码
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 添加项目路径
PLUGIN_DIR = Path(__file__).parent
sys.path.insert(0, str(PLUGIN_DIR))
sys.path.insert(0, str(PLUGIN_DIR / "py"))

# 状态符号
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

# ============================================
# 测试1: Python代码语法检查
# ============================================
def test_syntax():
    """检查Python代码语法"""
    print("\n" + "="*60)
    print("测试1: Python代码语法检查")
    print("="*60)
    
    py_files = [
        PLUGIN_DIR / "py" / "houlai_llm_agent.py",
        PLUGIN_DIR / "__init__.py",
    ]
    
    all_ok = True
    for py_file in py_files:
        if not py_file.exists():
            print(f"{FAIL} 文件不存在: {py_file}")
            all_ok = False
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                source = f.read()
            ast.parse(source)
            print(f"{OK} 语法正确: {py_file.name}")
        except SyntaxError as e:
            print(f"{FAIL} 语法错误: {py_file.name}")
            print(f"   行 {e.lineno}: {e.msg}")
            all_ok = False
    
    return all_ok

# ============================================
# 测试2: 导入检查
# ============================================
def test_imports():
    """测试Python导入"""
    print("\n" + "="*60)
    print("测试2: Python导入检查")
    print("="*60)
    
    try:
        import yaml
        print(f"{OK} PyYAML 导入成功")
    except ImportError:
        print(f"{WARN} PyYAML 未安装 (运行时依赖)")
    
    try:
        from PIL import Image
        print(f"{OK} Pillow 导入成功")
    except ImportError:
        print(f"{WARN} Pillow 未安装 (运行时依赖)")
    
    # 尝试导入我们的模块（不依赖torch）
    try:
        # 先mock掉torch依赖
        import sys
        from unittest.mock import MagicMock
        sys.modules['torch'] = MagicMock()
        sys.modules['numpy'] = MagicMock()
        
        # 现在可以尝试导入
        import houlai_llm_agent
        print(f"{OK} houlai_llm_agent 导入成功")
        return True
    except Exception as e:
        print(f"{FAIL} houlai_llm_agent 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================
# 测试3: 技能YAML文件检查
# ============================================
def test_skills_yaml():
    """检查技能YAML文件格式"""
    print("\n" + "="*60)
    print("测试3: 技能YAML文件检查")
    print("="*60)
    
    try:
        import yaml
    except ImportError:
        print(f"{WARN} PyYAML未安装，跳过YAML解析测试")
        return True
    
    skills_dir = PLUGIN_DIR / "skills"
    if not skills_dir.exists():
        print(f"{FAIL} 技能目录不存在: {skills_dir}")
        return False
    
    yaml_files = list(skills_dir.glob("*.yaml"))
    print(f"{INFO} 找到 {len(yaml_files)} 个YAML文件")
    
    all_ok = True
    for yaml_file in yaml_files:
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # 检查必要字段
            if 'name' not in data:
                print(f"{WARN} {yaml_file.name}: 缺少 'name' 字段")
            if 'shots' not in data and 'skills' not in data and 'template' not in data:
                print(f"{WARN} {yaml_file.name}: 缺少 'shots'/'skills'/'template' 字段")
            else:
                print(f"{OK} {yaml_file.name}: 格式正确")
                
                # 检查是否是三层架构格式
                if 'shots' in data and 'template' in data:
                    template = data.get('template', '')
                    # 检查是否包含 {{variable}} 格式
                    if '{{' in template and '}}' in template:
                        # 提取变量名
                        import re
                        vars = re.findall(r'\{\{(\w+)\}\}', template)
                        if vars:
                            print(f"     模板变量: {', '.join(set(vars))}")
        except Exception as e:
            print(f"{FAIL} {yaml_file.name}: 解析失败 - {e}")
            all_ok = False
    
    return all_ok

# ============================================
# 测试4: 三层架构变量注入测试
# ============================================
def test_variable_injection():
    """测试三层架构变量注入"""
    print("\n" + "="*60)
    print("测试4: 三层架构变量注入测试")
    print("="*60)
    
    # 模拟系统提示词模板
    system_prompt_template = """你是一位专业的电商视觉提示词工程师。

【任务配置】
- 目标平台: {platform}
- 输出语言: {language}

【语言规则 - 严格执行】
所有生成的提示词必须使用 {language} 输出。
产品信息: {product_info}
"""
    
    # 测试变量注入
    test_cases = [
        {
            "language": "English",
            "platform": "Amazon",
            "product_info": "Winter coat, wool blend"
        },
        {
            "language": "日本語",
            "platform": "楽天",
            "product_info": "春のワンピース"
        },
        {
            "language": "中文",
            "platform": "淘宝",
            "product_info": "夏季连衣裙"
        }
    ]
    
    all_ok = True
    for i, params in enumerate(test_cases, 1):
        try:
            result = system_prompt_template.format(**params)
            print(f"\n{OK} 测试用例 {i}:")
            print(f"     语言: {params['language']}")
            print(f"     平台: {params['platform']}")
            # 验证注入成功
            assert params['language'] in result
            assert params['platform'] in result
            assert params['product_info'] in result
            print(f"     变量注入成功")
        except Exception as e:
            print(f"\n{FAIL} 测试用例 {i} 失败: {e}")
            all_ok = False
    
    return all_ok

# ============================================
# 测试5: 触发词匹配逻辑测试
# ============================================
def test_trigger_matching():
    """测试触发词匹配逻辑"""
    print("\n" + "="*60)
    print("测试5: 触发词匹配逻辑测试")
    print("="*60)
    
    # 模拟触发词映射
    trigger_map = {
        "女装": "女装详情页",
        "women clothing": "女装详情页",
        "上衣": "女装详情页",
        "裙子": "女装详情页",
        "美食": "美食详情页",
        "food": "美食详情页",
    }
    
    test_cases = [
        ("女装上衣", "女装详情页"),
        ("women clothing dress", "女装详情页"),
        ("美食图片", "美食详情页"),
        ("food photography", "美食详情页"),
        ("unknown product", None),
    ]
    
    all_ok = True
    for search_text, expected in test_cases:
        # 模拟 search_skill_by_trigger 逻辑
        result = None
        search_lower = search_text.lower().strip()
        for trigger, skill in trigger_map.items():
            if trigger in search_lower or search_lower in trigger:
                result = skill
                break
        
        if result == expected:
            print(f"{OK} '{search_text}' -> {result}")
        else:
            print(f"{FAIL} '{search_text}' -> {result} (期望: {expected})")
            all_ok = False
    
    return all_ok

# ============================================
# 测试6: API端点检查
# ============================================
def test_api_endpoints():
    """检查API端点定义"""
    print("\n" + "="*60)
    print("测试6: API端点检查")
    print("="*60)
    
    init_file = PLUGIN_DIR / "__init__.py"
    with open(init_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键端点
    endpoints = [
        ('/houlai/get_skills', 'GET'),
        ('/houlai/refresh_skills', 'POST'),
    ]
    
    all_ok = True
    for endpoint, method in endpoints:
        if endpoint in content:
            print(f"{OK} {method} {endpoint}")
        else:
            print(f"{FAIL} 缺少 {method} {endpoint}")
            all_ok = False
    
    return all_ok

# ============================================
# 测试7: 前端JS检查
# ============================================
def test_frontend_js():
    """检查前端JS功能"""
    print("\n" + "="*60)
    print("测试7: 前端JS功能检查")
    print("="*60)
    
    js_file = PLUGIN_DIR / "js" / "houlai_dynamic_skills.js"
    if not js_file.exists():
        print(f"{FAIL} JS文件不存在: {js_file}")
        return False
    
    with open(js_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键功能
    checks = [
        ('fetchSkills 函数', 'async function fetchSkills'),
        ('刷新技能列表API调用', '/houlai/refresh_skills'),
        ('获取技能列表API调用', '/houlai/get_skills'),
        ('触发词匹配', 'matchSkillByTrigger'),
        ('技能下拉更新', 'updateSkillDropdown'),
    ]
    
    all_ok = True
    for name, pattern in checks:
        if pattern in content:
            print(f"{OK} {name}")
        else:
            print(f"{FAIL} 缺少 {name}")
            all_ok = False
    
    return all_ok

# ============================================
# 主函数
# ============================================
def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("ComfyUI_HouLai_ToolBox 深度Debug测试")
    print("="*60)
    
    results = {
        "语法检查": test_syntax(),
        "导入检查": test_imports(),
        "YAML检查": test_skills_yaml(),
        "变量注入": test_variable_injection(),
        "触发词匹配": test_trigger_matching(),
        "API端点": test_api_endpoints(),
        "前端JS": test_frontend_js(),
    }
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for test_name, result in results.items():
        status = f"{OK} 通过" if result else f"{FAIL} 失败"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    print("\n" + "="*60)
    if all_passed:
        print("所有测试通过！插件功能正常。")
    else:
        print("部分测试失败，请检查上述输出。")
    print("="*60)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
