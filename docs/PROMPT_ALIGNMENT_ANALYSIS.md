# 系统提示词与技能文件配合度分析报告

> 分析对象：[`prompts/default_system_prompt.md`](prompts/default_system_prompt.md) + [`skills/french_skirt.yaml`](skills/french_skirt.yaml)
> 分析时间：2026-02-21
> 分析目的：评估两者配合度，识别冲突点，提出优化建议

---

## 一、总体评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **架构设计配合** | ⭐⭐⭐⭐☆ (4/5) | 分层设计合理，但变量传递机制需明确 |
| **语言控制一致性** | ⭐⭐⭐⭐⭐ (5/5) | 两者都强调语言控制，逻辑一致 |
| **输出格式对齐** | ⭐⭐⭐☆☆ (3/5) | 存在明显冲突：系统要求多行提示词，技能模板要求单行 |
| **视觉元素协调** | ⭐⭐⭐⭐☆ (4/5) | 风格描述基本一致，但细节需统一 |
| **变量系统兼容** | ⭐⭐⭐⭐☆ (4/5) | 变量定义良好，但默认值覆盖机制待完善 |

**总体配合度：75/100** —— 可以工作，但需要优化解决冲突

---

## 二、详细分析

### 2.1 架构层级关系分析

```
┌─────────────────────────────────────────────────────────────┐
│                    【第一层】系统提示词                        │
│  (prompts/default_system_prompt.md)                          │
│  - 角色定义: 电商详情页视觉提示词生成专家                      │
│  - 通用规则: 语言控制、输出结构、质量检查                      │
│  - 变量占位: {role}, {instruction}, {{language}}            │
└─────────────────────────────────────────────────────────────┘
                              ↓ 注入
┌─────────────────────────────────────────────────────────────┐
│                    【第二层】技能模板                          │
│  (skills/french_skirt.yaml → template)                       │
│  - 专业角色: 法式女装视觉总监                                 │
│  - 场景定义: 法式半裙详情页8张图片规划                        │
│  - 风格规范: 色彩、字体、摄影、排版                          │
│  - 变量占位: {{platform}}, {{product_info}}, etc.            │
└─────────────────────────────────────────────────────────────┘
                              ↓ 注入
┌─────────────────────────────────────────────────────────────┐
│                    【第三层】图片提示词                        │
│  (shots → prompt_guide)                                      │
│  - 8个固定机位的具体提示词                                   │
│  - 纯英文提示词，含中文占位说明                               │
│  - 变量: {{clothing_item}}, {{fabric_type}}, etc.            │
└─────────────────────────────────────────────────────────────┘
```

**评估结论**：三层架构设计清晰，但层级之间的**变量作用域和覆盖规则**需要明确定义。

---

### 2.2 语言控制规则对比

#### ✅ 一致点（优秀配合）

| 系统提示词 | 技能模板 | 配合评价 |
|------------|----------|----------|
| `所有生成的提示词内容必须使用 {{language}} 输出` | `所有生成的提示词内容必须使用 {{language}} 输出` | ✅ 完全一致 |
| `场景描述：主体用英文（AI绘图模型优化），文字元素用 {{language}}` | 提示词guide全是英文主体描述 | ✅ 完全配合 |
| 禁止混合语言输出 | 模板中"French elegant style"等英文风格词 | ⚠️ 需明确允许保留的英文关键词 |

#### ⚠️ 冲突点

**冲突1：中文占位符的处理不一致**

系统提示词说：
```markdown
| 场景描述 | 主体用英文（AI绘图模型优化），文字元素用 {{language}} |
```

但技能文件中多处出现硬编码中文：
```yaml
"Fabric detail" elegant typography at top with Chinese subtitle tag
"Size info" elegant title with gray underline accent  
"Detail" elegant serif title with Chinese subtitle tag
measurement indicators with Chinese labels
Chinese column headers: 尺寸 腰围 臀围 裙长 推荐体重
```

