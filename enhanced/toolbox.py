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
import enhanced.gallery as gallery
import enhanced.version as version
import modules.flags as flags
import modules.meta_parser as meta_parser

from pathlib import Path
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from enhanced.backend import sync_model_info
from enhanced.translator import interpret, interpret_info
from modules.model_loader import load_file_from_url


# Toolbox context
toolbox_note_preset_title=interpret('Create a new preset using the current parameters.', silent = True)

toolbox_note_load_title=interpret('Load the metadata from the Image Log to prepare to regenerate. The positive and negative prompts will be overwritten. Press "Generate" when ready,', silent = True)

toolbox_note_missing_muid=interpret('The model in the params and configuration is missing the MUID. And the system will spend some time calculating the hash of model files and synchronizing information to obtain the MUID for usability and transferability.', silent = True)


# Not used in Gradio 3.43.2:
def catalogue_close(current_selection):
    if not current_selection or current_selection == 'None':
        gallery_update = gr.update(visible=False, value=[])
    else:
        # keep the current images so they are there when the user returns
        gallery_update = gr.update(visible=False)
    return (gr.update(visible=True),    # welcome_window
            gallery_update,             # history_gallery
            gr.update(visible=False),   # image_toolbox
            gr.update(open=False),      # history_accordion
            gr.update(autofocus=True),  # prompt
            gr.update(visible=False)    # toolbox_info_box
    )


def make_infobox_HTML(info, theme):
    # Theme Setup
    bgcolor = '#f3f4f6' if theme != "dark" else '#2d2d2d'
    text_color = '#111' if theme != "dark" else '#eee'
    header_border = 'rgba(0,0,0,0.1)'

    style = (
        f"background-color: {bgcolor}; color: {text_color}; "
        f"padding: 15px; border-radius: 8px; min-height: 50px; "
        f"line-height: 1.5; word-wrap: break-word;"
    )

    header_style = (
        f"font-weight: bold; font-size: 1.1em; margin-bottom: 10px; "
        f"padding-bottom: 5px; border-bottom: 1px solid {header_border};"
    )

    # 1. Pre-define localized strings (Python 3.10 Compatibility)
    title_text = interpret('Image Log Metadata', silent = True)
    gallery_label = interpret('[Gallery]', silent = True)
    advice_text = interpret('Use the "Image Metadata" tab to view or load the metadata information from the image.', silent = True)

    # "Extended" condition messages
    editor_explanation = interpret('This image may been produced by Upscale (Fast 2x) or copied from another folder.', silent = True)
    missing_file_explanation = interpret('The Image Log file is missing. "Disable Image Log" may have been enabled in the Advanced/Image Control section, or log.html was been removed from the output folder.', silent = True)

    # Generic fallback messages
    generic_err_title = interpret('[Toolbox] Image Log metadata not found.', silent = True)
    generic_combined_cause = interpret('This image may been produced by Upscale (Fast 2x) or the Image Log file is missing.', silent = True)

    wait_msg = interpret('Waiting for image info...', silent = True)

    # Initialize the container
    html = f'<div style="{style}">'
    html += f'<div style="{header_style}">{title_text}</div>'

    if info:
        content_added = False
        gallery_data = info.get("[Gallery]")

        # 2. Main Metadata Loop
        for key in info:
            skip_keys = [
                '[Gallery]', 'Filename', 'Advanced_parameters',
                'Fooocus V2 Expansion', 'Metadata Scheme', 'Version', 'Upscale (Fast)'
            ]
            if key in skip_keys or info[key] in [None, '', 'None']:
                continue

            html += f'<div><b>{key}:</b> {info[key]}</div>'
            content_added = True

        # 3. Targeted Error Handling
        if not content_added:
            if gallery_data:
                # headline_err is the localized version of the string from gallery.py
                headline_err = interpret(gallery_data)

                # Determine the extended "msg" flag based on the error type
                if "specific image" in gallery_data:
                    msg = editor_explanation
                else:
                    msg = missing_file_explanation

                # Display the Bold Headline + the Italic Explanation (msg)
                html += (
                    f'<div style="margin-top: 5px;"><b>{gallery_label}:</b> {headline_err}</div>'
                    f'<div style="font-style: italic; margin-top: 8px;">'
                    f'{msg}'
                    f'</div>'
                    f'<div style="margin-top: 8px;">'
                    f'{advice_text}'
                    f'</div>'
                )
            else:
                # True Fallback: metadata is missing but no [Gallery] error was provided
                html += (
                    f'<div style="font-style: italic; margin-top: 5px;">'
                    f'{generic_err_title} {generic_combined_cause}'
                    f'</div>'
                    f'<div style="margin-top: 8px;">'
                    f'{advice_text}'
                    f'</div>'
                )
    else:
        html += f'<p>{wait_msg}</p>'

    html += '</div>'
    return html


