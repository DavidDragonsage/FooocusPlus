"""
ComfyUI CacheDit 加速插件

基于增强版缓存引擎实现 diffusion 模型推理加速，支持标准 CacheDiT API。
在 FLUX 等模型上测试有效，能实现约 2x 加速效果。

使用方式：

## ComfyUI 节点方式
在 ComfyUI 工作流中添加 CacheDit 节点

## 标准 API 方式  
```python
import cache_dit
cache_dit.enable_cache(model)
cache_dit.disable_cache(model)
cache_dit.summary(model)
```
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# 导出标准 CacheDiT API
from . import api_compat as cache_dit

# 为了支持 `import cache_dit` 语法，将 api_compat 模块作为 cache_dit 导出
__all__ = [
    'NODE_CLASS_MAPPINGS', 
    'NODE_DISPLAY_NAME_MAPPINGS',
    'cache_dit'  # 标准 API 接口
]