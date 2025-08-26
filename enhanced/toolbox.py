import os
import json
import copy
import re
import math
import shutil
import time
import gradio as gr
import args_manager
import common
import modules.config as config
import modules.preset_resource as PR
import modules.sdxl_styles as sdxl_styles
import modules.ui_support as UIS
import modules.user_structure as US
import enhanced.all_parameters as ads
import enhanced.gallery as gallery
import enhanced.version as version
import modules.flags as flags
import modules.meta_parser as meta_parser

from pathlib import Path
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from enhanced.backend import sync_model_info
from modules.model_loader import load_file_from_url

css = '''
.toolbox {
    height: auto;
    position: absolute;
    top: 210px;
    left: 86%;
    width: 100px !important;
    z-index: 20;
    text-align: center;
}

.infobox {
    height: auto;
    position: absolute;
    top: -15rem;
    left: 50%;
    transform: translateX(-50%);
    width: 28rem !important;
    z-index: 20;
    text-align: left;
    opacity: 0.85;
    border-radius: 8px;
    padding: 6px;
    line-height: 120%;
    border: groove;
    color: var(--neutral-800);
}

.infobox_mobi {
    height: auto;
    position: absolute;
    top: -16rem;
    left: 50%;
    transform: translateX(-50%);
    width: 22rem !important;
    z-index: 20;
    text-align: left;
    opacity: 0.85;
    border-radius: 8px;
    padding: 6px;
    line-height: 120%;
    border: groove;
}

.toolbox_note {
    height: auto;
    position: absolute;
    top: 160px;
    left: 50%;
    transform: translateX(-50%);
    width: 300px !important;
    z-index: 21;
    text-align: left;
    opacity: 1;
    border-radius: 8px;
    padding: 0px;
    border: groove;
}

.identity_note {
    height: auto;
    position: absolute;
    top: 160px;
    left: 50%;
    transform: translateX(-50%);
    width: 400px !important;
    z-index: 21;
    text-align: left;
    opacity: 1;
    border-radius: 8px;
    padding: 0px;
    border: groove;
}

.note_info {
    padding: 8px;
}

.note_text {
    padding: 2px;
    text-align: center;
}
.preset_input textarea {
    width: 120px;
}

.tag_array {
    height: auto;
    position: absolute;
    top: 180px;
    left: 15%;
    width: 580px !important;
    z-index: 22;
}

.taglib_button {
    height: 35px;
    transform: translate(5%, 35%);
}

.min_pad0 {
    padding: 0px !important;
}

.min_pad {
    padding: 2px !important;
}
'''

# app context
toolbox_note_preset_title='Create a new preset using the current parameters. Leave blank and click Enter to cancel.'
toolbox_note_regenerate_title='Extract parameters to backfill for regeneration. Please note that some parameters will be modified!'
toolbox_note_embed_title='Embed parameters into images for easy identification of image sources and communication and learning.'
toolbox_note_missing_muid='The model in the params and configuration is missing MUID. And the system will spend some time calculating the hash of model files and synchronizing information to obtain the muid for usability and transferability.'

def make_infobox_markdown(info, theme):
    bgcolor = '#ddd'
    if theme == "dark":
        bgcolor = '#444'
    html = f'<div style="background: {bgcolor}">'
    if info:
        for key in info:
            if key in ['Filename', 'Advanced_parameters', 'Fooocus V2 Expansion', 'Metadata Scheme', 'Version', 'Upscale (Fast)'] or info[key] in [None, '', 'None']:
                continue
            html += f'<b>{key}:</b> {info[key]}<br/>'
    else:
        html += '<p>info</p>'
    html += '</div>'
    return html


def toggle_toolbox(state, state_params):
    if "gallery_state" in state_params and state_params["gallery_state"] == 'finished_index':
        return [gr.update(visible=state)]
    else:
        return [gr.update(visible=False)]


def toggle_prompt_info(state_params):
    infobox_state = state_params["infobox_state"]
    infobox_state = not infobox_state
    state_params.update({"infobox_state": infobox_state})
    #print(f'[Toolbox] Toggle_image_info: {infobox_state}')
    [choice, selected] = state_params["prompt_info"]
    prompt_info = gallery.get_images_prompt(choice, selected, state_params["__max_per_page"])
    return gr.update(value=make_infobox_markdown(prompt_info, state_params['__theme']), visible=infobox_state), state_params


