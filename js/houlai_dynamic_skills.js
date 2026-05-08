/**
 * ComfyUI_HouLai_ToolBox - 动态技能列表前端扩展（Prompt-Studio 风格 v2.0 - 优化版）
 * 
 * 功能：
 * 1. 监听"关键词搜索"输入，根据触发词自动匹配技能（支持权重）
 * 2. 节点创建时动态加载技能列表（支持新格式 {{variable}}）
 * 3. 支持自定义技能目录配置
 * 4. 支持分类浏览模式
 * 5. 线程安全的节点级缓存（WeakMap）
 * 6. 防抖定时器自动清理
 */

import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "ComfyUI_HouLai_ToolBox.DynamicSkills";

// ==================== 配置常量 ====================
const CACHE_TTL = 5 * 60 * 1000;  // 缓存过期时间：5分钟
const DEBOUNCE_DELAY = 500;       // 防抖延迟：500ms
const INIT_DELAY = 500;           // 初始化延迟：500ms

// ==================== 节点级缓存（使用WeakMap避免内存泄漏） ====================
const nodeCacheMap = new WeakMap();
const nodeStateMap = new WeakMap();  // 存储节点状态（如isRefreshing）

/**
 * 获取或创建节点的缓存数据
 * @param {Object} node - ComfyUI节点对象
 * @returns {Object} 节点缓存对象
 */
function getNodeCache(node) {
    if (!nodeCacheMap.has(node)) {
        nodeCacheMap.set(node, {
            skills: null,
            triggers: {},
            weights: {},
            categories: [],
            timestamp: 0,
            lastCustomPath: ""
        });
    }
    return nodeCacheMap.get(node);
}

/**
 * 获取或创建节点的状态数据
 * @param {Object} node - ComfyUI节点对象
 * @returns {Object} 节点状态对象
 */
function getNodeState(node) {
    if (!nodeStateMap.has(node)) {
        nodeStateMap.set(node, {
            isRefreshing: false,
            isInitialized: false,
            debounceTimer: null
        });
    }
    return nodeStateMap.get(node);
}

/**
 * 清理节点的状态（防止内存泄漏）
 * @param {Object} node - ComfyUI节点对象
 */
function cleanupNodeState(node) {
    const state = nodeStateMap.get(node);
    if (state) {
        if (state.debounceTimer) {
            clearTimeout(state.debounceTimer);
            state.debounceTimer = null;
        }
        nodeStateMap.delete(node);
    }
    nodeCacheMap.delete(node);
}

/**
 * 从后端API获取技能列表
 * @param {Object} node - ComfyUI节点对象
 * @param {string} customPath - 自定义技能目录路径
 * @param {boolean} forceRefresh - 是否强制刷新
 * @returns {Promise<{skills: string[], triggers: Object, weights: Object, categories: Object[]}>}
 */
async function fetchSkills(node, customPath = "", forceRefresh = false) {
    const cache = getNodeCache(node);
    const cacheKey = customPath || "default";
    const now = Date.now();
    
    // 检查缓存是否有效（路径匹配且未过期）
    if (!forceRefresh && 
        cache.skills && 
        cacheKey === cache.lastCustomPath && 
        (now - cache.timestamp) < CACHE_TTL) {
        console.log(`[${EXTENSION_NAME}] 使用节点缓存（${Math.round((now - cache.timestamp) / 1000)}秒前）`);
        return {
            skills: cache.skills,
            triggers: cache.triggers,
            weights: cache.weights,
            categories: cache.categories
        };
    }
    
    try {
        // 强制刷新使用POST端点，否则使用GET端点
        const response = forceRefresh
            ? await fetch("/houlai/refresh_skills", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ custom_path: customPath })
            })
            : await fetch(customPath 
                ? `/houlai/get_skills?custom_path=${encodeURIComponent(customPath)}`
                : `/houlai/get_skills`);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // 更新节点缓存
            cache.skills = data.skills || [];
            cache.triggers = data.triggers || {};
            cache.weights = data.weights || {};
            cache.categories = data.categories || [];
            cache.timestamp = now;
            cache.lastCustomPath = cacheKey;
            
            return {
                skills: cache.skills,
                triggers: cache.triggers,
                weights: cache.weights,
                categories: cache.categories
            };
        } else {
            throw new Error(data.error || "Unknown error");
        }
    } catch (error) {
        console.error(`[${EXTENSION_NAME}] 获取技能列表失败:`, error);
        // 如果有缓存，返回过期缓存作为后备
        if (cache.skills) {
            console.warn(`[${EXTENSION_NAME}] 使用过期缓存作为后备`);
            return {
                skills: cache.skills,
                triggers: cache.triggers,
                weights: cache.weights,
                categories: cache.categories,
                fromCache: true
            };
        }
        return {
            skills: ["加载失败，请检查路径"],
            triggers: {},
            weights: {},
            categories: [],
            error: error.message
        };
    }
}

