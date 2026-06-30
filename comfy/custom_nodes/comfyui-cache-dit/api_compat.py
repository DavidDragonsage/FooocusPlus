"""
CacheDiT API 兼容层

这个模块提供标准的 CacheDiT API 接口，同时保持对 ComfyUI ModelPatcher 架构的完美适配。
支持原版 CacheDiT 的所有 API 调用方式：

```python
import cache_dit
cache_dit.enable_cache(model, skip_interval=2, warmup_steps=3)
cache_dit.disable_cache(model) 
cache_dit.summary(model)
```

内部使用增强版的缓存引擎，提供更灵活的配置选项和详细的性能统计。
"""

from .cache_engine import global_cache, CacheStrategy
from typing import Optional, Dict, Any, Union
import warnings


def enable_cache(model, **cache_options) -> None:
    """
    为模型启用 CacheDiT 缓存加速
    
    这是标准的 CacheDiT API 入口点，与原版 API 完全兼容。
    支持多种缓存策略和配置选项。
    
    Args:
        model: 模型对象（支持 ComfyUI ModelPatcher 和其他模型类型）
        **cache_options: 缓存配置选项
            - skip_interval (int): 跳步间隔，默认为 2（每隔一步跳过）
            - warmup_steps (int): 预热步数，默认为 3
            - strategy (str): 缓存策略，可选 'fixed', 'dynamic', 'adaptive'
            - noise_scale (float): 噪声缩放因子，默认 0.001
            - enable_stats (bool): 是否启用详细统计，默认 True
            - debug (bool): 是否启用调试输出，默认 False
    
    Example:
        ```python
        import cache_dit
        
        # 基础用法
        cache_dit.enable_cache(model)
        
        # 自定义配置
        cache_dit.enable_cache(model, 
                              skip_interval=3, 
                              warmup_steps=5,
                              strategy='adaptive')
        ```
    """
    print(f"\n🚀 启用 CacheDiT 加速 (API 兼容模式)")
    
    # 设置默认配置
    default_options = {
        'skip_interval': 2,
        'warmup_steps': 3,
        'strategy': 'fixed',
        'noise_scale': 0.001,
        'enable_stats': True,
        'debug': False
    }
    
    # 合并用户配置
    config = {**default_options, **cache_options}
    
    # 创建缓存策略
    strategy = CacheStrategy(
        skip_interval=config['skip_interval'],
        warmup_steps=config['warmup_steps'],
        strategy_type=config['strategy'],
        noise_scale=config['noise_scale'],
        enable_stats=config['enable_stats'],
        debug=config['debug']
    )
    
    print(f"   配置: {config}")
    
    # 应用缓存到模型
    global_cache.enable_cache(model, strategy)
    
    print("✓ CacheDiT 缓存已启用")


def disable_cache(model) -> None:
    """
    为模型禁用 CacheDiT 缓存
    
    恢复模型的原始行为，移除所有缓存相关的修改。
    这是标准的 CacheDiT API 接口。
    
    Args:
        model: 之前应用了缓存的模型对象
        
    Example:
        ```python
        import cache_dit
        
        # 禁用缓存
        cache_dit.disable_cache(model)
        ```
    """
    print(f"\n🛑 禁用 CacheDiT 缓存 (API 兼容模式)")
    
    # 通过全局缓存管理器禁用缓存
    global_cache.disable_cache(model)
    
    print("✓ CacheDiT 缓存已禁用")


def summary(model) -> str:
    """
    获取模型的缓存统计摘要
    
    返回详细的缓存性能统计信息，包括命中率、加速比等。
    这是标准的 CacheDiT API 接口。
    
    Args:
        model: 模型对象
        
    Returns:
        str: 格式化的统计信息字符串
        
    Example:
        ```python
        import cache_dit
        
        # 获取统计信息
        stats = cache_dit.summary(model)
        print(stats)
        ```
    """
    print(f"\n📊 获取 CacheDiT 统计摘要 (API 兼容模式)")
    
    # 获取全局统计信息
    stats = global_cache.get_detailed_stats()
    
    return stats


def set_global_config(**config) -> None:
    """
    设置全局缓存配置
    
    影响后续所有 enable_cache 调用的默认行为。
    这是扩展的 API，提供更灵活的全局配置管理。
    
    Args:
        **config: 全局配置选项
            - default_skip_interval (int): 默认跳步间隔
            - default_warmup_steps (int): 默认预热步数
            - default_strategy (str): 默认缓存策略
            - global_debug (bool): 全局调试模式
            
    Example:
        ```python
        import cache_dit
        
        # 设置全局配置
        cache_dit.set_global_config(
            default_skip_interval=3,
            default_strategy='adaptive',
            global_debug=True
        )
        ```
    """
    print(f"\n⚙️ 设置 CacheDiT 全局配置")
    print(f"   配置项: {config}")
    
    global_cache.set_global_config(config)
    
    print("✓ 全局配置已更新")


def get_global_stats() -> Dict[str, Any]:
    """
    获取全局缓存统计信息
    
    返回包含所有模型缓存统计的详细信息字典。
    这是扩展的 API，用于高级监控和调试。
    
    Returns:
        Dict[str, Any]: 包含详细统计信息的字典
        
    Example:
        ```python
        import cache_dit
        
        # 获取全局统计
        stats = cache_dit.get_global_stats()
        print(f"总缓存命中: {stats['total_cache_hits']}")
        ```
    """
    return global_cache.get_global_stats()


def reset_cache_stats() -> None:
    """
    重置所有缓存统计信息
    
    清零所有计数器和性能指标，用于重新开始统计。
    这是扩展的 API，用于调试和测试。
    
    Example:
        ```python
        import cache_dit
        
        # 重置统计
        cache_dit.reset_cache_stats()
        ```
    """
    print(f"\n🔄 重置 CacheDiT 统计信息")
    
    global_cache.reset_stats()
    
    print("✓ 统计信息已重置")


# 兼容性别名 - 支持不同的导入方式
enable = enable_cache
disable = disable_cache
stats = summary

# 版本信息
__version__ = "1.0.0"
__api_version__ = "compatible"

# 导出的公共接口
__all__ = [
    'enable_cache',
    'disable_cache', 
    'summary',
    'set_global_config',
    'get_global_stats',
    'reset_cache_stats',
    # 别名
    'enable',
    'disable',
    'stats'
]