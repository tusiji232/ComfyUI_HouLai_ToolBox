# 生成提示词与产品图匹配度分析报告

> 分析对象：用户上传的米白毛绒外套产品图 vs 生成的6条提示词
> 技能文件：french_skirt.yaml（法式半裙模板被用于外套）
> 分析时间：2026-02-21

---

## 一、产品图深度分析

### 1.1 视觉特征识别

| 特征维度 | 观察结果 | 详细描述 |
|----------|----------|----------|
| **服装类型** | 短款外套/大衣 | Short coat / Hip-length jacket |
| **颜色** | 米白色/奶油白 | Cream / Off-white / Ivory |
| **外层面料** | 毛呢/麂皮质感 | Wool-blend / Suede-like texture |
| **内层/装饰** | 仿毛绒/人造皮草 | Faux fur lining, faux fur collar & cuffs |
| **领型** | 立领+毛绒围巾领 | Stand collar with detachable fur scarf |
| **门襟** | **中式盘扣** | Chinese frog buttons / Knot buttons |
| **袖口** | 毛绒翻边袖口 | Fur-trimmed folded cuffs |
| **口袋** | 贴袋设计 | Patch pockets on front |
| **长度** | 中短款（臀上） | Hip-length, covers hips |
| **风格** | **中式+现代融合** | Chinese-inspired modern winter coat |

### 1.2 关键设计元素（卖点）

```
┌─────────────────────────────────────────────────────┐
│  🔸 中式盘扣门襟 - 最具辨识度的设计特征               │
│  🔸 毛绒围巾领 - 可拆卸/一体式设计，保暖时尚          │
│  🔸 毛绒翻边袖口 - 与领口呼应的设计语言              │
│  🔸 米白配色 - 温柔百搭的冬季色调                     │
│  🔸 麂皮绒质感外层 - 高级触感                         │
│  🔸 仿皮草内衬 - 保暖性卖点                           │
└─────────────────────────────────────────────────────┘
```

---

## 二、生成提示词逐条分析

### 提示词 1/6：首屏主图 (Hero)

**生成内容**：
```
E-commerce French elegant coat hero banner, 9:16 vertical composition, full - body model shot in a styled French interior with a beige linen sofa and a cream - colored wall, wearing an off - white wool - blend coat with a fur scarf and fur cuffs, left - front 45° key light + right - bottom reflector fill light, soft and warm neutral tones, clean negative space at the bottom for text overlay in Chinese, title text area in Chinese at the top - left, professional fashion photography, minimalist background #F5F0E8, elegant and sophisticated mood, high - end boutique aesthetic, 4K quality
```

**匹配度分析**：

| 检查项 | 匹配状态 | 说明 |
|--------|----------|------|
| 服装类型 | ⚠️ 偏差 | 说是"coat"没错，但产品图是短款外套，提示词暗示长款大衣 |
| 颜色 | ✅ 准确 | "off-white" 正确匹配米白色 |
| 面料 | ⚠️ 部分 | "wool-blend" 可接受，但未体现外层麂皮质感 |
| 毛绒元素 | ✅ 准确 | "fur scarf and fur cuffs" 正确识别 |
| **中式盘扣** | 🔴 **缺失** | **最关键的设计特征完全未提及！** |
| 风格定位 | 🔴 偏差 | "French elegant" 与中式盘扣风格冲突 |
| 光线 | ✅ 符合技能 | 使用了技能定义的45°主光 |
| 背景色 | ✅ 符合技能 | 使用了 #F5F0E8 技能定义色 |
| 文字区域 | ✅ 符合要求 | "in Chinese" 标注正确 |

**评分：6/10**
- 基础信息正确，但**遗漏关键卖点（盘扣）**，**风格定位错误**

---

### 提示词 2/6：面料细节 (Fabric Detail)

**生成内容**：
```
Fabric texture close - up, macro photography of the wool - blend outer layer and fur lining, diagonal folds showing natural draping and softness, side lighting to emphasize the texture, off - white tones with subtle highlights, soft - focus background, sharp detail in the foreground, elegant typography at the top, "面料细节" title in Chinese, clean and minimalist layout, premium material showcase, professional textile photography, washing instruction icons at the bottom in Chinese, 4K detail
```

