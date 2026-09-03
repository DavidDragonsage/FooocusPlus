import os  # Strictly used only for os.environ environment variable checks
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

import common
import modules.flags as flags
import modules.user_structure as US
from args_manager import args
from enhanced.translator import interpret, \
    interpret_info, interpret_warn


current_dir = Path.cwd().resolve()
base_model_name = ''
lora_filenames = []
model_filenames = []
path_wildcards = Path(current_dir / 'wildcards')
sd15_model_path = 'SD1.5/realisticVisionV60B1_v51VAE.safetensors'
vae_filenames = []
wildcard_filenames = []


def is_comfy_checkpoint(file_path_str: str) -> bool:
    """Helper to check if a checkpoint resides inside a Comfy-only folder."""
    parts = Path(file_path_str).parts
    if parts:
        first_part = parts[0].lower()

        # --- MIXED ALTERNATIVE FOLDER GATEWAY ---
        # If the file is inside 'Alternative/', only allow it through if it is the
        # Playground model. Exclude all other Comfy-specific contents from standard view.
        if first_part == 'alternative':
            return 'playground' not in file_path_str.lower()

        # Exact folder name matches from your checkpoints directory
        comfy_checkpoint_folders = {'fluxdev', 'fluxkrea', 'fluxschnell', 'sd3x', 'sd1.5', 'z-image'}
        return first_part in comfy_checkpoint_folders
    return False


def get_base_model_list(engine='Fooocus', task_method=None, for_import=False):
    global base_model_name

    # If called by the metadata importer,
    # bypass all UI filters and return the raw list
    if for_import:
        return common.MODELS_INFO.get_model_names('checkpoints')

    # 1. Fetch the default filter and get the matching model list
    file_filter = flags.model_file_filter.get(engine, [])
    base_model_list = common.MODELS_INFO.get_model_names('checkpoints', file_filter)

    # Inspect the currently selected model name
    # to determine the dynamic filter mode
    model_lower = base_model_name.lower() if base_model_name else ''
    method_lower = str(task_method).lower() if task_method else ''

    # 2. For SD1.5 (Comfy SD1.5) engine modes:
    # Check if the model name or engine indicates SD1.5
    if 'sd1.5' in model_lower or engine == 'SD1':
        return [f for f in base_model_list if 'sd1.5' in f.replace('\\', '/').lower()]

    # 3. For standard Fooocus or Comfy (SDXL / SD1.5) modes:
    # Exclude specialized models (SD3, Flux, HyDiT) and any models inside subdirectories
    if engine in ['Fooocus', 'Comfy']:
        base_model_list = common.MODELS_INFO.get_model_names('checkpoints', flags.model_file_filter['Fooocus'], reverse=True)
        # Keep only the flat/root models (filter out anything containing path separators)
        return [f for f in base_model_list if not is_comfy_checkpoint(f)]

    # 4. For Flux engine modes:
    elif engine == 'Flux':

        # We determine the GGUF state purely from the active model name to prevent timing lags
        is_gguf_mode = '.gguf' in model_lower

        is_z_image = (
            any(kw in model_lower for kw in flags.Z_IMAGE_MODEL_KEYWORDS) or
            any(kw in method_lower for kw in flags.Z_IMAGE_METHOD_KEYWORDS)
        )

        # Base / Turbo sub-family flags
        is_turbo = (
            any(kw in model_lower for kw in flags.TURBO_MODEL_KEYWORDS) or
            any(kw in method_lower for kw in flags.TURBO_METHOD_KEYWORDS)
        )

        # A. Z-Image Sub-Family (Early Return)
        if is_z_image:
            if is_turbo:
                if is_gguf_mode:
                    # Turbo GGUF (e.g. z_image_turbo-Q8_0.gguf)
                    return [f for f in base_model_list if 'turbo' in f.lower() and f.endswith('gguf') and ('z-image' in f.lower() or 'z_image' in f.lower())]
                else:
                    # Turbo Safetensors (e.g. z-image-turbo-fp8-e4m3fn.safetensors)
                    return [f for f in base_model_list if 'turbo' in f.lower() and not f.endswith('gguf') and ('z-image' in f.lower() or 'z_image' in f.lower())]
            else:
                if is_gguf_mode:
                    # Base GGUF (e.g. z_image-Q8_0.gguf, z_image-Q5_K_M.gguf)
                    return [f for f in base_model_list if 'turbo' not in f.lower() and f.endswith('gguf') and ('z-image' in f.lower() or 'z_image' in f.lower() or 'z-img' in f.lower() or 'z_img' in f.lower())]
                else:
                    # Base Safetensors / FP8 (e.g. z-img_fp8-e4m3fn.safetensors)
                    return [f for f in base_model_list if 'turbo' not in f.lower() and not f.endswith('gguf') and ('z-image' in f.lower() or 'z_image' in f.lower() or 'z-img' in f.lower() or 'z_img' in f.lower())]

        # B. Flux Schnell Sub-Family (Early Return)
        if 'schnell' in model_lower or 'schnell' in method_lower:
            if is_gguf_mode:
                # GGUF Schnell only
                return [f for f in base_model_list if 'schnell' in f.lower() and f.endswith('gguf')]
            else:
                # FP8/Standard Schnell only (exclude GGUF)
                return [f for f in base_model_list if 'schnell' in f.lower() and not f.endswith('gguf')]

        # C. Standard Flux GGUF (excluding Schnell and Z-Image) (Early Return)
        if is_gguf_mode:
            return [f for f in base_model_list if f.endswith('gguf') and 'schnell' not in f.lower() and 'z-image' not in f.lower() and 'z_image' not in f.lower()]

        # D. Standard Flux FP8 / Safetensors (excluding Schnell, GGUF, and Z-Image) (Early Return)
        return [f for f in base_model_list if not f.endswith('gguf') and 'schnell' not in f.lower() and 'z-image' not in f.lower() and 'z_image' not in f.lower()]

    # 5. For SD3x engine modes:
    elif engine == 'SD3x':

        if '.gguf' in model_lower:
            return [f for f in base_model_list if f.endswith('gguf')]
        else:
            return [f for f in base_model_list if not f.endswith('gguf')]

    return base_model_list


