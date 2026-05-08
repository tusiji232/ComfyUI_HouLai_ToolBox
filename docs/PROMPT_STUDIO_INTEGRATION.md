# 结合 ComfyUI-Prompt-Studio 模式改进建议

## 📊 Prompt-Studio 核心特点分析

基于 ComfyUI 生态惯例，Prompt-Studio 的典型实现模式：

### 1. 数据层设计

```yaml
# Prompt-Studio 风格的 skills 结构
skills/
├── categories.yaml          # 分类索引
├── beauty/
│   ├── lipstick.yaml       # 单品类技能
│   └── skincare.yaml
└── digital/
    ├── phone.yaml
    └── earphone.yaml
```

### 2. 前端架构

```javascript
// Prompt-Studio 典型前端模式
class PromptStudioManager {
    constructor() {
        this.categories = [];      // 分类列表
        this.templates = {};       // 模板缓存
        this.currentCategory = null;
    }
    
    // 层级加载：分类 → 模板
    async loadCategories() {
        const response = await fetch('/prompt-studio/categories');
        this.categories = await response.json();
    }
    
    async loadTemplates(category) {
        const response = await fetch(`/prompt-studio/templates/${category}`);
        this.templates[category] = await response.json();
    }
}
```

### 3. 与我们的差异对比

| 特性 | Prompt-Studio | 我们的当前实现 | 建议 |
|------|---------------|----------------|------|
| **文件组织** | 分目录存储 | 单文件多技能 | 可结合：大分类分目录 |
| **分类层级** | 二级（分类→模板） | 一级（文件名-技能） | 可增加分类层级 |
| **变量系统** | `{{variable}}` | `{variable}` | 统一为 `{{}}` 更标准 |
| **预览功能** | 实时预览模板效果 | 无预览 | 可增加 |
| **搜索方式** | 分类浏览+关键词 | 触发词匹配 | 结合两种 |

---

## 🔧 具体结合方案

### 方案1: 优化 YAML 结构（推荐）

**当前结构**:
```yaml
# beauty.yaml（当前）
Lipstick_Detail:
  name: "口红详情页"
  category: "彩妆"
  triggers: ["口红", "lipstick"]
  template: |
    ...
```

**Prompt-Studio 风格优化**:
```yaml
# beauty/lipstick.yaml（建议）
category: "美妆/彩妆"
description: "口红产品展示技能集合"
version: "1.0"

skills:
  Lipstick_Detail:
    name: "口红详情页"
    description: "生成口红产品详情页的多角度构图描述"
    tags: ["口红", "lipstick", "唇膏"]
    author: "HouLai"
    variables:
      - name: "platform"
        description: "目标电商平台"
        default: "小红书"
      - name: "batch_count"
        description: "生成数量"
        default: 4
    template: |
      你是一位资深电商视觉专家...
      
  Lipstick_Model:
    name: "口红模特图"
    description: "模特上嘴效果展示"
    tags: ["模特", "试色"]
    variables: [...]
    template: |
      ...
```

### 方案2: 增强前端交互

**当前实现**:
```javascript
// 简单下拉菜单 + 关键词匹配
keywordWidget.callback = (value) => {
    const matched = matchSkill(value);
    skillWidget.value = matched;
};
```

**Prompt-Studio 风格增强**:
```javascript
// 层级选择器 + 搜索 + 预览
class SkillSelector {
    constructor(node) {
        this.node = node;
        this.categories = [];      // 分类
        this.filteredSkills = [];  // 过滤后的技能
    }
    
    // 1. 分类选择
    selectCategory(category) {
        this.filteredSkills = this.getSkillsByCategory(category);
        this.updateSkillList();
    }
    
    // 2. 实时搜索（Prompt-Studio 风格）
    search(query) {
        // 同时搜索名称、描述、标签
        return this.allSkills.filter(skill => 
            skill.name.includes(query) ||
            skill.description.includes(query) ||
            skill.tags.some(tag => tag.includes(query))
        );
    }
    
    // 3. 模板预览（新增）
    previewTemplate(skillKey) {
        const template = this.getTemplate(skillKey);
        // 显示格式化后的模板，高亮变量
        return this.highlightVariables(template);
    }
}
```

