import ctypes
import subprocess
import platform
import shutil
import sys
from pathlib import Path
from packaging.version import parse as parse_version

import common
import modules.user_structure as US
from args_manager import args
from modules.launch_util import is_win32_standalone_build, \
    python_embedded_path, win32_root

# moved from args_parser, but uses is_win32_standalone_build
# instead of the obsolete args.is_windows_embedded_python
if is_win32_standalone_build:
    args.in_browser = True
if args.disable_in_browser:
    args.in_browser = False

torch_base_ver = ''


def define_comfy_lockout(torch_ver_str, new_driver, driver_msg, total_vram_gb):
    """
    Evaluates the active PyTorch version,
    configures common.torch_status,
    then prints the localized hardware
    and driver compatibility warnings.
    """
    torch_ver_list = [int(x) for x in torch_ver_str.split('+')[0].split('.')[:2]]

    # --- UNIFIED STARTUP LOCKOUT ---
    # If PyTorch is legacy (< 2.7) or VRAM is extremely low (< 4GB),
    # force-disable Comfy at the earliest possible stage.
    common.comfy_capable = torch_ver_list >= [2, 7] and total_vram_gb >= 4.0 and not args.disable_comfyd

    if torch_ver_list < [2, 7]:
        common.torch_status = torch_ver_str
        print(f'The video system is set for PyTorch {torch_ver_str}')
        print('This software library is optimal for legacy hardware.')
    else:
        common.torch_status = 'New'
        if new_driver:
            print(f'Updated NVIDIA driver detected: {driver_msg}')
        else:
            print(f'This system does not use NVIDIA hardware or the NVIDIA driver has not been updated: {driver_msg}')
    return


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