def toggle_toolbox_info(state_params):
    infobox_state = state_params["infobox_state"]
    infobox_state = not infobox_state
    state_params.update({"infobox_state": infobox_state})
    #interpret(f'[Toolbox] Toggle_image_info: {infobox_state}')
    [choice, selected] = state_params["prompt_info"]
    prompt_info = gallery.get_images_prompt(choice, selected, state_params["__max_per_page"])
    return gr.update(value=make_infobox_HTML(prompt_info, state_params['__theme']), visible=infobox_state and prompt_info), state_params


def check_preset_models(checklist, state_params):
    note_box_state = state_params["note_box_state"]
    note_box_state[2] = 0
    state_params.update({"note_box_state": note_box_state})
    return state_params


def cancel_note_box(state_params):
    note_box_state = state_params.get("note_box_state", [None, False, False])
    note_box_state[1] = False # Set visibility flag to False
    state_params.update({"note_box_state": note_box_state})

    # We return a 'Hide Everything' update list.
    # The order must match the 'outputs' list in the .click handler.
    return [
        gr.update(visible=False), # toolbox_note_info
        gr.update(visible=False), # toolbox_note_input_name
        gr.update(visible=False), # toolbox_note_delete_button
        gr.update(visible=False), # toolbox_note_load_button
        gr.update(visible=False), # toolbox_note_preset_button
        gr.update(visible=False), # toolbox_note_cancel_button
        gr.update(visible=False), # toolbox_note_box
        state_params,             # state_topbar
        gr.update(value="")       # toolbox_note_input_name (reset value)
    ]


def toggle_note_box(item, state_params):
    note_box_state = state_params["note_box_state"]

    # Initialize state if needed
    if note_box_state[0] is None:
        note_box_state[0] = item

    # Logic to handle toggling or switching between tools
    if item == note_box_state[0]:
        note_box_state[1] = not note_box_state[1]
    elif not note_box_state[1]:
        note_box_state[1] = not note_box_state[1]
        note_box_state[0] = item
    else:
        # SWITCHING TOOLS: The "Early Return" must match the final return counts!
        state_params.update({"note_box_state": note_box_state})
        if item == 'preset':
            # Needs 7 outputs to match the Preset handler
            return [gr.update(visible=True)] + [gr.update()] * 5 + [state_params]
        else:
            # Needs 5 outputs to match Delete/Load handlers
            return [gr.update(visible=True)] + [gr.update()] * 3 + [state_params]

    state_params.update({"note_box_state": note_box_state})
    flag = note_box_state[1]

    if item == 'delete':
        msg = interpret('DELETE the current image from the output directory and log?', silent=True)
        return (
            gr.update(value=msg, visible=True),
            gr.update(visible=flag), # Delete Button
            gr.update(visible=flag), # Cancel Button
            gr.update(visible=flag), # Note Box container
            state_params
        )

    if item == 'load':
        msg = interpret(toolbox_note_load_title, silent=True)
        return (
            gr.update(value=msg, visible=True),
            gr.update(visible=flag), # Load Button
            gr.update(visible=flag), # Cancel Button
            gr.update(visible=flag), # Note Box container
            state_params
        )

    if item == 'preset':
        msg = interpret(toolbox_note_preset_title, silent=True)
        return (
            gr.update(value=msg, visible=True),
            gr.update(visible=flag), # Text Input Name
            gr.update(visible=flag), # Save Button
            gr.update(visible=flag), # Cancel Button
            gr.update(visible=flag), # Note Box container
            state_params,
            gr.update(value=args_manager.args.preset) # Reset value
        )


def toggle_note_box_delete(state_params):
    return toggle_note_box('delete', state_params)