def is_comfy_lora(file_path_str: str) -> bool:
    """Helper to check if a LoRA resides inside a Comfy-only folder."""
    parts = Path(file_path_str).parts
    if parts:
        first_part = parts[0].lower()
        # Exact folder name matches from the LoRAs directory
        # These folder names must be listed in lower case
        comfy_lora_folders = {'flux', 'sd1.5', 'sd3x', 'z-image'}
        return first_part in comfy_lora_folders
    return False


def get_lora_model_list(engine='Fooocus', task_method=None, for_import=False) -> list:
    """
    Recursively filters LoRA files based on the active preset
    - Alternative (Kolors, HyDiT, Playground): Shows flat root LoRAs + 'Alternative/' subfolder
      (except the HyDiT preset only shows the 'Alternative/' subfolder)
    - Flux: Shows only 'Flux/' folder LoRAs (excluding Z-Image)
    - SD3.5: Shows only 'SD3x/' folder LoRAs
    - SD1.5: Shows only 'SD1.5/' folder LoRAs
    - Pony: Shows only 'Pony/' folder LoRAs
    - Z-Image: Shows only 'Z-Image' folder LoRAs
    - SDXL (Standard): Shows flat root LoRAs + any custom user subdirectories, hiding Comfy-only folders
    """
    global base_model_name

    # Fetch all raw LoRA files (recursive list)
    raw_loras = common.MODELS_INFO.get_model_names('loras')

    # Bypassed by metadata importer to ensure paths are resolved regardless of UI state
    if for_import:
        return raw_loras

    # Extract state strings for checking
    model_lower = base_model_name.lower() if base_model_name else ''
    method_lower = str(task_method).lower() if task_method else ''

    # 1. Z-Image Engine check
    is_z_image = any(x in model_lower for x in ['z-image', 'z_image']) or \
                 any(x in method_lower for x in ['zit', 'zib'])
    if is_z_image:
        return [f for f in raw_loras if 'z-image' in f.lower() or 'z_image' in f.lower()]

    # 2. Flux Engine check
    if engine == 'Flux':
        return [f for f in raw_loras if 'flux' in f.lower() and 'z-image' not in f.lower() and 'z_image' not in f.lower()]

    # 3. SD3x Engine check
    if engine == 'SD3x':
        return [f for f in raw_loras if 'sd3x' in f.lower()]

    # 4. SD1 (SD1.5) Engine check
    if engine == 'SD1' or 'sd15' in method_lower:
        return [f for f in raw_loras if 'sd1.5' in f.replace('\\', '/').lower()]

    # 5. Pony Sub-Family (SDXL Checkpoints)
    if 'pony' in model_lower:
        return [f for f in raw_loras if 'pony' in f.lower()]

    # 6. Alternative Engines Filter
    # (Kolors and Playground Only)
    # Restricts the choices to flat root-level LoRAs plus those stored in the 'Alternative' subfolder
    if engine == 'Kolors+' or (model_lower and 'playground' in model_lower):
        return [
            f for f in raw_loras
            if '/' not in f and '\\' not in f or 'alternative' in f.lower()
        ]

    # 7. HyDiT+ Engine Filter (Strict Lockout)
    # Strictly protects HyDiT from standard SDXL
    # LoRAs by showing ONLY specialized LoRAs
    # stored inside the 'Alternative/' directory
    if engine == 'HyDiT+':
        return [f for f in raw_loras if 'alternative' in f.lower()]

    # 8. Standard SDXL (Fooocus / Comfy)
    # Include all subfolders except for the Comfy ones
    if engine in ['Fooocus', 'Comfy']:
        return [f for f in raw_loras if not is_comfy_lora(f)]

    # Fallback: return everything
    return raw_loras


