import subprocess
import os
import sys
import torch
import gc
import ldm_patched.modules.model_management as model_management
from . import comfyclient_pipeline, utils

comfyd_process = None
comfyd_active = False
comfyd_args = [[]]

def is_running():
    global comfyd_process
    if 'comfyd_process' not in globals():
        return False
    if comfyd_process is None:
        return False
    process_code = comfyd_process.poll()
    if process_code is None:
        return True
    print("[ComfyBase] Comfy process status code: {process_code}")
    return False

def start(args_patch=[[]]):
    global comfyd_process, comfyd_args
    if not is_running():
        backend_script = os.path.join(os.getcwd(),'comfy/main.py')
        args_comfyd = [["--preview-method", "auto"], ["--port", "8187"], ["--disable-auto-launch"]]
        if len(args_patch) > 0 and len(args_patch[0]) > 0:
            comfyd_args += args_patch
        if not utils.echo_off:
            print(f'[ComfyBase] args_comfyd was patched: {args_comfyd}, patch:{comfyd_args}')
        arguments = [arg for sublist in args_comfyd for arg in sublist]
        process_env = os.environ.copy()
        process_env["PYTHONPATH"] = os.pathsep.join(sys.path)
        model_management.unload_all_models()
        gc.collect()
        torch.cuda.empty_cache()
        if not utils.echo_off:
            print(f'[ComfyBase] Ready to start with arguments: {arguments}, env: {process_env}')
        if 'comfyd_process' not in globals():
            globals()['comfyd_process'] = None
        comfyd_process  = subprocess.Popen([sys.executable, backend_script] + arguments, env=process_env)
        comfyclient_pipeline.ws = None
    else:
        print("[ComfyBase] Comfy is active!")
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
        #free()
        gc.collect()
        print("[ComfyBase] Task finished!")
        return
    comfyclient_pipeline.ws = None
    free()
    gc.collect()
    print("[ComfyBase] Comfy stopped!")

def stop():
    global comfyd_process
    if 'comfyd_process' not in globals():
        return
    if comfyd_process is None:
        return
    if comfyd_active:
        free(all=True)
        gc.collect()
        print("[ComfyBase] Releasing Comfy!")
        return
    if is_running():
        comfyd_process.terminate()
        comfyd_process.wait()
    del comfyd_process
    comfyclient_pipeline.ws = None
    free()
    gc.collect()
    print("[ComfyBase] Comfy has stopped!")

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
        print("[ComfyBase] Smart memory disabled")
    else:
        print("[ComfyBase] Smart memory enabled")
    if not utils.echo_off:
        print(f'[ComfyBase] args_fooocus: {args_fooocus}\nargs_comfy: {args_comfy}')
    return args_comfy

def get_entry_point_id():
    global comfyd_process
    if 'comfyd_process' in globals() and comfyd_process:
        return gen_entry_point_id(comfyd_process.pid)
    else:
        return None