def toggle_note_box_load(*args):
    args = list(args)
    state_params = args.pop()
    for i in range(len(config.default_loras)):
        del args[4+i]
        del args[4+i+1]
    checklist = args[2:]
    state_params = check_preset_models(checklist, state_params)
    return toggle_note_box('load', state_params)


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

    # Get the metadata for the image we are about to delete
    info = gallery.get_images_prompt(choice, selected, max_per_page)
    file_name = info.get("Filename")

    # Early return if no image is actually selected
    if not file_name:
        return (
            gr.update(), gr.update(),
            gr.update(visible=False), # Delete Button
            gr.update(visible=False), # Note Box
            state_params,
            gr.update(visible=False), # Progress Window
            gr.update(visible=False), # welcome_window
            gr.update()               # Image Toolbox
        )

    output_index = choice.split('/')
    # Modernized path: No "20" prefix, using Path division
    dir_path = Path(config.path_outputs) / output_index[0]

    # 1. Handle HTML Log Deletion
    log_path = dir_path / 'log.html'
    if log_path.exists():
        file_text = ''
        d_line_flag = False
        # Using Path.open() for modern context management
        with log_path.open("r", encoding="utf-8") as log_file:
            for line in log_file:
                match = filename_regex.search(line)
                if match:
                    if match.group(1) == file_name[:-4]:
                        d_line_flag = True
                        continue
                    if d_line_flag:
                        d_line_flag = False

                if d_line_flag:
                    continue

                file_text += line

        with log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(file_text)

    # 2. Handle JSON Metadata Deletion (log_ads.json)
    log_name = dir_path / "log_ads.json"
    if log_name.exists():
        try:
            with log_name.open("r", encoding="utf-8") as f:
                log_ext = json.load(f)

            if file_name in log_ext:
                log_ext.pop(file_name)
                with log_name.open("w", encoding="utf-8") as f:
                    json.dump(log_ext, f)
        except Exception as e:
            # Silent fail for JSON errors to keep the UI moving
            pass

    # 3. Physically delete the image file
    file_path = dir_path / file_name
    file_erased= US.delete_file(file_path)
    # do not use with Gradio 3.43.2:
#    state_params.update({"show_welcome": file_erased})

    # 4. Update UI State & Page Calculations
    # refresh_images_catalog now uses the standardized choice string
    image_list_nums = len(gallery.refresh_images_catalog(output_index[0], True))

    if image_list_nums <= 0:
        # Cleanup the directory if empty
        if log_path.exists():
            log_path.unlink()
        if log_name.exists():
            log_name.unlink()

        try:
            dir_path.rmdir() # Only removes if empty
        except:
            pass

        index = state_params["__output_list"].index(choice)
        output_list, finished_nums, finished_pages = gallery.refresh_output_list(max_per_page, max_catalog)

        state_params.update({
            "__output_list": output_list,
            "__finished_nums_pages": f'{finished_nums},{finished_pages}'
        })

        # Adjust index if we deleted the last item in the list
        if index >= len(state_params["__output_list"]):
            index = len(state_params["__output_list"]) - 1
        if index < 0:
            index = 0

        choice = state_params["__output_list"][index] if state_params["__output_list"] else None

    elif image_list_nums < max_per_page:
        if selected > image_list_nums - 1:
            selected = image_list_nums - 1

        f_nums_pages = state_params["__finished_nums_pages"]
        finished_nums = int(f_nums_pages.split(',')[0]) - 1
        finished_pages = f_nums_pages.split(',')[1]
        state_params.update({"__finished_nums_pages": f'{finished_nums},{finished_pages}'})

    else:
        # Handle page shifts if the deletion emptied a page
        if image_list_nums % max_per_page == 0:
            page = int(output_index[1])
            if page > image_list_nums // max_per_page:
                page = image_list_nums // max_per_page

            choice = output_index[0] if page == 1 else f"{output_index[0]}/{page}"

            output_list, finished_nums, finished_pages = gallery.refresh_output_list(max_per_page, max_catalog)
            state_params.update({
                "__output_list": output_list,
                "__finished_nums_pages": f'{finished_nums},{finished_pages}'
            })
        else:
            f_nums_pages = state_params["__finished_nums_pages"]
            finished_nums = int(f_nums_pages.split(',')[0]) - 1
            finished_pages = f_nums_pages.split(',')[1]
            state_params.update({"__finished_nums_pages": f'{finished_nums},{finished_pages}'})

    # 5. Final state updates for the UI
    state_params.update({"prompt_info": [choice, selected]})
    images_gallery = gallery.get_images_from_gallery_index(choice, max_per_page)

    state_params.update({"note_box_state": ['', 0, 0]})

    return (
            gr.update(value=images_gallery),    # history_gallery
            gr.update(choices=state_params["__output_list"],
                value=choice),                  # gallery_index
            gr.update(visible=False),           # toolbox_note_delete_button
            gr.update(visible=False),           # toolbox_note_box
            state_params,                       # state_topbar
            gr.update(visible=False),           # preview_window
            gr.update(visible=False),           # welcome_window
            gr.update(visible=not file_erased)  # image_toolbox
        )