/**
 * 更新节点的技能选择下拉菜单
 * @param {Object} node - ComfyUI节点对象
 * @param {string[]} skills - 技能选项列表
 * @param {Object} customPathWidget - 自定义路径widget
 * @param {boolean} isRefreshing - 是否正在刷新中
 */
function updateSkillDropdown(node, skills, customPathWidget, isRefreshing = false) {
    if (!node.widgets) {
        console.warn(`[${EXTENSION_NAME}] 节点没有 widgets`);
        return;
    }
    
    const skillWidget = node.widgets.find(w => w.name === "技能选择");
    if (!skillWidget) {
        console.warn(`[${EXTENSION_NAME}] 未找到"技能选择"widget`);
        return;
    }
    
    console.log(`[${EXTENSION_NAME}] 更新技能列表: ${skills.length} 个技能`, skills);
    
    const currentValue = skillWidget.value;
    const isRefreshOption = currentValue && (currentValue.startsWith("🔄") || currentValue.startsWith("⏳"));
    
    // 添加刷新按钮作为第一个选项
    let newValues = skills.length > 0 ? [...skills] : ["无可用技能"];
    const refreshLabel = isRefreshing ? "⏳ 刷新中..." : "🔄 刷新技能列表";
    newValues = [refreshLabel, ...newValues];
    
    // 更新选项列表
    if (skillWidget.options) {
        skillWidget.options.values = newValues;
    } else {
        skillWidget.options = { values: newValues };
    }
    
    // 设置回调函数处理刷新选项
    const state = getNodeState(node);
    skillWidget.callback = async function(value) {
        // 处理刷新选项
        if (value && value.startsWith("🔄")) {
            if (state.isRefreshing) {
                console.log(`[${EXTENSION_NAME}] 刷新已在进行中，忽略重复请求`);
                return;
            }
            
            state.isRefreshing = true;
            console.log(`[${EXTENSION_NAME}] 触发刷新技能列表`);
            
            // 显示刷新中提示
            if (app.ui?.toast) {
                app.ui.toast({
                    message: "🔄 正在刷新技能列表...",
                    type: "info"
                });
            }
            
            try {
                // 临时更新下拉显示
                skillWidget.value = "⏳ 刷新中...";
                
                // 清空缓存并强制刷新
                const cache = getNodeCache(node);
                cache.skills = null;
                cache.timestamp = 0;
                
                const customPath = customPathWidget ? customPathWidget.value : "";
                const result = await fetchSkills(node, customPath, true);
                
                // 更新下拉菜单（递归调用，但isRefreshing=false）
                updateSkillDropdown(node, result.skills, customPathWidget, false);
                
                // 显示成功提示
                if (app.ui?.toast) {
                    const msg = result.fromCache 
                        ? `⚠️ 使用缓存（后端错误），${result.skills.length} 个技能`
                        : `✅ 已刷新！找到 ${result.skills.length} 个技能`;
                    app.ui.toast({
                        message: msg,
                        type: result.fromCache ? "warning" : "success"
                    });
                }
            } catch (error) {
                console.error(`[${EXTENSION_NAME}] 刷新失败:`, error);
                if (app.ui?.toast) {
                    app.ui.toast({
                        message: `❌ 刷新失败: ${error.message}`,
                        type: "error"
                    });
                }
            } finally {
                state.isRefreshing = false;
            }
            
            return;
        }
        
        // 跳过"刷新中"和"无可用技能"选项的选中
        if (value && (value.startsWith("⏳") || value === "无可用技能")) {
            return;
        }
    };
    
    // 恢复选中值或选择第一个实际技能（跳过刷新按钮）
    // 优先保留用户原来的选择（如果在新列表中存在）
    if (!isRefreshOption && currentValue && newValues.indexOf(currentValue) >= 0 && !currentValue.startsWith("⏳")) {
        skillWidget.value = currentValue;
    } else if (currentValue && !currentValue.startsWith("🔄") && !currentValue.startsWith("⏳") && !currentValue.startsWith("AUTO")) {
        // 如果用户的选择不在新列表中但看起来是有效的技能名称，仍然保留它
        // 这可能是从工作流加载的值
        console.log(`[${EXTENSION_NAME}] 保留用户选择（不在当前列表中）: ${currentValue}`);
        skillWidget.value = currentValue;
        // 将这个值添加到选项列表中，确保ComfyUI不会报错
        if (skillWidget.options && !skillWidget.options.values.includes(currentValue)) {
            skillWidget.options.values = [refreshLabel, currentValue, ...skills];
        }
    } else {
        // 选择第二个选项（第一个是刷新按钮）
        skillWidget.value = newValues[1] || newValues[0];
    }
    
    // 强制触发 ComfyUI 更新
    if (typeof app !== 'undefined' && app.canvas) {
        app.canvas.setDirty(true, true);
    }
    node.setDirtyCanvas(true, true);
}