### 方案3: 结合 LLM 的优势设计

Prompt-Studio 主要做静态模板替换，我们的优势是**LLM 智能生成**：

```yaml
# 增强版技能定义
Lipstick_Detail:
  name: "口红详情页"
  
  # 静态部分（Prompt-Studio 风格）
  system_prompt: |
    你是一位资深电商视觉专家...
  
  # 动态部分（LLM 生成）
  generation:
    mode: "llm"  # llm | template | hybrid
    model: "gpt-4o-vision"  # 可选指定模型
    temperature: 0.7
    max_tokens: 2048
  
  # 变量定义（更详细）
  variables:
    platform:
      type: "string"
      enum: ["小红书", "淘宝", "京东", "Amazon"]
      default: "小红书"
    
    selling_points:
      type: "text"
      required: true
      description: "产品卖点描述"
      # LLM 增强：自动从图片提取卖点
      auto_extract: 
        enabled: true
        from: "image_input"
    
    style:
      type: "select"
      options: ["ins风", "国潮", "极简", "奢华"]
      default: "ins风"
  
  # 输出格式定义（我们的特色）
  output:
    format: "list"  # list | json | text
    count: 4
    structure:
      - name: "product_shot"
        description: "产品主图"
      - name: "detail_shot"
        description: "细节特写"
      - name: "scene_shot"
        description: "场景图"
      - name: "creative_shot"
        description: "创意图"
```

---

## 📁 文件结构改进建议

### 当前结构
```
skills/
├── beauty.yaml
└── digital.yaml
```

### Prompt-Studio + LLM 混合结构（建议）
```
skills/
├── _index.yaml              # 技能库索引（新增）
├── _schema.yaml             # 技能定义规范（新增）
├── beauty/
│   ├── _category.yaml       # 分类元数据
│   ├── lipstick.yaml
│   ├── skincare.yaml
│   └── perfume.yaml
├── digital/
│   ├── _category.yaml
│   ├── phone.yaml
│   └── earphone.yaml
└── system/                  # 系统技能（新增）
    ├── auto_tag.yaml        # 自动标签生成
    ├── image_analysis.yaml  # 图片分析
    └── prompt_enhance.yaml  # 提示词增强
```

---

## 🎯 具体实施建议

### Phase 1: YAML 结构优化（立即可做）

1. **统一变量语法**
   ```yaml
   # 从 {variable} 改为 {{variable}}
   template: |
     平台: {{platform}}
     数量: {{batch_count}}
   ```

2. **增加元数据字段**
   ```yaml
   version: "1.0"
   author: "HouLai"
   updated_at: "2026-02-18"
   compatible_models: ["gpt-4o", "doubao", "deepseek"]
   ```

3. **标签化 triggers**
   ```yaml
   # 从简单列表改为结构化
   tags:
     - name: "口红"
       type: "product"
       weight: 1.0
     - name: "lipstick"
       type: "product"
       weight: 1.0
     - name: "美妆"
       type: "category"
       weight: 0.5
   ```

### Phase 2: 前端增强（后续迭代）

1. **分类浏览界面**
   - 左侧分类树
   - 右侧技能列表
   - 搜索框实时过滤

2. **模板预览功能**
   - 显示原始模板
   - 高亮变量占位符
   - 示例填充预览

3. **智能推荐**
   - 根据历史选择推荐
   - 根据图片内容推荐（LLM 分析）

### Phase 3: LLM 深度集成（长期）

