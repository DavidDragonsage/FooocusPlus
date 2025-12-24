import os
import zipfile
import shutil
import common
import ldm_patched
import modules.config as config
from enhanced.backend import ComfyTaskParams
from enhanced.translator import interpret_warn
from modules.model_loader import load_file_from_url

default_method_names = ['Blend the Foreground with IC-Light', 'Create the Foreground with Convolutional Injection']
default_method_list = {
    default_method_names[0]: 'iclight_fc',
    default_method_names[1]: 'layerdiffuse_fg',
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

default_base_SD15_name = 'SD1.5\\realisticVisionV60B1_v51VAE.safetensors'
default_base_SD3m_name_list = ['SD3x\sd3_medium_incl_clips.safetensors', 'SD3x\sd3_medium_incl_clips_t5xxlfp8.safetensors', 'SD3x\sd3_medium_incl_clips_t5xxlfp16.safetensors']
default_base_SD3x_name_list = ['SD3x\stableDiffusion35_large.safetensors', 'SD3x\sd3_medium_incl_clips_t5xxlfp8.safetensors', 'SD3x\sd3_medium_incl_clips_t5xxlfp16.safetensors']

default_base_Flux_name_list = ['flux1-schnell-bnb-nf4.safetensors', 'flux1-dev-bnb-nf4.safetensors', 'flux-hyp8-Q5_K_M.gguf']
flux_model_urls = {
    "flux1-schnell-bnb-nf4.safetensors": "https://huggingface.co/silveroxides/flux1-nf4-weights/resolve/main/flux1-schnell-bnb-nf4.safetensors?download=true",
    "flux1-dev-bnb-nf4-v2.safetensors": "https://huggingface.co/lllyasviel/flux1-dev-bnb-nf4/resolve/main/flux1-dev-bnb-nf4-v2.safetensors?download=true",
    "Flux\\hyperfluxDiversity_q5KS.gguf": "https://civitai.com/api/download/models/1147912?type=Model&format=GGUF&size=pruned&fp=fp8"
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

    if task_name == 'default':
        if task_method == default_method_names[1]:
            comfy_params = ComfyTaskParams(default_params)
            comfy_params.update_params({"layer_diffuse_injection": "SDXL, Conv Injection"})
            return ComfyTask(default_method_list[task_method], comfy_params)
        else:
            comfy_params = ComfyTaskParams(default_params)
            if input_images is None:
                raise ValueError("input_images cannot be None for this method")
            images = {"input_image": input_images[0]}
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
                width, height = fixed_width_height(default_params["width"], default_params["height"], 64)
                comfy_params.update_params({
                    "layer_diffuse_cond": "SDXL, Foreground",
                    "width": width,
                    "height": height,
                    })
                comfy_params.delete_params(['denoise'])
                return ComfyTask('layerdiffuse_cond', comfy_params, images)

    elif task_name == 'SD3x':
        if not common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=default_params["base_model"]):
            config.downloading_sd35_large_model()
        if 'base_model_dtype' in default_params:
            comfy_params.delete_params(['base_model_dtype'])
        return ComfyTask(task_method, comfy_params)

    elif task_name in ['Kolors+', 'Kolors']:
        comfy_params = ComfyTaskParams(default_params)
        total_vram = ldm_patched.modules.model_management.get_vram()
        if 'llms_model' not in default_params or default_params['llms_model'] == 'auto':
            comfy_params.update_params({
                "llms_model": 'quant4' if total_vram<VRAM8G else 'quant8' if total_vram<VRAM16G else 'fp16'
                })
        check_download_kolors_model(config.path_models_root)
        if task_name == 'Kolors':
            comfy_params.delete_params(['sampler'])
        return ComfyTask(task_method, comfy_params)

    elif task_name in ['HyDiT+', 'HyDiT']:
        comfy_params = ComfyTaskParams(default_params)
        if not common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=default_params["base_model"]):
            config.downloading_hydit_model()
        return ComfyTask(task_method, comfy_params)

    elif task_name == 'Flux':
        comfy_params = ComfyTaskParams(default_params)
        base_model = default_params['base_model']
        try:
            clip_model = default_params['clip_model']
        except:
            clip_model = 'auto'
        total_ram = ldm_patched.modules.model_management.get_sysram()
        total_vram = ldm_patched.modules.model_management.get_vram()
        if base_model == 'auto':
            model_dev = 'FluxDev\\flux1-dev-bnb-nf4-v2.safetensors'
            model_nf4 = 'FluxDev\\flux1-dev-bnb-nf4-v2.safetensors'
            model_hyp8 = 'FluxDev\\hyperfluxDiversity_q5KS.gguf'
            base_model = model_nf4 if total_vram<=VRAM8G1 else model_dev
            if not common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=base_model) and common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=model_hyp8):
                base_model = model_hyp8
                default_params['steps'] = 12
            default_params['base_model'] = base_model
        base_model_key = f'checkpoints/{base_model}'
        if 'nf4' in base_model.lower() and 'bnb' in base_model.lower():
            if total_vram<VRAM8G:
                task_method = 'flux_base_nf4_2'
            else:
                task_method = 'flux_base_nf4'
            comfy_params.delete_params(['clip_model', 'base_model_dtype', 'lora_1', 'lora_1_strength'])
        elif 'fp8' in base_model.lower() and common.MODELS_INFO.exists_model_key(base_model_key)  and common.MODELS_INFO.get_model_key_info(base_model_key)["size"]/(1024*1024*1024)>15:
            task_method = 'flux_base_fp8'
            if 'lora_1' in default_params:
                task_method = 'flux_base2_fp8'
            comfy_params.delete_params(['clip_model', 'base_model_dtype'])
        else:
            if 'clip_model' not in default_params or default_params['clip_model'] == 'auto':
                clip_model = 't5xxl_fp16.safetensors' if total_vram>VRAM8G1 and total_ram>RAM32G1 else 't5xxl_fp8_e4m3fn.safetensors'
                if not common.MODELS_INFO.exists_model("clip", clip_model):
                    if clip_model == 't5xxl_fp16.safetensors' and common.MODELS_INFO.exists_model("clip", 't5xxl_fp8_e4m3fn.safetensors'):
                        clip_model = 't5xxl_fp8_e4m3fn.safetensors'
                comfy_params.update_params({"clip_model": clip_model})
            if 'base_model_dtype' not in default_params or default_params['base_model_dtype'] == 'auto':
                comfy_params.update_params({
                    "base_model_dtype": 'fp8_e4m3fn' if total_vram<VRAM16G or total_ram<=RAM32G1 or 'fp8' in base_model.lower() or 'lora_1' in default_params else 'default' #'fp16'
                })
            else:
                base_model_dtype = default_params['base_model_dtype']
                if base_model_dtype == 'fp16':
                    base_model_dtype = 'default'
                elif base_model_dtype != 'default':
                    base_model_dtype = 'fp8_e4m3fn'

                if base_model_dtype == 'default' and 'lora_1' in default_params:
                    base_model_dtype = 'fp8_e4m3fn'
                comfy_params.update_params({"base_model_dtype": base_model_dtype})
            if 'lora_1' in default_params and '.gguf' not in base_model:
                task_method = 'flux_base2'
            if '.gguf' in base_model:
                task_method = 'flux_base_gguf'
                if 'lora_1' in default_params:
                    task_method = 'flux_base2_gguf'
                comfy_params.delete_params(['base_model_dtype'])
        check_download_flux_model(default_params["base_model"], default_params.get("clip_model", None))
        return ComfyTask(task_method, comfy_params)
    else:  # SeamlessTiled
        comfy_params = ComfyTaskParams(default_params)
        #check_download_base_model(default_params["base_model"])
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

