import sys
from pathlib import Path

# Resolve the repository root dynamically (4 levels up) and add it to sys.path
repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Import neutral variables exchange module and standard Comfy loaders
import common
import folder_paths

# --- Dynamic Path Resolution Block ---
diffusers_dir = None
models_root = None

# 1. Primary Path Resolution: Read ComfyUI's extra_model_paths.yaml directly
yaml_path = repo_root / 'comfy' / 'extra_model_paths.yaml'
if yaml_path.exists():
    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f)
        comfyui_paths = yaml_data.get('comfyui', {})

        # Read the exact absolute diffusers path written by modules.config
        raw_diffusers = comfyui_paths.get('diffusers')
        if raw_diffusers:
            diffusers_dir = Path(raw_diffusers).resolve()

        # Read the exact absolute models root path
        raw_models_root = comfyui_paths.get('models_root')
        if raw_models_root:
            models_root = Path(raw_models_root).resolve()
    except Exception as e:
        print(f"[nodes.py] Warning: Could not parse extra_model_paths.yaml: {e}")

# 2. Fallback Path Resolution: Fall back to common variables
if not diffusers_dir:
    if getattr(common, 'path_diffusers', None):
        diffusers_dir = Path(common.path_diffusers).resolve()
    else:
        # Standard repository UserDir fallback structure
        diffusers_dir = (repo_root / 'UserDir' / 'models' / 'diffusers').resolve()

if not models_root:
    models_root = diffusers_dir.parent

# Register the "llms" checkpoints folder in the correct user-configured path
llms_path = models_root / 'llms' / 'checkpoints'
folder_paths.add_model_folder_path('llms', str(llms_path))
# -------------------------------------

import torch
import random
import re
import gc
import json
import psutil
import types  # added for Transformers patch
import comfy.model_management as mm
from comfy.utils import ProgressBar, load_torch_file

from .kolors.pipelines.pipeline_stable_diffusion_xl_chatglm_256 import StableDiffusionXLPipeline
from .kolors.models.modeling_chatglm import ChatGLMModel, ChatGLMConfig
from .kolors.models.tokenization_chatglm import ChatGLMTokenizer
from diffusers import UNet2DConditionModel
from diffusers import (DPMSolverMultistepScheduler,
        EulerDiscreteScheduler,
        EulerAncestralDiscreteScheduler,
        DEISMultistepScheduler,
        UniPCMultistepScheduler
)

from contextlib import nullcontext
try:
    from accelerate import init_empty_weights
    from accelerate.utils import set_module_tensor_to_device
    is_accelerate_available = True
except:
    pass
from comfy.utils import ProgressBar


import logging
import warnings

# 1. Mute standard Python UserWarnings and
# FutureWarnings (e.g. upscaling.py and autocast)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# 2. Intercept and silence the legacy UNet
# key mapping outputs globally in ComfyUI
# with recursion guard
if not getattr(logging.Logger,
    '__fooocus_logger_patched__', False):
    logging.Logger.__fooocus_logger_patched__ = True

    _orig_logger_warning = logging.Logger.warning
    def _safe_logger_warning(self, msg, *args, **kwargs):
        msg_str = str(msg)
        noise_keywords = [
            'load_unet_state_dict', 'skip_connection', 'resnets', 'conv_shortcut',
            'down_blocks', 'up_blocks', 'label_emb', 'class_embedding', 'cudaLaunchKernel'
        ]
        if any(kw in msg_str for kw in noise_keywords):
            return
        _orig_logger_warning(self, msg, *args, **kwargs)

    logging.Logger.warning = _safe_logger_warning



def patch_kolors_tokenizer(tokenizer):
    """
    Runtime hotfix for ChatGLM3 tokenizer to prevent
    'padding_side' TypeError under newer versions
    of the Hugging Face transformers library.
    """
    if hasattr(tokenizer, '_pad'):
        class_name = type(tokenizer).__name__
        if 'ChatGLM' in class_name:
            original_pad = tokenizer._pad
            # Prevent infinite recursion if already patched
            if not getattr(original_pad, '__wrapped_for_padding_side__', False):
                import types
                def wrapped_pad(self, *args, padding_side=None, **kwargs):
                    return original_pad(*args, **kwargs)
                wrapped_pad.__wrapped_for_padding_side__ = True
                tokenizer._pad = types.MethodType(wrapped_pad, tokenizer)
    return tokenizer


