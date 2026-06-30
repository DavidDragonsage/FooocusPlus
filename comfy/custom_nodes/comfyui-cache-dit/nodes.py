"""
ComfyUI 缓存加速节点

这个文件定义了 ComfyUI 的自定义节点，用户可以通过这些节点在工作流中应用缓存加速。
基于增强版缓存引擎，支持多种缓存策略和配置选项。

新增功能：
- 缓存配置节点：支持多种策略和参数调整
- 缓存控制节点：动态启用/禁用缓存
- 增强统计节点：提供更详细的性能信息
"""

from .cache_engine import patch_model_simple, get_simple_stats, global_cache, CacheStrategy


class CacheDitAccelerateNode:
    """
    CacheDit 加速节点
    
    将缓存加速应用到 ComfyUI 模型，实现 2x+ 推理加速
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
            }
        }

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("加速模型",)
    FUNCTION = "accelerate_model"
    CATEGORY = "CacheDit"

    def accelerate_model(self, model):
        """
        应用缓存加速到模型
        
        Args:
            model: 输入的 ComfyUI 模型
            
        Returns:
            tuple: (加速后的模型,)
        """
        print("\n🚀 应用 CacheDit 加速...")
        
        # 应用缓存补丁
        accelerated_model = patch_model_simple(model)
        
        print("✓ CacheDit 加速已应用")
        return (accelerated_model,)


class CacheDitStatsNode:
    """
    CacheDit 统计节点
    
    显示缓存统计信息，包括命中率和预期加速比
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "trigger": ("*",),  # 接受任何类型作为触发器
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("统计信息",)
    FUNCTION = "get_stats"
    CATEGORY = "CacheDit"

    def get_stats(self, trigger):
        """
        获取缓存统计信息
        
        Args:
            trigger: 触发器（任何值）
            
        Returns:
            tuple: (统计信息字符串,)
        """
        stats = get_simple_stats()
        return (stats,)


class CacheDitConfigNode:
    """
    CacheDit 配置节点
    
    提供高级缓存配置选项，支持多种缓存策略和参数调整
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "strategy": (["fixed", "dynamic", "adaptive"], {"default": "fixed"}),
                "skip_interval": ("INT", {"default": 2, "min": 1, "max": 10, "step": 1}),
                "warmup_steps": ("INT", {"default": 3, "min": 0, "max": 20, "step": 1}),
            },
            "optional": {
                "noise_scale": ("FLOAT", {"default": 0.001, "min": 0.0, "max": 0.1, "step": 0.001}),
                "enable_debug": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("配置模型",)
    FUNCTION = "configure_cache"
    CATEGORY = "CacheDit"

    def configure_cache(self, model, strategy, skip_interval, warmup_steps, 
                       noise_scale=0.001, enable_debug=False):
        """
        配置并应用缓存加速到模型
        
        Args:
            model: 输入的 ComfyUI 模型
            strategy: 缓存策略类型
            skip_interval: 跳步间隔
            warmup_steps: 预热步数
            noise_scale: 噪声缩放因子
            enable_debug: 是否启用调试输出
            
        Returns:
            tuple: (配置后的模型,)
        """
        print(f"\n🔧 配置 CacheDit 加速...")
        print(f"   策略: {strategy}")
        print(f"   跳步间隔: {skip_interval}")
        print(f"   预热步数: {warmup_steps}")
        print(f"   噪声缩放: {noise_scale}")
        print(f"   调试模式: {enable_debug}")
        
        # 创建缓存策略
        cache_strategy = CacheStrategy(
            skip_interval=skip_interval,
            warmup_steps=warmup_steps,
            strategy_type=strategy,
            noise_scale=noise_scale,
            enable_stats=True,
            debug=enable_debug
        )
        
        # 应用缓存配置
        configured_model = global_cache.enable_cache(model, cache_strategy)
        
        print("✓ CacheDit 缓存配置已应用")
        return (configured_model,)


class CacheDitControlNode:
    """
    CacheDit 控制节点
    
    动态启用或禁用模型的缓存功能
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "enable_cache": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("控制模型",)
    FUNCTION = "control_cache"
    CATEGORY = "CacheDit"

    def control_cache(self, model, enable_cache):
        """
        控制模型的缓存启用状态
        
        Args:
            model: 输入的 ComfyUI 模型
            enable_cache: 是否启用缓存
            
        Returns:
            tuple: (控制后的模型,)
        """
        print(f"\n🎛 控制 CacheDit 缓存: {'启用' if enable_cache else '禁用'}")
        
        if enable_cache:
            # 启用缓存（使用默认策略）
            controlled_model = global_cache.enable_cache(model, CacheStrategy())
        else:
            # 禁用缓存
            global_cache.disable_cache(model)
            controlled_model = model
        
        print(f"✓ CacheDit 缓存已{'启用' if enable_cache else '禁用'}")
        return (controlled_model,)


class CacheDitDetailedStatsNode:
    """
    CacheDit 详细统计节点
    
    显示详细的缓存统计信息，包括多模型统计
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "trigger": ("*",),  # 接受任何类型作为触发器
            },
            "optional": {
                "show_model_details": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("详细统计",)
    FUNCTION = "get_detailed_stats"
    CATEGORY = "CacheDit"

    def get_detailed_stats(self, trigger, show_model_details=True):
        """
        获取详细的缓存统计信息
        
        Args:
            trigger: 触发器（任何值）
            show_model_details: 是否显示模型详情
            
        Returns:
            tuple: (详细统计信息字符串,)
        """
        if show_model_details:
            stats = global_cache.get_detailed_stats()
        else:
            stats = global_cache.get_stats()
        return (stats,)


# 节点映射
NODE_CLASS_MAPPINGS = {
    # 原有节点（保持向后兼容）
    "CacheDitAccelerate": CacheDitAccelerateNode,
    "CacheDitStats": CacheDitStatsNode,
    
    # 新增的增强节点
    "CacheDitConfig": CacheDitConfigNode,
    "CacheDitControl": CacheDitControlNode,
    "CacheDitDetailedStats": CacheDitDetailedStatsNode,
}

# 节点显示名称映射
NODE_DISPLAY_NAME_MAPPINGS = {
    # 原有节点
    "CacheDitAccelerate": "CacheDit 模型加速",
    "CacheDitStats": "CacheDit 统计信息",
    
    # 新增节点
    "CacheDitConfig": "CacheDit 高级配置",
    "CacheDitControl": "CacheDit 缓存控制",
    "CacheDitDetailedStats": "CacheDit 详细统计",
}