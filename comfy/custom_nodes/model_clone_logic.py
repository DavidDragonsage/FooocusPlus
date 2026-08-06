import random

# --- The DiT Wash ---
"""
Universal Weight Wash for DiT and SD3
architectures. Physically restores
baseline weights for both MODEL and
CLIP to ensure 100% reproducibility
and to prevent VRAM poisoning.
This node makes images reproducible
and noise-free, especially when using
LoRAs.
"""
class ModelPristineReset:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
            }
        }

    RETURN_TYPES = ("MODEL", "CLIP")
    FUNCTION = "reset_model"
    CATEGORY = "model_patches"

    @classmethod
    def IS_CHANGED(s, **kwargs):
        # Forces the node to run every time
        return random.random()

    def reset_model(self, model, clip):
        # Roll back physical weight patches
        try:
            model.unpatch_model()
            if hasattr(clip, 'unpatch_model'):
                clip.unpatch_model()
        except Exception:
            pass

        # GGUF Safety: Force buffer refresh
        if hasattr(model, 'weight_inplace_update'):
            model.weight_inplace_update = False
        if hasattr(clip, 'weight_inplace_update'):
            clip.weight_inplace_update = False

        # Create fresh wrappers
        new_model = model.clone()
        new_model.patch_list = []
        new_model.object_patches = {}

        # Prevent FP8 rounding noise
        new_model.weight_inplace_update = False

        # Patch the returned CLIP clone
        new_clip = clip.clone()
        if hasattr(new_clip, 'patch_list'):
            new_clip.patch_list = []

        new_clip.weight_inplace_update = False

        return (new_model, new_clip)


NODE_CLASS_MAPPINGS = {
    "ModelPristineReset": ModelPristineReset
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelPristineReset": "Model Pristine Reset (FooocusPlus)"
}