**匹配度分析**：

| 检查项 | 匹配状态 | 说明 |
|--------|----------|------|
| 外层面料 | ⚠️ 简化 | "wool-blend" 可以接受，但"suede/velvet texture"更准确 |
| 内层面料 | ✅ 准确 | "fur lining" 正确 |
| 颜色 | ✅ 准确 | "off-white tones" 正确 |
| **盘扣细节** | 🔴 **缺失** | 面料特写应该展示盘扣的编织纹理 |
| 文字处理 | ⚠️ 问题 | "面料细节"是硬编码中文，应为 `"fabric detail title in Chinese"` |
| 布局 | ✅ 符合技能 | 遵循了技能文件的框架 |

**评分：6.5/10**
- 面料描述基本正确，但**遗漏盘扣纹理细节**

---

### 提示词 3/6：尺码信息 (Size Chart)

**生成内容**：
```
Fashion technical drawing, minimalist line illustration of the coat, measurement indicators with labels in Chinese, clean white background, black line art, professional size chart visualization, waist, hip and length measurement callouts, simple and clear instructional design, neutral gray accent lines, technical fashion sketch style, E - commerce size chart table, minimalist data visualization, column headers in Chinese, size info title in Chinese with a gray underline, 4K clarity
```

**匹配度分析**：

| 检查项 | 匹配状态 | 说明 |
|--------|----------|------|
| 服装类型 | ✅ 准确 | "coat" 正确 |
| 测量点 | ⚠️ 需调整 | 外套应测量：肩宽、袖长、胸围、衣长（而非腰围臀围） |
| 文字标注 | ✅ 符合要求 | "in Chinese" 标注正确 |
| 风格 | ✅ 符合技能 | 技术制图风格正确 |

**评分：7/10**
- 通用尺码表，**未针对外套调整测量点**

---

### 提示词 4/6：场景搭配 (Lifestyle Styled)

**生成内容**：
```
Fashion lifestyle photography, full - body model in a French - chic room with a beige wall and white wainscoting, off - white coat outfit showcase with annotation callouts in Chinese, elegant line pointers to design features (fur scarf, horn button, fur - cuffed sleeves) with Chinese text labels, pointed - toe heels and a leather handbag, soft diffused light from the window, warm neutral color palette #F5F0E8 #8B7355 #FFFFFF, French elegant aesthetic, sophisticated casual style, text overlay area in Chinese at the bottom - right, 4K fashion photography
```

**匹配度分析**：

| 检查项 | 匹配状态 | 说明 |
|--------|----------|------|
| 风格定位 | 🔴 **严重偏差** | "French-chic"、"horn button" 与**中式盘扣**冲突！ |
| 标注元素 | 🔴 **错误** | 标注了"horn button（牛角扣）"，实际是**中式盘扣** |
| 毛绒元素 | ✅ 准确 | "fur scarf"、"fur-cuffed sleeves" 正确 |
| 场景 | ✅ 符合技能 | 法式室内场景与技能一致 |
| 配色 | ✅ 符合技能 | 使用了技能定义的色彩代码 |

**评分：4/10**
- **严重错误**：将中式盘扣描述为牛角扣，风格定位完全错误

---

### 提示词 5/6：多色搭配 (Color Variants)

**生成内容**：
```
Fashion color variant grid, layout showing the off - white wool - blend coat in multiple colors (ivory, blush, navy, gray, black), consistent French room setting (beige sofa, cream - colored wall), models wearing color - coordinated outfits, soft natural lighting, cohesive aesthetic, each panel with a unique styling, versatile wardrobe piece showcase, text description area in Chinese at the top of each panel, 4K quality
```

**匹配度分析**：

| 检查项 | 匹配状态 | 说明 |
|--------|----------|------|
| 服装描述 | ⚠️ 偏差 | "wool-blend coat" 可以接受 |
| 配色方案 | ✅ 合理 | 提供的5个颜色搭配合理 |
| 场景 | ⚠️ 重复 | 与首图场景重复，可考虑变化 |
| **盘扣展示** | 🔴 **缺失** | 多色展示应该突出盘扣在不同颜色下的效果 |