class DownloadAndLoadKolorsModel:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "model": (
                    [
                    'Kwai-Kolors/Kolors',
                    ],
                    ),
            "precision": ([ 'fp16'],
                    {
                    "default": 'fp16'
                    }),
            },
        }

    RETURN_TYPES = ("KOLORSMODEL",)
    RETURN_NAMES = ("kolors_model",)
    FUNCTION = "loadmodel"
    CATEGORY = "KwaiKolorsWrapper"

    def loadmodel(self, model, precision):
        device = mm.get_torch_device()
        offload_device = mm.unet_offload_device()
        dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[precision]

        pbar = ProgressBar(4)

        model_name = model.rsplit('/', 1)[-1]

        # Point to the dynamically resolved global diffusers directory
        model_path = diffusers_dir / model_name

        if not model_path.exists():
            print(f"Downloading Kolor model to: {model_path}")
            from huggingface_hub import snapshot_download
            snapshot_download(repo_id=model,
                            allow_patterns=['*fp16.safetensors*', '*.json'],
                            ignore_patterns=['vae/*', 'text_encoder/*', 'tokenizer/*'],
                            local_dir=str(model_path),
                            local_dir_use_symlinks=False)
        pbar.update(1)

        ram_rss_start = psutil.Process().memory_info().rss
        scheduler = EulerDiscreteScheduler.from_pretrained(str(model_path), subfolder='scheduler')

        print(f'Load UNET...')
        unet = UNet2DConditionModel.from_pretrained(str(model_path), subfolder='unet', variant='fp16', revision=None, low_cpu_mem_usage=True).to(dtype).eval()
        ram_rss_end = psutil.Process().memory_info().rss
        print(f'Kolors-unet: RAM allocated = {(ram_rss_end-ram_rss_start)/(1024*1024*1024):.3f}GB')
        pipeline = StableDiffusionXLPipeline(
                unet=unet,
                scheduler=scheduler,
                )

        kolors_model = {
            'pipeline': pipeline,
            'dtype': dtype
            }

        return (kolors_model,)

class LoadChatGLM3:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "chatglm3_checkpoint": (folder_paths.get_filename_list("llms"),),
            },
        }

    RETURN_TYPES = ("CHATGLM3MODEL",)
    RETURN_NAMES = ("chatglm3_model",)
    FUNCTION = "loadmodel"
    CATEGORY = "KwaiKolorsWrapper"

    def loadmodel(self, chatglm3_checkpoint):
        device=mm.get_torch_device()
        offload_device=mm.unet_offload_device()
        print(f'chatglm3: device={device}, offload_device={offload_device}')

        pbar = ProgressBar(2)
        chatglm3_path = folder_paths.get_full_path("llms", chatglm3_checkpoint)
        print("Load TEXT_ENCODER...")
        text_encoder_config = script_directory / 'configs' / 'text_encoder_config.json'
        with open(text_encoder_config, 'r') as file:
            text_config = json.load(file)

        text_encoder_config = ChatGLMConfig(**text_config)
        with (init_empty_weights() if is_accelerate_available else nullcontext()):
            text_encoder = ChatGLMModel(text_encoder_config)
            if '4bit' in chatglm3_checkpoint:
                text_encoder.quantize(4)
            elif '8bit' in chatglm3_checkpoint:
                text_encoder.quantize(8)

        text_encoder_sd = load_torch_file(chatglm3_path)

        if is_accelerate_available:
            for key in text_encoder_sd:
                set_module_tensor_to_device(text_encoder, key, device=offload_device, value=text_encoder_sd[key])
        else:
            text_encoder.load_state_dict()

        tokenizer_path = script_directory / 'configs' / 'tokenizer'
        tokenizer = ChatGLMTokenizer.from_pretrained(str(tokenizer_path))
        pbar.update(1)

        chatglm3_model = {
            'text_encoder': text_encoder,
            'tokenizer': tokenizer
            }

        return (chatglm3_model,)

