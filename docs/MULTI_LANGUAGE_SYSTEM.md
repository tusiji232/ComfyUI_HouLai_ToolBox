# 多语言支持系统文档

## 概述

本系统实现了动态多语言支持，允许用户通过"语言"参数控制 LLM 技能路由器的输出语言。支持中文、英文、日文、韩文等多种语言。

## 核心机制

### 1. 双层语言控制

系统通过两个层面确保语言一致性：

#### A. 动态系统提示词 (System Prompt)

在 `houlai_llm_agent.py` 中，`_build_system_prompt()` 方法根据用户指定的语言动态生成系统提示词：

```python
def _build_system_prompt(self, language: str = "", base_prompt: str = "") -> str:
    # 语言指令映射
    language_instructions = {
        "中文": {
            "role": "你是一位电商视觉提示词专家",
            "instruction": "请使用中文输出所有内容",
            ...
        },
        "english": {
            "role": "You are an expert E-commerce Visual Prompt Engineer",
            "instruction": "You MUST output ALL content in English ONLY",
            ...
        },
        "日本語": {...},
        "한국어": {...}
    }
```

#### B. Skill 模板语言指令

每个 Skill YAML 文件中的模板都包含语言变量 `{{language}}`：

```yaml
template: |
  【语言要求】
  用户指定的输出语言是: {{language}}
  - 所有生成的提示词内容必须使用 {{language}} 输出
  - 如果图片中有文字，请将其含义转换为 {{language}} 的等价表达
```

### 2. 变量传递流程

```
用户输入语言参数 (如 "English")
          ↓
Ecommerce_Skill_Router.process()
          ↓
替换 {{language}} 变量到 Skill 模板
          ↓
构建动态系统提示词 (_build_system_prompt)
          ↓
调用 LLM API (携带语言参数)
          ↓
LLM 按指定语言生成提示词
```

## 支持的变量

### Skill 模板变量

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `{{platform}}` | 目标平台 | 淘宝, Amazon, 京东 |
| `{{language}}` | 输出语言 | 中文, English, 日本語, 한국어 |
| `{{product_info}}` | 产品信息汇总 | 产品名称: xxx\n卖点: xxx |
| `{{batch_count}}` | 生图数量 | 4 |

### 语言参数支持格式

系统支持灵活的语言参数输入：

| 用户输入 | 识别结果 | 说明 |
|----------|----------|------|
| "English" / "english" / "英文" / "en" | English | 英文输出 |
| "中文" / "Chinese" / "zh" | 中文 | 中文输出（默认） |
| "日本語" / "Japanese" / "jp" / "日本" | 日本語 | 日文输出 |
| "한국어" / "Korean" / "ko" / "韩国" | 한국어 | 韩文输出 |

## 使用示例

### 1. 中文输出（默认）

```yaml
# Skill Router 节点参数
语言: "中文"
平台: "淘宝"

# 生成的系统提示词（部分）
你是一位电商视觉提示词专家。
【语言要求】请使用中文输出所有内容
```

### 2. 英文输出

```yaml
# Skill Router 节点参数
语言: "English"
平台: "Amazon"

# 生成的系统提示词（部分）
You are an expert E-commerce Visual Prompt Engineer.
【语言要求】You MUST output ALL content in English ONLY
```

### 3. 日文输出

```yaml
# Skill Router 节点参数
语言: "日本語"
平台: "Amazon Japan"

# 生成的系统提示词（部分）
あなたはEコマースビジュアルプロンプトの専門家です
【语言要求】すべての内容を日本語で出力してください
```

## 图片文字处理

当用户上传包含文字的产品图片时，系统会：

1. **识别图片内容**：LLM 分析图片中的产品特征和文字
2. **语言转换**：将图片中的文字含义转换为目标语言的等价表达
3. **统一输出**：所有生成的提示词使用用户指定的语言

### 示例转换

| 图片中的文字 | 中文输出 | 英文输出 | 日文输出 |
|-------------|----------|----------|----------|
| 萌犬刺绣加绒连帽卫衣 | 萌犬刺绣加绒连帽卫衣 | cute dog embroidered fleece-lined hoodie | かわいい犬刺繍フリースパーカー |
| 可爱刺绣 \| 舒适加绒 | 可爱刺绣 \| 舒适加绒 | cute embroidery \| comfortable fleece | かわいい刺繍 \| 快適なフリース |

## 配置建议

### Universal_LLM_Config 节点

系统提示词可以保持为空或简单设置，因为动态系统提示词会自动覆盖并增强：

```python
# 推荐设置
system_prompt: ""  # 留空，使用系统默认动态提示词

# 或添加自定义指令
system_prompt: "专注于生成高质量的电商详情页图片提示词"
```

### Ecommerce_Skill_Router 节点

```python
# 必需参数
语言: "English"  # 根据目标市场设置
平台: "Amazon"   # 根据销售平台设置

# 可选参数
图片1-4: [上传产品图片]
产品名称: "Hoodie Sweatshirt"
卖点: "cute embroidery, comfortable fleece lining"
```

## 故障排查

### 问题：输出仍然是中英混合

**原因**：
1. LLM 看到中文 Skill 模板后未正确遵循语言指令
2. 图片中的中文文字被直接复制

**解决**：
1. 确保"语言"参数正确填写（如 "English"）
2. 检查 `_build_system_prompt` 是否被调用
3. 查看 LLM 调用日志中的 system prompt 内容

### 问题：语言参数未生效

**检查点**：
1. 确认 `{{language}}` 变量已在 Skill YAML 中定义
2. 确认 `houlai_llm_agent.py` 中已添加 `{{language}}` 替换逻辑
3. 确认 `_call_llm` 方法接收并使用了 language 参数

## 扩展更多语言

要添加新的语言支持，修改 `houlai_llm_agent.py` 中的 `language_instructions` 字典：

```python
language_instructions = {
    # 现有语言...
    "Français": {
        "role": "Vous êtes un expert en ingénierie visuelle e-commerce",
        "instruction": "Veuillez produire tout le contenu en français",
        "requirement": "Tout le texte généré doit être en français..."
    },
    "Deutsch": {
        "role": "Sie sind ein E-Commerce-Visual-Prompt-Experte",
        "instruction": "Bitte geben Sie alle Inhalte auf Deutsch aus",
        "requirement": "Alle generierten Texte müssen auf Deutsch sein..."
    }
}
```

## 版本历史

- **v3.2**: 添加动态多语言系统提示词支持
- **v3.1**: 支持 `{{language}}` 变量替换
- **v3.0**: 基础 Skill 系统架构