**评分：6/10**
- 常规多色展示，**未突出产品特色**

---

### 提示词 6/6：工艺细节 (Craft Details)

**生成内容**：
```
Garment detail close - up, horn button and fur cuff on a white background, soft and even lighting showing fabric quality, sharp focus on stitching and texture, minimalist product photography, "细节展示" title in Chinese at the top, washing instruction icons at the bottom in Chinese, professional craftsmanship showcase, 4K macro quality
```

**匹配度分析**：

| 检查项 | 匹配状态 | 说明 |
|--------|----------|------|
| 展示元素 | 🔴 **严重错误** | "horn button" 再次错误！应该是**Chinese frog buttons** |
| 毛绒袖口 | ✅ 准确 | "fur cuff" 正确 |
| 文字处理 | ⚠️ 问题 | "细节展示"是硬编码中文 |
| 背景 | ✅ 符合技能 | 纯白背景正确 |

**评分：4/10**
- **致命错误**：工艺细节是盘扣的最大卖点，却被描述为牛角扣

---

## 三、综合评估

### 3.1 总体匹配度评分

| 维度 | 评分 | 权重 | 加权得分 |
|------|------|------|----------|
| 基础信息（颜色、面料大类） | 7/10 | 20% | 1.4 |
| 毛绒元素识别 | 9/10 | 15% | 1.35 |
| **中式盘扣识别** | **1/10** | **30%** | **0.3** |
| 风格定位 | 3/10 | 20% | 0.6 |
| 技能文件遵循度 | 8/10 | 15% | 1.2 |
| **总分** | - | - | **4.85/10** |

### 3.2 关键问题总结

```
🔴 致命问题（必须修复）
├── 1. 中式盘扣被完全遗漏或错误描述为"horn button"
│   └── 影响：产品核心卖点丢失，生成图与实际产品不符
│
├── 2. 风格定位错误：法式 vs 中式
│   └── 影响：目标受众错位，详情页与实际产品风格冲突
│
└── 3. 技能文件不匹配：使用半裙模板生成外套
    └── 影响：尺码表、构图、场景可能不适用

🟡 次要问题（建议优化）
├── 4. 面料描述不够精确（缺少麂皮绒质感）
├── 5. 硬编码中文未完全替换为变量
└── 6. 外套测量点未针对服装类型调整
```

---

## 四、问题根因分析

### 4.1 为什么盘扣被遗漏？

**根因 1：技能文件限制**
- 使用的是 `french_skirt.yaml`（法式半裙模板）
- 该模板没有任何关于"中式元素"、"盘扣"的变量或提示
- LLM被限制在技能文件的框架内，无法自主添加未定义的卖点

**根因 2：产品图分析不足**
- 系统提示词虽然要求"分析产品图"，但没有明确要求"识别独特的文化设计元素"
- LLM可能识别到了盘扣，但没有将其作为关键变量提取

**根因 3：风格预设冲突**
- 技能文件明确定义了"French elegant"风格
- LLM倾向于将观察到的元素强行匹配到预设风格（盘扣→horn button）

### 4.2 架构层面的问题

```
当前流程的问题：

产品图（中式盘扣外套）
    ↓
[匹配技能文件] → 错误匹配到 french_skirt.yaml（法式半裙）
    ↓
[变量提取] → 提取了通用变量（coat/off-white/fur）
    ↓
              ┌─ 未能提取关键卖点：中式盘扣
              └─ 因为技能文件没有相关变量
    ↓
[生成提示词] → 使用法式半裙模板生成外套提示词
    ↓
输出：风格错位、卖点缺失的提示词
```

---

## 五、修复建议

### 5.1 短期修复（当前技能文件）

**方案 A：修改变量提取逻辑**
在系统提示词中增加"文化设计元素"的提取要求：