**问题**：这些中文应该由系统根据 `{{language}}` 动态替换，但当前是硬编码。

**冲突2：输出格式要求矛盾**

| 来源 | 要求 | 冲突程度 |
|------|------|----------|
| 系统提示词 | "每行一条独立的英文提示词" "不要带序号" | 🔴 严重 |
| 系统提示词 | 要求包含"文字排版区域说明（title area...）" | 🟡 中等 |
| 技能模板 | 输出8张图片的提示词，包含文字区域 | 🟢 兼容 |
| 技能shots | prompt_guide已经是英文提示词 | 🟢 兼容 |

**核心矛盾**：系统提示词要求输出多条提示词，但技能模板只提供了一个整体模板。

---

### 2.3 视觉风格规范对比

#### ✅ 高度一致的区域

| 元素 | 系统提示词定义 | 技能文件定义 | 匹配度 |
|------|----------------|--------------|--------|
| 色彩基调 | 低饱和度、温暖中性色 | 低饱和度大地色系（米、咖、灰、蓝） | ✅ 95% |
| 光线风格 | soft lighting, natural light | 柔和漫射光，左前方45°主光 | ✅ 90% |
| 背景要求 | 简约无干扰 | 浅米色/纯白，简约无干扰 | ✅ 100% |
| 整体风格 | French style, elegant | French chic aesthetic, elegant | ✅ 95% |
| 构图比例 | aspect ratio（通用） | 9:16（竖版手机端优先） | ⚠️ 技能更具体 |

#### ⚠️ 需要统一的区域

**问题1：字体规范**
- 系统提示词：未提及具体字体
- 技能文件：明确定义了 Didot/Bodoni + 思源黑体/苹方

**建议**：系统提示词应补充字体规范作为通用要求。

**问题2：文字区域标注方式**
- 系统提示词：`text area for title in {{language}}`
- 技能文件：实际输出的是英文提示词，文字区域用英文描述

**建议**：统一文字区域的描述方式。

---

### 2.4 输出格式严重冲突

这是**最关键的冲突**：

#### 系统提示词的输出要求（第54-77行）

```markdown
## 【输出要求】

### 提示词结构
每条提示词必须包含以下要素：
1. **主体描述**：产品/模特/场景的核心描述
2. **文字排版区域**：明确标注标题区、卖点区、标签区位置
3. **构图布局**：layout, composition, aspect ratio
4. **光影效果**：lighting style, shadow, highlight
5. **风格修饰**：platform style, aesthetic keywords
6. **质量参数**：4K, high quality, professional photography
```

#### 技能模板的输出要求（第215-226行）

```markdown
【输出要求】
1. 每行一条独立的英文提示词
2. 不要带序号、不要加引号
3. 按上述图片顺序生成
4. 每条提示词必须包含:
   - 主体描述（模特/产品/场景）
   - 文字排版区域说明（title area, text space, label zone等）
   - 构图布局（layout, composition）
   - 光影和背景
   - 风格修饰词（French style, e-commerce, elegant等）
5. 强调"French elegant style""e-commerce detail page""text layout area"等关键词
6. 适合 Flux/Qwen 等绘图模型使用
```

#### 🔴 冲突分析

| 冲突点 | 系统要求 | 技能要求 | 严重程度 |
|--------|----------|----------|----------|
| 输出格式 | 结构化多段文本 | 单行英文提示词 | 🔴 严重 |
| 序号要求 | 未明确 | 不要带序号 | 🟢 一致 |
| 引号要求 | 未明确 | 不要加引号 | 🟡 需统一 |
| 提示词数量 | 根据batch_count | 固定8张 | 🔴 严重 |

**核心问题**：系统提示词期望输出的是"结构化报告"，而技能文件期望输出的是"纯提示词列表"。

---

## 三、优化建议

### 3.1 架构层面优化

#### 建议1：明确三层职责边界

