import os
import json
import random
import gradio as gr
import args_manager
from ldm_patched.modules import model_management
from pathlib import Path

category_selection = 'Favorite'
current_preset = 'Default'

def get_preset_paths():              # called by update_files() in modules.config
    preset_path = Path('.\presets')  # also used to check if preset files exist
    presets = list(preset_path.rglob('*.json'))
    if not [presets]:
        print('No presets found')
        presets = ['initial']
        return presets
    return presets

def get_random_preset():
    presets = get_preset_paths()
    random_preset = random.randint(0, (len(presets)-1))
    print(f'Selected a random preset file: {presets[random_preset]}')
    return presets[random_preset]

def get_presets_in_folder(arg_folder_name):
    if not arg_folder_name:
        arg_folder_name = category_selection
    if arg_folder_name == '.\presets':
        arg_folder_name = ''
    presets_in_folder = []
    folder_name = Path(f'.\presets\{arg_folder_name}') 
    if os.path.exists(folder_name):
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
    if folder_name == 'Random':
        random_preset = get_random_preset()
        presetname = Path(random_preset)
        presetnames_in_folder = [presetname.stem]
    else:
        presets_in_folder = get_presets_in_folder(folder_name)
        for preset_file in presets_in_folder:
            presetname = Path(preset_file)
            presetnames_in_folder.append(presetname.stem)
    return presetnames_in_folder

def get_all_presetnames():    
    return get_presetnames_in_folder('.\presets')

def find_preset_file(preset):
    preset_json = f'{preset}.json'
    preset_file = ''
    preset_path = Path('.\presets')
    for preset_file in preset_path.rglob(preset_json):
      if not preset_file:
        print(f'Could not find the {preset} preset')
        print()
        return {}
    return preset_file

def get_preset_content(preset):
    preset_file = find_preset_file(preset)
    if preset_file:
        try:
          with open(preset_file, "r", encoding="utf-8") as json_file:
              json_content = json.load(json_file)
              print(f'Loaded the {preset} preset from {preset_file}')
              return json_content
        except Exception as e:
            print(f'Could not load the {preset} preset from {preset_file}')
            print(e)
        print()
    return {}

def get_initial_preset_content():
    preset = args_manager.args.preset
    if (preset=='initial' or preset.lower()=='default')\
    and (int(model_management.get_vram())<6000)\
    and (find_preset_file('4GB_Default')):
        preset='4GB_Default'
        args_manager.args.preset = preset
        print('Loading the "4GB_Default" preset, the default for low VRAM systems')
    if not find_preset_file(preset):
        if find_preset_file('Default'):
            preset = 'Default'
        else:
            print('Could not find the startup preset')
            preset = get_random_preset()
            if not preset:
                print('Could not find any presets')
                preset = 'initial'
    json_content = get_preset_content(preset)
    return json_content

def get_preset_foldernames():
    preset_folder = '.\presets'
    preset_foldernames = []
    if os.path.exists(preset_folder):
        preset_foldernames = [f.name for f in os.scandir(preset_folder) if f.is_dir()]
        if not preset_foldernames:
            print(f'Could not find any preset subfolders in {preset_folder}')
            print()
            return preset_foldernames
    else:
        print(f'Could not find the {preset_folder} folder')
        print()    
    preset_foldernames.append('Random')
    return preset_foldernames

def set_category_selection(arg_category_selection):
    global category_selection
    if arg_category_selection == '':
        category_selection = 'Favorite'
    category_selection = arg_category_selection
    return gr.update(value=category_selection)

def preset_count():
    return len(get_preset_paths())   
