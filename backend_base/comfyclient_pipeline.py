import json
import websocket
import uuid
import random
import httpx
import time
import numpy as np
from io import BytesIO
from PIL import Image
from pathlib import Path

import common
import ldm_patched.modules.model_management as model_management
import modules.flags as flags
from . import utils
from enhanced.translator import interpret


def upload_mask(mask):
    with BytesIO() as output:
        mask.save(output)
        output.seek(0)
        files = {'mask': ('mask.jpg', output)}
        data = {'overwrite': 'true', 'type': 'example_type'}
        response = httpx.post('http://{}/upload/mask'.format(server_address), files=files, data=data)
    return response.json()


def queue_prompt(prompt):
    p = {'prompt': prompt, 'client_id': client_id}
    data = json.dumps(p).encode('utf-8')
    try:
        with httpx.Client() as client:
            response = client.post('http://{}/prompt'.format(server_address), data=data)
            return json.loads(response.read())
    except httpx.RequestError as e:
        print(f'httpx.RequestError: {e}')
    return None


def get_image(filename, subfolder, folder_type):
    params = httpx.QueryParams({
        'filename': filename,
        'subfolder': subfolder,
        'type': folder_type
    })
    with httpx.Client() as client:
        response = client.get(f'http://{server_address}/view', params=params)
        return response.read()


def get_history(prompt_id):
    with httpx.Client() as client:
        response = client.get('http://{}/history/{}'.format(server_address, prompt_id))
        return json.loads(response.read())


def get_images(ws, prompt, callback=None):
    prompt_id = queue_prompt(prompt)['prompt_id']
    print('[ComfyClient] Request and get ComfyTask_id:{}'.format(prompt_id))
    output_images = {}
    current_node = ''
    last_node = None
    preview_image = []
    last_step = None
    current_step = None
    current_total_steps = None
    while True:
        model_management.throw_exception_if_processing_interrupted()
        try:
            out = ws.recv()
        except ConnectionResetError as e:
            print(f'[ComfyClient] The connection created an exception. Restart and try again: {e}')
            ws = websocket.WebSocket()
            ws.connect('ws://{}/ws?clientId={}'.format(server_address, client_id))
            out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            current_type = message['type']
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
                else:
                    current_node = data['node']
            elif message['type'] == 'progress':
                current_step = message['data']['value']
                current_total_steps = message['data']['max']
        else:
            if current_type == 'progress':
                if prompt[current_node]['class_type'] in ['KSampler', 'SamplerCustomAdvanced', 'TiledKSampler'] and callback is not None:
                    if current_step == last_step:
                        preview_image.append(out[8:])
                    else:
                        if last_step is not None:
                            callback(last_step, current_total_steps, Image.open(BytesIO(preview_image[0])))
                        preview_image = []
                        preview_image.append(out[8:])
                        last_step = current_step
                if prompt[current_node]['class_type'] == 'SaveImageWebsocket':
                    images_output = output_images.get(prompt[current_node]['_meta']['title'], [])
                    images_output.append(out[8:])
                    output_images[prompt[current_node]['_meta']['title']] = images_output[0]
            continue

    output_images = {k: np.array(Image.open(BytesIO(v))) for k, v in output_images.items()}
    print(f'[ComfyClient] The ComfyTask:{prompt_id} has finished: {len(output_images)}')
    return output_images


def images_upload(images):
    result = {}
    if images is None:
        return result
    for k, np_image in images.items():
        pil_image = Image.fromarray(np_image)
        with BytesIO() as output:
            pil_image.save(output, format='PNG')
            output.seek(0)
            files = {'image': (f'image_{client_id}_{random.randint(1000, 9999)}.png', output)}
            data = {'overwrite': 'true', 'type': 'input'}
            response = httpx.post('http://{}/upload/image'.format(server_address), files=files, data=data)
        result.update({k: response.json()['name']})
    print(f'[ComfyClient] The ComfyTask: upload_input_images has finished: {len(result)}')
    return result