```markdown
### 步骤2增强：分析产品图提取变量

从产品图中识别并提取以下关键变量：
...原有变量...

**新增 - 独特设计元素**：
- `{{design_feature}}`: 特殊设计特征（如：Chinese frog buttons, asymmetric hem）
- `{{style_origin}}`: 风格来源（如：Chinese-inspired, French vintage）
- `{{unique_selling_point}}`: 核心卖点（如：detachable fur collar）
```

**方案 B：扩展技能文件变量**
在 `french_skirt.yaml` 中增加：

```yaml
# 新增变量
# {{design_detail}} - 独特设计细节描述
# {{button_type}} - 扣子类型（frog button, horn button, etc.）
```

### 5.2 中期修复（技能匹配优化）

**问题**：中式盘扣外套不应该匹配到 `french_skirt.yaml`

**解决方案**：
1. **创建新技能文件**：`chinese_coat.yaml`（中式外套模板）
2. **或扩展现有技能**：在 `women_clothing.yaml` 中增加中式风格分支
3. **改进技能匹配逻辑**：增加风格标签匹配（Chinese → 中式技能）

### 5.3 长期修复（架构优化）

**建议 1：增加"卖点强化"机制**
```
产品图分析
    ↓
提取：颜色、面料、款式（基础变量）
    ↓
识别：独特卖点（盘扣、不对称设计等）
    ↓
强化：在对应shot的prompt中强调卖点
```

**建议 2：技能文件动态扩展**
允许LLM在技能文件模板基础上，根据产品图自主添加描述：
```
基础模板（来自技能文件）
    + 产品图特有元素（LLM自主添加）
    = 最终提示词
```

---

## 六、修正后的提示词示例

基于产品图（中式盘扣毛绒外套），正确的提示词应该这样生成：

### 首屏主图（修正版）

```
E-commerce Chinese-inspired winter coat hero banner, 9:16 vertical composition, full-body model shot in a styled minimalist interior with warm beige tones, wearing an off-white hip-length coat with distinctive Chinese frog button closure, detachable faux fur scarf collar and fur-trimmed cuffs, suede-like outer texture with plush faux fur lining visible at open front, soft natural lighting from left side, warm cream and ivory color palette, minimalist wooden panel background, clean negative space at bottom for text overlay in Chinese, title text area in Chinese at top-left, professional fashion photography, elegant fusion of modern and traditional style, high-end boutique aesthetic, 4K quality
```

**关键修正**：
- ✅ "Chinese-inspired" 替代 "French elegant"
- ✅ "Chinese frog button closure" 明确盘扣设计
- ✅ "detachable faux fur scarf collar" 准确描述围巾领
- ✅ "suede-like outer texture" 体现外层质感

---

## 七、结论

### 7.1 当前提示词质量评级

| 评估维度 | 评级 | 说明 |
|----------|------|------|
| **产品准确性** | ⚠️ **不合格** | 遗漏核心卖点（盘扣），风格定位错误 |
| **技能遵循度** | ✅ 良好 | 基本遵循了french_skirt.yaml的框架 |
| **批量输出格式** | ✅ 合格 | 每行1条，无序号，格式正确 |
| **语言控制** | ⚠️ 需改进 | 仍有少量硬编码中文 |

### 7.2 关键行动项

| 优先级 | 行动项 | 影响 |
|--------|--------|------|
| 🔴 P0 | 修复"中式盘扣"被识别为"牛角扣"的问题 | 避免生成图与产品不符 |
| 🔴 P0 | 为中式风格服装创建专用技能文件 | 解决技能匹配错误 |
| 🟡 P1 | 增强系统提示词的"独特元素提取"要求 | 防止卖点遗漏 |
| 🟢 P2 | 统一文字区域的变量化处理 | 消除硬编码中文 |

### 7.3 最终建议

**当前生成的提示词不建议直接使用**，因为：
1. 会生成"法式牛角扣大衣"而非"中式盘扣外套"
2. 产品核心卖点（盘扣设计）完全丢失
3. 目标受众与产品实际风格错位

**建议先修复技能匹配问题**，再重新生成提示词。

---

*报告完成。如需协助修复技能文件或系统提示词，请告知。*
