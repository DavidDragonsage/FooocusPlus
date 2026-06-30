import ctypes
import subprocess
import platform
import shutil
import sys
from pathlib import Path
from packaging.version import parse as parse_version

from args_manager import args
import modules.user_structure as US
from modules.launch_util import is_win32_standalone_build, \
    python_embedded_path, win32_root

# moved from args_parser, but uses is_win32_standalone_build
# instead of the obsolete args.is_windows_embedded_python
if is_win32_standalone_build:
    args.in_browser = True
if args.disable_in_browser:
    args.in_browser = False

torch_base_ver = ''


def get_nvidia_driver_compatibility():
    """
    Determines if the installed NVIDIA driver
    supports CUDA 13.0.
    Returns:
        tuple (bool, str): (is_compatible, status_description)
    """
    # 1. Query the driver's maximum supported
    # CUDA API version via ctypes
    try:
        cuda_version = ctypes.c_int()
        if sys.platform == 'win32':
            cuda_lib = ctypes.windll.nvcuda
            if cuda_lib.cuDriverGetVersion(ctypes.byref(cuda_version)) == 0:
                if cuda_version.value >= 13000:
                    major = cuda_version.value // 1000
                    minor = (cuda_version.value % 1000) // 10
                    return True, f"CUDA {major}.{minor} supported (Driver API value: {cuda_version.value})"
        elif sys.platform == 'linux':
            cuda_lib = ctypes.CDLL('libcuda.so')
            if cuda_lib.cuDriverGetVersion(ctypes.byref(cuda_version)) == 0:
                if cuda_version.value >= 13000:
                    major = cuda_version.value // 1000
                    minor = (cuda_version.value % 1000) // 10
                    return True, f"CUDA {major}.{minor} supported (Driver API value: {cuda_version.value})"
    except Exception:
        pass

    # 2. Fallback: Parse the raw driver
    # version string from nvidia-smi
    try:
        res = subprocess.run(
            ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            check=True
        )
        driver_str = res.stdout.strip()
        if driver_str:
            if parse_version(driver_str) >= parse_version('580.65'):
                return True, f"Driver version {driver_str} >= 580.65"
            else:
                return False, f"Driver version {driver_str} < 580.65"
    except Exception as e:
        return False, f"NVIDIA driver or nvidia-smi not detected: {e}"

    return False, "The NVIDIA graphics card and/or driver status is unknown"


