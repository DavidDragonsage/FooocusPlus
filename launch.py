import sys
import importlib
import common
import enhanced.version as version

# Preserve the update event flag before reloading
cached_version_update = getattr(common, 'version_update', 0)

# Force-reload these modules immediately to
# avoid stale cache problems when updating
importlib.reload(common)
importlib.reload(version)

# Restore the update event flag so the UI can announce the changes
common.version_update = cached_version_update

fooocusplus_ver, hotfix, hotfix_title = version.get_fooocusplus_ver()


import os
import ssl
from pathlib import Path
from common import ROOT
from backend_base.comfy_patch import apply_comfy_patch

print('[System ARGV] ' + str(sys.argv))
print(f'Root {ROOT}')

REINSTALL_ALL = False

if not version.get_required_library():
    # Set the terminal text colour to Bright Red/Orange
    print('\033[91m', end='')
    print()
    print(f'Python Library {version.get_library_ver()} does not support FooocusPlus {fooocusplus_ver}')
    print('Please install the new python_embedded archive from')
    print('https://huggingface.co/DavidDragonsage/FooocusPlus/resolve/main/python_embedded.7z')
    print('The library needs to be extracted to the FooocusPlus directory')
    print()
    # Reset the terminal test colour to default
    print('\033[0m', end='')
    quit()

print()
print('Checking for required library files and patches...')
apply_comfy_patch()

# Environment memory assignments (strictly platform-independent writes)
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'
os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'
os.environ['GRADIO_SERVER_PORT'] = '7865'
# an update would cause some serious errors:
os.environ['NO_ALBUMENTATIONS_UPDATE'] = 'True'
ssl._create_default_https_context = ssl._create_unverified_context


from modules.launch_requirements import is_installed, \
    python, run_pip_url, requirements_met, windows_patch, \
    git_clone, index_url, target_path_install, met_diff

from launch_support import delete_torch_dependencies, \
    dependency_resolver, read_torch_base, \
    write_torch_base

from modules.launch_util import is_win32_standalone_build, \
    python_embedded_path, run, run_pip, \
    verify_installed_version, win32_root

verify_installed_version('torchruntime', '2.1.0', False)

windows_patch()
requirements_file = os.environ.get('REQS_FILE', 'requirements_versions.txt')
if requirements_met(requirements_file):
    print('All requirements met')
else:
    print('Some requirements have not been met')

def ini_args():
    from args_manager import args
    return args


args = ini_args()
if not args.language.startswith('en'):
    from enhanced.translator import load_translator
    load_translator()
from enhanced.translator import interpret

interpret('Checking installed software...')

patch_requirements = 'requirements_patch.txt'
if (REINSTALL_ALL or not requirements_met(patch_requirements)) and not \
    is_win32_standalone_build:
        print('Updating with required patch files...')
        run_pip(f'install -r "{patch_requirements}"', 'patching requirements')

torch_ver = ''
torch_info = ''
import torchruntime
import platform
from modules.user_structure import cleanup_structure

cleanup_structure(args.directml, args.user_dir,
    python_embedded_path, win32_root)


