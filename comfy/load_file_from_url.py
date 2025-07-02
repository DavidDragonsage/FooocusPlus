import os
import folder_paths
import json
from pathlib import Path # FooocusPlus_Comfymod
from urllib.parse import urlparse
from typing import Optional


def load_file_from_url(
        url: str,
        *,
        model_dir: str,
        progress: bool = True,
        file_name: Optional[str] = None,
) -> str:
    """Download a file from `url` into `model_dir`, using the file present if possible.
    Returns the path to the downloaded file.
    """
    os.makedirs(model_dir, exist_ok=True)
    if not file_name:
        parts = urlparse(url)
        file_name = os.path.basename(parts.path)
    cached_file = os.path.abspath(os.path.join(model_dir, file_name))
    if not os.path.exists(cached_file):
        if url.find("huggingface.co")>=0:
            url = url.replace('huggingface.co', 'hf-mirror.com')
        print(f'Downloading: "{url}" to {cached_file}\n')
        from torch.hub import download_url_to_file
        download_url_to_file(url, cached_file, progress=progress)

    return cached_file


def load_model_for_path(models_url, root_name):
    models_root = folder_paths.get_folder_paths(root_name)[0]
    for model_path in models_url:
        model_full_path = os.path.join(models_root, model_path)
        if not os.path.exists(model_full_path):
            model_full_path = load_file_from_url(
                url=models_url[model_path], model_dir=models_root, file_name=model_path
            )


# FooocusPlus_Comfymod: set IC-Light paths:
default_base_SD15_name = str(Path(folder_paths.user_models_dir/'checkpoints/SD1.5/realisticVisionV60B1_v51VAE.safetensors'))
default_unet_SD15_name = str(Path(folder_paths.user_models_dir/'unet/iclight_sd15_fc_unet_ldm.safetensors'))

# FooocusPlus_Comfymod: # fake out model downloading: its done in modules.config
def load_model_for_iclight():
    global default_base_SD15_name, default_unet_SD15_name
    models_path = default_unet_SD15_name
    model_full_path = Path(default_unet_SD15_name)
    models_path = default_base_SD15_name
    model_full_path = Path(default_base_SD15_name)
    return
