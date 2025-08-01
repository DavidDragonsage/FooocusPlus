import os
import json
import random
import threading
import time
import gradio as gr
import args_manager as args
import common
import modules.user_structure as US
from ldm_patched.modules import model_management
from pathlib import Path

current_preset = args.args.preset
presets_path = Path('presets')
random_block = False # used by Random Preset Category


def find_preset_file(preset):
    global presets_path
    preset_name_path = Path(preset)
    if preset_name_path.suffix != 'json':
        preset_name_path = Path(preset_name_path.with_suffix(preset_name_path.suffix + '.json'))
    preset_file_path = US.find_file_path(presets_path, preset_name_path)
    if not preset_file_path:
        if preset != 'Default':
            print(f'Could not find the {preset} preset')
            print()
        return {}
    common.preset_file_path = preset_file_path # used to guarantee use of SD1.5 AR template
    return preset_file_path

def find_preset_category(preset):
    try:
        preset_file = Path(find_preset_file(preset))
        if preset_file:
            preset_category = (preset_file.parent).name
        else:
            preset_category = 'Favorite'
    except:
        preset_category = 'Favorite'
    return preset_category

category_selection = find_preset_category(current_preset)

def get_preset_list(): # called by update_files() in modules.config
    preset_list = list(presets_path.rglob('*.json'))
    if not [preset_list]:   # also used to check if preset files exist
        print('No presets found')
        preset_list = ['initial']
        return preset_list
    return preset_list

def get_presets_in_folder(arg_folder_name):
    if not arg_folder_name:
        arg_folder_name = category_selection
    presets_in_folder = []
    if arg_folder_name == presets_path:
        folder_name = presets_path
    else:
        folder_name = Path(presets_path/arg_folder_name)
    if folder_name.is_dir():
        presets_in_folder = list(folder_name.rglob('*.json'))
        if not presets_in_folder:
            print(f'Could not find presets in the {arg_folder_name} folder.')
            print()
    else:
        print(f'Could not find the {arg_folder_name} folder.')
        print()
    return presets_in_folder

def get_presetnames_in_folder(folder_name):
    presetnames_in_folder = []
    if folder_name == 'All':
        folder_name = presets_path
    presets_in_folder = get_presets_in_folder(folder_name)
    if presets_in_folder:
        for preset_file in presets_in_folder:
            presetname = Path(preset_file)
            presetnames_in_folder.append(presetname.stem)
        if folder_name == presets_path: # if we are listing files in all folders
            temp_set = set(presetnames_in_folder)    # then remove duplicates
            presetnames_in_folder = sorted(temp_set) # now convert back to a list
    return presetnames_in_folder

def get_all_presetnames():
    return get_presetnames_in_folder(presets_path)

def get_preset_foldernames(omit_current_dir = False):
    preset_foldernames = []
    if presets_path.is_dir():
        for item in presets_path.iterdir():
            if item.is_dir():
                if omit_current_dir and item.name == category_selection:
                    continue
                else:
                    preset_foldernames.append(item.name)
        if not preset_foldernames:
            print(f'Could not find any preset subfolders in {preset_folder}')
            print()
            return preset_foldernames
    else:
        print(f'Could not find the {presets_path} folder')
        print()
    return preset_foldernames

def get_preset_categories():
    preset_categories = get_preset_foldernames()
    if preset_categories:
        preset_categories.append('All')
        preset_categories.append('Random')
        preset_categories.sort()
    return preset_categories

def countdown(arg_seconds): # used by the Random Preset Category
    global random_block
    random_block = True
    while arg_seconds >0:
        time.sleep(1)
        arg_seconds -= 1
    random_block = False
    return

def init_countdown_blocker(timer_duration = 5):
    timer_thread = threading.Thread(target=countdown, args=(timer_duration,))
    timer_thread.start()
    return

def get_random_preset_in_category(rand_category):
    global category_selection, presets_path
    if rand_category == 'All':
        rand_category = presets_path
    preset_list = get_presetnames_in_folder(rand_category)
    if len(preset_list) >1:
        random_index = random.randint(0, (len(preset_list)-1))
        random_preset_path = Path(preset_list[random_index])
        random_preset_name = random_preset_path.stem
    else:
        try:
            random_preset_name = preset_list[0]
        except:
            print(f'No presets found in the {rand_category} category')
            random_preset_name = ''
    return random_preset_name


def set_category_selection(arg_category_selection):
    global category_selection, current_preset, random_block
    if arg_category_selection == '':
        category_selection = 'Favorite'
    if (arg_category_selection == 'Random') and\
        (arg_category_selection != category_selection):
        category_selection = 'All'
    else:
        category_selection = arg_category_selection
    preset_choices = get_presetnames_in_folder(category_selection)
    if (not current_preset in preset_choices or arg_category_selection == 'Random') and not random_block:
        current_preset = get_random_preset_in_category(category_selection)
        if arg_category_selection == 'Random':
            init_countdown_blocker(2)
    return gr.update(value=category_selection),\
        gr.update(choices=preset_choices, value=current_preset),\
        gr.update(value=f'Current Preset: {current_preset}')