def prepare_environment():
    global torch_ver, fooocusplus_ver, hotfix
    target_path_win = Path(python_embedded_path / 'Lib/site-packages')
    torch_dict = dependency_resolver()
    torch_ver = torch_dict['torch_ver']
    torchvision_ver = torch_dict['torchvision_ver']
    torchaudio_ver = torch_dict['torchaudio_ver']
    xformers_ver = torch_dict['xformers_ver']
    bitsandbytes_ver = torch_dict['bitsandbytes_ver']
    torch_platform_ver = torch_dict['torch_platform_ver']

    torch_base_ver = read_torch_base()

    if common.comfy_capable:
        try:
            import comfy.comfyui_version
            comfy_ver = comfy.comfyui_version.__version__
        except Exception:
            comfy_ver = 'Not Available'
    else:
        comfy_ver = 'Not Available'
    common.comfy_ver = comfy_ver

    print()
    interpret('Program Versions:')
    print(f"Python {sys.version}")
    print(f"Python Library {version.get_library_ver()}, Comfy Version: {comfy_ver}")

    # --- Pinokio System Bypass ---
    # If gpu_type is 'none', bypass the installation of PyTorch and its dependencies
    if args.gpu_type == 'none':
        # If xformers is not installed in the Pinokio environment,
        # enable native PyTorch attention:
        if not is_installed('xformers'):
            args.attention_pytorch = True
            args.disable_xformers = True

        print(f"Torch {torch_ver} (Managed externally by Pinokio)")
        print(f"FooocusPlus Version: {fooocusplus_ver}, Hotfix: {hotfix}")
        return

    # For systems where xformers is disabled,
    # force native PyTorch attention
    if xformers_ver == 'None':
        args.attention_pytorch = True
        args.disable_xformers = True

    # 2. Print standard path-specific CUDA/Torch/Xformers details
    if torch_ver == torch_base_ver:
        from backend_base.__init__ import get_torch_xformers_cuda_version as get_torch_info
        torch_info, xformers_info, cuda_info = get_torch_info()
        if torch_info == '':
            torch_info = 'not installed'
            xformers_info = torch_info
        elif xformers_info == '':
            if args.attention_pytorch:
                xformers_info = 'Not Installed: using native attention'
            else:
                xformers_info = 'not installed'
        elif xformers_info != '' and args.disable_xformers:
            if xformers_ver == 'None':
                delete_torch_dependencies(depend_list='xformers')
                if not is_installed('xformers'):
                    xformers_info = 'Removed: using native attention'
        print(f"Torch {torch_info}{cuda_info}, Xformers {xformers_info}")
    else:
        print()
        print(f"Torch {torch_base_ver}")
        print()

    print(f"FooocusPlus Version: {fooocusplus_ver}, Hotfix: {hotfix}")

    if REINSTALL_ALL or torch_ver != torch_base_ver or \
        torch_info == 'not installed':
        if args.gpu_type == 'auto':
            print('Using Torchruntime to configure Torch')
            print(f'Updating to Torch {torch_ver} and its dependencies:')
        else:
            print(f'Using the "--gpu-type {args.gpu_type}" argument to configure Torch')
            print(f'Installing Torch {torch_ver} and its dependencies:')
        print(torch_dict)
        print()
        delete_torch_dependencies()

        # Setup torch install
        from torchruntime.installer import get_install_commands, get_pip_commands, run_commands
        torch_statement = 'torch==' + torch_ver
        torchvision_statement = ' torchvision==' + torchvision_ver
        torchaudio_statement = ' torchaudio==' + torchaudio_ver
        no_warning_statement = '--no-warn-script-location'
        packages = [no_warning_statement, torch_statement, torchvision_statement, torchaudio_statement]

        # Inject --no-deps for Blackwell/CUDA 13.0
        # to protect NumPy 1.26.4
        if torch_platform_ver == 'cu130':
            packages.append('--no-deps')

        # Run the installer
        cmds = get_install_commands(torch_platform_ver, packages)
        cmds = get_pip_commands(cmds)
        run_commands(cmds)
    else:
        delete_torch_dependencies(['pytorch_lightning',
            'lightning_fabric'])

    verify_installed_version('bitsandbytes', bitsandbytes_ver, False)
    print()

    if xformers_ver != 'None' and (REINSTALL_ALL or not is_installed('xformers')):
        if platform.python_version().startswith('3.10'):
            if torch_platform_ver == 'cu130':
                verify_installed_version('xformers', xformers_ver, False, use_index='https://download.pytorch.org/whl/cu130', package_url='')
            elif torch_platform_ver == 'cu128':
                verify_installed_version('xformers', xformers_ver, False, use_index='https://download.pytorch.org/whl/cu128', package_url='')
            elif torch_platform_ver == 'cu124':
                verify_installed_version('xformers', xformers_ver, False, use_index='https://download.pytorch.org/whl/cu124', package_url='')
            else:
                xformers_statement = 'xformers==' + xformers_ver
                torchruntime.install(['--no-deps', xformers_statement])
        else:
            print('Installation of xformers is not supported in this version of Python.')
            print('You can also check this and build manually:' + \
                'https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Xformers#building-xformers-on-windows-by-duckness')
            if not is_installed('xformers'):
                exit(0)
    return


