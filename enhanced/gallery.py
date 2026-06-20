import gradio as gr
import os
import math
import json
import copy
import re
import common
import modules.util as util
import modules.config as config
import enhanced.toolbox as toolbox
from lxml import etree
from enhanced.translator import interpret
from pathlib import Path


# app context
images_list = {}
images_list_keys = []
images_prompt = {}
images_prompt_keys = []
images_ads = {}


image_types = ['.png', '.jpg', '.jpeg', '.webp']
output_images_regex = re.compile(r'\d{4}-\d{2}-\d{2}')

last_selected_full_path = None
last_selected_folder_choice = None
target_index_lock = None


def gallery_report(total_image_count, actual_total_pages, viewable_pages):
    print()
    interpret(f'[Gallery] The image catalogue contains a total of {total_image_count} images and {actual_total_pages} pages,')
    interpret(f'of which the last {viewable_pages} pages are available for viewing within', 'FooocusPlus.')
    print()
    return


def refresh_output_list(max_per_page, max_catalog):
    global image_types

    listdirs = [f for f in os.listdir(config.path_outputs) if output_images_regex.findall(f) and os.path.isdir(os.path.join(config.path_outputs,f))]
    if listdirs is None:
        return None
    listdirs1 = listdirs.copy()
    total_nums = 0
    for index in listdirs:
        path_gallery = os.path.join(config.path_outputs, index)
        nums = len(util.get_files_from_folder(path_gallery, image_types, None))
        total_nums += nums
        if nums > max_per_page:
            max_page_no = math.ceil(nums/max_per_page)
            for i in range(1,max_page_no+1):
                listdirs1.append("{}/{}".format(index, str(i).zfill(len(str(max_page_no)))))
            listdirs1.remove(index)
    output_list = sorted([f for f in listdirs1], reverse=True)
    actual_total_pages = len(output_list)
    display_max_pages = max_catalog
    output_list = output_list[:display_max_pages]
    viewable_pages = len(output_list)
    gallery_report(total_nums, actual_total_pages, viewable_pages)
    return output_list, total_nums, actual_total_pages


def images_list_update(choice, state_params):
    if "__output_list" not in state_params.keys():
        return  gr.update(), gr.update(), state_params, gr.update()
    output_list = state_params["__output_list"]
    if choice is None and len(output_list) > 0:
        choice = output_list[0]
    images_gallery = get_images_from_gallery_index(choice, state_params["__max_per_page"])
    state_params.update({"prompt_info": [choice, 0]})

    # Check if we are coming from a deletion
    show_welcome = state_params.get("show_welcome", False)

    # Clear it immediately so subsequent manual clicks work normally
    if show_welcome:
        state_params["show_welcome"] = False

    if common.is_generating:
        common.is_generating = False
        # Keep history hidden
        history_gallery_update = gr.update(value=images_gallery, visible=False)
        # Keep progress_gallery open and visible
        progress_gallery_update = gr.update(visible=True)
    else:
        # Show history normally:
        history_gallery_update = gr.update(value=images_gallery, visible=True)
        # Turn off progress
        progress_gallery_update = gr.update(visible=False)

    return (history_gallery_update,
            gr.update(open=False, visible=len(output_list)>0),
            state_params,
            # Dynamic progress_gallery visibility update:
            progress_gallery_update,
            gr.update(visible=show_welcome)) # turn off welcome_window


def select_index(choice, image_tools_checkbox, state_params, evt: gr.SelectData):
    if "__output_list" in state_params.keys():
        state_params.update({"infobox_state": 0})
        state_params.update({"note_box_state": ['',0,0]})
    print(f'[Gallery] Selected_gallery_catalog: change image catalog:{choice}.')
    state_params.update({"gallery_state": 'finished_index'})
    return [gr.update(visible=True)] + [gr.update(visible=image_tools_checkbox)] + [gr.update(visible=False)] * 8 + [state_params]


def select_history_gallery(choice, state_params, backfill_prompt, evt: gr.SelectData):
    if "__output_list" not in state_params.keys():
        return  [gr.update()] * 7 + [state_params]
    state_params.update({"note_box_state": ['',0,0]})
    state_params.update({"prompt_info": [choice, evt.index]})
    if choice is None and len(state_params["__output_list"]) > 0:
        choice = state_params["__output_list"][0]
    result = get_images_prompt(choice, evt.index, state_params["__max_per_page"], True)
    #print(f'[Gallery] Selected_gallery: selected index {evt.index} of {choice} images_list:{result["Filename"]}.')
    if backfill_prompt and 'Prompt' in result:
        return [gr.update(value=toolbox.make_infobox_HTML(result, state_params['__theme'])), gr.update(value=result["Prompt"]), gr.update(value=result["Negative Prompt"])] + [gr.update(visible=False)] * 4 + [state_params]
    else:
        return [gr.update(value=toolbox.make_infobox_HTML(result, state_params['__theme'])), gr.update(), gr.update()] + [gr.update(visible=False)] * 4 + [state_params]