def check_preset_models(checklist, state_params):
    note_box_state = state_params["note_box_state"]
    note_box_state[2] = 0
    state_params.update({"note_box_state": note_box_state})
    return state_params


def toggle_note_box(item, state_params):
    note_box_state = state_params["note_box_state"]
    if note_box_state[0] is None:
        note_box_state[0] = item
    if item == note_box_state[0]:
        note_box_state[1] = not note_box_state[1]
    elif not note_box_state[1]:
        note_box_state[1] = not note_box_state[1]
        note_box_state[0] = item
    else:
        state_params.update({"note_box_state": note_box_state})
        return [gr.update(visible=True)] + [gr.update()] * (3 if item == 'preset' else 2) + [state_params]
    state_params.update({"note_box_state": note_box_state})
    flag = note_box_state[1]
    title_extra = ""
    if note_box_state[2]:
        title_extra = '\n' + toolbox_note_missing_muid
    if item == 'delete':
        [choice, selected] = state_params["prompt_info"]
        info = gallery.get_images_prompt(choice, selected, state_params["__max_per_page"])
        return gr.update(value=f'DELETE the image from output directory and logs!', \
            visible=True), gr.update(visible=flag), gr.update(visible=flag), state_params
    if item == 'regen':
        return gr.update(value=toolbox_note_regenerate_title, visible=True), \
            gr.update(visible=flag), gr.update(visible=flag), state_params
    if item == 'preset':
        return gr.update(value=toolbox_note_preset_title + title_extra, visible=True), \
            gr.update(visible=flag), gr.update(visible=flag), gr.update(visible=flag), \
            state_params, gr.update(value=args_manager.args.preset)
    if item == 'embed':
        return gr.update(value=toolbox_note_embed_title + title_extra, visible=True), \
            gr.update(visible=flag), gr.update(visible=flag), state_params

def toggle_note_box_delete(state_params):
    return toggle_note_box('delete', state_params)


def toggle_note_box_regen(*args):
    args = list(args)
    state_params = args.pop()
    for i in range(len(config.default_loras)):
        del args[4+i]
        del args[4+i+1]
    checklist = args[2:]
    state_params = check_preset_models(checklist, state_params)
    return toggle_note_box('regen', state_params)

def toggle_note_box_preset(*args):
    args = list(args)
    state_params = args.pop()
    for i in range(len(config.default_loras)):
        del args[4+i]
        del args[4+i+1]
    checklist = args[2:]
    state_params = check_preset_models(checklist, state_params)
    return toggle_note_box('preset', state_params)


filename_regex = re.compile(r'\<div id=\"(.*?)_png\"')