1. **智能变量提取**
   ```python
   # 从图片自动提取产品信息
   def extract_from_image(image):
       prompt = "分析这张产品图，提取：产品类型、颜色、材质、卖点"
       result = call_llm(image, prompt)
       return parse_result(result)
   ```

2. **动态模板生成**
   ```yaml
   # 基础模板 + LLM 增强
   base_template: |
     生成 {{batch_count}} 张{{product_type}}产品图
   
   llm_enhance:
     enabled: true
     prompt: "根据产品特点优化描述"
   ```

---

## 🔗 参考实现代码片段

### 结合 Prompt-Studio 的前端改进

```javascript
// js/houlai_skill_enhanced.js
import { app } from "../../scripts/app.js";

class EnhancedSkillManager {
    constructor(node) {
        this.node = node;
        this.categories = [];
        this.skills = {};
        this.cache = new Map();
    }
    
    // Prompt-Studio 风格的层级加载
    async loadSkillLibrary() {
        // 1. 加载分类索引
        const index = await fetch('/houlai/skills/index').then(r => r.json());
        this.categories = index.categories;
        
        // 2. 按需加载技能
        for (const category of this.categories) {
            const skills = await fetch(`/houlai/skills/category/${category.id}`).then(r => r.json());
            this.skills[category.id] = skills;
        }
    }
    
    // 增强的搜索（Prompt-Studio + 我们的触发词）
    search(query) {
        const results = [];
        
        for (const [catId, skills] of Object.entries(this.skills)) {
            for (const [skillId, skill] of Object.entries(skills)) {
                // 1. 标签匹配（我们的特色）
                const tagMatch = skill.tags?.some(tag => 
                    tag.toLowerCase().includes(query.toLowerCase())
                );
                
                // 2. 名称/描述匹配（Prompt-Studio 风格）
                const nameMatch = skill.name?.includes(query);
                const descMatch = skill.description?.includes(query);
                
                if (tagMatch || nameMatch || descMatch) {
                    results.push({
                        category: catId,
                        skill: skillId,
                        score: this.calculateScore(skill, query),
                        preview: this.generatePreview(skill)
                    });
                }
            }
        }
        
        return results.sort((a, b) => b.score - a.score);
    }
    
    // 模板预览（新增）
    generatePreview(skill) {
        let template = skill.template;
        // 用示例值填充变量
        for (const [key, config] of Object.entries(skill.variables || {})) {
            const example = config.example || config.default || `[${key}]`;
            template = template.replace(new RegExp(`{{${key}}}`, 'g'), example);
        }
        return template;
    }
}

// 注册增强版扩展
app.registerExtension({
    name: "ComfyUI_HouLai_ToolBox.EnhancedSkills",
    
    nodeCreated(node) {
        if (node.type === "Ecommerce_Skill_Router") {
            const manager = new EnhancedSkillManager(node);
            // ... 初始化逻辑
        }
    }
});
```

---

## ✅ 总结建议

**可以立即借鉴的 Prompt-Studio 特点**:

1. ✅ **YAML 元数据增强** - 添加 version、author、compatible_models
2. ✅ **变量语法统一** - 从 `{var}` 改为 `{{var}}`
3. ✅ **分类层级** - 大分类单独目录（beauty/、digital/）
4. ✅ **标签权重** - triggers 可以带权重分数

**保持我们的独特优势**:

1. ✅ **LLM 集成** - Prompt-Studio 没有的智能生成
2. ✅ **触发词匹配** - 实时自动匹配是特色
3. ✅ **多模态** - 图片输入分析
4. ✅ **批量生成** - 4图组合是电商刚需

**后续迭代方向**:

1. 🔄 **前端界面** - 参考 Prompt-Studio 的分类浏览
2. 🔄 **模板预览** - 显示格式化后的模板
3. 🔄 **智能推荐** - 基于历史的选择推荐

这样结合后，既有 Prompt-Studio 的规范性和易用性，又有 LLM 的智能和电商的专业性。