def dependency_resolver():
    """
    Provides the dependent versions of a Torch build.
    Returns a dictionary with:
    - torch_ver: str
    - torchvision_ver: str
    - torchaudio_ver: str
    - xformers_ver: str
    - bitsandbytes_default: str
    - torch_platform_ver: str
    """
    import torchruntime
    from torchruntime.device_db import get_gpus
    from torchruntime.platform_detection import get_torch_platform, get_nvidia_arch

    # set our defaults for 2.7.1
    torch_default = "2.7.1"
    torchvision_default = "0.22.1"
    torchaudio_default = "2.7.1"
    if sys.platform == "linux":
        xformers_default = "0.0.31"
    else:
        xformers_default = "0.0.30"
    bitsandbytes_default = "0.49.2"
    torch_platform_default = "cu128"

    torch_ver = torch_default # initialize torch to the default
    gpu_infos = get_gpus()
    torchruntime_platform = get_torch_platform(gpu_infos)
    device_names = set(gpu.device_name for gpu in gpu_infos)
    arch_version = get_nvidia_arch(device_names)

    # First, take care of special cases
    # Note, torchruntime.torchruntime.platform_detection.py
    # suggests "directml" should be used for Intel
    #
    if platform.machine == "amd64" or torchruntime_platform == "xpu" \
        or args.gpu_type == 'directml' \
        or args.gpu_type == 'amd64':
        if not args.directml:
            args.directml = -1 # trigger an GPU ID auto-detect
        torch_ver = "2.3.1"

    # check for latest NVIDIA driver
    # fallback to Torch "2.7.1" if not
    new_driver, driver_msg = get_nvidia_driver_compatibility()
    print()
    if new_driver:
        print(f"Updated NVIDIA driver detected: {driver_msg}")
    else:
        print(f"This system does not use NVIDIA hardware or the NVIDIA driver has not been updated: {driver_msg}")

    # --gpu-type command line overrides:
    # in this case Torchruntime is ignored
    # but if "gpu_type == auto" (the default)
    # then Torchruntime is active
    if args.gpu_type == "amd64" or args.gpu_type == "directml":
        torchruntime_platform = "directml"
        if args.gpu_type == "directml":
            torch_ver = "2.4.1"
    elif args.gpu_type == "cu124":
        torch_ver = "2.4.1"
        torchruntime_platform = "cu124"
    elif args.gpu_type == "cu128" or (
        args.gpu_type == 'cu130' and not
        new_driver):
        torch_ver = "2.7.1"
        torchruntime_platform = "cu128"
    elif args.gpu_type == 'cu130':
        torch_ver = '2.10.0'
        torchruntime_platform = 'cu130'
    elif args.gpu_type == "rocm5.2":
        torch_ver = "1.13.1"
        torchruntime_platform = "rocm5.2"
    elif args.gpu_type == "rocm5.7":
        torch_ver = "2.3.1"
        torchruntime_platform = "rocm5.7"

    # Detection Logic: Windows (win32) defaults to
    # "2.10.0+cu130" for most modern NVidia GPUs
    elif sys.platform == "win32":
        # New: Full support for Blackwell (50xx)
        if arch_version >= 12.0 and new_driver:
            torch_ver = "2.10.0"
            torchruntime_platform = "cu130"
        elif arch_version >= 7.5:
            torch_ver = "2.7.1"
            torchruntime_platform = "cu128"
        # older NVIDIA cards like the 10xx
        # series & P40 use cu124 and
        # AMD, using directml instead:
        else:
            torch_ver = "2.4.1"

    # Linux also defaults to "2.10.0+cu130"
    elif sys.platform == "linux":
        # New: Full support for Blackwell (50xx)
        if arch_version >= 12.0 and new_driver:
            torch_ver = "2.10.0"
            torchruntime_platform = "cu130"

        elif arch_version >= 7.5:
            # NVIDIA GTX1650 to NVIDIA 5xxx
            # (Blackwell fallback)
            torch_ver = "2.7.1"
        else:
            # older NVIDIA cards like the 10xx
            # & P40 use cu124 and AMD,
            # using directml instead
            torch_ver = "2.4.1"
        if torchruntime_platform == "rocm5.7":
            torch_ver = "2.3.1"
        elif torchruntime_platform == "rocm5.2":
            torch_ver = "1.13.1"

    # (OSX) Apple Silicon"2.5.1"
    elif sys.platform == "darwin":
        torch_ver = "2.5.1"
        if platform.machine == "amd64":
            torch_ver = "2.2.2"

    # Begin the assignment of dependencies:
    if torch_ver == '2.10.0': # Blackwell native mode
        if arch_version >= 12.0:
            xformers_blackwell = 'None'
        else:
            xformers_blackwell = '0.0.34'
        dependencies = dict(
            torch_ver = '2.10.0',
            torchvision_ver = '0.25.0',
            torchaudio_ver = '2.10.0',
            xformers_ver = xformers_blackwell,
            bitsandbytes_ver = '0.48.0',
            torch_platform_ver = torchruntime_platform
        )

    elif torch_ver == "2.5.1":
        dependencies = dict(
            torch_ver = "2.5.1",
            torchvision_ver = "0.20.1",
            torchaudio_ver = "2.5.1",
            xformers_ver = "0.0.29.post1",
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torchruntime_platform
        )

    elif torch_ver == "2.4.1":
        dependencies = dict(
            torch_ver = "2.4.1",
            torchvision_ver = "0.19.1",
            torchaudio_ver = "2.4.1",
            xformers_ver = "0.0.28.post1",
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torchruntime_platform
        )

     # for Linux rocm5.7
    elif torch_ver == "2.3.1":
        dependencies = dict(
            torch_ver = "2.3.1",
            torchvision_ver = "0.18.1",
            torchaudio_ver = "2.3.1",
            xformers_ver = "0.0.27",
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torchruntime_platform
        )

    # the last version supporting Intel Macs
    elif torch_ver == "2.2.2":
        dependencies = dict(
            torch_ver = "2.2.2",
            torchvision_ver = "0.17.2",
            torchaudio_ver = "2.2.2",
            xformers_ver = "0.0.27.post2", # but not MPS compatible
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torchruntime_platform
        )

    # earliest possible supported release: rocm5.2
    elif torch_ver == "1.13.1":
        dependencies = dict(
            torch_ver = "1.13.1",
            torchvision_ver = "0.14.1",
            torchaudio_ver = "0.13.1",
            xformers_ver = "0.0.20", # but not compatible with ROCm, rocm6.2.4 only
            bitsandbytes_ver = "0.42.0",
            torch_platform_ver = torchruntime_platform
        )

    else:
        # use the torch_ver 2.7.1 defaults
        dependencies = dict(
            torch_ver = torch_default,
            torchvision_ver = torchvision_default,
            torchaudio_ver = torchaudio_default,
            xformers_ver = xformers_default,
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torch_platform_default
        )

    # return the result
    return dependencies