def select_gallery_progress(state_params, evt: gr.SelectData):
    #if "__output_list" not in state_params.keys():
    #    return  [gr.update()] * 5 + [state_params]
    state_params.update({"note_box_state": ['',0,0]})
    state_params.update({"prompt_info": [None, evt.index]})
    result = get_images_prompt(state_params["__output_list"][0], evt.index, state_params["__max_per_page"])
    return [gr.update(value=toolbox.make_infobox_HTML(result, state_params['__theme']), visible=False)] + [gr.update(visible=False)] * 4 + [state_params]


def get_images_from_gallery_index(choice, max_per_page):
    global images_list

    page = 0
    _page = choice.split("/")
    if len(_page) > 1:
        choice = _page[0]
        page = int(_page[1])

    images_gallery = refresh_images_catalog(choice)
    nums = len(images_gallery)
    if page > 0:
        page = abs(page-math.ceil(nums/max_per_page))+1
        if page*max_per_page < nums:
            images_gallery = images_list[choice][(page-1)*max_per_page:page*max_per_page]
        else:
            images_gallery = images_list[choice][nums-max_per_page:]

    base_path = Path(config.path_outputs) / choice
    images_gallery = [str(base_path / f) for f in images_gallery]
    #print(f'[Gallery]Get images from index: choice={choice}, page={page}, images_gallery={images_gallery}')
    return images_gallery


def refresh_images_catalog(choice: str, passthrough = False):
    global images_list, images_list_keys, image_types

    if not passthrough and choice in images_list_keys:
        images_list_keys.remove(choice)
        images_list_keys.append(choice)
        return images_list[choice]

    # Pathlib modernization: Direct path mapping
    base_path = Path(config.path_outputs) / choice

    # Get files from folder using the string representation of the Path
    images_list_new = sorted([f for f in util.get_files_from_folder(str(base_path), image_types, None)], reverse=True)

    if len(images_list_new) == 0:
        parse_html_log(choice, passthrough)
        if choice in images_list_keys:
            images_list_keys.remove(choice)
            images_list.pop(choice, None)
        return []

    # Cache Management
    if choice in images_list_keys:
        images_list_keys.remove(choice)

    if len(images_list_keys) > 15:
        old_key = images_list_keys.pop(0)
        images_list.pop(old_key, None)

    images_list.update({choice: images_list_new})
    images_list_keys.append(choice)

    # This now uses the modernized choice string internally
    parse_html_log(choice, passthrough)

    print(f'[Gallery] Refresh_images_catalog: loaded {len(images_list[choice])} items for {choice}.')
    return images_list[choice]


def get_gallery_label(state_params):
    global last_selected_full_path

    # 1. Run the scan to get current counts
    new_output_list, total_count, total_pages = refresh_output_list(
        config.default_image_catalog_max_per_page,
        config.default_image_catalog_max_number
    )

    # 2. MAGIC: Calculate the new address if we have a selected image
    target_folder, target_index = None, None
    if last_selected_full_path:
        target_folder, target_index = get_new_virtual_address(last_selected_full_path, config.default_image_catalog_max_per_page)

    # 3. Calculate viewable pages logic
    viewable = total_pages if total_pages < config.default_image_catalog_max_number else config.default_image_catalog_max_number

    # 4. Create the localized string via Argos/Interpret
    label_text = interpret(
        f"Generated Images Catalog: {total_count} images and {total_pages} pages ({viewable} pages viewable)",
        "",
        silent=True
    )

    return (
        gr.update(choices=new_output_list,
            value=target_folder), # Update Radio
        label_text,               # Update Textbox
        gr.update(visible=False)  # Update Gallery (Remove selected_index)
    )


def get_images_prompt(choice, selected, max_per_page, display_index=False):
    global images_list, images_prompt, images_prompt_keys, images_ads

    if choice is None:
        return None

    page = 0
    _page = choice.split("/")
    if len(_page) > 1:
        choice = _page[0]
        page = int(_page[1])

    page_choice = page
    page_index = selected

    # A. Call the parser and capture the file existence flag
    log_file_exists = parse_html_log(choice)

    # B. Determine Catalog Numbers
    if choice not in images_list.keys():
        nums = len(refresh_images_catalog(choice))
    else:
        nums = len(images_list[choice])

    # C. Handle Pagination
    if page > 0:
        page = abs(page - math.ceil(nums / max_per_page)) + 1
        if page * max_per_page < nums:
            selected = (page - 1) * max_per_page + selected
        else:
            selected = nums - max_per_page + selected

    filename = images_list[choice][selected]

    # D. DIAGNOSTIC BRANCHING
    # Condition 1: The entire log file is missing
    if not log_file_exists:
        return {
            "[Gallery]": "The HTML Image Log is not available for this date.",
            "Filename": filename
        }

    # Condition 2: Log exists, but this specific image is not in it (e.g., Editor composite)
    if choice not in images_prompt or filename not in images_prompt[choice]:
        return {
            "[Gallery]": "Metadata for this specific image was not found in the Log.",
            "Filename": filename
        }

    # E. Success: Return MetaInfo
    metainfo = images_prompt[choice][filename]

    if display_index:
        print(f'[Gallery] Image selected: {filename} (Catalog: {choice})')

    if choice in images_ads.keys() and filename in images_ads[choice].keys():
        metainfo.update({"Advanced_parameters": images_ads[choice][filename]})

    return metainfo