/**
 * 根据触发词搜索匹配的技能（支持权重评分）
 * @param {string} text - 搜索文本
 * @param {Object} triggerMap - 触发词映射 {trigger: skillName}
 * @param {Object} tagWeights - 标签权重配置
 * @returns {Object|null} - {skill: string, score: number, matchedTags: string[]}
 */
function matchSkillByTrigger(text, triggerMap, tagWeights = {}) {
    if (!text || !triggerMap) return null;
    
    const lowerText = text.toLowerCase().trim();
    if (!lowerText) return null;
    
    const scores = {};  // skill -> {score, matchedTags}
    
    for (const [trigger, skillName] of Object.entries(triggerMap)) {
        const lowerTrigger = trigger.toLowerCase();
        let matched = false;
        let matchWeight = 1.0;
        
        // 完全匹配权重最高
        if (lowerText === lowerTrigger) {
            matched = true;
            matchWeight = 2.0;
        }
        // 搜索词包含触发词
        else if (lowerText.includes(lowerTrigger)) {
            matched = true;
            matchWeight = 1.0;
        }
        // 触发词包含搜索词
        else if (lowerTrigger.includes(lowerText)) {
            matched = true;
            matchWeight = 0.8;
        }
        
        if (matched) {
            const tagTypeWeight = tagWeights[trigger] || 1.0;
            const totalScore = matchWeight * tagTypeWeight;
            
            if (!scores[skillName]) {
                scores[skillName] = { score: 0, matchedTags: [] };
            }
            scores[skillName].score += totalScore;
            scores[skillName].matchedTags.push(trigger);
        }
    }
    
    // 找最高分
    let bestMatch = null;
    let maxScore = 0;
    
    for (const [skillName, data] of Object.entries(scores)) {
        if (data.score > maxScore) {
            maxScore = data.score;
            bestMatch = {
                skill: skillName,
                score: data.score,
                matchedTags: data.matchedTags
            };
        }
    }
    
    if (bestMatch) {
        console.log(`[${EXTENSION_NAME}] 触发词匹配: '${text}' -> ${bestMatch.skill} (得分: ${bestMatch.score.toFixed(2)})`);
    }
    
    return bestMatch;
}

/**
 * 为"后来_电商技能路由"节点添加动态技能功能
 * @param {Object} node - ComfyUI节点对象
 */
