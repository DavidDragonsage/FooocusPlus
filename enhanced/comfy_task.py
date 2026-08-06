from pathlib import Path

import common
import ldm_patched
import modules.config as config

from enhanced.backend import ComfyTaskParams
from enhanced.translator import interpret_warn
from modules.model_loader import load_file_from_url

default_method_names = ['Blend the Foreground with IC-Light']
default_method_list = {
    default_method_names[0]: 'iclight_fc'
}

iclight_source_names = ['Top Left Light', 'Top Light', 'Top Right Light', 'Middle Left Light', 'Middle Light', 'Middle Right Light', 'Bottom Left Light', 'Bottom Light', 'Bottom Right Light']
iclight_source_text = {
    iclight_source_names[0]: "Top Left Light",
    iclight_source_names[1]: "Top Light",
    iclight_source_names[2]: "Top Right Light",
    iclight_source_names[3]: "Left Light",
    iclight_source_names[5]: "Right Light",
    iclight_source_names[6]: "Bottom Left Light",
    iclight_source_names[7]: "Bottom Light",
    iclight_source_names[8]: "Bottom Right Light",
    }

RAM32G = 32500
RAM32G1 = 32768
RAM16G = 16300
VRAM8G = 8180
VRAM8G1 = 8192  # include 8G
VRAM16G = 16300

def is_lowlevel_device():
    return ldm_patched.modules.model_management.get_vram()<VRAM8G

def is_highlevel_device():
    return ldm_patched.modules.model_management.get_vram()>VRAM16G

default_base_SD15_name = 'SD1.5/realisticVisionV60B1_v51VAE.safetensors'
default_base_SD3m_name_list = ['SD3x/sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors']
default_base_SD3x_name_list = ['SD3x/sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors']

default_base_Flux_name_list = ['FluxDev/flux1-dev-Q5_K_S.gguf']
flux_model_urls = {
    "FluxDev/flux1-dev-Q5_K_S.gguf": "https://huggingface.co/lllyasviel/FLUX.1-dev-gguf/resolve/main/flux1-dev-Q5_K_S.gguf?download=true"
    }

quick_prompts = [
    'blue hour',
    'eerie, evil, gothic',
    'firelight',
    'golden hour',
    'light and shadow',
    'luminous',
    'moonlight',
    'natural lighting',
    'nautical twilight',
    'neon light, city',
    'sci-fi RGB glowing, cyberpunk',
    'shadow from the window',
    'soft studio lighting',
    'sparkling, twinkling',
    'sunshine in the forest',
    'sunshine from the window',
    'sunset over the sea',
    'warm atmosphere, at home, bedroom'
]
quick_prompts = [[x] for x in quick_prompts]


quick_subjects = [
    'beautiful woman, detailed face',
    'handsome man, detailed face',
]
quick_subjects = [[x] for x in quick_subjects]


class ComfyTask:
    def __init__(self, name, params, images=None):
        self.name = name
        self.params = params
        self.images = images