def prune_inactive_loras(workflow: dict) -> None:
    """
    Scans the workflow dictionary for inactive LoraLoader or LoraLoaderModelOnly nodes.
    Deletes them and dynamically heals the model and clip connection paths around them.
    """
    node_ids = list(workflow.keys())
    for node_id in node_ids:
        if node_id not in workflow:
            continue
        node = workflow[node_id]
        class_type = node.get('class_type')

        if class_type in ['LoraLoader', 'LoraLoaderModelOnly']:
            lora_name = node.get('inputs', {}).get('lora_name')

            # If the LoRA is set to None or left empty, prune and heal
            if lora_name == 'None' or not lora_name:
                input_model_link = node['inputs'].get('model')  # e.g., ["12", 0]
                input_clip_link = node['inputs'].get('clip')    # e.g., ["11", 0] (None if ModelOnly)

                # Scan all other nodes to redirect connections around this pruned node
                for other_id, other_node in workflow.items():
                    if other_id == node_id:
                        continue
                    inputs = other_node.get('inputs', {})
                    for input_key, input_val in inputs.items():
                        if isinstance(input_val, list) and len(input_val) == 2:
                            # Redirect model connections
                            if str(input_val[0]) == str(node_id) and input_val[1] == 0:
                                other_node['inputs'][input_key] = input_model_link
                            # Redirect clip connections
                            elif str(input_val[0]) == str(node_id) and input_val[1] == 1:
                                other_node['inputs'][input_key] = input_clip_link

                # Delete the inactive node
                del workflow[node_id]

    return


def ensure_vae_downloaded(vae_filename: str) -> None:
    """
    Checks if a VAE file is physically on disk
    in the VAE directory. If missing, resolves its URL from the flags catalogues and downloads it on demand.
    """
    if not vae_filename or vae_filename == 'Default (model)':
        return

    clean_vae = flags.extract_vae_filename(vae_filename)
    vae_disk_path = Path(common.path_vae) / clean_vae

    if not vae_disk_path.is_file():
        catalog = {}
        if hasattr(flags, 'SDXL_VAES'): catalog.update(flags.SDXL_VAES)
        if hasattr(flags, 'SD15_VAES'): catalog.update(flags.SD15_VAES)
        if hasattr(flags, 'FLUX_VAES'): catalog.update(flags.FLUX_VAES)
        if hasattr(flags, 'SD3_VAES'): catalog.update(flags.SD3_VAES)

        download_url = None
        for label, url in catalog.items():
            if flags.extract_vae_filename(label) == clean_vae:
                download_url = url
                break

        # Direct fallback for standard SDXL VAE
        if not download_url and clean_vae == 'sdxl_vae.safetensors':
            download_url = 'https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors'

        if download_url:
            interpret('[ComfyClient] Downloading on-demand VAE:', f'{clean_vae}...')
            import modules.loader as loader
            loader.load_file_from_url(
                url=download_url,
                model_dir=str(Path(common.path_vae)),
                file_name=clean_vae
            )
            common.MODELS_INFO.refresh_from_path()
    return