def update_files(engine='Fooocus', task_method=None):
    # called by the webui "Refresh All Files" button
    # and by launch.py
    global model_filenames, lora_filenames, \
        path_wildcards, vae_filenames, \
        wildcard_filenames
    common.MODELS_INFO.refresh_from_path()
    model_filenames = get_base_model_list(engine, task_method)
    lora_filenames = get_lora_model_list(engine, task_method)
    vae_filenames = common.MODELS_INFO.get_model_names('vae')
    wildcard_filenames = US.list_files_by_patterns(path_wildcards, ['*.txt'])
    return model_filenames, lora_filenames, vae_filenames


# --- Model Download Section ---
def load_file_from_url(
        url: str,
        *,
        model_dir: str,
        progress: bool = True,
        file_name: Optional[str] = None,
) -> str:
    # this line traps LowVRAMdef when used as the default preset
    if url.find('segmind-vega.safetensors') != -1:
        return ''

    """Download a file from `url` into `model_dir`, using the file present if possible.
    Returns the path to the downloaded file.
    """
    # 1. Resolve Hugging Face Mirror environment configurations
    domain = os.environ.get('HF_MIRROR', 'https://huggingface.co').rstrip('/')
    url = str.replace(url, 'https://huggingface.co', domain, 1)

    # 2. Resolve paths using pathlib.Path (No os for file operations)
    model_path_dir = Path(model_dir)
    model_path_dir.mkdir(parents=True, exist_ok=True)

    if not file_name:
        parts = urlparse(url)
        file_name = Path(parts.path).name

    cached_file = (model_path_dir / file_name).resolve()

    # 3. If the file is missing from your drive, initiate the download
    if not cached_file.exists():
        # Print the UI popup and console warnings EXACTLY ONCE here
        interpret_info('[Loader] Downloading:', url + ' → ' + str(cached_file))
        interpret('Please wait for the download to complete.')
        interpret_warn('Please wait for the download to complete. Progress can be checked in the console window.', silent=True)

        is_hf = 'huggingface.co' in url or (domain != 'https://huggingface.co' and domain in url)
        hf_download_success = False

        # --- AUTOMATED HUGGING FACE LFS/XET INTERCEPTOR ---
        if is_hf:
            try:
                from huggingface_hub import hf_hub_download

                # Parse the repo_id from the URL string, respecting custom mirror domains
                parts = url.split(domain + '/')
                if len(parts) > 1:
                    separator = '/resolve/' if '/resolve/' in parts[1] else '/blob/'
                    sub_parts = parts[1].split(separator)
                    if len(sub_parts) > 1:
                        repo_id = sub_parts[0]

                        # Execute the secure, automated download
                        hf_hub_download(
                            repo_id=repo_id,
                            filename=file_name,
                            local_dir=str(model_path_dir)
                        )
                        interpret_info('[Loader] Successfully downloaded:', file_name)
                        print()
                        hf_download_success = True
            except Exception as e:
                # If hf_hub_download fails
                # or is missing, fallback
                interpret_info(f'[Loader] Using the standard downloader...')

        # --- ORIGINAL FALLBACK DOWNLOADER (Using torch.hub) ---
        # Runs only if the hf_hub download was skipped or failed
        if not hf_download_success:
            from torch.hub import download_url_to_file
            try:
                download_url_to_file(url, str(cached_file), progress=progress)
            except Exception:
                interpret_info('Could not download', str(cached_file))
                interpret_warn('It may need to be downloaded manually from', url)
                print()

    return str(cached_file)