vae_approx_filenames = [
    ('xlvaeapp.pth', 'https://huggingface.co/lllyasviel/misc/resolve/main/xlvaeapp.pth'),
    ('vaeapp_sd15.pth', 'https://huggingface.co/lllyasviel/misc/resolve/main/vaeapp_sd15.pt'),
    ('xl-to-v1_interposer-v4.0.safetensors',
     'https://huggingface.co/mashb1t/misc/resolve/main/xl-to-v1_interposer-v4.0.safetensors')
]

prepare_environment()
interpret('Analyzing the graphics system...')

if args.gpu_device_id is not None:
    os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu_device_id)
    print('Set device to:', args.gpu_device_id)

if args.hf_mirror is not None:
    os.environ['HF_MIRROR'] = str(args.hf_mirror)
    print('The hf_mirror is:', args.hf_mirror)

import modules.loader as loader
import modules.preset_resource as PR
from enhanced.backend import comfyd
from modules import config
from modules.hash_cache import init_cache
from modules.preset_support import init_config_preset
from modules.loader import load_file_from_url

# Cast directory Path targets to string for os.environ compatibility
os.environ['U2NET_HOME'] = str(common.paths_inpaint[0])
os.environ['BERT_HOME'] = str(common.paths_llms[0])
os.environ['GRADIO_TEMP_DIR'] = str(config.temp_path)


# Blackwell sm_100 Specific Performance Tuning
# Excludes Apple Silicon using the force_compatibility flag
if (torch_ver == '2.10.0'
        and not getattr(common, 'is_legacy_gpu', False)
        and not getattr(common, 'force_compatibility', False)
        and sys.platform != 'darwin'):

    print()
    interpret('[Launch] Applying optimized Blackwell CUDA 13 and hardware tuning settings...')
    print()

    # Memory Allocator Optimization
    # Prevents memory fragmentation on Blackwell GPUs
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True,max_split_size_mb:512'
    os.environ['TORCH_CUDA_GRAPH_MEM_POOL_COALESCE'] = '1'
    os.environ['PYTORCH_JIT_USE_NNC'] = '0'

    # PyTorch C++ Level Optimizations (Defensively wrapped to prevent launch crashes)
    try:
        import torch

        # Enable TF32 math precision on Blackwell Tensor Cores
        try:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
        except Exception as e:
            interpret('[Launch] Warning: Failed to configure TF32 precision:', e)

        # Force cuDNN autotuner to search for optimal sm_100 execution paths
        try:
            torch.backends.cudnn.benchmark = True
        except Exception as e:
            interpret('[Launch] Warning: Failed to configure cuDNN benchmark:', e)

        # Ensure native attention dispatches directly to optimized FlashAttention/SDP kernels
        try:
            # Correct PyTorch API names are enable_flash_sdp, enable_mem_efficient_sdp, enable_math_sdp
            if hasattr(torch.backends.cuda, 'enable_flash_sdp'):
                torch.backends.cuda.enable_flash_sdp(True)
            if hasattr(torch.backends.cuda, 'enable_mem_efficient_sdp'):
                torch.backends.cuda.enable_mem_efficient_sdp(True)
            if hasattr(torch.backends.cuda, 'enable_math_sdp'):
                torch.backends.cuda.enable_math_sdp(False)
        except Exception as e:
            interpret('[Launch] Warning: Failed to configure Scaled Dot-Product Attention:', e)

    except Exception as e:
        interpret('[Launch] Warning: Failed to apply Blackwell hardware tuning:', e)


write_torch_base(torch_ver)

# Comfy Lockout Control & Bypass Check
# common.total_vram_gb & common.torch_status
# are set in launch_support.
# Set the terminal text colour to
# Bold Yellow for this section
print('\033[1;33m', end='')
if args.disable_comfyd:
    interpret('ComfyUI has been disabled by the command line argument:', '"--disable-comfyd"')
elif common.total_vram_gb < 4:
    args.async_cuda_allocation = False
    args.disable_async_cuda_allocation = True
    print()
    interpret('Systems with less than 4GB of VRAM are not able to run large models, including:',
        'Flux, SD3.5, Kolors, HyDiT and Z-Image')
    interpret('The ComfyUI support system for these models will be disabled')
