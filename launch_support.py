import os
import glob
import platform
import shutil
import sys
import args_manager
import modules.user_structure as US
from pathlib import Path

current_dir = Path.cwd()
win32_root = current_dir.resolve().parent
python_embedded_path = Path(win32_root/'python_embedded')
is_win32_standalone_build = python_embedded_path.is_dir()

torch_base_ver = ''


def dependency_resolver():
    """
    Provides the dependent versions of a Torch build.
    Returns a dictionary with:
    - torch_ver: str
    - torchvision_ver: str
    - torchaudio_ver: str
    - xformers_ver: str
    - pytorchlightning_ver: str
    - lightningfabric_ver: str
    - torch_platform_ver: str
    """
    import torchruntime
    from torchruntime.device_db import get_gpus
    from torchruntime.platform_detection import get_torch_platform, get_nvidia_arch

    # set our defaults for 2.7.1
    torch_default = "2.7.1"
    torchvision_default = "0.22.1"
    torchaudio_default = "2.7.1"
    xformers_default = "0.0.30"
    pytorchlightning_default = "2.5.2"
    lightningfabric_default = "2.5.2"
    torch_platform_default = "cu128"

    torch_ver = torch_default # initialize torch to the default
    gpu_infos = get_gpus()
    torchruntime_platform = get_torch_platform(gpu_infos)

    device_names = set(gpu.device_name for gpu in gpu_infos)
    arch_version = get_nvidia_arch(device_names)

    # First, take care of special cases
    # Note, torchruntime/torchruntime/platform_detection.py
    # suggests "directml" should be used for Intel
    #
    if platform.machine == "amd64" or torchruntime_platform == "xpu" \
        or args_manager.args.gpu_type == 'directml' \
        or args_manager.args.gpu_type == 'amd64':
        args_manager.args.directml = True # switch on AMD/Intel support
        torch_ver = "2.3.1"


    # --gpu-type command line overrides: in this case Torchruntime is ignored
    # but if "gpu_type == auto" (the default) then Torchruntime is active
    if args_manager.args.gpu_type == "amd64":
        torch_ver = "2.2.2"
    elif args_manager.args.gpu_type == "cu124":
        torch_ver = "2.4.1"
    elif args_manager.args.gpu_type == "cu128":
        torch_ver = "2.7.1"
    elif args_manager.args.gpu_type == "rocm5.2":
        torch_ver = "1.13.1"
    elif args_manager.args.gpu_type == "rocm5.7":
        torch_ver = "2.3.1"


    # Detection Logic: Windows (win32) defaults to "2.7.1+cu128"
    # almost all modern NVIDIA cards including NVIDIA 50xx (Blackwell)
    elif sys.platform == "win32":
        if arch_version >= 7.5:
            torch_ver = "2.7.1"
        # older NVIDIA cards like the 10xx series & P40 use cu124
        else:
            torch_ver = "2.4.1"

    elif sys.platform == "linux":  # Linux also defaults to "2.7.1+cu128"
        if arch_version >= 7.5: # NVIDIA GTX1650 through to NVIDIA 5xxx (Blackwell)
            torch_ver = "2.7.1"
        else:
            torch_ver = "2.4.1" # older NVIDIA cards like the 10xx & P40 use cu124
        if torchruntime_platform == "rocm5.7":
            torch_ver = "2.3.1"
        elif torchruntime_platform == "rocm5.2":
            torch_ver = "1.13.1"

    elif sys.platform == "darwin": # (OSX) Apple Silicon defaults to "2.5.1"
        if platform.machine == "amd64":
            torch_ver = "2.2.2"

    # Begin the assignment of dependencies:
    if torch_ver == "2.5.1":
        dependencies = dict(
            torch_ver = "2.5.1",
            torchvision_ver = "0.20.1",
            torchaudio_ver = "2.5.1",
            xformers_ver = "0.0.29.post1",
            pytorchlightning_ver = "2.5.1.post0",
            lightningfabric_ver = "2.5.1",
            torch_platform_ver = "cu124",
        )

    elif torch_ver == "2.4.1":
        dependencies = dict(
            torch_ver = "2.4.1",
            torchvision_ver = "0.19.1",
            torchaudio_ver = "2.4.1",
            xformers_ver = "0.0.28.post1",
            pytorchlightning_ver = "2.5.1.post0", # will be compatible with slightly older versions
            lightningfabric_ver = "2.5.1",
            torch_platform_ver = "cu124",
        )

    elif torch_ver == "2.3.1": # for Linux rocm5.7
        dependencies = dict(
            torch_ver = "2.3.1",
            torchvision_ver = "0.18.1",
            torchaudio_ver = "2.3.1",
            xformers_ver = "0.0.27",
            pytorchlightning_ver = "2.4.0",
            lightningfabric_ver = "2.4.0",
            torch_platform_ver = "cu124",
        )

    elif torch_ver == "2.2.2": # last version supporting Intel Macs
        dependencies = dict(
            torch_ver = "2.2.2",
            torchvision_ver = "0.17.2",
            torchaudio_ver = "2.2.2",
            xformers_ver = "0.0.27.post2", # but not MPS compatible
            pytorchlightning_ver = "2.4.0", # confirm 2.5.1 compatibility when versioning policy updated
            lightningfabric_ver = "2.4.0",
            torch_platform_ver = "cu124",
        )

    elif torch_ver == "1.13.1": # earliest possible supported release: rocm5.2
        dependencies = dict(
            torch_ver = "1.13.1",
            torchvision_ver = "0.14.1",
            torchaudio_ver = "0.13.1",
            xformers_ver = "0.0.20", # but not compatible with ROCm, rocm6.2.4 only
            pytorchlightning_ver = "2.2.5",
            lightningfabric_ver = "2.2.5",
            torch_platform_ver = "cu124",
        )

    else:
        # use the torch_ver 2.7.1 defaults
        dependencies = dict(
            torch_ver = torch_default,
            torchvision_ver = torchvision_default,
            torchaudio_ver = torchaudio_default,
            xformers_ver = xformers_default,
            pytorchlightning_ver = pytorchlightning_default,
            lightningfabric_ver = lightningfabric_default,
            torch_platform_ver = torch_platform_default,
        )

    # return the result
    return dependencies