def check_download_kolors_model(path_root):
    check_model_file = [
            "diffusers/Kolors/text_encoder/pytorch_model-00007-of-00007.bin",
            "diffusers/Kolors/unet/diffusion_pytorch_model.fp16.safetensors",
            "diffusers/Kolors/vae/diffusion_pytorch_model.fp16.safetensors",
            ]
    path_temp = os.path.join(path_root, 'temp')
    if not os.path.exists(path_temp):
        os.makedirs(path_temp)
    if not common.MODELS_INFO.exists_model_key(check_model_file[0]):
        load_file_from_url(
            url='https://huggingface.co/DavidDragonsage/FooocusPlus/resolve/main/KwaiKolors.zip',
            model_dir=path_temp,
            file_name='KwaiKolors.zip'
        )
        downfile = os.path.join(path_temp, 'KwaiKolors.zip')
        with zipfile.ZipFile(downfile, 'r') as zipf:
            print(f'[ComfyTask] Extracting: {downfile} to {path_root}')
            zipf.extractall(path_root)
        if os.path.exists(downfile): os.remove(downfile)
        if os.path.exists(path_temp) and os.path.isdir(path_temp):
            shutil.rmtree(path_temp)

    if not common.MODELS_INFO.exists_model_key(check_model_file[1]):
        path_dst = os.path.join(config.paths_diffusers[0], 'Kolors/unet/diffusion_pytorch_model.fp16.safetensors')
        path_org = os.path.join(config.path_unet, 'kolors_unet_fp16.safetensors')
        print(f'[ComfyTask] Model file copy: {path_org} to {path_dst}')
        shutil.copy(path_org, path_dst)

    if not common.MODELS_INFO.exists_model_key(check_model_file[2]):
        path_dst = os.path.join(config.paths_diffusers[0], 'Kolors/vae/diffusion_pytorch_model.fp16.safetensors')
        path_org = os.path.join(config.path_vae, 'sdxl_fp16.vae.safetensors')
        print(f'[ComfyTask] Model file copy: {path_org} to {path_dst}')
        shutil.copy(path_org, path_dst)

    common.MODELS_INFO.refresh_from_path()
    return

def check_download_base_model(base_model):
    if not common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=base_model):
        load_file_from_url(
            url='https://huggingface.co/silveroxides/flux1-nf4-weights/resolve/main/{base_model}',
            model_dir=config.paths_checkpoints[0],
            file_name=base_model
        )
    return

def check_download_flux_model(base_model, clip_model=None):
    if not common.MODELS_INFO.exists_model(catalog="checkpoints", model_path=base_model):
        if 'nf4' in base_model:
            if 'schnell' in base_model:
                load_file_from_url(
                    url=f'https://huggingface.co/silveroxides/flux1-nf4-weights/resolve/main/{base_model}',
                    model_dir=config.paths_checkpoints[0],
                    file_name=base_model
                )
            else:
                load_file_from_url(
                    url=f'https://huggingface.co/lllyasviel/flux1-dev-bnb-nf4/resolve/main/{base_model}',
                    model_dir=config.paths_checkpoints[0],
                    file_name=base_model
                )
        elif 'fp8' in base_model:
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