def delete_image(state_params):
    [choice, selected] = state_params["prompt_info"]
    max_per_page = state_params["__max_per_page"]
    max_catalog = state_params["__max_catalog"]
    info = gallery.get_images_prompt(choice, selected, max_per_page)
    file_name = info["Filename"]
    output_index = choice.split('/')
    dir_path = os.path.join(config.path_outputs, "20{}".format(output_index[0]))

    log_path = os.path.join(dir_path, 'log.html')
    if os.path.exists(log_path):
        file_text = ''
        d_line_flag = False
        with open(log_path, "r", encoding="utf-8") as log_file:
            line = log_file.readline()
            while line:
                match = filename_regex.search(line)
                if match:
                    if match.group(1)==file_name[:-4]:
                        d_line_flag = True
                        line = log_file.readline()
                        continue
                    if d_line_flag:
                        d_line_flag = False
                if d_line_flag:
                    line = log_file.readline()
                    continue
                file_text += line
                line = log_file.readline()
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(file_text)
        print(f'[Toolbox] Delete item from log.html: {file_name}')

    log_name = os.path.join(dir_path, "log_ads.json")
    log_ext = {}
    if os.path.exists(log_name):
        log_ext = {}
        with open(log_name, "r", encoding="utf-8") as log_file:
            log_ext.update(json.load(log_file))
        if file_name in log_ext.keys():
            log_ext.pop(file_name)
        with open(log_name, 'w', encoding='utf-8') as log_file:
            json.dump(log_ext, log_file)

    file_path = os.path.join(dir_path, file_name)
    if os.path.exists(file_path):
        os.remove(file_path)
    print(f'[Toolbox] Delete image file: {file_path}')

    image_list_nums = len(gallery.refresh_images_catalog(output_index[0], True))
    if image_list_nums<=0:
        os.remove(log_path)
        os.rmdir(dir_path)
        index = state_params["__output_list"].index(choice)
        output_list, finished_nums, finished_pages = gallery.refresh_output_list(max_per_page, max_catalog)
        state_params.update({"__output_list": output_list})
        state_params.update({"__finished_nums_pages": f'{finished_nums},{finished_pages}'})
        if index>= len(state_params["__output_list"]):
            index = len(state_params["__output_list"]) -1
            if index<0:
                index = 0
        choice = state_params["__output_list"][index]
    elif image_list_nums < max_per_page:
        if selected > image_list_nums-1:
            selected = image_list_nums-1
        finished_nums_pages = state_params["__finished_nums_pages"]
        finished_nums = int(finished_nums_pages.split(',')[0])-1
        finished_pages = finished_nums_pages.split(',')[1]
        state_params.update({"__finished_nums_pages": f'{finished_nums},{finished_pages}'})
    else:
        if image_list_nums % max_per_page == 0:
            page = int(output_index[1])
            if page > image_list_nums//max_per_page:
                page = image_list_nums//max_per_page
            if page == 1:
                choice = output_index[0]
            else:
                choice = output_index[0] + '/' + str(page)
            output_list, finished_nums, finished_pages = gallery.refresh_output_list(max_per_page, max_catalog)
            state_params.update({"__output_list": output_list})
            state_params.update({"__finished_nums_pages": f'{finished_nums},{finished_pages}'})
        else:
            finished_nums_pages = state_params["__finished_nums_pages"]
            finished_nums = int(finished_nums_pages.split(',')[0])-1
            finished_pages = finished_nums_pages.split(',')[1]
            state_params.update({"__finished_nums_pages": f'{finished_nums},{finished_pages}'})

    state_params.update({"prompt_info":[choice, selected]})
    images_gallery = gallery.get_images_from_gallery_index(choice, max_per_page)
    state_params.update({"note_box_state": ['',0,0]})
    return gr.update(value=images_gallery), gr.update(choices=state_params["__output_list"], value=choice), gr.update(visible=False), gr.update(visible=False), state_params


def reset_params_by_image_meta(metadata, state_params, is_generating, inpaint_mode):
    if metadata is None:
        metadata = {}
    metadata_scheme = meta_parser.MetadataScheme('simple')
    metadata_parser = meta_parser.get_metadata_parser(metadata_scheme)
    parsed_parameters = metadata_parser.to_json(metadata)

    results = meta_parser.switch_layout_template(parsed_parameters, state_params)
    results += meta_parser.load_parameter_button_click(parsed_parameters, is_generating, inpaint_mode)

    engine_name = parsed_parameters.get("Backend Engine", parsed_parameters.get("backend_engine", "SDXL-Fooocus"))
    print(f'[Toolbox] Reset_params_from_image: -->{engine_name} params from the image with embedded parameters.')
    return results

def reset_image_params(state_params, is_generating, inpaint_mode):
    [choice, selected] = state_params["prompt_info"]
    metainfo = gallery.get_images_prompt(choice, selected, state_params["__max_per_page"])
    metadata = copy.deepcopy(metainfo)
    metadata['Refiner Model'] = metainfo.get('Refiner Model', 'None')
    state_params.update({"note_box_state": ['',0,0]})

    results = reset_params_by_image_meta(metadata, state_params, is_generating, inpaint_mode)
    return results + [gr.update(visible=False)] * 2


def apply_enabled_loras(loras):
        enabled_loras = []
        for lora_enabled, lora_model, lora_weight in loras:
            if lora_enabled:
                enabled_loras.append([lora_model, lora_weight])
        return enabled_loras


