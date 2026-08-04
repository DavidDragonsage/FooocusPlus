"""
Streamlined FooocusPlus Loader for Z-Image Text Encoders.
Only registers the essential Z-Image nodes to keep startup clean.
"""
from .nodes.z_image_encoder import ZImageTextEncoder, ZImageTextEncoderSimple, ZImageTurnBuilder

NODE_CLASS_MAPPINGS = {
    'ZImageTextEncoder': ZImageTextEncoder,
    'ZImageTextEncoderSimple': ZImageTextEncoderSimple,
    'ZImageTurnBuilder': ZImageTurnBuilder
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'ZImageTextEncoder': 'Z-Image Text Encoder',
    'ZImageTextEncoderSimple': 'Z-Image Text Encoder (Simple)',
    'ZImageTurnBuilder': 'Z-Image Turn Builder'
}