def delete_torch_dependencies():
    if is_win32_standalone_build:
        library_path = os.path.abspath(f'../python_embedded/Lib/site-packages')
        file_paths = ['torch', 'torchaudio', 'torchvision', 'xformers',\
            'pytorch_lightning', 'lightning-fabric']
        for file_path in file_paths:
            scratch_path = file_path
            if os.path.exists(f'{library_path}/{file_path}'):
                print(file_path)
                shutil.rmtree(f'{library_path}/{file_path}', ignore_errors=True)
            for scratch_path in glob.glob(f'{library_path}/{file_path}-*-info'):
                print(scratch_path)
                shutil.rmtree(scratch_path, ignore_errors=True)
    return


def get_split_value(full_string):
    divider = '= '
    scratch = full_string.split(divider, 1)
    split_value = scratch[1] if len(scratch) > 1 else ''
    return split_value

# IMPORTANT! The config.txt user_dir setting has been removed
# if for some reason the args_manager.args.user_dir setting is not valid
# it is set to the default value in this function
def get_torch_base_path(): # the config.txt user_dir
    global win32_root      # setting is deprecated
    try:
        user_dir_path = Path(args_manager.args.user_dir)
    except:
        user_dir_path = Path(win32_root/'UserDir')
        args_manager.args.user_dir = user_dir_path
    torch_base_path = Path(user_dir_path/'torch_base.txt')
    return torch_base_path

def read_torch_base():     # the file auto-closes
    torch_base_text = US.load_textfile(get_torch_base_path())
    if torch_base_text == False:
        torch_base_ver = 'needs to be installed'
    else:
        torch_base_text = torch_base_text.strip()
        torch_base_ver = get_split_value(torch_base_text)
        if torch_base_ver == '':
            torch_base_ver = 'is undefined'
    return torch_base_ver

def write_torch_base(torch_base_ver): # the file auto-closes
    US.save_textfile(f"Torch base version = {torch_base_ver}", get_torch_base_path())
    return