def get_comfy_task(task_name, task_method, default_params, input_images, options={}):
    global default_method_names, default_method_list

    comfy_params = ComfyTaskParams(default_params)
    base_model = default_params.get('base_model', '')

    if task_name == 'default':
        if input_images is None:
            raise ValueError("input_images cannot be None for this method")
        images = {"input_image": input_images[0]}

        # IC-Light is the only active feature
        # handled by the 'default' task name
        if 'iclight_enable' in options and options["iclight_enable"]:
            if common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=default_base_SD15_name):
                config.downloading_base_sd15_model()
            comfy_params.update_params({"base_model": default_base_SD15_name})
            if options["iclight_source_radio"] == 'CenterLight':
                comfy_params.update_params({"light_source_text_switch": False})
            else:
                comfy_params.update_params({
                    "light_source_text_switch": True,
                    "light_source_text": iclight_source_text[options["iclight_source_radio"]]
                })
            return ComfyTask(default_method_list[task_method], comfy_params, images)
        else:
            raise ValueError("IC-Light must be enabled to run the 'default' Comfy task engine.")

    elif task_name == 'SD3x':
        if '.gguf' in base_model.lower():
            # route GGUF models to the GGUF workflow
            task_method = 'sd3x_base_gguf'
            comfy_params.delete_params(['base_model_dtype'])
        else:
            if not common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=default_params["base_model"]):
                config.downloading_sd3_medium_model()
            if 'base_model_dtype' in default_params:
                comfy_params.delete_params(['base_model_dtype'])
        return ComfyTask(task_method, comfy_params)

    elif task_name == 'Kolors+':
        total_vram = ldm_patched.modules.model_management.get_vram()
        if 'llms_model' not in default_params or default_params['llms_model'] == 'auto':
            comfy_params.update_params({
                "llms_model": 'quant4' if total_vram < VRAM8G else 'quant8' if total_vram < VRAM16G else 'fp16'
            })
        check_download_kolors_model()
        return ComfyTask(task_method, comfy_params)

    elif task_name in ['HyDiT+']:
        if not common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=default_params["base_model"]):
            config.downloading_hydit_model()
        return ComfyTask(task_method, comfy_params)

    elif task_name == 'Flux':
        base_model = default_params.get('base_model', '')
        is_z_model = 'z-image' in base_model.lower() or 'z_image' in base_model.lower() or 'z-img' in base_model.lower() or 'z_img' in base_model.lower()

        # 1. Handle Z-IMAGE Models (Exclusive Logic)
        if is_z_model:
            # If the preset provides a specific
            # Z-workflow (like shift6), keep it.
            # Otherwise, auto-assign the
            # correct Z-workflow.
            if not (isinstance(task_method, str) and ('ZIB' in task_method or 'ZIT' in task_method)):
                if '.gguf' in base_model.lower():
                    task_method = 'ZIT_gguf' if 'turbo' in base_model.lower() else 'ZIB_gguf'
                else:
                    task_method = 'ZIT' if 'turbo' in base_model.lower() else 'ZIB'

            # Resolve 'clip_model' if set to 'auto'
            if comfy_params.params.get('clip_model') == 'auto':
                comfy_params.update_params({'clip_model': 'Qwen_3_4b-Q6_K.gguf'})

            if '.gguf' in base_model.lower():
                comfy_params.delete_params(['base_model_dtype'])
            elif comfy_params.params.get('base_model_dtype') == 'auto':
                comfy_params.update_params({'base_model_dtype': 'fp8_e4m3fn'})

            return ComfyTask(task_method, comfy_params)

        # -------------------------------------------
        # FLUX DEV/SCHENLL/KREA/ALL-IN-ONE FP8
        # -------------------------------------------
        total_ram = ldm_patched.modules.model_management.get_sysram()
        total_vram = ldm_patched.modules.model_management.get_vram()

        # SAFETY CHECK: If a Z-Image workflow is
        # lingering but the model is standard,
        # we MUST reset to a standard Flux workflow
        # or it will crash (Shape Mismatch).
        if isinstance(task_method, str) and ('ZIB' in task_method or 'ZIT' in task_method):
            task_method = 'flux_base_gguf' if '.gguf' in base_model.lower() else 'flux_base'

        # Handle 'auto' model selection
        if base_model == 'auto':
            model_dev = 'FluxDev\\FluxDev/flux1-dev-Q5_K_S.gguf'
            model_hyp8 = 'FluxDev\\hyperfluxDiversity_q5KS.gguf'
            if not common.MODELS_INFO.exists_model(catalog='checkpoints', model_path=base_model) and common.MODELS_INFO.exists_model(catalog='checkpoints', model_path=model_hyp8):
                base_model = model_hyp8
                default_params['steps'] = 12
            default_params['base_model'] = base_model

        base_model_key = f'checkpoints/{base_model}'

        if 'fp8' in base_model.lower() and common.MODELS_INFO.exists_model_key(base_model_key) and common.MODELS_INFO.get_model_key_info(base_model_key)['size']/(1024*1024*1024) > 15:
            if task_method == 'flux_base':
                task_method = 'flux_base_fp8'
            comfy_params.delete_params(['clip_model', 'base_model_dtype'])
            return ComfyTask(task_method, comfy_params)

        # -------------------------------------------
        # 4. FLUX SPLIT MODEL ARCHITECTURES
        # (UNet + CLIP + VAE)
        # -------------------------------------------
        # Determine clip_model based on safe, conservative VRAM threshold (VRAM16G)
        if 'clip_model' not in default_params or default_params['clip_model'] == 'auto':
            clip_model = 't5xxl_fp16.safetensors' if total_vram > VRAM16G and total_ram > RAM32G1 else 't5xxl_fp8_e4m3fn.safetensors'

            # Check for file existence, falling back to FP8 if FP16 is missing
            if not common.MODELS_INFO.exists_model('clip', clip_model):
                if clip_model == 't5xxl_fp16.safetensors' and common.MODELS_INFO.exists_model('clip', 't5xxl_fp8_e4m3fn.safetensors'):
                    clip_model = 't5xxl_fp8_e4m3fn.safetensors'
            comfy_params.update_params({'clip_model': clip_model})

        # Force FP8 model-weights on GPUs with less than 16GB VRAM
        if 'base_model_dtype' not in default_params or default_params['base_model_dtype'] == 'auto':
            comfy_params.update_params({
                'base_model_dtype': 'fp8_e4m3fn' if total_vram < VRAM16G or total_ram <= RAM32G1 or 'fp8' in base_model.lower() or 'lora_1' in default_params else 'default'
            })
        else:
            base_model_dtype = default_params['base_model_dtype']
            if base_model_dtype == 'fp16':
                base_model_dtype = 'default'
            elif base_model_dtype != 'default':
                base_model_dtype = 'fp8_e4m3fn'

            if base_model_dtype == 'default' and 'lora_1' in default_params:
                base_model_dtype = 'fp8_e4m3fn'
            comfy_params.update_params({'base_model_dtype': base_model_dtype})

        # Delete base_model_dtype only for GGUF formats
        if '.gguf' in base_model.lower():
            comfy_params.delete_params(['base_model_dtype'])

        # Assign task method based on standard Flux model format (standard vs GGUF)
        if '.gguf' in base_model:
            task_method = 'flux_base_gguf'
        else:
            task_method = 'flux_base'

    # This is the fallback for SD1 (SD1.5)
    # and all other custom presets
    return ComfyTask(task_method, comfy_params)