def override_vae_loader(workflow: dict, params=None) -> None:
    """
    Overrides or injects a VAE into the workflow:
    1. If the workflow has a VAELoader
       (e.g. Split Flux, SD3.5 GGUF), updates its 'vae_name'.
    2. If the workflow uses CheckpointLoaderSimple
       (e.g. SD1.5, AIO) and a custom VAE is chosen,
       dynamically injects a VAELoader and rewires VAEDecode to use the external VAE.
    3. If running 'Default (model)', scans any native
       VAELoader nodes and downloads
       their default VAE if missing.
    4. If vae_sharpness != 0.0, dynamically splices
       VAESharpnessPatch before VAEDecode.
    """
    selected_vae = None

    # 1. Load the argument from the task packet
    if params is not None and hasattr(params, 'params') and isinstance(params.params, dict):
        selected_vae = params.params.get('vae_name') or params.params.get('vae')

    # 2. Fallback to common
    if not selected_vae:
        selected_vae = getattr(common, 'current_vae', 'Default (model)')

    # 3. Strip any label prefix
    # (e.g. 'Anime | kl-f8...' -> 'kl-f8...')
    selected_vae = flags.extract_vae_filename(selected_vae)

    # 4. If Default (model) or unset,
    # check if an SD1.5 checkpoint has no embedded VAE
    if not selected_vae or selected_vae == 'Default (model)':
        from modules.util import has_embedded_vae, get_file_from_folder_list

        ckpt_name = None
        for node in workflow.values():
            if isinstance(node, dict) and node.get('class_type') == 'CheckpointLoaderSimple':
                ckpt_name = node.get('inputs', {}).get('ckpt_name')
                break

        # If running an SD1.5 checkpoint,
        # verify if it has a built-in VAE
        if ckpt_name and any(k in ckpt_name.lower() for k in ['sd1.5', 'sd15', 'v1-5', '1.5']):
            ckpt_path = get_file_from_folder_list(ckpt_name, common.paths_checkpoints)
            if ckpt_path and not has_embedded_vae(ckpt_path):
                selected_vae = 'vae-ft-mse-840000-ema-pruned.safetensors'
                vae_disk_path = Path(common.path_vae) / selected_vae

                if not vae_disk_path.is_file():
                    interpret('[ComfyClient] Downloading fallback SD1.5 VAE:', f'{selected_vae}...')
                    import modules.loader as loader
                    url = flags.SD15_VAES.get(
                        'SAI | vae-ft-mse-840000-ema-pruned.safetensors',
                        'https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors'
                    )
                    loader.load_file_from_url(
                        url=url,
                        model_dir=str(Path(common.path_vae)),
                        file_name=selected_vae
                    )
                    common.MODELS_INFO.refresh_from_path()

                if hasattr(params, 'params') and isinstance(params.params, dict):
                    params.params['vae_name'] = selected_vae
                interpret('[ComfyClient] Pruned SD1.5 model detected:', ckpt_name)
                interpret('[ComfyClient] Automatically injecting:', selected_vae)

    # 5. External VAE branch vs.
    # Default Workflow VAE branch
    if selected_vae and selected_vae != 'Default (model)':
        # Ensure the custom selected VAE is on disk
        ensure_vae_downloaded(selected_vae)

        # Case 1: Workflow already has a VAELoader node
        # (Split models)
        vae_loader_found = False
        for node_id, node in workflow.items():
            if isinstance(node, dict) and node.get('class_type') == 'VAELoader':
                inputs = node.get('inputs', {})
                if 'vae_name' in inputs:
                    old_vae = inputs['vae_name']
                    vae_loader_found = True
                    if old_vae != selected_vae:
                        inputs['vae_name'] = selected_vae
                        interpret(f'[ComfyClient] Overriding VAELoader (Node {node_id}): {old_vae} → {selected_vae}')

        # Case 2: Workflow uses CheckpointLoaderSimple
        # (AIO). Dynamically inject a VAELoader node
        # and rewire nodes receiving checkpoint VAE
        if not vae_loader_found:
            highest_id = max([int(k) for k in workflow.keys() if k.isdigit()] + [100])
            inject_id = str(highest_id + 1)

            workflow[inject_id] = {
                'inputs': {'vae_name': selected_vae},
                'class_type': 'VAELoader',
                '_meta': {'title': 'Dynamic VAE Override'}
            }

            rewired = False
            for node_id, node in workflow.items():
                if isinstance(node, dict):
                    inputs = node.get('inputs', {})
                    vae_input = inputs.get('vae')
                    if isinstance(vae_input, list) and len(vae_input) == 2 and vae_input[1] == 2:
                        inputs['vae'] = [inject_id, 0]
                        interpret('[ComfyClient] Dynamically injected VAELoader with', selected_vae)
                        rewired = True

            if not rewired:
                del workflow[inject_id]
    else:
        # Default (model) branch:
        # If the workflow already defines a VAELoader
        # (e.g. Node 70 in Kolors,
        # ae.safetensors in Flux),
        # ensure that default file exists on disk
        for node_id, node in workflow.items():
            if isinstance(node, dict) and node.get('class_type') == 'VAELoader':
                default_node_vae = node.get('inputs', {}).get('vae_name')
                if default_node_vae:
                    ensure_vae_downloaded(default_node_vae)

    # 6. Splicer for VAE Sharpness / Glow
    # (Runs for ALL workflows)
    vae_sharpness = 0.0
    if params is not None and hasattr(params, 'params') and isinstance(params.params, dict):
        vae_sharpness = float(params.params.get('vae_sharpness', 0.0))

    if vae_sharpness != 0.0:
        for node_id, node in list(workflow.items()):
            if isinstance(node, dict) and node.get('class_type') == 'VAEDecode':
                old_vae_link = node['inputs'].get('vae')
                if old_vae_link:
                    highest_id = max([int(k) for k in workflow.keys() if k.isdigit()] + [100])
                    sharp_id = str(highest_id + 1)

                    # Inject the VAESharpnessPatch node
                    workflow[sharp_id] = {
                        'inputs': {
                            'vae': old_vae_link,
                            'sharpness': vae_sharpness
                        },
                        'class_type': 'VAESharpnessPatch',
                        '_meta': {'title': 'VAE Sharpness Patch'}
                    }

                    # Rewire VAEDecode to take the patched VAE output
                    node['inputs']['vae'] = [sharp_id, 0]
                    interpret(f'[ComfyClient] Spliced VAESharpnessPatch (Node {sharp_id}) with sharpness:', str(vae_sharpness))
    return