class DownloadAndLoadChatGLM3:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "precision": ([ 'fp16', 'quant4', 'quant8'],
                    {
                    "default": 'fp16'
                    }),
            },
        }

    RETURN_TYPES = ("CHATGLM3MODEL",)
    RETURN_NAMES = ("chatglm3_model",)
    FUNCTION = "loadmodel"
    CATEGORY = "KwaiKolorsWrapper"

    def loadmodel(self, precision):

        pbar = ProgressBar(2)
        model = "Kwai-Kolors/Kolors"
        model_name = model.rsplit('/', 1)[-1]

        # Point to the dynamically resolved global diffusers directory
        model_path = diffusers_dir / model_name
        text_encoder_path = model_path / 'text_encoder'

        if not text_encoder_path.exists():
            print(f"Downloading ChatGLM3 to: {text_encoder_path}")
            from huggingface_hub import snapshot_download
            snapshot_download(repo_id=model,
                            allow_patterns=['text_encoder/*'],
                            ignore_patterns=['*.py', '*.pyc'],
                            local_dir=str(model_path),
                            local_dir_use_symlinks=False)

        pbar.update(1)

        ram_rss_start = psutil.Process().memory_info().rss
        device = mm.get_torch_device()
        offload_device = mm.unet_offload_device()
        print(f"Load TEXT_ENCODER..., {precision}, {offload_device}")
        text_encoder = ChatGLMModel.from_pretrained(
            str(text_encoder_path),
            torch_dtype=torch.float16
            ).to(offload_device)
        if precision == 'quant8':
            text_encoder.quantize(8)
        elif precision == 'quant4':
            text_encoder.quantize(4)

        tokenizer = ChatGLMTokenizer.from_pretrained(str(text_encoder_path))
        pbar.update(1)

        chatglm3_model = {
            'text_encoder': text_encoder,
            'tokenizer': tokenizer
            }
        ram_rss_end = psutil.Process().memory_info().rss
        print(f'chatglm3: RAM allocated = {(ram_rss_end-ram_rss_start)/(1024*1024*1024):.3f}GB')
        return (chatglm3_model,)

