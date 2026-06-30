# CacheDiT API 文档

本文档详细介绍了 CacheDiT 插件提供的所有 API 接口和 ComfyUI 节点。

## 🔌 标准 CacheDiT API

### 导入方式
```python
import cache_dit
```

### 核心 API

#### `enable_cache(model, **cache_options)`
为模型启用 CacheDiT 缓存加速。

**参数:**
- `model`: 模型对象（支持 ComfyUI ModelPatcher 和其他模型类型）
- `**cache_options`: 缓存配置选项
  - `skip_interval` (int): 跳步间隔，默认为 2（每隔一步跳过）
  - `warmup_steps` (int): 预热步数，默认为 3
  - `strategy` (str): 缓存策略，可选 'fixed', 'dynamic', 'adaptive'
  - `noise_scale` (float): 噪声缩放因子，默认 0.001
  - `enable_stats` (bool): 是否启用详细统计，默认 True
  - `debug` (bool): 是否启用调试输出，默认 False

**示例:**
```python
# 基础用法
cache_dit.enable_cache(model)

# 自定义配置
cache_dit.enable_cache(model, 
                      skip_interval=3, 
                      warmup_steps=5,
                      strategy='adaptive',
                      noise_scale=0.002,
                      debug=True)
```

#### `disable_cache(model)`
为模型禁用 CacheDiT 缓存。

**参数:**
- `model`: 之前应用了缓存的模型对象

**示例:**
```python
cache_dit.disable_cache(model)
```

#### `summary(model)`
获取模型的缓存统计摘要。

**参数:**
- `model`: 模型对象

**返回:**
- `str`: 格式化的统计信息字符串

**示例:**
```python
stats = cache_dit.summary(model)
print(stats)
```

### 扩展 API

#### `set_global_config(**config)`
设置全局缓存配置。

**参数:**
- `**config`: 全局配置选项
  - `default_skip_interval` (int): 默认跳步间隔
  - `default_warmup_steps` (int): 默认预热步数
  - `default_strategy` (str): 默认缓存策略
  - `global_debug` (bool): 全局调试模式

**示例:**
```python
cache_dit.set_global_config(
    default_skip_interval=3,
    default_strategy='adaptive',
    global_debug=True
)
```

#### `get_global_stats()`
获取全局缓存统计信息。

**返回:**
- `Dict[str, Any]`: 包含详细统计信息的字典

**示例:**
```python
stats = cache_dit.get_global_stats()
print(f"总缓存命中: {stats['total_cache_hits']}")
print(f"活跃模型数: {stats['active_models']}")
```

#### `reset_cache_stats()`
重置所有缓存统计信息。

**示例:**
```python
cache_dit.reset_cache_stats()
```

### API 别名
为了更好的兼容性，提供以下别名：
- `cache_dit.enable` → `cache_dit.enable_cache`
- `cache_dit.disable` → `cache_dit.disable_cache`
- `cache_dit.stats` → `cache_dit.summary`

## 🎛 ComfyUI 节点

### 基础节点（向后兼容）

#### CacheDit 模型加速
- **输入**: MODEL
- **输出**: 加速模型 (MODEL)
- **功能**: 使用默认设置应用缓存加速

#### CacheDit 统计信息
- **输入**: 触发器 (任意类型)
- **输出**: 统计信息 (STRING)
- **功能**: 显示基础缓存统计信息

### 高级节点（新功能）

#### CacheDit 高级配置
提供完整的缓存配置选项。

**输入参数:**
- `model` (MODEL): 输入模型
- `strategy` (选择): 缓存策略 - fixed/dynamic/adaptive
- `skip_interval` (整数): 跳步间隔 (1-10)
- `warmup_steps` (整数): 预热步数 (0-20)
- `noise_scale` (浮点): 噪声缩放 (0.0-0.1)
- `enable_debug` (布尔): 调试模式

**输出:**
- `配置模型` (MODEL): 应用配置后的模型

#### CacheDit 缓存控制
动态控制缓存的启用状态。

**输入参数:**
- `model` (MODEL): 输入模型
- `enable_cache` (布尔): 是否启用缓存

**输出:**
- `控制模型` (MODEL): 控制后的模型

#### CacheDit 详细统计
显示详细的多层级统计信息。

**输入参数:**
- `trigger` (任意): 触发器
- `show_model_details` (布尔): 是否显示模型详情