def process_flow(flow_name, params, images, callback=None):
    global ws

    # --- INACTIVE HTTP MODEL SCAN DIAGNOSTICS (Uncomment using ''' to troubleshoot) ---
    '''
    import sys
    import httpx

    print('\n======================================================================')
    print('[DIAGNOSTIC] Querying running ComfyUI Server for registered models...')
    print('======================================================================')

    try:
        # Query the live ComfyUI server directly over its HTTP API
        response = httpx.get(f'http://{server_address}/object_info', timeout=5.0)
        if response.status_code == 200:
            data = response.json()

            # 1. Fetch Checkpoint Loader choices
            ckpt_info = data.get('CheckpointLoaderSimple', {})
            ckpt_list = ckpt_info.get('input', {}).get('required', {}).get('ckpt_name', [[]])[0]
            print(f'\n-> Registered Checkpoints ({len(ckpt_list)} files found):')
            for idx, ckpt in enumerate(sorted(ckpt_list)):
                print(f'   {idx + 1: >2}. {ckpt}')

            # 2. Fetch UNET Loader choices (standard Flux / SD3)
            unet_info = data.get('UNETLoader', {})
            unet_list = unet_info.get('input', {}).get('required', {}).get('unet_name', [[]])[0]
            print(f'\n-> Registered UNet Models ({len(unet_list)} files):')
            for idx, unet in enumerate(sorted(unet_list)):
                print(f'   {idx + 1: >2}. {unet}')

            # 3. Fetch GGUF Loader choices
            gguf_info = data.get('UnetLoaderGGUF', {})
            gguf_list = gguf_info.get('input', {}).get('required', {}).get('unet_name', [[]])[0]
            print(f'\n-> Registered GGUF Models ({len(gguf_list)} files):')
            for idx, gguf in enumerate(sorted(gguf_list)):
                print(f'   {idx + 1: >2}. {gguf}')

        else:
            print(f'❌ ComfyUI Server returned HTTP Status: {response.status_code}')
    except Exception as e:
        print(f'❌ Failed to query ComfyUI server over network: {e}')

    print('======================================================================\n')
    sys.stdout.flush()
    sys.exit(0)  # Terminate and freeze the console so you can inspect the lists
    '''
    # ------------------------------------------------------------------

    flow_file = WORKFLOW_DIR / f'{flow_name}_api.json'
    if ws is None or ws.status != 101:
        if ws is not None:
            print(f'[ComfyClient] websocket status: {ws.status}, timeout:{ws.timeout}s.')
            ws.close()
        try:
            ws = websocket.WebSocket()
            ws.connect('ws://{}/ws?clientId={}'.format(server_address, client_id))
        except ConnectionRefusedError as e:
            print(f'[ComfyClient] The connect_to_server has failed, sleep and try again: {e}')
            time.sleep(8)
            try:
                ws = websocket.WebSocket()
                ws.connect('ws://{}/ws?clientId={}'.format(server_address, client_id))
            except ConnectionRefusedError as e:
                print(f'[ComfyClient] The connect_to_server has failed, restart and try again: {e}')
                time.sleep(12)
                ws = websocket.WebSocket()
                ws.connect('ws://{}/ws?clientId={}'.format(server_address, client_id))

    images_map = images_upload(images)
    params.update_params(images_map)
    with open(flow_file, 'r', encoding='utf-8') as workflow_api_file:
        flowdata = json.load(workflow_api_file)
    print(f'[ComfyClient] Ready ComfyTask to process: workflow={flow_name}')
    for k, v in params.params.items():
        print(f'    {k} = {v}')

    # flowdata is the workflow loaded from disk
    # prompt_str is the resulting Python dictionary
    # of Comfy nodes and their inputs
    try:
        prompt_str = params.convert2comfy(flowdata)

        # Inject the pruner to safely clean up unmapped LoRA slots
        prune_inactive_loras(prompt_str)

        # Dynamically override the VAE if a custom VAE
        # is selected in the UI dropdown or preset
        override_vae_loader(prompt_str, params)

        if not utils.echo_off:
            interpret('[ComfyClient] ComfyTask prompt:', prompt_str)
        images = get_images(ws, prompt_str, callback=callback)
    except websocket.WebSocketException as e:
        interpret('[ComfyClient] The connection has been closed, restart and try again:', e)
        ws = None

    images_keys = sorted(images.keys(), reverse=True)
    imgs = [images[key] for key in images_keys]

    # Check if UltraFlux was used for this generation
    active_vae = ''
    if hasattr(params, 'params') and isinstance(params.params, dict):
        active_vae = params.params.get('vae_name', '')
    if not active_vae:
        active_vae = getattr(common, 'current_vae', '')

    # Full centring & perimeter healing for UltraFlux:
    # shifted right 1 pixel to centre horizontally,
    # padded 1-pixel on the left edge,
    # shifted down 1 pixel to centre vertically,
    # and padded 2 pixels on both top and bottom.
    if 'ultraflux' in str(active_vae).lower():
        for img in imgs:
            if isinstance(img, np.ndarray) and img.ndim == 3:
                # 1. Shift image down by 1 pixel
                img[2:-1, :] = img[1:-2, :].copy()

                # 2. Pad 2 pixels at the top edge
                img[0, :] = img[2, :]
                img[1, :] = img[2, :]

                # 3. Pad 2 pixels at the bottom edge
                img[-1, :] = img[-2, :]

                # 4. Shift image right by 1 pixel
                img[:, 1:] = img[:, :-1].copy()

                # 5. Pad 1 pixel at the left edge
                img[:, 0] = img[:, 1]

    # Apply VAE sharpness to all decoded images:
    from modules.util import apply_optical_sharpness
    vae_sharpness = 0.0
    if params is not None and hasattr(params, 'params') and isinstance(params.params, dict):
        vae_sharpness = float(params.params.get('vae_sharpness', 0.0))

    if vae_sharpness != 0.0:
        from modules.util import apply_optical_sharpness
        imgs = [apply_optical_sharpness(img, vae_sharpness) for img in imgs]

    return imgs


def interrupt():
    try:
        with httpx.Client() as client:
            response = client.post('http://{}/interrupt'.format(server_address))
            return response
    except httpx.RequestError as e:
        print(f'httpx.RequestError: {e}')
    return None


def free(all=False):
    p = {'unload_models': all == True, 'free_memory': True}
    data = json.dumps(p).encode('utf-8')
    try:
        with httpx.Client() as client:
            response = client.post('http://{}/free'.format(server_address), data=data)
            return response
    except httpx.RequestError as e:
        print(f'httpx.RequestError: {e}')
    return None


WORKFLOW_DIR = Path('workflows')
COMFYUI_ENDPOINT_IP = '127.0.0.1'
COMFYUI_ENDPOINT_PORT = '8187'
server_address = f'{COMFYUI_ENDPOINT_IP}:{COMFYUI_ENDPOINT_PORT}'
client_id = str(uuid.uuid4())
ws = None
