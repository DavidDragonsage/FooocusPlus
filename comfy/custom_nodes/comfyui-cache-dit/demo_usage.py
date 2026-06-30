#!/usr/bin/env python3
"""
CacheDiT API 使用演示

这个脚本演示了如何使用新的 CacheDiT API，无需实际的 torch/ComfyUI 环境。
展示了 API 的基本调用方式和预期行为。

在实际使用中，请确保有完整的 ComfyUI 和 torch 环境。
"""

class MockModel:
    """模拟 ComfyUI 模型用于演示"""
    def __init__(self, name):
        self.name = name
        self.model = self
        self.diffusion_model = self
        
    def __repr__(self):
        return f"MockModel({self.name})"


def demo_standard_api():
    """演示标准 CacheDiT API 用法"""
    print("=" * 50)
    print("标准 CacheDiT API 演示")
    print("=" * 50)
    
    # 模拟模型
    model = MockModel("FLUX-Model")
    print(f"创建模型: {model}")
    
    # 演示 API 调用（实际使用时取消注释）
    api_demo = '''
    # 导入 CacheDiT API
    import cache_dit
    
    # 1. 启用缓存（基础用法）
    cache_dit.enable_cache(model)
    print("✓ 缓存已启用（默认设置）")
    
    # 2. 启用缓存（高级配置）
    cache_dit.enable_cache(model, 
                          skip_interval=3,        # 每3步跳过1步
                          warmup_steps=5,         # 前5步预热
                          strategy='adaptive',    # 自适应策略
                          noise_scale=0.002,      # 噪声缩放
                          debug=True)             # 启用调试
    print("✓ 缓存已启用（自定义配置）")
    
    # 3. 运行推理
    # result = your_inference_function(model, prompt)
    print("✓ 推理完成（模拟）")
    
    # 4. 获取统计信息
    stats = cache_dit.summary(model)
    print(f"统计信息:\\n{stats}")
    
    # 5. 获取全局统计
    global_stats = cache_dit.get_global_stats()
    print(f"全局统计: {global_stats}")
    
    # 6. 禁用缓存
    cache_dit.disable_cache(model)
    print("✓ 缓存已禁用")
    '''
    
    print("API 调用示例:")
    print(api_demo)


def demo_comfyui_nodes():
    """演示 ComfyUI 节点用法"""
    print("=" * 50)
    print("ComfyUI 节点演示")
    print("=" * 50)
    
    node_demo = '''
    ComfyUI 工作流节点使用：
    
    基础工作流：
    [加载模型] → [CacheDit 模型加速] → [推理节点] → [CacheDit 统计信息]
    
    高级工作流：
    [加载模型] → [CacheDit 高级配置] → [推理节点] → [CacheDit 详细统计]
                       ↓
                 [CacheDit 缓存控制] (可选的动态控制)
    
    节点配置示例：
    
    1. CacheDit 高级配置节点：
       - 策略: adaptive
       - 跳步间隔: 3
       - 预热步数: 5
       - 噪声缩放: 0.001
       - 调试模式: False
    
    2. CacheDit 缓存控制节点：
       - 启用缓存: True/False
    
    3. CacheDit 详细统计节点：
       - 显示模型详情: True
    '''
    
    print(node_demo)


def demo_performance_comparison():
    """演示性能对比方法"""
    print("=" * 50)
    print("性能对比演示")
    print("=" * 50)
    
    perf_demo = '''
    性能测试代码示例：
    
    import time
    import cache_dit
    
    # 假设的性能数据
    baseline_times = [0.8, 0.9, 0.85, 0.88, 0.92]  # 无缓存
    cached_times = [0.8, 0.9, 0.85, 0.45, 0.46]    # 有缓存（前3步预热）
    
    baseline_avg = sum(baseline_times) / len(baseline_times)
    cached_avg = sum(cached_times) / len(cached_times)
    speedup = baseline_avg / cached_avg
    
    print(f"基准平均时间: {baseline_avg:.3f}秒")
    print(f"缓存平均时间: {cached_avg:.3f}秒")
    print(f"加速比: {speedup:.2f}x")
    
    # 缓存命中率计算
    warmup_steps = 3
    total_steps = len(cached_times)
    potential_hits = max(0, total_steps - warmup_steps)
    cache_hit_rate = (potential_hits / total_steps) * 100
    
    print(f"缓存命中率: {cache_hit_rate:.1f}%")
    '''
    
    print("性能对比方法:")
    print(perf_demo)
    
    # 模拟统计结果
    print("\n模拟的统计结果:")
    mock_stats = '''
    缓存统计信息:
    总 Forward 调用: 20
    缓存命中: 8
    缓存命中率: 40.0%
    平均计算时间: 0.650秒
    预期加速比: 2.0x
    '''
    print(mock_stats)


def demo_advanced_features():
    """演示高级特性"""
    print("=" * 50)
    print("高级特性演示")
    print("=" * 50)
    
    advanced_demo = '''
    高级特性使用：
    
    1. 全局配置管理：
    cache_dit.set_global_config(
        default_skip_interval=3,
        default_strategy='adaptive',
        global_debug=True
    )
    
    2. 多模型管理：
    models = [flux_model, sd_model, other_model]
    for i, model in enumerate(models):
        cache_dit.enable_cache(model, 
                              skip_interval=2+i,
                              strategy=['fixed', 'dynamic', 'adaptive'][i])
    
    3. 详细监控：
    global_stats = cache_dit.get_global_stats()
    for model_id, details in global_stats['model_details'].items():
        print(f"模型 {model_id}: 命中率 {details['hit_rate']:.1f}%")
    
    4. 统计重置：
    cache_dit.reset_cache_stats()  # 重新开始统计
    
    5. 调试模式：
    cache_dit.enable_cache(model, debug=True)  # 查看详细日志
    '''
    
    print("高级特性:")
    print(advanced_demo)


def main():
    """主演示函数"""
    print("CacheDiT API 使用演示")
    print("版本: 1.0.0 (API 兼容)")
    print("支持标准 CacheDiT API + ComfyUI 节点")
    
    demo_standard_api()
    demo_comfyui_nodes()
    demo_performance_comparison()
    demo_advanced_features()
    
    print("=" * 50)
    print("演示完成")
    print("=" * 50)
    print("更多信息:")
    print("- 查看 README.md 了解详细使用方法")
    print("- 查看 API.md 了解完整 API 文档")
    print("- 查看 examples.py 了解更多示例")
    print("- 在 ComfyUI 中添加相应节点开始使用")


if __name__ == "__main__":
    main()