def fixed_width_height(width, height, factor):
    fixed_width = int(((height // factor + 1) * factor * width)/height)
    fixed_width = fixed_width if fixed_width % factor == 0 else int((fixed_width // factor + 1) * factor )
    width = width if height % factor == 0 else fixed_width
    height = height if height % factor == 0 else int((height // factor + 1) * factor)
    return width, height

default_kolors_base_model_name = 'kolors_unet_fp16.safetensors'

kolors_scheduler_list = [ "EulerDiscreteScheduler",
                          "EulerAncestralDiscreteScheduler",
                          "DPMSolverMultistepScheduler",
                          "DPMSolverMultistepScheduler_SDE_karras",
                          "UniPCMultistepScheduler",
                          "DEISMultistepScheduler" ]
default_kolors_scheduler = kolors_scheduler_list[0]

def check_task_model():
    #check_model_files_from_download_of_preset_file
    pass


def check_download_kolors_model() -> None:
    """
    Checks for the existence of the Kolors diffuser models in the active
    user-configured models directory. Downloads and extracts them if missing.
    """
    import shutil
    import zipfile
    from tqdm import tqdm

    # 1. Standardized paths using relative keys
    check_model_file = [
        'diffusers/Kolors/text_encoder/pytorch_model-00007-of-00007.bin',
        'diffusers/Kolors/unet/diffusion_pytorch_model.fp16.safetensors',
        'diffusers/Kolors/vae/diffusion_pytorch_model.fp16.safetensors',
    ]

    # 2. Derive the correct user-configured models directory from paths_diffusers[0]
    # config.paths_diffusers[0] points to '.../models/diffusers'
    diffusers_path = Path(common.path_diffusers)
    path_root = diffusers_path.parent  # Resolves to the parent '.../models' root directory

    path_temp = path_root / 'temp'
    if not path_temp.exists():
        path_temp.mkdir(parents=True, exist_ok=True)

    # 3. Check for existence in the registered search paths
    if not common.MODELS_INFO.exists_model_key(check_model_file[0]):
        downfile = path_temp / 'KwaiKolors.zip'
        load_file_from_url(
            url='https://huggingface.co/DavidDragonsage/FooocusPlus/resolve/main/KwaiKolors.zip',
            model_dir=str(path_temp),
            file_name='KwaiKolors.zip'
        )

        with zipfile.ZipFile(downfile, 'r') as zipf:
            file_list = zipf.infolist()
            print(f'[ComfyTask] Extracting: {downfile} to {path_root}')

            # Extract each file sequentially
            # to drive the console progress bar
            for member in tqdm(file_list, desc='Extracting Kolors Shards', unit='file'):
                zipf.extract(member, path_root)

        if downfile.exists():
            downfile.unlink()
        if path_temp.exists() and path_temp.is_dir():
            shutil.rmtree(path_temp)

    # 4. Copy unet and vae using pathlib
    if not common.MODELS_INFO.exists_model_key(check_model_file[1]):
        path_dst = diffusers_path / 'Kolors/unet/diffusion_pytorch_model.fp16.safetensors'
        path_org = Path(config.path_unet) / 'kolors_unet_fp16.safetensors'

        # Ensure destination subfolders exist
        path_dst.parent.mkdir(parents=True, exist_ok=True)

        print(f'[ComfyTask] Model file copy: {path_org} to {path_dst}')
        shutil.copy(path_org, path_dst)

    if not common.MODELS_INFO.exists_model_key(check_model_file[2]):
        path_dst = diffusers_path / 'Kolors/vae/diffusion_pytorch_model.fp16.safetensors'
        path_org = Path(config.path_vae) / 'sdxl_fp16.vae.safetensors'

        # Ensure destination subfolders exist
        path_dst.parent.mkdir(parents=True, exist_ok=True)

        print(f'[ComfyTask] Model file copy: {path_org} to {path_dst}')
        shutil.copy(path_org, path_dst)

    common.MODELS_INFO.refresh_from_path()
    return


def check_download_flux_model(base_model, clip_model=None):
    if not common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=base_model):
        if 'fp8' in base_model:
            if 'schnell' in base_model:
                load_file_from_url(
                    url=f'https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/{base_model}',
                    model_dir=config.paths_checkpoints[0],
                    file_name=base_model
                )
            else:
                load_file_from_url(
                    url=f'https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/{base_model}',
                    model_dir=config.paths_checkpoints[0],
                    file_name=base_model
                )
        elif 'hyp8' in base_model:
            if '_K' in base_model:
                load_file_from_url(
                    url=f'https://huggingface.co/mhnakif/flux-hyp8-gguf-k/tree/main/{base_model}',
                    model_dir=config.paths_checkpoints[0],
                    file_name=base_model
                )
            else:
                load_file_from_url(
                    url=f'https://huggingface.co/mhnakif/flux-hyp8/tree/main/{base_model}',
                    model_dir=config.paths_checkpoints[0],
                    file_name=base_model
                )
        else:
            interpret_warn('[ComfyTask] Could not automatically download', base_model)
            interpret_warn('Please download this Flux file manually and place it in the correct Flux subdirectory')

    if clip_model:
        if not common.MODELS_INFO.exists_model(catalog="clip", model_path=clip_model):
            load_file_from_url(
                url=f'https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/{clip_model}',
                model_dir=config.path_clip,
                file_name=f'{clip_model}'
            )
        if not common.MODELS_INFO.exists_model(catalog="clip", model_path='clip_l.safetensors'):
            load_file_from_url(
                url=f'https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors',
                model_dir=config.path_clip,
                file_name=f'clip_l.safetensors'
            )
        if not common.MODELS_INFO.exists_model(catalog="vae", model_path='ae.safetensors'):
            load_file_from_url(
                url='https://huggingface.co/lovis93/testllm/resolve/ed9cf1af7465cebca4649157f118e331cf2a084f/ae.safetensors?download=true',
                model_dir=config.path_vae,
                file_name='ae.safetensors'
            )