class KolorsTextEncode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "chatglm3_model": ("CHATGLM3MODEL", ),
                "prompt": ("STRING", {"multiline": True, "default": "",}),
                "negative_prompt": ("STRING", {"multiline": True, "default": "",}),
                "num_images_per_prompt": ("INT", {"default": 1, "min": 1, "max": 128, "step": 1}),
            },
        }

    RETURN_TYPES = ("KOLORS_EMBEDS",)
    RETURN_NAMES = ("kolors_embeds",)
    FUNCTION = "encode"
    CATEGORY = "KwaiKolorsWrapper"

    def encode(self, chatglm3_model, prompt, negative_prompt, num_images_per_prompt):
        device = mm.get_torch_device()
        offload_device = mm.unet_offload_device()
        mm.unload_all_models()
        mm.soft_empty_cache()
         # Function to randomly select an option from the brackets
        def choose_random_option(match):
            options = match.group(1).split('|')
            return random.choice(options)

        # Randomly choose between options in brackets for prompt and negative_prompt
        prompt = re.sub(r'\{([^{}]*)\}', choose_random_option, prompt)
        negative_prompt = re.sub(r'\{([^{}]*)\}', choose_random_option, negative_prompt)

        if "|" in prompt:
            prompt = prompt.split("|")
            negative_prompt = [negative_prompt] * len(prompt)  # Replicate negative_prompt to match length of prompt list


        print(prompt)
        do_classifier_free_guidance = True

        if prompt is not None and isinstance(prompt, str):
            batch_size = 1
        elif prompt is not None and isinstance(prompt, list):
            batch_size = len(prompt)

        # Define tokenizers and text encoders
        tokenizer = chatglm3_model['tokenizer']

        # ---> THE TRANSFORMERS PATCH LINE <---
        tokenizer = patch_kolors_tokenizer(tokenizer)

        text_encoder = chatglm3_model['text_encoder']

        text_encoder.to(device)

        text_inputs = tokenizer(
            prompt,
            padding="max_length",
            max_length=256,
            truncation=True,
            return_tensors="pt",
        ).to(device)

        output = text_encoder(
                input_ids=text_inputs['input_ids'] ,
                attention_mask=text_inputs['attention_mask'],
                position_ids=text_inputs['position_ids'],
                output_hidden_states=True)

        prompt_embeds = output.hidden_states[-2].permute(1, 0, 2).clone() # [batch_size, 77, 4096]
        text_proj = output.hidden_states[-1][-1, :, :].clone() # [batch_size, 4096]
        bs_embed, seq_len, _ = prompt_embeds.shape
        prompt_embeds = prompt_embeds.repeat(1, num_images_per_prompt, 1)
        prompt_embeds = prompt_embeds.view(bs_embed * num_images_per_prompt, seq_len, -1)


        if do_classifier_free_guidance:
            uncond_tokens = []
            if negative_prompt is None:
                uncond_tokens = [""] * batch_size
            elif prompt is not None and type(prompt) is not type(negative_prompt):
                raise TypeError(
                    f"`negative_prompt` should be the same type to `prompt`, but got {type(negative_prompt)} !="
                    f" {type(prompt)}."
                )
            elif isinstance(negative_prompt, str):
                uncond_tokens = [negative_prompt]
            elif batch_size != len(negative_prompt):
                raise ValueError(
                    f"`negative_prompt`: {negative_prompt} has batch size {len(negative_prompt)}, but `prompt`:"
                    f" {prompt} has batch size {batch_size}. Please make sure that passed `negative_prompt` matches"
                    " the batch size of `prompt`."
                )
            else:
                uncond_tokens = negative_prompt


            max_length = prompt_embeds.shape[1]
            uncond_input = tokenizer(
                uncond_tokens,
                padding="max_length",
                max_length=max_length,
                truncation=True,
                return_tensors="pt",
            ).to(device)
            output = text_encoder(
                    input_ids=uncond_input['input_ids'],
                    attention_mask=uncond_input['attention_mask'],
                    position_ids=uncond_input['position_ids'],
                    output_hidden_states=True)
            negative_prompt_embeds = output.hidden_states[-2].permute(1, 0, 2).clone() # [batch_size, 77, 4096]
            negative_text_proj = output.hidden_states[-1][-1, :, :].clone() # [batch_size, 4096]

            if do_classifier_free_guidance:
                # duplicate unconditional embeddings for each generation per prompt, using mps friendly method
                seq_len = negative_prompt_embeds.shape[1]

                negative_prompt_embeds = negative_prompt_embeds.to(dtype=text_encoder.dtype, device=device)

                negative_prompt_embeds = negative_prompt_embeds.repeat(1, num_images_per_prompt, 1)
                negative_prompt_embeds = negative_prompt_embeds.view(
                    batch_size * num_images_per_prompt, seq_len, -1
                )

        bs_embed = text_proj.shape[0]
        text_proj = text_proj.repeat(1, num_images_per_prompt).view(
            bs_embed * num_images_per_prompt, -1
        )
        negative_text_proj = negative_text_proj.repeat(1, num_images_per_prompt).view(
            bs_embed * num_images_per_prompt, -1
        )
        text_encoder.to(offload_device)
        mm.soft_empty_cache()
        gc.collect()
        kolors_embeds = {
            'prompt_embeds': prompt_embeds,
            'negative_prompt_embeds': negative_prompt_embeds,
            'pooled_prompt_embeds': text_proj,
            'negative_pooled_prompt_embeds': negative_text_proj
        }

        return (kolors_embeds,)