def delete_torch_dependencies(depend_list=None):
    """
    Cleans out older installed PyTorch and related
    dependency folders from site-packages
    to prepare for a fresh installation.
    """
    if is_win32_standalone_build:
        # Resolve the site-packages directory
        # cleanly using Pathlib
        library_path = (Path(python_embedded_path) / 'Lib' / 'site-packages').resolve()

        if depend_list is None:
            file_paths = [
                'torch', 'torchaudio',
                'torchvision', 'xformers',
                'pytorch_lightning',
                'lightning_fabric',
                'bitsandbytes'
            ]
        else:
            file_paths = depend_list

        for folder_name in file_paths:
            # 1. Clean up the physical package directory
            package_dir = library_path / folder_name
            if package_dir.exists():
                print(f"Removing package directory: {folder_name}")
                shutil.rmtree(package_dir, ignore_errors=True)

            # 2. Clean up metadata dist-info
            # directories (replaces glob.glob)
            # Matches folder patterns like:
            # xformers-0.0.34-info,
            # bitsandbytes-0.49.2.dist-info, etc.
            for dist_info_dir in library_path.glob(f"{folder_name}-*-info"):
                print(f"Removing metadata folder: {dist_info_dir.name}")
                shutil.rmtree(dist_info_dir, ignore_errors=True)
    return


# IMPORTANT! The config.txt user_dir setting
# has been removed if for some reason the
# args.user_dir setting is not valid it is
# set to the default value in this function
def get_torch_base_path():
    global win32_root
    try:
        user_path = Path(args.user_dir)
    except:
        user_path = Path(win32_root/'UserDir')
        args.user_dir = user_path
    torch_base_path = Path(user_path/'torch_base.txt')
    return torch_base_path

def read_torch_base():     # the file auto-closes
    torch_base_text = US.load_textfile(get_torch_base_path())
    if torch_base_text == False:
        torch_base_ver = 'needs to be installed'
    else:
        torch_base_ver = US.locate_value(torch_base_text, 'Torch base version = ')
        if torch_base_ver == '':
            torch_base_ver = 'is undefined'
    return torch_base_ver

def write_torch_base(torch_base_ver): # the file auto-closes
    US.save_textfile(f"Torch base version = {torch_base_ver}", get_torch_base_path())
    return

def perform_btn_click():
    return