def get_system_vram_gb():
    """
    Safely retrieves the total VRAM
    (or Apple Unified Memory) of the primary GPU
    prioritizing PyTorch's native checks if available
    to prevent slow subprocess calls on subsequent boots.
    """
    print()
    # Primary PyTorch Check
    # For all subsequent boots once PyTorch is installed
    try:
        import torch
        if torch.cuda.is_available():
            dev = torch.device(torch.cuda.current_device())
            vram_info = torch.cuda.get_device_properties(dev).total_memory / (1024 * 1024 * 1024)
            vram_rounded = round(vram_info)
            print(f'VRAM information loaded from PyTorch: {vram_rounded} GB')
            return vram_rounded
        elif hasattr(torch, 'xpu') and torch.xpu.is_available():
            dev = torch.device('xpu')
            vram_info = torch.xpu.get_device_properties(dev).total_memory / (1024 * 1024 * 1024)
            vram_rounded = round(vram_info)
            print(f'VRAM information loaded from PyTorch XPU: {vram_rounded} GB')
            return vram_rounded
    except Exception:
        pass

    # --- First-Boot Fallback Section Begins ---
    # Executes only if PyTorch is not yet installed
    if sys.platform == 'win32':
        # Primary NVIDIA Check (Windows)
        # nvidia-smi is installed natively with all NVIDIA drivers and is 100% accurate.
        try:
            res = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, check=True
            )
            vrams = [int(x.strip()) for x in res.stdout.strip().split() if x.strip().isdigit()]
            if vrams:
                vram_info = max(vrams) / 1024.0
                vram_rounded = round(vram_info)
                print(f'Windows VRAM information loaded from nvidia-smi: {vram_rounded} GB')
                return vram_rounded
        except Exception:
            pass

        # Fallback: Try WMI/PowerShell For AMD/Intel
        # Windows users. Caps at 4.0 GB, but it is
        # perfect for establishing < 4.0 GB Comfy lockout
        try:
            cmd = 'powershell -command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty AdapterRAM"'
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            vrams = [int(x.strip()) for x in output.strip().split() if x.strip().isdigit()]
            if vrams:
                vram_info = max(vrams) / (1024 * 1024 * 1024)
                vram_rounded = round(vram_info)
                print(f'Windows VRAM information loaded from WMI: {vram_rounded} GB')
                return vram_rounded
        except Exception:
            pass

    elif sys.platform == 'linux':
        # Query nvidia-smi for NVIDIA GPUs
        try:
            res = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, check=True
            )
            vrams = [int(x.strip()) for x in res.stdout.strip().split() if x.strip().isdigit()]
            if vrams:
                vram_info = max(vrams) / 1024.0
                vram_rounded = round(vram_info)
                print(f'Linux VRAM information loaded from nvidia-smi: {vram_rounded} GB')
                return vram_rounded
        except Exception:
            pass

        # Fallback: Try rocm-smi (AMD ROCm on Linux)
        try:
            res = subprocess.run(
                ['rocm-smi', '--showmeminfo', 'vram'],
                capture_output=True, text=True, check=True
            )
            all_numbers = [int(s) for s in re.findall(r'\d+', res.stdout)]
            vrams = [x for x in all_numbers if x >= 2147483648]
            if vrams:
                vram_info = max(vrams) / (1024 * 1024 * 1024)
                vram_rounded = round(vram_info)
                print(f'Linux VRAM information loaded from rocm-smi: {vram_rounded} GB')
                return vram_rounded
        except Exception:
            pass

    elif sys.platform == 'darwin':
        try:
            # On macOS, unified memory is the hardware memory size
            output = subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True, stderr=subprocess.DEVNULL)
            vram_info = int(output.strip()) / (1024 * 1024 * 1024)
            vram_rounded = round(vram_info)
            print(f'macOS unified memory information loaded from the hardware memory size: {vram_rounded} GB')
            return vram_rounded
        except Exception:
            pass

    print('No reported VRAM!')
    return 0


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

    # Check for video driver compatibility
    new_driver, driver_msg = get_nvidia_driver_compatibility()

    # Record total VRAM in GB
    total_vram_gb = get_system_vram_gb()
    common.total_vram_gb = total_vram_gb

    # --- Pinokio External Resolver Bypass ---
    if args.gpu_type == 'none':
        try:
            import importlib.metadata
            installed_torch_ver = importlib.metadata.version('torch')
        except Exception:
            installed_torch_ver = '2.7.1'  # Fallback default

        # Do the comfy lockout check
        define_comfy_lockout(installed_torch_ver, new_driver, driver_msg, total_vram_gb)

        # Return a safe dictionary mapping to
        # prevent unpacking errors in launch.py
        return dict(
            torch_ver=installed_torch_ver,
            torchvision_ver='None',
            torchaudio_ver='None',
            xformers_ver='None',
            bitsandbytes_ver='None',
            torch_platform_ver='none'
        )

    # set our defaults for 2.7.1
    torch_default = '2.7.1'
    torchvision_default = '0.22.1'
    torchaudio_default = '2.7.1'
    bitsandbytes_default = '0.49.2'
    torch_platform_default = 'cu128'

    torch_ver = torch_default # initialize torch to the default
    gpu_infos = get_gpus()
    torchruntime_platform = get_torch_platform(gpu_infos)
    device_names = set(gpu.device_name for gpu in gpu_infos)
    arch_version = get_nvidia_arch(device_names)

    # First, take care of special cases
    # Note, torchruntime.torchruntime.platform_detection.py
    # suggests "directml" should be used for Intel
    #
    if platform.machine == 'amd64' or torchruntime_platform == 'xpu' \
        or args.gpu_type == 'directml' \
        or args.gpu_type == 'amd64':
        if not args.directml:
            args.directml = -1 # trigger a GPU ID auto-detect
        torch_ver = '2.3.1'

    # --gpu-type command line overrides:
    # in this case Torchruntime is ignored
    # but if "gpu_type == auto" (the default)
    # then Torchruntime is active
    if args.gpu_type == 'amd64' or args.gpu_type == 'directml':
        torchruntime_platform = 'directml'
        if args.gpu_type == 'directml':
            torch_ver = '2.4.1'
    elif args.gpu_type == 'cu124':
        torch_ver = '2.4.1'
        torchruntime_platform = 'cu124'
    elif args.gpu_type == 'cu128' or (
        args.gpu_type == 'cu130' and not
        new_driver):
        torch_ver = '2.7.1'
        torchruntime_platform = 'cu128'
    elif args.gpu_type == 'cu130':
        torch_ver = '2.10.0'
        torchruntime_platform = 'cu130'
    elif args.gpu_type == 'rocm5.2':
        torch_ver = '1.13.1'
        torchruntime_platform = 'rocm5.2'
    elif args.gpu_type == 'rocm5.7':
        torch_ver = '2.3.1'
        torchruntime_platform = 'rocm5.7'

    # Detection Logic: Windows (win32) defaults to
    # "2.7.1+cu128" for most modern NVidia GPUs
    elif sys.platform == 'win32':
        # New: Full support for Blackwell (50xx)
        if arch_version >= 12.0 and new_driver:
            torch_ver = '2.10.0'
            torch_platform_ver = 'cu130'
        elif arch_version >= 7.5:
            torch_ver = '2.7.1'
            torch_platform_ver = 'cu128'

        # --- FORCED COMPATIBILITY MODE (Windows) ---
        # If legacy GPU but has at least 11 GB VRAM
        # and user has not disabled Comfy,
        # and we are using NVIDIA, allow upgrading
        # to PyTorch 2.7.1 to bypass the lockout
        elif arch_version >= 6.0 and total_vram_gb >= 11.0 and not args.disable_comfyd and args.gpu_type != 'cu124':
            common.force_compatibility = True
            torch_ver = '2.7.1'
            torch_platform_ver = 'cu128'
        else:
            torch_ver = '2.4.1'

    # Linux detection logic
    elif sys.platform == 'linux':
        if arch_version >= 12.0 and new_driver:
            torch_ver = '2.10.0'
            torch_platform_ver = 'cu130'
        elif arch_version >= 7.5:
            torch_ver = '2.7.1'
        # --- FORCED COMPATIBILITY MODE (Linux NVIDIA) ---
        elif arch_version >= 6.0 and total_vram_gb >= 11.0 and not args.disable_comfyd and args.gpu_type != 'cu124':
            common.force_compatibility = True
            torch_ver = '2.7.1'
        else:
            torch_ver = '2.4.1'
        if torchruntime_platform == 'rocm5.7':
            torch_ver = '2.3.1'
        elif torchruntime_platform == 'rocm5.2':
            torch_ver = '1.13.1'

    # (OSX) Apple Silicon / Intel Mac Detection
    elif sys.platform == "darwin":
        if platform.machine() == 'x86_64':
            # Keep Intel-based Macs on stable legacy
            torch_ver = "2.2.2"
        # --- FORCED COMPATIBILITY MODE (Apple Silicon) ---
        # If not Intel (guaranteed Apple Silicon)
        # and has at least 11 GB of Unified Memory,
        # allow upgrading to PyTorch 2.10.0
        elif total_vram_gb >= 11.0 and not args.disable_comfyd:
            common.force_compatibility = True
            # Upgraded to 2.10.0 for
            # modern MPS optimizations
            torch_ver = "2.10.0"
        else:
            # Lower unified memory Macs remain on
            # stable legacy 2.5.1 (Comfy lockout)
            torch_ver = "2.5.1"


    # Begin the assignment of xformers:
    is_nvidia_platform = torch_platform_ver.startswith('cu') if torch_platform_ver else False
    xformers_ver = 'None'

    if is_nvidia_platform and sys.platform != 'darwin':
        # Blackwell & cu130: PyTorch 2.10.0 replaces
        # xformers entirely on all hardware
        if torch_ver == '2.10.0':
            xformers_ver = 'None'

        # 2. Turing / Ampere / Ada on cu128 (PyTorch 2.7.1)
        elif torch_ver == '2.7.1':
            # Disable xformers (use native FlashAttention-2)
            # for modern GPUs (>= 7.5),
            # but keep it active ('0.0.30') for legacy
            # Pascal users (< 7.5) who need it!
            xformers_ver = 'None' if arch_version >= 7.5 else '0.0.30'

        # 3. Legacy Pascal on cu124 (PyTorch 2.4.1)
        elif torch_ver == '2.4.1':
            xformers_ver = '0.0.28.post1'


    # Begin the assignment of dependencies:
    if torch_ver == '2.10.0': # Blackwell native mode
        dependencies = dict(
            torch_ver = '2.10.0',
            torchvision_ver = '0.25.0',
            torchaudio_ver = '2.10.0',
            xformers_ver = xformers_ver,
            bitsandbytes_ver = '0.48.0',
            torch_platform_ver = torchruntime_platform
        )

    elif torch_ver == '2.5.1':
        dependencies = dict(
            torch_ver = '2.5.1',
            torchvision_ver = '0.20.1',
            torchaudio_ver = '2.5.1',
            xformers_ver = xformers_ver,
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torchruntime_platform
        )

    elif torch_ver == '2.4.1':
        dependencies = dict(
            torch_ver = '2.4.1',
            torchvision_ver = '0.19.1',
            torchaudio_ver = '2.4.1',
            xformers_ver = xformers_ver,
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torchruntime_platform
        )

    # for Linux rocm5.7
    elif torch_ver == '2.3.1':
        dependencies = dict(
            torch_ver = '2.3.1',
            torchvision_ver = '0.18.1',
            torchaudio_ver = '2.3.1',
            xformers_ver = xformers_ver,
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torchruntime_platform
        )

    # the last version supporting Intel Macs
    elif torch_ver == '2.2.2':
        dependencies = dict(
            torch_ver = '2.2.2',
            torchvision_ver = '0.17.2',
            torchaudio_ver = '2.2.2',
            xformers_ver = xformers_ver,
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torchruntime_platform
        )

    # earliest possible supported release: rocm5.2
    elif torch_ver == '1.13.1':
        dependencies = dict(
            torch_ver = '1.13.1',
            torchvision_ver = '0.14.1',
            torchaudio_ver = '0.13.1',
            xformers_ver = xformers_ver,
            bitsandbytes_ver = '0.42.0',
            torch_platform_ver = torchruntime_platform
        )

    else:
        # use the torch_ver 2.7.1 defaults
        dependencies = dict(
            torch_ver = torch_default,
            torchvision_ver = torchvision_default,
            torchaudio_ver = torchaudio_default,
            xformers_ver = xformers_ver,
            bitsandbytes_ver = bitsandbytes_default,
            torch_platform_ver = torch_platform_default
        )

    # Lockout Comfy if PyTorch < 2.7
    define_comfy_lockout(torch_ver, new_driver, driver_msg, total_vram_gb)

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
        elif isinstance(depend_list, str):
            if depend_list == 'xformers':
                print('Optimizing for native attention: removing xformers...')
            file_paths = [depend_list]
        else:
            file_paths = list(depend_list)

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