def load_log_info_into_prompt(state_params):
    [choice, selected] = state_params["prompt_info"]

    # 1. Retrieve the dictionary
    metainfo = gallery.get_images_prompt(choice, selected, state_params["__max_per_page"])

    # 2. Early return if no metadata found
    if not metainfo or "[Gallery]" in metainfo:
        return ""

    # 3. Convert the dictionary back into
    # the standard "Fooocus Log" string format
    # that meta_parser.read_meta_from_log expects to see:
    log_string = ""
    for key, value in metainfo.items():
        if key not in ["Filename", "Advanced_parameters"]:
            log_string += f"{key}: {value}\n"

    # Add advanced params if they exist
    if "Advanced_parameters" in metainfo:
        log_string += f"Advanced_parameters: {metainfo['Advanced_parameters']}\n"

    return log_string


def reset_params_by_meta(metadata, state_params, is_generating, inpaint_mode):
    if metadata is None:
        metadata = {}
    metadata_scheme = meta_parser.MetadataScheme('simple')
    metadata_parser = meta_parser.get_metadata_parser(metadata_scheme)
    parsed_parameters = metadata_parser.to_json(metadata)

    results = meta_parser.switch_layout_template(parsed_parameters,
        state_params)
    results += meta_parser.read_meta_from_log(parsed_parameters, is_generating, inpaint_mode)

    engine_name = parsed_parameters.get("Backend Engine", parsed_parameters.get("backend_engine", "SDXL-Fooocus"))
    interpret('[Toolbox] Loaded parameters from the metadata')
    interpret('The image was created with the engine:', engine_name)
    return results


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
    v2_substyle = args.pop()
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
    try:
        adaptive_cfg = args.pop()
    except:
        adaptive_cfg = config.default_cfg_scale
    try:
        clip_skip = args.pop()
    except:
        clip_skip = config.default_clip_skip
    base_model = args.pop()
    refiner_model = args.pop()
    refiner_switch = args.pop()
    refiner_switch = config.default_refiner_switch
    sampler_name = args.pop()
    sampler_name = config.default_sampler
    scheduler_name = args.pop()
    scheduler_name = config.default_scheduler
    vae_name = args.pop()
    seed_random = args.pop()
    image_seed = args.pop()
    inpaint_engine = args.pop()
    inpaint_engine_state = args.pop()
    inpaint_mode = args.pop()
    enhance_inpaint_mode_ctrls = [args.pop() for _ in range(config.default_enhance_tabs)]
    generate_button = args.pop()
    load_parameter_button = args.pop()
         # note, freeu_ctrls are not actually saved to a preset
    try: # error control from FooocusPlus 1.0.8.5, user reported float error
        freeu_ctrls = [(args.pop()), (args.pop()), (args.pop()), (args.pop()), (args.pop())] # removed forced type control on args.pop()
    except:
        freeu_ctrls = config.default_freeu
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
        preset["default_cfg_tsnr"] = adaptive_cfg
        preset["default_clip_skip"] = clip_skip
        preset["default_sampler"] = sampler_name
        preset["default_scheduler"] = scheduler_name
        preset["default_performance"] = performance_selection
        if common.overwrite_prompts:
            preset["default_prompt"] = prompt
            preset["default_prompt_negative"] = negative_prompt
        else:
            preset["default_prompt"] = ''
            preset["default_prompt_negative"] = ''
        preset["default_styles"] = style_selections
        preset["v2_substyle"] = v2_substyle
        if common.save_resolution:
            preset["default_aspect_ratio"] = common.resolution.split(' | ')[0].replace('×', '*')
        else:
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
        if save_name == 'Default' or save_name == 'Custom':
            save_path = Path(path_presets/f'Favorite/{save_name}.json')
            user_category = Path(path_user/'user_presets/Favorite')
        else:
            save_path = Path(path_presets/f'{PR.category_selection}/{save_name}.json')
            user_category = Path(path_user/f'user_presets/{PR.category_selection}')

        # temp. save to working presets:
        US.save_json(preset, save_path)
        # perm. save to user presets
        user_path = US.mkdir_copy_file(save_path, user_category)
        if user_path:
            interpret_info(f'[Toolbox] Saved the current parameters to the preset:', user_path)
            state_params.update({"__preset": save_name})
            args_manager.args.preset = save_name
            PR.current_preset = save_name
        else:
            interpret_info(f'Could not save the new preset:', save_name)
    state_params.update({"note_box_state": ['',0,0]})
    results = [gr.update(visible=False)] * 3 + [state_params]
    results += UIS.refresh_nav_bars(state_params)
    return results