```yaml
# 系统提示词职责（第一层）
- 定义通用角色和能力边界
- 规定语言控制规则（第一优先级）
- 提供通用输出格式框架
- 不做具体视觉风格规定

# 技能模板职责（第二层）  
- 定义专业领域角色（法式女装视觉总监）
- 提供场景化设计规范（色彩、字体、摄影）
- 生成图片规划方案
- 调用shots层获取具体提示词

# Shots职责（第三层）
- 提供纯英文AI绘图提示词
- 包含可替换变量占位符
- 不含任何自然语言指令
```

#### 建议2：统一变量命名规范

当前变量命名不一致：

| 系统提示词 | 技能文件 | 建议统一为 |
|------------|----------|------------|
| `{{language}}` | `{{language}}` | ✅ 保持一致 |
| `{role}` | - | 改为 `{{role}}` |
| `{instruction}` | - | 改为 `{{instruction}}` |
| - | `{{batch_count}}` | 系统层也使用 |
| - | `{{shot_plan}}` | 系统层支持注入 |

---

### 3.2 语言控制优化

#### 建议3：移除技能文件中的硬编码中文

**当前问题代码**（skills/french_skirt.yaml 第78行）：
```yaml
Chinese column headers: 尺寸 腰围 臀围 裙长 推荐体重
```

**优化方案**：
```yaml
# 改为变量占位
{{size_column_headers}}  # 根据language动态生成
```

#### 建议4：建立语言关键词映射表

在技能文件中增加语言关键词配置：

```yaml
# 在 skills/french_skirt.yaml 中添加
language_keywords:
  zh-CN:
    fabric_detail_title: "面料细节"
    size_info_title: "尺码信息"
    model_look_title: "模特试穿"
    detail_title: "细节展示"
    columns: ["尺寸", "腰围", "臀围", "裙长", "推荐体重"]
  
  en:
    fabric_detail_title: "Fabric Detail"
    size_info_title: "Size Information"
    model_look_title: "Model Reference"
    detail_title: "Details"
    columns: ["Size", "Waist", "Hip", "Length", "Weight"]
  
  ja:
    fabric_detail_title: "生地詳細"
    # ... 其他语言
```

---

### 3.3 输出格式优化

#### 建议5：分离"报告模式"和"提示词模式"

当前两者混在一起导致冲突。建议明确两种输出模式：

**模式A：详情页方案报告（默认）**
```markdown
## 法式半裙详情页视觉方案

### 图片 1/8：首屏主图
**构图思路**：模特半身展示，浅木色背景...
**提示词**：
```
E-commerce fashion hero banner, 9:16 vertical composition...
```
**文字区域规划**：
- 标题区：{{title_zh}}
- 副标题区：{{subtitle_zh}}

### 图片 2/8：面料细节
...
```

**模式B：纯提示词列表（API调用）**
```
E-commerce fashion hero banner, 9:16 vertical composition, model upper body shot...
Fabric texture close-up, macro photography of satin...
Fashion technical drawing, minimalist line illustration...
...
```

在系统提示词中增加模式选择变量：`{{output_mode}}`

---

### 3.4 具体文件修改建议

#### 修改1：系统提示词（default_system_prompt.md）

**第54-77行：增加输出模式区分**

```markdown
## 【输出要求】

### 输出模式
根据使用场景选择输出模式：
- **report**: 生成完整的详情页方案报告（含思路说明）
- **prompts**: 仅生成纯提示词列表（用于API调用）
当前模式: {{output_mode}}

### 提示词结构（适用于 report 和 prompts 模式）
每条提示词必须包含...
```

**第103-109行：增加语言关键词检查**

```markdown
## 【质量检查】

生成完成后，请自我检查：
- [ ] 所有文字元素是否都使用了 {{language}}？
- [ ] 标题、副标题、标签、按钮是否都已本地化？
- [ ] 是否与用户指定的语言完全一致？
- [ ] 是否保持了专业的电商视觉风格？
- [ ] **是否将技能模板中的硬编码文字替换为 {{language}} 版本？**
```

