import subprocess
import os
import sys
import torch
import gc
import socket
from pathlib import Path
import common
from enhanced.translator import interpret
import ldm_patched.modules.model_management as model_management
from . import comfyclient_pipeline, utils

comfyd_process = None
comfyd_active = False
comfyd_args = [[]]


def find_free_port(start_port=8187):
    """
    Safely finds a free TCP port starting from start_port.
    Binds strictly to loopback (127.0.0.1) to prevent
    external network exposure.
    """
    # Safety blocklist of common browser-restricted ports
    restricted_ports = {2049, 3659, 4045, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669}

    for port in range(start_port, start_port + 100):
        if port in restricted_ports:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Setting a quick timeout to check connection status
            s.settimeout(0.5)
            # connect_ex returns non-zero if the port is free to bind
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port


def is_running():
    global comfyd_process
    if 'comfyd_process' not in globals():
        return False
    if comfyd_process is None:
        return False
    process_code = comfyd_process.poll()
    if process_code is None:
        return True
    interpret("[ComfyBase] Comfy process status code: {process_code}")
    return False


def start(args_patch=[[]]):
    global comfyd_process, comfyd_args
    if not is_running():
        backend_script = Path.cwd().joinpath('comfy', 'main.py')

        # Dynamically locate a free port starting at 8187
        port = find_free_port(8187)

        # Save the port globally so the client
        # pipeline knows where to connect
        common.comfy_port = port

        # Force Comfy to listen strictly on loopback
        # (127.0.0.1) for local security
        args_comfyd = [
            ['--preview-method', 'auto'],
            ['--port', str(port)],
            ['--listen', '127.0.0.1'],
            ['--disable-auto-launch']
        ]

        if len(args_patch) > 0 and len(args_patch[0]) > 0:
            comfyd_args += args_patch
        if not utils.echo_off:
            interpret(f'[ComfyBase] args_comfyd was patched: {args_comfyd}, patch:{comfyd_args}')
        arguments = [arg for sublist in args_comfyd for arg in sublist]
        process_env = os.environ.copy()
        process_env['PYTHONPATH'] = os.pathsep.join(sys.path)
        model_management.unload_all_models()
        gc.collect()
        torch.cuda.empty_cache()
        if not utils.echo_off:
            interpret(f'[ComfyBase] Ready to start with arguments: {arguments}, env: {process_env}')
        if 'comfyd_process' not in globals():
            globals()['comfyd_process'] = None

        # Passing str(backend_script) for maximum cross-platform compatibility inside Popen
        comfyd_process = subprocess.Popen([sys.executable, str(backend_script)] + arguments, env=process_env)
        comfyclient_pipeline.ws = None
    else:
        interpret('[ComfyBase] Comfy is active!')
    return


def active(flag=False):
    global comfyd_active
    comfyd_active = flag
    if flag and not is_running():
        start()
    if not flag and is_running():
        stop()
    return


def finished():
    global comfyd_process
    if 'comfyd_process' not in globals():
        return
    if comfyd_process is None:
        return
    if comfyd_active:
        gc.collect()
        interpret("[ComfyBase] Task finished!")
        return
    comfyclient_pipeline.ws = None
    free()
    gc.collect()
    interpret("[ComfyBase] Comfy stopped!")


def stop():
    global comfyd_process
    if 'comfyd_process' not in globals():
        return
    if comfyd_process is None:
        return
    if comfyd_active:
        free(all=True)
        gc.collect()
        interpret("[ComfyBase] Releasing Comfy!")
        return
    if is_running():
        comfyd_process.terminate()
        comfyd_process.wait()
    del comfyd_process
    comfyclient_pipeline.ws = None
    free()
    gc.collect()
    interpret("[ComfyBase] Comfy has stopped!")


def free(all=False):
    global comfyd_process
    if 'comfyd_process' not in globals():
        return
    if comfyd_process is None:
        return
    comfyclient_pipeline.free(all)
    return


def interrupt():
    global comfyd_process
    if 'comfyd_process' not in globals():
        return
    if comfyd_process is None:
        return
    comfyclient_pipeline.interrupt()
    return


def args_mapping(args_fooocus):
    args_comfy = []
    if "--gpu-device-id" in args_fooocus:
        args_comfy += [["--cuda-device", args_fooocus[args_fooocus.index("--gpu-device-id")+1]]]
    if "--async-cuda-allocation" in args_fooocus:
        args_comfy += [["--cuda-malloc"]]
    if "--disable-async-cuda-allocation" in args_fooocus:
        args_comfy += [["--disable-cuda-malloc"]]
    if "--vae-in-cpu" in args_fooocus:
        args_comfy += [["--vae-in-cpu"]]
    if "--directml" in args_fooocus:
        args_comfy += [["--directml"]]
    if "--disable-xformers" in args_fooocus:
        args_comfy += [["--disable-xformers"]]
    if "--always-cpu" in args_fooocus:
        args_comfy += [["--cpu"]]
    if "--always-low-vram" in args_fooocus:
        args_comfy += [["--lowvram"]]
    if "--always-gpu" in args_fooocus:
        args_comfy += [["--gpu-only"]]
    print()
    if "--always-offload-from-vram" in args_fooocus:
        args_comfy += [["--disable-smart-memory"]]
        interpret("[ComfyBase] Smart memory disabled")
    else:
        interpret("[ComfyBase] Smart memory enabled")
    if not utils.echo_off:
        interpret(f'[ComfyBase] args_fooocus: {args_fooocus}\nargs_comfy: {args_comfy}')
    return args_comfy

def get_entry_point_id():
    global comfyd_process
    if 'comfyd_process' in globals() and comfyd_process:
        return gen_entry_point_id(comfyd_process.pid)
    else:
        return None
