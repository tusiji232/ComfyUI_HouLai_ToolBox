# 后来工具箱 - 技能文件格式 v2.0 规范

## 版本信息

- **版本**: 2.0
- **更新日期**: 2026-02-18
- **兼容**: 向后兼容 v1.0 格式

## 主要改进

1. ✅ **YAML 元数据增强** - 支持 version、author、compatible_models
2. ✅ **变量语法统一** - 支持 `{{var}}` 和 `{var}` 两种格式
3. ✅ **分类层级** - 支持分目录存储（beauty/、digital/）
4. ✅ **标签权重系统** - 支持带权重的触发词匹配

---

## 文件结构

### 目录组织

```
skills/
├── _index.yaml              # 技能库索引（全局配置）
├── _template.yaml           # 技能模板示例
├── beauty/                  # 美妆分类目录
│   ├── lipstick.yaml       # 口红技能集合
│   ├── skincare.yaml       # 护肤技能集合
│   └── perfume.yaml        # 香水技能集合
├── digital/                 # 数码分类目录
│   ├── phone.yaml          # 手机技能集合
│   └── earphone.yaml       # 耳机技能集合
└── ...                     # 其他分类
```

---

## 索引文件格式

### `_index.yaml`

```yaml
# 技能库元数据
library:
  name: "后来工具箱技能库"
  version: "2.0"
  description: "电商产品AI绘图提示词技能库"
  author: "HouLai"
  updated_at: "2026-02-18"
  
  # 支持的模型
  compatible_models:
    - "gpt-4o"
    - "doubao-vision"
    - "deepseek-chat"
  
  # 默认配置
  defaults:
    platform: "小红书"
    batch_count: 4
    temperature: 0.7

# 分类索引
categories:
  - id: "beauty"
    name: "美妆"
    icon: "💄"
    path: "beauty/"
    tags: ["美妆", "beauty", "makeup"]
  
  - id: "digital"
    name: "数码"
    icon: "📱"
    path: "digital/"
    tags: ["数码", "digital", "3c"]

# 全局标签权重配置
tag_weights:
  product: 1.0      # 产品名称标签
  category: 0.8     # 分类标签
  style: 0.6        # 风格标签

# 变量类型定义
variable_types:
  platform:
    type: "select"
    options: ["小红书", "淘宝", "京东", "Amazon"]
    default: "小红书"
```

---

## 技能文件格式

### 新格式 v2.0（推荐）

```yaml
# ============================================
# 分类-产品技能集合
# ============================================

category: "分类/子分类"
description: "该技能文件的描述"
version: "2.0"
author: "作者名"
updated_at: "2026-02-18"
icon: "💄"

# 文件级别的标签（应用于所有技能）
tags:
  - name: "标签名"
    weight: 1.0           # 权重
    type: "product"       # product | category | style
  - name: "英文标签"
    weight: 1.0
    type: "product"

# 支持的模型
compatible_models:
  - "gpt-4o-vision"
  - "doubao-vision"

# 技能定义
skills:
  # 技能唯一标识（英文，驼峰或下划线）
  SkillName_SceneType:
    # 显示名称
    name: "中文技能名称"
    description: "技能功能描述"
    icon: "📸"
    
    # 技能级别的标签
    tags:
      - name: "触发词1"
        weight: 0.9
      - name: "触发词2"
        weight: 0.7
    
    # 变量定义（详细版）
    variables:
      platform:
        type: "select"
        description: "目标电商平台"
        enum: ["小红书", "淘宝", "京东", "Amazon"]
        default: "小红书"
      
      batch_count:
        type: "int"
        description: "生成图片数量"
        min: 1
        max: 20
        default: 4
      
      selling_points:
        type: "text"
        description: "产品卖点描述"
        required: true
      
      # 自定义变量
      custom_var:
        type: "select"
        description: "自定义选项"
        options: ["选项1", "选项2", "选项3"]
        default: "选项1"
    
    # LLM 生成配置
    generation:
      mode: "llm"                    # llm | template | hybrid
      model: "gpt-4o-vision"
      temperature: 0.7
      max_tokens: 2048
      system_prompt: |
        你是一位资深的电商视觉内容专家...
    
    # 输出格式定义
    output:
      format: "list"
      count: "{{batch_count}}"
      structure:
        - name: "shot_1"
          description: "第一张图说明"
        - name: "shot_2"
          description: "第二张图说明"
    
    # 模板内容（使用 {{variable}} 格式）
    template: |
      你是一位精通 {{platform}} 平台的专业电商视觉设计师。
      
      请为以下产品生成 {{batch_count}} 个AI绘图提示词：
      
      【产品卖点】
      {{selling_points}}
      
      【展示要求】
      1. 第一张：产品正面展示...
      2. 第二张：细节特写...
      
      【输出格式】
      - 每行一条独立的英文提示词
```

