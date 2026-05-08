# 三层架构设计文档

## 架构概述

系统采用**三层架构**设计，实现关注点分离和高度可配置性：

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: Universal_LLM_Config (LLM Config 节点)                   │
│  ─────────────────────────────────────────────────────────────      │
│  职责: 定义基础规则 (大脑)                                           │
│  输入: system_prompt (可包含 {language}, {platform}, {product_info}) │
│  特点: 一处定义，全局生效；可随时修改系统行为                          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ llm_config (携带 system_prompt)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: Ecommerce_Skill_Router (Skill Router 节点)               │
│  ─────────────────────────────────────────────────────────────      │
│  职责: 收集用户输入参数                                               │
│  输入: 语言、平台、产品名称、卖点、参数、图片(1-4张)                   │
│  加载: Skill YAML 模板 (仅含场景描述，不含语言逻辑)                    │
│  输出: 将所有参数传递给 _call_llm                                     │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ prompt + images + language + platform + product_info
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: _call_llm (内部方法)                                      │
│  ─────────────────────────────────────────────────────────────      │
│  职责: 变量注入与API调用                                              │
│  逻辑:                                                              │
│   1. 获取 Layer 1 的 system_prompt (可能含变量)                      │
│   2. 获取 Layer 2 的参数 (language, platform, product_info)          │
│   3. 注入变量: system_prompt.format(language=..., platform=...)      │
│   4. 调用 LLM API                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## 三层职责详解

### Layer 1: Universal_LLM_Config (基础规则层)

**定位**: AI 的"大脑"，定义全局行为规则

**配置位置**: `system_prompt` 字段

**支持变量**:
- `{language}` - 由 Skill Router 的"语言"参数注入
- `{platform}` - 由 Skill Router 的"平台"参数注入
- `{product_info}` - 由 Skill Router 的各项产品参数汇总注入

**示例配置**:

```markdown
你是一位专业的电商视觉提示词工程师。

【当前任务配置】
- 目标平台: {platform}
- 输出语言: {language}
- 产品信息: {product_info}

【语言规则 - 严格执行】
所有生成的提示词必须使用 {language} 输出。
如果图片中包含其他语言的文字，请将其含义转换为 {language} 的等价表达。

【核心任务】
分析用户上传的产品图片（1-4张），结合 Skill 模板的场景规划，生成电商详情页用的AI绘图提示词。

【输出要求】
1. 每行一条独立的完整提示词
2. 包含产品主体描述、文字排版区域说明、构图光影、风格修饰词
3. 适合 Flux/Qwen 等绘图模型使用

【重要】
生成的提示词中所有文字内容都必须是 {language}，严禁混合其他语言。
```

**如果留空**: 使用系统默认的 `DEFAULT_SYSTEM_PROMPT_TEMPLATE`

### Layer 2: Ecommerce_Skill_Router (参数收集层)

**定位**: 用户输入的"收集器"，纯数据传递

**收集的参数**:
- `语言` → 注入到 `{language}`
- `平台` → 注入到 `{platform}`
- `产品名称`/`目标人群`/`产品参数`/`卖点` → 汇总注入到 `{product_info}`
- `图片1-4` → 多模态输入

**加载 Skill 模板**:
- 仅包含场景描述（shots）和基础任务描述
- **不包含**语言相关的逻辑（因为语言控制在 Layer 1）
- 示例 Skill 模板:

```yaml
template: |
  【任务】
  请为女装产品生成 {{batch_count}} 个电商详情页图片的AI绘图提示词。
  
  【产品信息】
  {{product_info}}
  
  【场景规划】
  按顺序生成以下 {{batch_count}} 张图片的提示词：
  {{shot_plan}}
  
  【设计要求】
  1. 文字排版：预留清晰的标题区、卖点区、参数区
  2. 参数表格：尺码表要有表格线条、S/M/L/XL列
  3. 整体风格：简约现代、留白充足、9:16竖版
  
  【输出规范】
  1. 每行一条独立的提示词
  2. 包含：主体描述、文字排版区域说明、构图光影
```

### Layer 3: _call_llm (变量注入层)

**定位**: 连接 Layer 1 和 Layer 2 的"桥梁"

**核心逻辑**:

```python
def _call_llm(self, llm_config, prompt, images, language, platform, product_info):
    # Layer 1: 获取基础 system_prompt
    base_system_prompt = llm_config.get("system_prompt", "")
    
    # 如果用户未设置，使用默认模板
    if not base_system_prompt.strip():
        base_system_prompt = DEFAULT_SYSTEM_PROMPT_TEMPLATE
    
    # Layer 3: 注入变量
    final_system_prompt = base_system_prompt.format(
        language=language,
        platform=platform,
        product_info=product_info
    )
    
    # 调用 LLM API
    messages = [
        {"role": "system", "content": final_system_prompt},
        {"role": "user", "content": [images..., prompt]}
    ]
    return call_llm_api(messages)
```

## 优势对比

### 传统方式（修改前）

| 问题 | 说明 |
|------|------|
| 重复配置 | 每个 Skill YAML 都要包含语言逻辑 |
| 修改困难 | 50个 Skill 文件需要修改50次 |
| 不一致 | 不同 Skill 的语言规则可能不一致 |
| 冗余代码 | 大量重复的 `{{language}}` 替换逻辑 |

### 三层架构（修改后）

| 优势 | 说明 |
|------|------|
| 单一配置 | 语言规则只在 Layer 1 (system_prompt) 定义一次 |
| 易于修改 | 修改一处，影响所有 Skill |
| 一致性 | 所有 Skill 使用相同的语言控制逻辑 |
| Skill 精简 | Skill YAML 只关注场景描述，无语言逻辑 |
| 可扩展 | 添加新 Skill 无需考虑语言问题 |

## 使用示例

### 示例 1: 英文输出 (Amazon)

**Layer 1 (Universal_LLM_Config)**:
```markdown
You are an expert E-commerce Visual Prompt Engineer.

【Configuration】
- Platform: {platform}
- Language: {language}

【Rules】
You MUST output ALL content in {language} ONLY.
If images contain text in other languages, translate the meaning to {language}.
...
```

**Layer 2 (Skill Router)**:
- 语言: `English`
- 平台: `Amazon`
- 产品名称: `Hoodie Sweatshirt`

**注入后的 System Prompt**:
```markdown
You are an expert E-commerce Visual Prompt Engineer.

【Configuration】
- Platform: Amazon
- Language: English

【Rules】
You MUST output ALL content in English ONLY...
```

### 示例 2: 日文输出 (乐天)

**Layer 1**:
```markdown
あなたはEコマースビジュアルプロンプトの専門家です。

【設定】
- プラットフォーム: {platform}
- 言語: {language}

【ルール】
すべての出力は{language}で行ってください...
```

**Layer 2**:
- 语言: `日本語`
- 平台: `楽天`

**注入结果**:
- 所有提示词都是日文
- 图片中的中文被翻译成日文

### 示例 3: 留空使用默认

**Layer 1**: `system_prompt` 留空

**系统自动使用**:
```python
DEFAULT_SYSTEM_PROMPT_TEMPLATE = """
你是一位专业的电商视觉提示词工程师...
所有生成的提示词必须使用 {language} 输出...
"""
```

## 扩展更多语言

要支持新语言，**只需修改 Layer 1** 的 system_prompt:

### 法语示例

**Layer 1 (system_prompt)**:
```markdown
Vous êtes un expert en ingénierie visuelle e-commerce.

【Configuration】
- Plateforme: {platform}
- Langue: {language}

【Règles】
Vous DEVEZ produire tout le contenu en {language} UNIQUEMENT.
Si les images contiennent du texte dans d'autres langues,
traduisez le sens vers {language}.
...
```

**Layer 2**: 语言填 `Français`

**结果**: 所有输出都是法语

## 故障排查

### 问题: 输出仍然是中文

**排查步骤**:
1. 检查 Layer 1 (LLM Config) 的 `system_prompt` 是否包含语言规则
2. 检查 Layer 2 (Skill Router) 的"语言"参数是否正确填写
3. 查看日志中 "System Prompt 已生成" 的输出来确认变量注入是否正确

### 问题: 变量未被替换

**排查步骤**:
1. 确认 `system_prompt` 中使用的是 `{language}` 而不是 `{{language}}`
2. 确认使用的是单大括号 `{}` 格式（Python str.format）
3. 检查日志中的最终 system prompt 内容

## 最佳实践

1. **Layer 1 配置建议**:
   - 定义清晰的语言规则
   - 说明平台特点（淘宝/Amazon风格差异）
   - 明确输出格式要求

2. **Layer 2 使用建议**:
   - 保持 Skill YAML 简洁，只描述场景
   - 不要在 Skill 中添加语言相关逻辑
   - 充分利用 shots 定义图片规划

3. **扩展 Skill**:
   - 复制简化版模板
   - 修改 shots 场景描述
   - 无需考虑语言问题