**输出:**
- `详细统计` (STRING): 详细统计信息

## 📊 统计信息格式

### 基础统计
```
缓存统计信息:
总 Forward 调用: 20
缓存命中: 8
缓存命中率: 40.0%
平均计算时间: 0.150秒
预期加速比: 2.0x
```

### 详细统计
```
=== CacheDiT 详细统计 ===
全局统计:
  总 Forward 调用: 50
  总缓存命中: 20
  全局命中率: 40.0%
  平均计算时间: 0.145秒
  预期加速比: 2.0x
  活跃模型数: 2

模型详情:
  模型 ModelPatcher_140234...:
    调用次数: 30
    缓存命中: 12
    命中率: 40.0%
    平均耗时: 0.140s
    策略: fixed
    状态: 启用

  模型 ModelPatcher_140235...:
    调用次数: 20
    缓存命中: 8
    命中率: 40.0%
    平均耗时: 0.155s
    策略: adaptive
    状态: 启用
```

### 全局统计字典格式
```python
{
    'total_calls': 50,
    'total_cache_hits': 20,
    'global_hit_rate': 40.0,
    'average_compute_time': 0.145,
    'expected_speedup': 2.0,
    'active_models': 2,
    'model_details': {
        'model_id_1': {
            'calls': 30,
            'hits': 12,
            'hit_rate': 40.0,
            'avg_time': 0.140,
            'strategy': 'fixed',
            'enabled': True
        },
        # ... 更多模型
    }
}
```

## 🧠 缓存策略详解

### Fixed Strategy (固定策略)
```python
cache_dit.enable_cache(model, strategy='fixed', skip_interval=2)
```
- 按固定间隔跳过计算
- 预热后每 N 步跳过 1 步
- 最简单可靠的策略

### Dynamic Strategy (动态策略)
```python
cache_dit.enable_cache(model, strategy='dynamic', skip_interval=2)
```
- 随着步数增加，跳步频率提高
- 适合长序列推理
- 自动优化性能表现

### Adaptive Strategy (自适应策略)
```python
cache_dit.enable_cache(model, strategy='adaptive', skip_interval=2)
```
- 根据性能监控自动调整
- 智能优化缓存策略
- 最佳的性能表现（实验性）

## 🔧 配置建议

### 不同场景的推荐配置

#### 快速原型验证
```python
cache_dit.enable_cache(model)  # 使用默认设置
```

#### 生产环境优化
```python
cache_dit.enable_cache(model, 
                      strategy='adaptive',
                      skip_interval=2,
                      warmup_steps=5,
                      noise_scale=0.001)
```

#### 调试和分析
```python
cache_dit.enable_cache(model,
                      debug=True,
                      enable_stats=True)
```

#### 批量处理优化
```python
cache_dit.enable_cache(model,
                      strategy='dynamic',
                      skip_interval=3,
                      warmup_steps=2)
```

## ⚠️ 注意事项

1. **模型兼容性**: 主要支持基于 transformer 架构的模型
2. **质量权衡**: 噪声缩放因子影响生成质量，建议在 0.001-0.01 之间
3. **内存使用**: 缓存会占用额外的显存来存储中间结果
4. **并发限制**: 每个模型实例只能应用一次缓存
5. **策略选择**: 不同策略适合不同场景，建议先测试后部署

## 🆘 故障排查

### 常见错误码和解决方案

#### 找不到 transformer 组件
```
❌ 未能找到 transformer 组件
```
**解决方案**: 检查模型类型，确保使用支持的模型架构

#### 重复缓存应用
```
⚠ 模型已经应用过缓存
```
**解决方案**: 先调用 `disable_cache()` 再重新配置

#### 导入失败
```
ModuleNotFoundError: No module named 'cache_dit'
```
**解决方案**: 确保插件正确安装到 ComfyUI 的 custom_nodes 目录

### 调试技巧

1. **启用调试模式**
   ```python
   cache_dit.enable_cache(model, debug=True)
   ```

2. **查看详细日志**
   ```python
   stats = cache_dit.get_global_stats()
   print(stats)
   ```

3. **重置统计重新测试**
   ```python
   cache_dit.reset_cache_stats()
   ```

4. **使用 ComfyUI 详细统计节点**
   添加 "CacheDit 详细统计" 节点查看实时状态