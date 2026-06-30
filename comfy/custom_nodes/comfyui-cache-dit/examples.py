"""
CacheDiT 使用示例

这个文件展示了如何使用 CacheDiT 插件的各种功能，包括：
1. 标准 CacheDiT API 使用方式
2. ComfyUI 节点使用方式  
3. 高级配置和自定义策略

运行前请确保已安装 ComfyUI 和相关依赖。
"""

# ======================================================================
# 示例 1: 标准 CacheDiT API 使用方式
# ======================================================================

def example_standard_api():
    """
    演示标准 CacheDiT API 的使用方法
    
    这种方式与原版 CacheDiT 完全兼容，可以直接替换现有代码。
    """
    print("=== 示例 1: 标准 CacheDiT API ===")
    
    # 假设您有一个模型（在实际使用中，这将是您的 ComfyUI 模型）
    # model = load_your_model()
    
    try:
        # 导入 CacheDiT API
        import cache_dit
        
        # 启用缓存（使用默认设置）
        print("1. 启用缓存（默认设置）")
        # cache_dit.enable_cache(model)
        
        # 启用缓存（自定义设置）
        print("2. 启用缓存（自定义设置）")
        # cache_dit.enable_cache(model, 
        #                       skip_interval=3,      # 每3步跳过1步
        #                       warmup_steps=5,       # 前5步预热
        #                       strategy='adaptive',  # 自适应策略
        #                       noise_scale=0.002)    # 噪声缩放
        
        # 运行推理
        print("3. 运行推理...")
        # result = run_inference(model, prompt)
        
        # 获取统计信息
        print("4. 获取统计信息")
        # stats = cache_dit.summary(model)
        # print(stats)
        
        # 禁用缓存
        print("5. 禁用缓存")
        # cache_dit.disable_cache(model)
        
        print("✓ 标准 API 示例完成")
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保插件正确安装到 ComfyUI 的 custom_nodes 目录")


# ======================================================================
# 示例 2: 高级配置和监控
# ======================================================================

def example_advanced_api():
    """
    演示高级 API 功能
    
    包括全局配置、详细统计、动态调整等功能。
    """
    print("\n=== 示例 2: 高级 API 功能 ===")
    
    try:
        import cache_dit
        
        # 设置全局配置
        print("1. 设置全局配置")
        # cache_dit.set_global_config(
        #     default_skip_interval=2,
        #     default_strategy='adaptive',
        #     global_debug=True
        # )
        
        # 启用多个模型的缓存
        print("2. 为多个模型启用缓存")
        # models = [model1, model2, model3]
        # for i, model in enumerate(models):
        #     cache_dit.enable_cache(model, 
        #                           skip_interval=2+i,  # 不同的策略
        #                           strategy='fixed')
        
        # 获取全局统计
        print("3. 获取全局统计")
        # global_stats = cache_dit.get_global_stats()
        # print(f"总缓存命中: {global_stats['total_cache_hits']}")
        # print(f"活跃模型数: {global_stats['active_models']}")
        
        # 重置统计信息
        print("4. 重置统计信息")
        # cache_dit.reset_cache_stats()
        
        print("✓ 高级 API 示例完成")
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")


# ======================================================================
# 示例 3: ComfyUI 节点使用指南
# ======================================================================

def example_comfyui_nodes():
    """
    演示 ComfyUI 节点的使用方法
    
    这是在 ComfyUI 工作流中使用缓存加速的推荐方式。
    """
    print("\n=== 示例 3: ComfyUI 节点使用 ===")
    
    workflow_example = """
    ComfyUI 工作流节点使用示例：
    
    基础用法：
    1. 加载模型 → CacheDit 模型加速 → 使用加速模型进行推理
    2. 任意触发器 → CacheDit 统计信息 → 查看性能数据
    
    高级用法：
    1. 加载模型 → CacheDit 高级配置 → 使用配置模型进行推理
       配置选项：
       - 策略: fixed/dynamic/adaptive
       - 跳步间隔: 1-10
       - 预热步数: 0-20
       - 噪声缩放: 0.0-0.1
       - 调试模式: True/False
    
    2. 配置模型 → CacheDit 缓存控制 → 动态启用/禁用缓存
    
    3. 任意触发器 → CacheDit 详细统计 → 查看详细性能分析
    
    推荐工作流：
    模型加载 → CacheDit 高级配置 → 推理节点 → CacheDit 详细统计
    """
    
    print(workflow_example)


# ======================================================================
# 示例 4: 性能对比测试
# ======================================================================

def example_performance_comparison():
    """
    演示如何进行性能对比测试
    
    比较启用和禁用缓存时的性能差异。
    """
    print("\n=== 示例 4: 性能对比测试 ===")
    
    test_code = '''
    import time
    import cache_dit
    
    # 假设您有一个模型和测试数据
    # model = load_your_model()
    # test_prompts = ["test prompt 1", "test prompt 2", ...]
    
    # 禁用缓存的基准测试
    print("进行基准测试（无缓存）...")
    cache_dit.disable_cache(model)
    
    start_time = time.time()
    for prompt in test_prompts:
        result = run_inference(model, prompt)
    baseline_time = time.time() - start_time
    
    print(f"基准时间: {baseline_time:.2f}秒")
    
    # 启用缓存的测试
    print("进行缓存测试...")
    cache_dit.enable_cache(model, skip_interval=2, warmup_steps=3)
    
    start_time = time.time()
    for prompt in test_prompts:
        result = run_inference(model, prompt)
    cached_time = time.time() - start_time
    
    print(f"缓存时间: {cached_time:.2f}秒")
    print(f"加速比: {baseline_time/cached_time:.2f}x")
    
    # 获取详细统计
    stats = cache_dit.summary(model)
    print(stats)
    '''
    
    print("性能对比测试代码示例：")
    print(test_code)


# ======================================================================
# 示例 5: 错误处理和调试
# ======================================================================

def example_debugging():
    """
    演示错误处理和调试技巧
    
    如何诊断和解决常见问题。
    """
    print("\n=== 示例 5: 错误处理和调试 ===")
    
    debugging_tips = """
    常见问题及解决方法：
    
    1. 模型无法找到 transformer 组件
       - 检查模型结构是否支持
       - 查看控制台输出的调试信息
       - 尝试不同的模型类型
    
    2. 缓存效果不明显
       - 检查缓存命中率统计
       - 调整跳步间隔和预热步数
       - 尝试不同的缓存策略
    
    3. 图像质量下降
       - 减小噪声缩放因子
       - 增加预热步数
       - 使用 adaptive 策略
    
    调试技巧：
    1. 启用调试模式：
       cache_dit.enable_cache(model, debug=True)
    
    2. 查看详细统计：
       stats = cache_dit.get_global_stats()
       
    3. 使用 ComfyUI 详细统计节点：
       添加 "CacheDit 详细统计" 节点到工作流
    
    4. 重置统计信息：
       cache_dit.reset_cache_stats()
    """
    
    print(debugging_tips)


# ======================================================================
# 主函数 - 运行所有示例
# ======================================================================

if __name__ == "__main__":
    print("CacheDiT 使用示例")
    print("================")
    
    # 运行所有示例
    example_standard_api()
    example_advanced_api()
    example_comfyui_nodes()
    example_performance_comparison()
    example_debugging()
    
    print("\n=== 所有示例演示完成 ===")
    print("更多信息请参考 README.md 和 API 文档")