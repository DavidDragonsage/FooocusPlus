import json
import websocket
import uuid
import random
import httpx
import time
import numpy as np
import ldm_patched.modules.model_management as model_management
from io import BytesIO
from PIL import Image
from pathlib import Path

from . import utils


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
    try:
        prompt_str = params.convert2comfy(flowdata)

        # Inject the pruner to safely clean up unmapped LoRA slots
        prune_inactive_loras(prompt_str)

        if not utils.echo_off:
            print(f'[ComfyClient] ComfyTask prompt: {prompt_str}')
        images = get_images(ws, prompt_str, callback=callback)
    except websocket.WebSocketException as e:
        print(f'[ComfyClient] The connection has been closed, restart and try again: {e}')
        ws = None

    images_keys = sorted(images.keys(), reverse=True)
    imgs = [images[key] for key in images_keys]
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