class KolorsSampler:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "kolors_model": ("KOLORSMODEL", ),
                "kolors_embeds": ("KOLORS_EMBEDS", ),

                "width": ("INT", {"default": 1024, "min": 64, "max": 2048, "step": 64}),
                "height": ("INT", {"default": 1024, "min": 64, "max": 2048, "step": 64}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 25, "min": 1, "max": 200, "step": 1}),
                "cfg": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 20.0, "step": 0.01}),

                "scheduler": (
                    [
                        "EulerDiscreteScheduler",
                        "EulerAncestralDiscreteScheduler",
                        "DPMSolverMultistepScheduler",
                        "DPMSolverMultistepScheduler_SDE_karras",
                        "UniPCMultistepScheduler",
                        "DEISMultistepScheduler",
                    ],
                      {
                    "default": 'EulerDiscreteScheduler'
                    }
                    ),
                },
                "optional": {
                      "latent": ("LATENT", ),
                      "denoise_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "process"
    CATEGORY = "KwaiKolorsWrapper"

    def process(self, kolors_model, kolors_embeds, width, height, seed, steps, cfg, scheduler, latent=None, denoise_strength=1.0):
        device = mm.get_torch_device()
        offload_device = mm.unet_offload_device()

        vae_scaling_factor = 0.13025 #SDXL scaling factor

        mm.soft_empty_cache()
        gc.collect()

        pipeline = kolors_model['pipeline']

        scheduler_config = {
            "beta_schedule": "scaled_linear",
            "beta_start": 0.00085,
            "beta_end": 0.014,
            "dynamic_thresholding_ratio": 0.995,
            "num_train_timesteps": 1100,
            "prediction_type": "epsilon",
            "rescale_betas_zero_snr": False,
            "steps_offset": 1,
            "timestep_spacing": "leading",
            "trained_betas": None,
        }
        if scheduler == "DPMSolverMultistepScheduler":
            noise_scheduler = DPMSolverMultistepScheduler(**scheduler_config)
        elif scheduler == "DPMSolverMultistepScheduler_SDE_karras":
            scheduler_config.update({"algorithm_type": "sde-dpmsolver++"})
            scheduler_config.update({"use_karras_sigmas": True})
            noise_scheduler = DPMSolverMultistepScheduler(**scheduler_config)
        elif scheduler == "DEISMultistepScheduler":
            scheduler_config.pop("rescale_betas_zero_snr")
            noise_scheduler = DEISMultistepScheduler(**scheduler_config)
        elif scheduler == "EulerDiscreteScheduler":
            scheduler_config.update({"interpolation_type": "linear"})
            scheduler_config.pop("dynamic_thresholding_ratio")
            noise_scheduler = EulerDiscreteScheduler(**scheduler_config)
        elif scheduler == "EulerAncestralDiscreteScheduler":
            scheduler_config.pop("dynamic_thresholding_ratio")
            noise_scheduler = EulerAncestralDiscreteScheduler(**scheduler_config)
        elif scheduler == "UniPCMultistepScheduler":
            scheduler_config.pop("rescale_betas_zero_snr")
            noise_scheduler = UniPCMultistepScheduler(**scheduler_config)

        pipeline.scheduler = noise_scheduler

        generator= torch.Generator(device).manual_seed(seed)

        pipeline.unet.to(device)

        if latent is not None:
            samples_in = latent['samples']
            samples_in = samples_in * vae_scaling_factor
            samples_in = samples_in.to(pipeline.unet.dtype).to(device)

        latent_out = pipeline(
            prompt=None,
            latents=samples_in if latent is not None else None,
            prompt_embeds = kolors_embeds['prompt_embeds'],
            pooled_prompt_embeds = kolors_embeds['pooled_prompt_embeds'],
            negative_prompt_embeds = kolors_embeds['negative_prompt_embeds'],
            negative_pooled_prompt_embeds = kolors_embeds['negative_pooled_prompt_embeds'],
            height=height,
            width=width,
            num_inference_steps=steps,
            guidance_scale=cfg,
            num_images_per_prompt=1,
            generator= generator,
            strength=denoise_strength,
            ).images

        pipeline.unet.to(offload_device)

        latent_out = latent_out / vae_scaling_factor

        return ({'samples': latent_out},)

NODE_CLASS_MAPPINGS = {
    "DownloadAndLoadKolorsModel": DownloadAndLoadKolorsModel,
    "DownloadAndLoadChatGLM3": DownloadAndLoadChatGLM3,
    "KolorsSampler": KolorsSampler,
    "KolorsTextEncode": KolorsTextEncode,
    "LoadChatGLM3": LoadChatGLM3
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DownloadAndLoadKolorsModel": "(Down)load Kolors Model",
    "DownloadAndLoadChatGLM3": "(Down)load ChatGLM3 Model",
    "KolorsSampler": "Kolors Sampler",
    "KolorsTextEncode": "Kolors Text Encode",
    "LoadChatGLM3": "Load ChatGLM3 Model"
}