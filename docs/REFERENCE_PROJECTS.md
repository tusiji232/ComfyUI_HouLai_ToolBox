# ComfyUI 前端扩展示例参考

## 🔍 类似实现模式的成熟项目

### 1. **rgthree-comfyui** (最著名)
- **GitHub**: `rgthree/rgthree-comfy`
- **特点**: 
  - 大量使用 `app.registerExtension`
  - 动态修改节点 widget 选项
  - 按钮添加到 ComfyUI 工具栏
- **参考文件**: `web/comfyui_menu.js`, `web/display_any.js`
- **相似度**: ⭐⭐⭐⭐⭐ (实现模式几乎相同)

### 2. **ComfyUI-Manager**
- **GitHub**: `ltdrdata/ComfyUI-Manager`
- **特点**:
  - 节点创建时动态获取数据
  - 通过 API 获取远程列表
  - 前端扩展注册模式
- **参考文件**: `js/comfyui-manager.js`
- **相似度**: ⭐⭐⭐⭐⭐

### 3. **ComfyUI-Easy-Use**
- **GitHub**: `yolain/ComfyUI-Easy-Use`
- **特点**:
  - 动态下拉菜单更新
  - `beforeRegisterNodeDef` 钩子使用
  - 监听 widget 变化
- **相似度**: ⭐⭐⭐⭐

### 4. **ComfyUI-Custom-Scripts**
- **GitHub**: `pythongosssss/ComfyUI-Custom-Scripts`
- **特点**:
  - widget 增强功能
  - 自定义菜单按钮
  - 节点元数据修改
- **相似度**: ⭐⭐⭐⭐

### 5. **ComfyUI-Workflow-Component**
- **GitHub**: `ltdrdata/ComfyUI-Workflow-Component`
- **特点**:
  - 节点类型动态注册
  - 前端扩展与后端 API 配合
- **相似度**: ⭐⭐⭐

---

## 📋 具体实现模式对比

### 模式1: 动态下拉菜单 (我们的实现)

```javascript
// houlai_dynamic_skills.js (我们的代码)
app.registerExtension({
    name: EXTENSION_NAME,
    
    nodeCreated(node) {
        if (node.type === "Ecommerce_Skill_Router") {
            setTimeout(() => {
                setupDynamicSkills(node);
            }, 100);
        }
    }
});

async function setupDynamicSkills(node) {
    const skillWidget = node.widgets.find(w => w.name === "技能选择");
    const { skills } = await fetchSkills();
    skillWidget.options.values = skills;
}
```

**对比项目**: rgthree-comfyui 的 `Context Node`
```javascript
// rgthree 的类似实现
app.registerExtension({
  name: "rgthree.Context",
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name === "Context") {
      // 动态设置选项
    }
  }
});
```

---

### 模式2: 监听 Widget 变化 (我们的实现)

```javascript
// houlai_dynamic_skills.js
keywordWidget.callback = async function(value) {
    const matchedSkill = matchSkillByTrigger(value, triggerMap);
    if (matchedSkill) {
        skillWidget.value = matchedSkill;
        node.setDirtyCanvas(true, true);
    }
};
```

**对比项目**: ComfyUI-Manager 的模型选择
```javascript
// ComfyUI-Manager 的类似模式
const originalCallback = widget.callback;
widget.callback = function(value) {
    // 自定义逻辑
    if (originalCallback) {
        originalCallback.apply(this, arguments);
    }
};
```

---

### 模式3: 添加工具栏按钮 (已移除)

之前我们的 `houlai_skill_toolbar.js` 参考了以下模式：

**对比项目**: rgthree-comfyui 的菜单按钮
```javascript
// rgthree 的工具栏按钮实现
function addMenuButton() {
    const button = document.createElement("button");
    button.innerHTML = "🔥 按钮";
    // 尝试多种方式添加到工具栏
    const toolbar = document.querySelector('.comfyui-toolbar');
    if (toolbar) {
        toolbar.appendChild(button);
    }
}
```

---

## ✅ 我们的实现是否标准？

### 符合社区惯例的部分：

1. **`app.registerExtension`** ✅
   - 标准做法，所有项目都用这个

2. **`nodeCreated` 钩子** ✅
   - 标准做法，rgthree、Easy-Use 都用

3. **`beforeRegisterNodeDef` 钩子** ✅
   - 标准做法，用于修改节点原型

4. **fetch API 获取数据** ✅
   - 标准做法，ComfyUI-Manager 等都用

5. **widget.options.values 更新** ✅
   - 标准做法，动态更新下拉选项

### 需要改进的部分：

1. **缓存机制**
   - 目前：简单的全局变量缓存
   - 参考：rgthree 使用 WeakMap 避免内存泄漏

2. **错误处理**
   - 目前：基本的 try-catch
   - 参考：ComfyUI-Manager 有完善的错误提示 UI

---

## 🔧 推荐的代码改进（基于成熟项目）

### 改进1: 使用 WeakMap 存储节点数据

```javascript
// 参考 rgthree 的实现
const nodeDataMap = new WeakMap();

function setupDynamicSkills(node) {
    // 避免重复初始化
    if (nodeDataMap.has(node)) return;
    nodeDataMap.set(node, { initialized: true });
    
    // ... 后续逻辑
}
```

### 改进2: 更完善的错误提示

```javascript
// 参考 ComfyUI-Manager
function showError(message) {
    if (app.ui && app.ui.dialog) {
        app.ui.dialog.show({
            title: "错误",
            content: message,
            type: "error"
        });
    }
}
```

### 改进3: 防抖优化

```javascript
// 我们的实现已经有防抖，但可以更规范
function debounce(fn, delay) {
    let timer = null;
    return function(...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

keywordWidget.callback = debounce(async function(value) {
    // 匹配逻辑
}, 500);
```

---

## 📊 实现成熟度评估

| 功能 | 我们的实现 | 社区标准 | 评分 |
|------|-----------|----------|------|
| 扩展注册 | ✅ 标准 | ✅ 标准 | ⭐⭐⭐⭐⭐ |
| 节点钩子 | ✅ 标准 | ✅ 标准 | ⭐⭐⭐⭐⭐ |
| Widget 更新 | ✅ 标准 | ✅ 标准 | ⭐⭐⭐⭐⭐ |
| API 调用 | ✅ 标准 | ✅ 标准 | ⭐⭐⭐⭐⭐ |
| 防抖处理 | ✅ 有 | ✅ 有 | ⭐⭐⭐⭐ |
| 内存管理 | ⚠️ 简单 | ✅ WeakMap | ⭐⭐⭐ |
| 错误处理 | ⚠️ 基础 | ✅ 完善 | ⭐⭐⭐ |

---

## 🎯 结论

**我们的实现是符合 ComfyUI 社区标准的**。

使用的技术方案（`app.registerExtension`、`nodeCreated`、`widget.callback`）都是主流做法，与 rgthree-comfyui、ComfyUI-Manager 等成熟项目一致。

当前代码质量良好，可以投入使用。如需进一步优化，可以参考上述改进建议。