import copy
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

    def reset_model(self, model, clip=None):
        # 1. Guard against missing CLIP
        # (e.g. modular UNet used with an AIO preset)
        if clip is None:
            raise ValueError(
                '[ModelPristineReset] CLIP is missing! This usually occurs when a modular '
                'model is selected with an All-In-One (AIO) preset. '
                'Please switch to a standard split preset (e.g. ZI-Turbo) or use an All-In-One base model.'
            )
        if model is None:
            raise ValueError('[ModelPristineReset] Error: MODEL input is missing from the workflow.')

        # 2. Roll back physical weight patches
        try:
            model.unpatch_model()
            if hasattr(clip, 'unpatch_model'):
                clip.unpatch_model()
        except Exception:
            pass

        # 3. GGUF Safety: Force buffer refresh
        if hasattr(model, 'weight_inplace_update'):
            model.weight_inplace_update = False
        if hasattr(clip, 'weight_inplace_update'):
            clip.weight_inplace_update = False

        # 4. Create fresh wrappers
        new_model = model.clone() if model is not None else None
        if new_model is not None:
            new_model.patch_list = []
            new_model.object_patches = {}
            new_model.weight_inplace_update = False

        # 5. Patch the returned CLIP clone
        new_clip = clip.clone() if clip is not None else None
        if new_clip is not None:
            if hasattr(new_clip, 'patch_list'):
                new_clip.patch_list = []
            new_clip.weight_inplace_update = False

        return (new_model, new_clip)



# Support for the VAE Sharpness UI slider control
class VAESharpnessPatch:
    @classmethod
    def INPUT_TYPES(s):
        return {
            'required': {
                'vae': ('VAE',),
                'sharpness': ('FLOAT', {'default': 0.0, 'min': -1.0, 'max': 1.0, 'step': 0.01}),
            }
        }

    RETURN_TYPES = ('VAE',)
    FUNCTION = 'patch'
    CATEGORY = 'model_patches'

    def patch(self, vae, sharpness=0.0):
        if sharpness == 0.0 or vae is None:
            return (vae,)

        new_vae = copy.copy(vae)
        orig_decode = vae.decode

        def patched_decode(samples_in):
            model = getattr(new_vae, 'first_stage_model', None)
            decoder = getattr(model, 'decoder', None) if model else None
            conv_out = getattr(decoder, 'conv_out', None) if decoder else None

            if conv_out is None or not hasattr(conv_out, 'weight'):
                print('[VAESharpnessPatch] Warning: conv_out not found in VAE model!')
                return orig_decode(samples_in)

            orig_weight = conv_out.weight.data.clone()
            W = conv_out.weight.data

            try:
                # True Zero-Sum Optical Unsharp Mask
                # (Energy delta = 0 across all channels)
                centre = orig_weight[:, :, 1, 1]
                delta = centre * sharpness

                # Full +4x centre peak:
                W[:, :, 1, 1] += delta * 4.0
                # -1x cardinal neighbours:
                W[:, :, 0, 1] -= delta * 1.0
                W[:, :, 2, 1] -= delta * 1.0
                W[:, :, 1, 0] -= delta * 1.0
                W[:, :, 1, 2] -= delta * 1.0

                return orig_decode(samples_in)

            finally:
                # Restore pristine weights in VRAM immediately after decode
                conv_out.weight.data.copy_(orig_weight)

        new_vae.decode = patched_decode
        return (new_vae,)


NODE_CLASS_MAPPINGS = {
    'ModelPristineReset': ModelPristineReset,
    'VAESharpnessPatch': VAESharpnessPatch
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'ModelPristineReset': 'Model Pristine Reset (FooocusPlus)',
    'VAESharpnessPatch': 'VAE Sharpness Patch (FooocusPlus)'
}