function setupDynamicSkills(node) {
    console.log(`[${EXTENSION_NAME}] setupDynamicSkills 被调用`, node);
    
    if (!node.widgets) {
        console.warn(`[${EXTENSION_NAME}] 节点没有 widgets`);
        return;
    }
    
    // 重复初始化保护（仅跳过完全相同的节点实例）
    const state = getNodeState(node);
    if (state.isInitialized) {
        console.log(`[${EXTENSION_NAME}] 节点已初始化，重新加载技能列表`);
        // 重置初始化状态以允许重新加载（比如模式切换后）
        state.isInitialized = false;
    }
    state.isInitialized = true;
    
    // 找到关键widgets
    const skillWidget = node.widgets.find(w => w.name === "技能选择");
    const keywordWidget = node.widgets.find(w => w.name === "关键词搜索");
    const customPathWidget = node.widgets.find(w => w.name === "自定义技能目录");
    
    console.log(`[${EXTENSION_NAME}] 找到 widgets:`, {
        skill: !!skillWidget,
        keyword: !!keywordWidget,
        customPath: !!customPathWidget
    });
    
    // 设置节点销毁时的清理函数
    const originalOnRemoved = node.onRemoved;
    node.onRemoved = function() {
        console.log(`[${EXTENSION_NAME}] 节点被移除，清理资源`);
        cleanupNodeState(node);
        if (originalOnRemoved) {
            originalOnRemoved.apply(this, arguments);
        }
    };
    
    // 初始化时加载技能列表
    const initSkills = async () => {
        console.log(`[${EXTENSION_NAME}] 初始化技能列表...`);
        
        // 保存用户原始选择（如果有）
        const originalValue = skillWidget ? skillWidget.value : null;
        
        // 显示加载中（但不覆盖已保存的有效值）
        if (skillWidget && (!originalValue || originalValue === "AUTO_LOAD")) {
            skillWidget.value = "⏳ 正在加载技能列表...";
            if (skillWidget.options) {
                skillWidget.options.values = ["🔄 刷新技能列表", "⏳ 正在加载技能列表..."];
            }
            node.setDirtyCanvas(true, true);
        }
        
        const customPath = customPathWidget ? customPathWidget.value : "";
        const result = await fetchSkills(node, customPath);
        
        updateSkillDropdown(node, result.skills, customPathWidget);
        
        // 缓存到节点
        const cache = getNodeCache(node);
        cache.triggers = result.triggers;
        cache.weights = result.weights;
        cache.categories = result.categories;
        
        console.log(`[${EXTENSION_NAME}] 初始化完成: ${result.skills.length} 个技能, ${result.categories.length} 个分类`);
        
        // 如果有错误，显示警告
        if (result.error && app.ui?.toast) {
            app.ui.toast({
                message: `⚠️ 技能加载警告: ${result.error}`,
                type: "warning"
            });
        }
    };
    
    // 延迟初始化
    setTimeout(initSkills, INIT_DELAY);
    
    // 监听自定义技能目录变化
    if (customPathWidget) {
        const originalCallback = customPathWidget.callback;
        customPathWidget.callback = async function(value) {
            console.log(`[${EXTENSION_NAME}] 自定义技能目录变化:`, value);
            
            // 清空缓存并强制刷新
            const cache = getNodeCache(node);
            cache.skills = null;
            cache.timestamp = 0;
            
            const result = await fetchSkills(node, value, true);
            updateSkillDropdown(node, result.skills, customPathWidget);
            
            // 更新缓存
            cache.triggers = result.triggers;
            cache.weights = result.weights;
            cache.categories = result.categories;
            
            if (originalCallback) {
                originalCallback.apply(this, arguments);
            }
        };
    }
    
    // 监听"关键词搜索"输入变化（带防抖）
    if (keywordWidget && skillWidget) {
        const originalKeywordCallback = keywordWidget.callback;
        
        keywordWidget.callback = async function(value) {
            console.log(`[${EXTENSION_NAME}] 关键词搜索:`, value);
            
            // 清除之前的定时器
            if (state.debounceTimer) {
                clearTimeout(state.debounceTimer);
            }
            
            state.debounceTimer = setTimeout(async () => {
                if (value && value.trim()) {
                    const searchText = value.trim();
                    const cache = getNodeCache(node);
                    
                    // 使用本地缓存的触发词
                    let matched = matchSkillByTrigger(searchText, cache.triggers, cache.weights);
                    
                    // 如果本地没有匹配且缓存已过期，尝试刷新
                    if (!matched && (Date.now() - cache.timestamp) > CACHE_TTL) {
                        console.log(`[${EXTENSION_NAME}] 缓存过期，尝试刷新...`);
                        const customPath = customPathWidget ? customPathWidget.value : "";
                        const result = await fetchSkills(node, customPath);
                        cache.triggers = result.triggers;
                        cache.weights = result.weights;
                        matched = matchSkillByTrigger(searchText, result.triggers, result.weights);
                    }
                    
                    // 如果找到匹配，自动选中
                    if (matched && matched.skill) {
                        const skillValues = skillWidget.options?.values || [];
                        if (skillValues.indexOf(matched.skill) >= 0) {
                            skillWidget.value = matched.skill;
                            console.log(`[${EXTENSION_NAME}] 自动选择: ${matched.skill}`);
                            node.setDirtyCanvas(true, true);
                            
                            if (app.ui?.toast) {
                                app.ui.toast({
                                    message: `已匹配: ${matched.skill} (${matched.matchedTags.join(', ')})`,
                                    type: "info"
                                });
                            }
                        }
                    }
                }
                
                state.debounceTimer = null;
            }, DEBOUNCE_DELAY);
            
            if (originalKeywordCallback) {
                originalKeywordCallback.apply(this, arguments);
            }
        };
    }
    
    console.log(`[${EXTENSION_NAME}] setupDynamicSkills 完成`);
}

// 注册ComfyUI扩展
app.registerExtension({
    name: EXTENSION_NAME,
    
    // 节点创建后调用
    nodeCreated(node) {
        const nodeName = node.type || node.comfyClass || "";
        if (nodeName === "Ecommerce_Skill_Router") {
            console.log(`[${EXTENSION_NAME}] 检测到 Ecommerce_Skill_Router 节点`);
            
            // 延迟执行，确保 widgets 已初始化
            setTimeout(() => {
                setupDynamicSkills(node);
            }, 100);
        }
    }
});

console.log(`[${EXTENSION_NAME}] 动态技能列表扩展已加载 (v2.1 优化版)`);