def select_data_from_preset(preset_content):
    assert isinstance(preset_content, dict)
    global current_preset
    preset_prepared = {}
    items = preset_content

    # for presets that do not have a default prompt or negative prompt
    # and almost all presets do not have an image quantity
    items.setdefault("default_prompt", common.positive)
    items.setdefault("default_prompt_negative", common.negative)
    items.setdefault("default_image_quantity", common.image_quantity)
    items.setdefault("default_sampler", common.sampler_name)
    items.setdefault("default_scheduler", common.scheduler_name)

    preset_prompt = items.get("default_prompt")
    if preset_prompt != "":
        common.positive = preset_prompt

    preset_negative = items.get("default_prompt_negative")
    if preset_negative != "":
        common.negative = preset_negative

    preset_quantity = items.get("default_image_quantity")
    if preset_quantity != common.image_quantity:
        common.image_quantity = preset_quantity
        print(f'[Preset] Image Quantity set to {common.image_quantity} by preset')

    preset_sampler = items.get("default_sampler")
    if preset_sampler != common.sampler_name:
        common.sampler_name = preset_sampler
        print()
        print(f'[Preset] Sampler set to {common.sampler_name} by the {current_preset} preset')

    preset_scheduler = items.get("default_scheduler")
    if preset_scheduler != common.scheduler_name:
        common.scheduler_name = preset_scheduler
        print(f'[Preset] Scheduler set to {common.scheduler_name} by the {current_preset} preset')
    return


def get_preset_content(preset, quiet=True):
    preset_file = find_preset_file(preset)
    if preset_file:
        try:
            with open(preset_file, "r", encoding="utf-8") as json_file:
                json_content = json.load(json_file)
                if not quiet:
                    print(f'[Preset] Loaded the {preset} preset content from:')
                    print(f' {preset_file}')
            common.preset_content = json_content
            return json_content
        except Exception as e:
            print(f'Could not load the {preset} preset content from {preset_file}')
            print(e)
        print()
    return {}

def set_preset_selection(arg_preset_selection, state_params):
    global category_selection, current_preset, random_block
    if arg_preset_selection == '' and not random_block:
        if current_preset == '':
            current_preset = args.args.preset
        print(f'Using the {current_preset} preset...')

    elif (current_preset != arg_preset_selection) and not random_block and \
        (category_selection == find_preset_category(arg_preset_selection) \
        or category_selection == 'All'):
        current_preset = arg_preset_selection  # update the current preset tracker

    state_params.update({'bar_button': current_preset})
    args.args.preset = current_preset      # for use by AR Shortlist/Standard toggle

    # determine prompt and quantity values in current preset
    # so that they can update their UI controls
    preset_content = get_preset_content(current_preset, quiet = True)
    select_data_from_preset(preset_content)

    return gr.update(value=current_preset), \
        gr.update(value=state_params), \
        gr.update(value=f'Current Preset: {current_preset}'), \
        gr.update(value=common.current_AR), \
        gr.update(value=category_selection), \
        gr.update(value=common.positive), \
        gr.update(value=common.negative), \
        gr.update(value=common.image_quantity), \
        gr.update(value=common.sampler_name), \
        gr.update(value=common.scheduler_name)

def bar_button_change(bar_button, state_params):
    global category_selection, current_preset
    state_params.update({'bar_button': bar_button})
    current_preset = bar_button
    args.args.preset = current_preset
    category_selection = find_preset_category(current_preset)
    return state_params, gr.update(value=category_selection),\
        gr.update(value=current_preset)

def get_initial_preset_content():
    global current_preset, category_selection
    json_content = ''
    preset = args.args.preset
    if not find_preset_file(preset):
        if find_preset_file('Default'):
            preset = 'Default'
        else:
            print('Could not find the startup preset')
            category_selection = 'Random'
            if not preset:
                print('Could not find any presets')
                current_preset = 'initial'
    if category_selection != 'Random' and current_preset != 'initial':
        args.args.preset = preset
        current_preset = preset
        category_selection = find_preset_category(preset)
    if current_preset != 'initial':
        set_category_selection(category_selection)
        json_content = get_preset_content(current_preset, quiet=False)
    return json_content

def get_lowVRAM_preset_content():
    global current_preset, category_selection
    json_content = ''
    if find_preset_file('4GB_Default'):
        common.is_low_vram_preset = True
        category_selection = 'LowVRAM'
        common.default_bar_category = category_selection
        args.args.preset = '4GB_Default'
        current_preset = args.args.preset
        json_content = get_preset_content(current_preset, quiet=False)
        print('The 4GB_Default preset is optimized for low VRAM systems')
    return json_content


def preset_count():
    return len(get_preset_list())

def pad_list(arg_list, arg_length, arg_value):
    list_length = len(arg_list)
    if list_length >= arg_length:
        return arg_list
    else:
        padding_size = arg_length - list_length
        padded_list = arg_list + [arg_value] * padding_size
        return padded_list

def preset_bar_count():
    preset_bar_list = get_presets_in_folder(common.default_bar_category)
    preset_bar_count = len(preset_bar_list)
    return preset_bar_count

def save_preset(x):
    global category_selection, current_preset
    PR_choices = get_presetnames_in_folder(category_selection)
    return gr.update(), gr.update(value=current_preset), \
        gr.update(choices=PR_choices)