#### 修改2：技能文件（french_skirt.yaml）

**第59行、72行、96行、108行、158行**：
移除所有硬编码的 "Chinese" 描述，改为语言变量。

```yaml
# 修改前
"Fabric detail" elegant typography at top with Chinese subtitle tag
measurement indicators with Chinese labels
"Detail" elegant serif title with Chinese subtitle tag
"Model look" elegant title with rounded tag subtitle

# 修改后
"{{fabric_detail_title}}" elegant typography at top with {{language}} subtitle tag
measurement indicators with {{language}} labels
"{{detail_title}}" elegant serif title with {{language}} subtitle tag
"{{model_look_title}}" elegant title with rounded tag subtitle
```

**第168-180行（template）**：
明确 shots 的调用机制。

```yaml
template: |
  【角色设定】
  你是一位资深法式女装视觉总监...

  【任务】
  请为上述法式半裙产品生成 **{{batch_count}}** 个AI绘图提示词...

  【图片规划】
  {{shot_plan}}
  
  【生图提示词】
  根据上述规划，生成以下提示词：
  {{#each selected_shots}}
  {{this.prompt_guide}}
  {{/each}}
```

---

## 四、配合流程优化图

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 系统层：default_system_prompt.md                             │
│ 1. 注入 {role}, {instruction}, {{language}}                 │
│ 2. 确定输出模式（report/prompts）                           │
│ 3. 加载对应的 skill.yaml                                    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 技能层：french_skirt.yaml                                    │
│ 1. 注入法式半裙专业规范                                      │
│ 2. 根据 batch_count 选择 shots                              │
│ 3. 替换语言关键词（从 language_keywords 表）                 │
│ 4. 组装 shot_plan                                           │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Shots层：prompt_guide × N                                    │
│ 1. 替换变量：{{clothing_item}}, {{fabric_type}}...          │
│ 2. 输出纯英文AI绘图提示词                                    │
│ 3. 保持 {{language}} 文字区域描述                           │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
输出（根据 output_mode）
  ├─ report: 结构化报告 + 提示词
  └─ prompts: 纯提示词列表
```

---

## 五、优先级建议

| 优先级 | 问题 | 影响 | 建议行动 |
|--------|------|------|----------|
| 🔴 P0 | 输出格式冲突 | 导致LLM输出混乱 | **立即修复** |
| 🔴 P0 | 硬编码中文 | 违背语言控制规则 | **立即修复** |
| 🟡 P1 | 变量命名不一致 | 可能导致注入失败 | 建议修复 |
| 🟡 P1 | 缺少语言关键词表 | 翻译质量不稳定 | 建议补充 |
| 🟢 P2 | 缺少输出模式选择 | 灵活性不足 | 可选优化 |
| 🟢 P2 | 系统层缺少字体规范 | 风格统一性弱 | 可选补充 |

---

## 六、结论

### 当前状态
系统提示词和技能文件**基本架构合理，可以配合使用**，但存在**关键冲突**需要解决：

1. ✅ **语言控制理念一致** — 两者都强调语言变量的重要性
2. ⚠️ **输出格式存在冲突** — 系统要结构化报告，技能要纯提示词
3. 🔴 **硬编码中文违规** — 技能文件中多处违反语言控制规则

### 优化后预期效果
修复上述问题后，系统将能够：
- 根据产品图自动分析并匹配法式半裙技能
- 生成符合目标语言要求的8张详情页提示词
- 保持法式优雅风格的视觉一致性
- 灵活切换"报告模式"和"API模式"

### 建议的修改顺序
1. **首先**修复 `french_skirt.yaml` 中的硬编码中文
2. **然后**在系统提示词中增加 `{{output_mode}}` 区分
3. **最后**统一变量命名规范

---

*报告完成。如需我协助实施具体修改，请告知。*