---

## 旧格式 v1.0（向后兼容）

```yaml
# 仍支持旧格式，但不推荐使用

SkillKey:
  name: "技能名称"
  description: "描述"
  category: "分类"
  triggers: ["触发词1", "触发词2"]  # 简单列表，无权重
  template: |
    使用 {variable} 格式的模板...
```

---

## 变量格式说明

### 支持的变量语法

| 格式 | 示例 | 说明 |
|------|------|------|
| `{{variable}}` | `{{platform}}` | 新格式，推荐 |
| `{variable}` | `{platform}` | 旧格式，向后兼容 |

### 内置变量

| 变量名 | 类型 | 说明 |
|--------|------|------|
| `{{platform}}` | string | 目标平台名称 |
| `{{selling_points}}` | text | 产品卖点描述 |
| `{{batch_count}}` | int | 生成数量 |

### 自定义变量

在 `variables` 中定义，支持：
- `type`: "string" | "text" | "int" | "select" | "boolean"
- `description`: 变量说明
- `default`: 默认值
- `required`: 是否必需
- `options`: 选项列表（select 类型）
- `min`/`max`: 数值范围（int 类型）

---

## 标签权重系统

### 权重计算

匹配分数 = 匹配类型权重 × 标签类型权重

**匹配类型权重**:
- 完全匹配: 2.0
- 包含匹配: 1.0
- 被包含匹配: 0.8

**标签类型权重**:
- product: 1.0
- category: 0.8
- style: 0.6
- scene: 0.5

### 示例

```yaml
tags:
  - name: "口红"
    weight: 1.0
    type: "product"
  
  - name: "美妆"
    weight: 0.8
    type: "category"
```

输入"哑光口红"时的匹配:
- "口红": 完全匹配 (2.0) × product (1.0) = 2.0
- "美妆": 无匹配

---

## 快速创建新技能

### 1. 创建分类目录（如需要）

```bash
mkdir skills/新分类/
```

### 2. 复制模板

```bash
cp skills/_template.yaml skills/新分类/my_product.yaml
```

### 3. 修改内容

- 修改 `category`
- 修改 `tags`
- 定义 `skills` 下的具体技能
- 编写 `template`

### 4. 验证

启动 ComfyUI，检查技能是否正确加载。

---

## 迁移指南（v1.0 → v2.0）

### 旧文件

```yaml
Lipstick_Detail:
  name: "口红详情页"
  description: "生成口红产品详情页"
  category: "彩妆"
  triggers: ["口红", "lipstick"]
  template: |
    你是一位专家...
    平台: {platform}
```

### 新文件

```yaml
category: "美妆/彩妆"
description: "口红产品展示技能"
version: "2.0"
author: "HouLai"

tags:
  - name: "口红"
    weight: 1.0
    type: "product"

skills:
  Lipstick_Detail:
    name: "口红详情页"
    description: "生成口红产品详情页的多角度构图描述"
    
    tags:
      - name: "详情页"
        weight: 0.9
    
    variables:
      platform:
        type: "select"
        default: "小红书"
    
    template: |
      你是一位专家...
      平台: {{platform}}
```

---

## 文件命名规范

- 文件名使用小写英文
- 多个单词用下划线连接
- 使用产品类型命名

**示例**:
- `lipstick.yaml` ✅
- `smart_phone.yaml` ✅
- `Lipstick Product.yaml` ❌

---

## 完整示例

见 `skills/beauty/lipstick.yaml` 和 `skills/digital/phone.yaml`