def get_write_directory(paths) -> Path:
    """Safely extracts the primary writable directory, falling back to current working dir if empty."""
    if isinstance(paths, list) and len(paths) > 0:
        return Path(paths[0])
    elif isinstance(paths, (str, Path)) and paths:
        return Path(paths)
    return Path.cwd()


def download_antelope_models():
    # load the Comfy  insightface directory,
    # used by the Flux PuLID and InstantID custom nodes
    # not currently used in FooocusPlus
    insightface_root = Path(getattr(common, 'path_insightface', Path.cwd() / 'models' / 'insightface'))
    model_dir = insightface_root / 'models' / 'antelopev2'

    antelope_files = [
        '1k3d68.onnx',
        '2d106det.onnx',
        'genderage.onnx',
        'glintr100.onnx',
        'scrfd_10g_bnkps.onnx'
    ]

    # Download all 5 files sequentially
    for file_name in antelope_files:
        load_file_from_url(
            url=f'https://huggingface.co/monas/InstantID/resolve/main/models/antelopev2/{file_name}',
            model_dir=str(model_dir),
            file_name=file_name
        )
    return str(model_dir)


def download_base_sd15_model():
    # Resolve the relative path dynamically from the global string
    global sd15_model_path
    rel_path = Path(sd15_model_path)

    # rel_path.parent -> 'SD1.5'
    # rel_path.name   -> 'realisticVisionV60B1_v51VAE.safetensors'
    model_path = get_write_directory(common.paths_checkpoints) / rel_path.parent
    model_file_name = rel_path.name

    # Download the base SD1.5 checkpoint
    # Required for both Fooocus and
    # Comfy IC-Light modes
    load_file_from_url(
        url='https://huggingface.co/moiu2998/mymo/resolve/3c3093fa083909be34a10714c93874ce5c9dabc4/realisticVisionV60B1_v51VAE.safetensors?download=true',
        model_dir=str(model_path),
        file_name=model_file_name
    )

    # Conditionally download the IC-Light
    # LDM UNet weights if Comfy is active
    if common.comfy_active:
        unet_dir = Path(common.path_unet)
        ic_light_unet_name = 'iclight_sd15_fc_unet_ldm.safetensors'

        load_file_from_url(
            url='https://huggingface.co/huchenlei/IC-Light-ldm/resolve/main/iclight_sd15_fc_unet_ldm.safetensors',
            model_dir=str(unet_dir),
            file_name=ic_light_unet_name
        )

    return str(model_path / model_file_name)