elif common.torch_status != 'New':
    print()
    interpret('FooocusPlus uses ComfyUI to support diverse models such as Flux, Kolors, HyDit, SD1.5, SD3.5 and Z-Image.')
    interpret('ComfyUI no longer supports legacy graphics hardware (GPUs) that requires PyTorch 2.5 or earlier.')
    interpret('The installed GPU is using PyTorch', common.torch_status)
    interpret('Comfy startup errors occur and some Comfy custom nodes do not load at all when used with legacy GPUs.')
    print()
    interpret('For legacy GPUs, Comfy mode is locked out.')
    interpret('This was an agonizing choice but it is irresponsible to support a partially broken system.')
    interpret('However FooocusPlus will continue to fully support SDXL mode (original Fooocus mode) which is completely independent of Comfy.')
elif not config.default_comfy_active_checkbox:
    print()
    interpret('Comfy has been temporarily disabled using the config.txt "comfyd_active_checkbox" option.')
    interpret('It can be re-enabled within the UI from the "Enable Comfy Mode" checkbox under the Extras tab.')
elif common.comfy_active and common.is_legacy_gpu and not common.force_compatibility:
    print()
    interpret('Comfy lockout has been bypassed using run_FooocusPlus_cu128.bat or a similar file. Please be aware that this is entirely at your own risk. This method is unsupported and any Comfy related bug reports filed for a system that bypasses Comfy Lockout will be removed.')
    print()
    interpret('At the very least, expect this method to cause image generation to be slower in both Comfy and SDXL modes, and indeed Comfy may still not work using this option due to hardware limitations. You can revert to optimal mode using run_FooocusPlus_cu124.bat.')

# Reset the terminal text colour to default
print('\033[0m', end='')

if common.comfy_capable == False:
    config.default_comfy_active_checkbox = False

# This equivalence avoids any chance of circular errors:
common.comfy_active = config.default_comfy_active_checkbox

if common.total_vram_gb < 6:
    print()
    interpret(f'The video subsystem has only {common.total_vram_gb} GB of memory (VRAM) but FooocusPlus')
    interpret('will give you access to models that are optimized for Low VRAM systems.')
    interpret('However, any system with less than 6 GB of VRAM will tend to be slow and unreliable.')
    interpret('Some 4 GB VRAM cards may even be unable to generate SDXL images')
    if common.comfy_capable:
        interpret('and they may or may not be able to generate images using Flux or other large models.')

print()
interpret('Initializing preset support...')


def download_models(default_model, previous_default_models, checkpoint_downloads, embeddings_downloads, lora_downloads, vae_downloads):
    # Only download the universal system/engine files required for boot
    for file_name, url in vae_approx_filenames:
        load_file_from_url(url=url, model_dir=str(Path(common.path_vae_approx)), file_name=file_name)

    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/fooocus_expansion.bin',
        model_dir=str(Path(common.path_fooocus_expansion)),
        file_name='pytorch_model.bin'
    )

    # Return immediately:
    # async_worker loads checkpoints, LoRAs & VAEs
    # on demand from the presets
    return default_model, checkpoint_downloads


if (config.default_low_vram_presets == True or common.total_vram_gb < 6) and \
    (args.preset == 'initial' or args.preset == 'Default'):
    low_vram_preset_content = PR.get_lowVRAM_preset_content()
    if low_vram_preset_content:
        common.preset_content = low_vram_preset_content
        config.default_low_vram_presets = True
    else:
        PR.get_initial_preset_content()
        config.default_low_vram_presets = False
    if common.comfy_active:
        comfyd.stop()
else:
    PR.get_initial_preset_content()

init_config_preset()

# This call prevents errors but does not
# download models specified by the presets
loader.base_model_name, config.checkpoint_downloads = download_models(
    loader.base_model_name, config.previous_default_models,
    config.checkpoint_downloads, config.embeddings_downloads,
    config.lora_downloads, config.vae_downloads)

loader.update_files()
init_cache(loader.model_filenames, common.paths_checkpoints, loader.lora_filenames, common.paths_loras)

from webui import *