def save_preset(*args):
    args = list(args)
    args.reverse()
    save_name = args.pop() # retrieve the save_name the user entered
    backend_params = dict(args.pop())
    output_format = args.pop()
    inpaint_advanced_masking_checkbox = args.pop()
    mixing_image_prompt_and_vary_upscale = args.pop()
    mixing_image_prompt_and_inpaint = args.pop()
    backfill_prompt = args.pop()
    translation_methods = args.pop()
    input_image_checkbox = args.pop()
    state_params = dict(args.pop())

    advanced_checkbox = args.pop()
    image_quantity = int(args.pop())
    prompt = args.pop()
    negative_prompt = args.pop()
    style_selections = args.pop()
    performance_selection = args.pop()
    overwrite_step = int(args.pop())
    overwrite_switch = args.pop()
    aspect_ratios_selection = args.pop()
    overwrite_width = args.pop()
    overwrite_height = args.pop()
    guidance_scale = args.pop()
    sharpness = args.pop()
    adm_scaler_positive = args.pop()
    adm_scaler_negative = args.pop()
    adm_scaler_end = args.pop()
    refiner_swap_method = args.pop()
    adaptive_cfg = args.pop()
    clip_skip = args.pop()
    base_model = args.pop()
    refiner_model = args.pop()
    refiner_switch = args.pop()
    refiner_switch = common.refiner_slider
    sampler_name = args.pop()
    sampler_name = common.sampler_name
    scheduler_name = args.pop()
    scheduler_name = common.scheduler_name
    vae_name = args.pop()
    seed_random = args.pop()
    image_seed = args.pop()
    inpaint_engine = args.pop()
    inpaint_engine_state = args.pop()
    inpaint_mode = args.pop()
    enhance_inpaint_mode_ctrls = [args.pop() for _ in range(config.default_enhance_tabs)]
    generate_button = args.pop()
    load_parameter_button = args.pop()
    freeu_ctrls = [bool(args.pop()), float(args.pop()), float(args.pop()), float(args.pop()), float(args.pop())]
    loras = [(bool(args.pop()), str(args.pop()), float(args.pop())) for _ in range(config.default_max_lora_number)]

    if save_name:
        # remove save_name's leading & trailing spaces
        # convert in-string spaces to underscore
        # then make initial character upper, do not change the rest
        save_name = save_name.strip()
        save_name = save_name.replace(" ", "_")
        save_name = save_name[:1].upper() + save_name[1:]
        preset = {}

        if 'backend_engine' in backend_params and backend_params['backend_engine']!='Fooocus':
            preset["default_engine"] = backend_params
        preset["default_model"] = base_model
        preset["default_refiner"] = refiner_model
        preset["default_refiner_switch"] = refiner_switch
        preset["default_loras"] = loras
        preset["default_cfg_scale"] = guidance_scale
        preset["default_sample_sharpness"] = sharpness
        if ads.default["adaptive_cfg"] != adaptive_cfg:
            preset["default_cfg_tsnr"] = adaptive_cfg
        if ads.default["clip_skip"] != clip_skip:
            preset["default_clip_skip"] = clip_skip
        preset["default_sampler"] = sampler_name
        preset["default_scheduler"] = scheduler_name
        preset["default_performance"] = performance_selection
        preset["default_prompt"] = prompt
        preset["default_prompt_negative"] = negative_prompt
        preset["default_styles"] = style_selections
        preset["default_aspect_ratio"] = "0*0"
        preset["default_overwrite_step"] = overwrite_step
        preset["checkpoint_downloads"] = {}
        preset["embeddings_downloads"] = {}
        preset["lora_downloads"] = {}
        preset["vae_downloads"] = {}
        preset["default_vae"] = vae_name
        preset["default_inpaint_engine"] = {} # "inpaint_engine" causes junk to be added

        path_presets = Path('presets')
        path_user = Path(args_manager.args.user_dir)
        save_path = Path(path_presets/f'{PR.category_selection}/{save_name}.json')
        user_category = Path(path_user/f'user_presets/{PR.category_selection}')

        # temp. save to working presets:
        US.save_json(preset, save_path)
        # perm. save to user presets
        user_path = US.mkdir_copy_file(save_path, user_category)
        if user_path:
            print(f'[Toolbox] Saved the current parameters to {user_path.resolve()}')
            state_params.update({"__preset": save_name})
            args_manager.args.preset = save_name
        else:
            print(f'Could not save the new {save_name} preset')
    state_params.update({"note_box_state": ['',0,0]})
    results = [gr.update(visible=False)] * 3 + [state_params]
    results += UIS.refresh_nav_bars(state_params)
    return results