def download_bert_model():
    llms_root = Path(getattr(common, 'path_llms', Path.cwd() / 'models' / 'llms'))
    model_dir = llms_root / 'bert-base-uncased'
    file_name = 'model.safetensors'

    load_file_from_url(
        url='https://huggingface.co/google-bert/bert-base-uncased/resolve/main/model.safetensors',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_controlnet_canny():
    model_dir = get_write_directory(common.paths_controlnet)
    file_name = 'control-lora-canny-rank128.safetensors'
    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/control-lora-canny-rank128.safetensors',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_controlnet_cpds():
    model_dir = get_write_directory(common.paths_controlnet)
    file_name = 'fooocus_xl_cpds_128.safetensors'
    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/fooocus_xl_cpds_128.safetensors',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_eva_clip_model():
    model_dir = get_write_directory(common.path_clip)
    file_name = 'EVA02_CLIP_L_336_psz14_s6B.pt'
    load_file_from_url(
        url='https://huggingface.co/QuanSun/EVA-CLIP/resolve/main/EVA02_CLIP_L_336_psz14_s6B.pt',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_faceid_lora():
    model_dir = get_write_directory(common.paths_loras)
    file_name = 'ip-adapter-faceid-plusv2_sdxl_lora.safetensors'

    load_file_from_url(
        url='https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sdxl_lora.safetensors',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_groundingdino_model():
    # Resolve the physical destination directory
    model_dir = get_write_directory(common.paths_inpaint)
    file_name = 'groundingdino_swint_ogc.pth'

    load_file_from_url(
        url='https://huggingface.co/ShilongLiu/GroundingDINO/resolve/main/groundingdino_swint_ogc.pth',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_inpaint_models(v):
    if not v:
        v = 'v2.6'

    model_dir = get_write_directory(common.paths_inpaint)

    load_file_from_url(
        url='https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/fooocus_inpaint_head.pth',
        model_dir=str(model_dir),
        file_name='fooocus_inpaint_head.pth'
    )
    head_file = str(model_dir / 'fooocus_inpaint_head.pth')
    patch_file = None

    if v == 'v2.5':
        patch_name = 'inpaint_v25.fooocus.patch'
        load_file_from_url(
            url='https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/inpaint_v25.fooocus.patch',
            model_dir=str(model_dir),
            file_name=patch_name
        )
        patch_file = str(model_dir / patch_name)
    else:   # i.e. v=='v2.6'
        patch_name = 'inpaint_v26.fooocus.patch'
        load_file_from_url(
            url='https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/inpaint_v26.fooocus.patch',
            model_dir=str(model_dir),
            file_name=patch_name
        )
        patch_file = str(model_dir / patch_name)

    return head_file, patch_file


def download_ip_adapters(v):
    assert v in ['ip', 'face']

    results = []
    clip_dir = get_write_directory(common.path_clip_vision)
    control_dir = get_write_directory(common.paths_controlnet)

    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/clip_vision_vit_h.safetensors',
        model_dir=str(clip_dir),
        file_name='clip_vision_vit_h.safetensors'
    )
    results.append(str(clip_dir / 'clip_vision_vit_h.safetensors'))

    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/fooocus_ip_negative.safetensors',
        model_dir=str(control_dir),
        file_name='fooocus_ip_negative.safetensors'
    )
    results.append(str(control_dir / 'fooocus_ip_negative.safetensors'))

    if v == 'ip':
        file_name = 'ip-adapter-plus_sdxl_vit-h.bin'
        load_file_from_url(
            url='https://huggingface.co/lllyasviel/misc/resolve/main/ip-adapter-plus_sdxl_vit-h.bin',
            model_dir=str(control_dir),
            file_name=file_name
        )
        results.append(str(control_dir / file_name))

    if v == 'face':
        file_name = 'ip-adapter-plus-face_sdxl_vit-h.bin'
        load_file_from_url(
            url='https://huggingface.co/lllyasviel/misc/resolve/main/ip-adapter-plus-face_sdxl_vit-h.bin',
            model_dir=str(control_dir),
            file_name=file_name
        )
        results.append(str(control_dir / file_name))

    return results


def download_pulid_flux_model():
    # Resolve the physical destination directory
    model_dir = get_write_directory(common.paths_pulid)
    file_name = 'pulid_flux_v0.9.1.safetensors'

    load_file_from_url(
        url='https://huggingface.co/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_safety_checker_model():
    model_dir = get_write_directory(common.path_safety_checker)
    file_name = 'stable-diffusion-safety-checker.bin'
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/stable-diffusion-safety-checker.bin',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_sam_model(sam_model: str) -> str:
    match sam_model:
        case 'vit_b':
            return download_sam_vit_b()
        case 'vit_l':
            return download_sam_vit_l()
        case 'vit_h':
            return download_sam_vit_h()
        case _:
            raise ValueError(f'sam model {sam_model} does not exist.')


def download_sam_vit_b():
    model_dir = get_write_directory(common.path_sam)
    file_name = 'sam_vit_b_01ec64.pth'
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sam_vit_b_01ec64.pth',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_sam_vit_l():
    model_dir = get_write_directory(common.path_sam)
    file_name = 'sam_vit_l_0b3195.pth'
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sam_vit_l_0b3195.pth',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_sam_vit_h():
    model_dir = get_write_directory(common.path_sam)
    file_name = 'sam_vit_h_4b8939.pth'
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sam_vit_h_4b8939.pth',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_sdxl_lcm_lora():
    model_dir = get_write_directory(common.paths_loras)
    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/sdxl_lcm_lora.safetensors',
        model_dir=str(model_dir),
        file_name=flags.PerformanceLoRA.Extreme_Speed.value
    )
    return flags.PerformanceLoRA.Extreme_Speed.value


def download_sdxl_lightning_lora():
    model_dir = get_write_directory(common.paths_loras)
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sdxl_lightning_4step_lora.safetensors',
        model_dir=str(model_dir),
        file_name=flags.PerformanceLoRA.Lightning.value
    )
    return flags.PerformanceLoRA.Lightning.value


def download_sdxl_hyper_sd_lora():
    model_dir = get_write_directory(common.paths_loras)
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sdxl_hyper_sd_4step_lora.safetensors',
        model_dir=str(model_dir),
        file_name=flags.PerformanceLoRA.Hyper_SD.value
    )
    return flags.PerformanceLoRA.Hyper_SD.value