def parse_html_log(choice: str, passthrough = False):
    global images_prompt, images_prompt_keys, images_ads

    # 1. Clean the choice index
    choice = choice.split('/')[0]

    # 2. Cache Check: If we already have it, return True
    if not passthrough and choice in images_prompt:
        if choice in images_prompt_keys:
            images_prompt_keys.remove(choice)
        images_prompt_keys.append(choice)
        return True

    # 3. Pathlib Construction
    base_path = Path(config.path_outputs) / choice
    html_file = base_path / 'log.html'

    # 4. Physical Existence Check
    if not html_file.exists():
        return False

    # 5. Parsing Logic
    try:
        html = etree.parse(str(html_file), etree.HTMLParser(encoding='utf-8'))
    except Exception as e:
        print(f'[Gallery] Parse Error: {e}')
        return False

    prompt_infos = html.xpath('/html/body/div')
    images_prompt_list = {}

    for info in prompt_infos:
        text = info.xpath('.//p//text()')
        if len(text) > 20:
            def standardized(x):
                if x.startswith(', '): x = x[2:]
                if x.endswith(': '): x = x[:-2]
                return '' if x == ' ' else x

            text = list(map(standardized, info.xpath('.//p//text()')))
            if text[6] != '': text.insert(6, '')
            if text[8] == '': text.insert(8, '')

            info_dict = {"Filename": text[0]}
            if text[3] == '':
                info_dict[text[1]] = text[2]
                info_dict[text[4]] = text[5]
                info_dict[text[7]] = text[8]
                for i in range(0, int(len(text)/2)-5):
                    info_dict[text[10+i*2]] = text[11+i*2]
            else:
                if text[4] != 'Fooocus V2 Expansion':
                    del text[6]
                else:
                    text.insert(4, '')
                    if text[6] == 'Styles':
                        text.insert(6, '')
                        del text[8]
                    else:
                        del text[7]
                for i in range(0, int(len(text)/2)-1):
                    info_dict[text[1+i*2]] = text[2+i*2]
        else:
            text = info.xpath('.//td//text()')
            if len(text) > 10:
                # Handle line breaks
                for idx in [2, 5, 8, 29, 32, 35, 41]:
                    if idx < len(text) and text[idx] in ['\n', '\r\n']:
                        text.insert(idx, '')

                info_dict = {"Filename": text[0]}
                for i in range(0, int(len(text)/3)):
                    key = text[1+i*3].strip()
                    value = text[2+i*3].strip()
                    if key in ['', None, 'Full raw prompt', 'Positive', 'Negative']:
                        continue
                    info_dict[key] = value
            else:
                if 'Upscale (Fast)' not in text:
                    print(f'[Gallery] Parse error for {choice}, file={html_file}')
                info_dict = {"Filename": text[1]}
                info_dict[text[2]] = text[3]

        images_prompt_list.update({info_dict["Filename"]: info_dict})

    # 6. Cleanup if log was found but is empty
    if not images_prompt_list:
        if choice in images_prompt:
            if choice in images_prompt_keys:
                images_prompt_keys.remove(choice)
            images_prompt.pop(choice, None)
            images_ads.pop(choice, None)
        return False

    # 7. Update Cache
    if choice in images_prompt_keys:
        images_prompt_keys.remove(choice)

    if len(images_prompt) > 15:
        key = images_prompt_keys.pop(0)
        images_prompt.pop(key, None)
        images_ads.pop(key, None)

    images_prompt.update({choice: images_prompt_list})
    images_prompt_keys.append(choice)

    # 8. Load JSON Logs (Advanced Params)
    log_json = html_file.parent / "log_ads.json"
    log_ext = {}
    if log_json.exists():
        try:
            with log_json.open("r", encoding="utf-8") as f:
                log_ext.update(json.load(f))
        except Exception as e:
            print(f'[Gallery] JSON Error: {e}')

    images_ads.update({choice: log_ext})
    print(f'[Gallery] Parse_html_log: loaded {len(images_prompt[choice])} entries for {choice}.')
    return True