def download_siglip_vision_model():
    # Resolve the local clip_vision path
    # This file is currently not used but
    # is for Flux/SD3.5 Image Prompt
    model_dir = get_write_directory(common.path_clip_vision)
    file_name = 'sigclip_vision_patch14_384.safetensors'

    load_file_from_url(
        url='https://huggingface.co/Comfy-Org/siglip_vision_patch14_384/resolve/main/sigclip_vision_patch14_384.safetensors',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_superprompter_model():
    path_superprompter = get_write_directory(common.paths_llms) / 'superprompt-v1'
    load_file_from_url(
        url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/model.safetensors',
        model_dir=str(path_superprompter),
        file_name='model.safetensors'
    )
    load_file_from_url(
        url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/config.json',
        model_dir=str(path_superprompter),
        file_name='config.json'
    )
    load_file_from_url(
        url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/generation_config.json',
        model_dir=str(path_superprompter),
        file_name='generation_config.json'
    )
    load_file_from_url(
        url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/README.md',
        model_dir=str(path_superprompter),
        file_name='README.md'
    )
    load_file_from_url(
        url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/spiece.model',
        model_dir=str(path_superprompter),
        file_name='spiece.model'
    )
    load_file_from_url(
        url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/tokenizer.json',
        model_dir=str(path_superprompter),
        file_name='tokenizer.json'
    )
    load_file_from_url(
        url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/tokenizer_config.json',
        model_dir=str(path_superprompter),
        file_name='tokenizer_config.json'
    )
    return str(path_superprompter / 'model.safetensors')


def download_ultrasharp_model():
    model_dir = get_write_directory(common.path_upscale_models)
    file_name = '4x-UltraSharp.pth'

    load_file_from_url(
        url='https://huggingface.co/lokcx/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)


def download_upscale_model():
    model_dir = get_write_directory(common.path_upscale_models)
    file_name = 'fooocus_upscaler_s409985e5.bin'
    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/fooocus_upscaler_s409985e5.bin',
        model_dir=str(model_dir),
        file_name=file_name
    )
    return str(model_dir / file_name)
