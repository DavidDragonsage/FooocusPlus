import os
import copy
import json
import numbers
import random
import re
import gradio as gr
from pathlib import Path

import common
import enhanced.gallery as gallery_util
import enhanced.superprompter as superprompter
import enhanced.comfy_task as comfy_task
import modules.aspect_ratios as AR
import modules.config as config
import modules.constants as constants
import modules.flags
import modules.meta_parser as meta_parser
import modules.preset_resource as PR
import modules.sdxl_styles
import modules.sdxl_styles as sdxl_styles
import modules.style_sorter as style_sorter
import modules.util as util

from args_manager import args
from enhanced.backend import comfyd
from enhanced.translator import interpret
from enhanced.version import announce_version
from enhanced.welcome import get_welcome_image
from modules.preset_support import parse_meta_from_preset
from modules.model_loader import load_file_from_url


# app context
nav_name_list = ''
system_message = ''
config_ext = {}
enhanced_config = os.path.abspath(f'./enhanced/config.json')
if os.path.exists(enhanced_config):
    with open(enhanced_config, "r", encoding="utf-8") as json_file:
        config_ext.update(json.load(json_file))
else:
    config_ext.update({'fooocus_line': '# 2.1.852'})


def get_system_message():
    global config_ext
    fooocus_log = os.path.abspath(f'./fooocusplus_log.md')
    update_msg_f = ''
    first_line_f = None
    if os.path.exists(fooocus_log):
        with open(fooocus_log, "r", encoding="utf-8") as log_file:
            line = log_file.readline()
            while line:
                if line == '\n':
                    line = log_file.readline()
                    continue
                if line.startswith("# ") and first_line_f is None:
                    first_line_f = line.strip()
                if line.strip() == config_ext['fooocus_line']:
                    break
                if first_line_f:
                    update_msg_f += line
                line = log_file.readline()
    update_msg_f = update_msg_f.replace("\n","  ")

    f_log_path = os.path.abspath("./fooocusplus_log.md")
    if len(update_msg_f)>0:
        body_f = f'<b id="update_f">[FooocusPlus]</b>: {update_msg_f}<a href="file={f_log_path}">>></a>   '
    else:
        body_f = '<b id="update_f"> </b>'
    import mistune
    body = mistune.html(body_f)
    if first_line_f and (first_line_f != config_ext['fooocus_line']):
        config_ext['fooocus_line']=first_line_f
        with open(enhanced_config, "w", encoding="utf-8") as config_file:
            json.dump(config_ext, config_file)
    return body if body else ''

def preset_no_instruction():
    head = "<div style='max-width:0px; max-height:0px; overflow:hidden'>"
    foot = "</div>"
    body = ''
    return head + body + foot

get_system_params_js = '''
function(system_params) {
    const params = new URLSearchParams(window.location.search);
    const url_params = Object.fromEntries(params);
    if (url_params["__lang"]!=null) {
        lang=url_params["__lang"];
        system_params["__lang"]=lang;
    }
    if (url_params["__theme"]!=null) {
        theme=url_params["__theme"];
        system_params["__theme"]=theme;
    }
    setObserver();
    return system_params;
}
'''

refresh_topbar_status_js = '''
function(system_params) {
    const preset=system_params["__preset"];
    const theme=system_params["__theme"];
    const nav_name_list_str = system_params["__nav_name_list"];
    let nav_name_list = new Array();
    nav_name_list = nav_name_list_str.split(",")
    for (let i=0;i<nav_name_list.length;i++) {
        let item_id = "bar"+i;
        let item_name = nav_name_list[i];
        let nav_item = gradioApp().getElementById(item_id);
        if (nav_item!=null) {
            if (item_name != preset) {
                if (theme == "light") {
                    nav_item.style.color = 'var(--neutral-400)';
                    nav_item.style.background= 'var(--neutral-100)';
                } else {
                    nav_item.style.color = 'var(--neutral-400)';
                    nav_item.style.background= 'var(--neutral-700)';
                }
            } else {
                if (theme == 'light') {
                    nav_item.style.color = 'var(--secondary-700)';
                    nav_item.style.background= 'var(--neutral-300)';
                } else {
                    nav_item.style.color = 'white';
                    nav_item.style.background= 'var(--secondary-600)';
                }
            }
        }
    }
    const message=system_params["__message"];
    if (message!=null && message.length>60) {
        showSysMsg(message, theme);
    }
    let infobox=gradioApp().getElementById("infobox");
    if (infobox!=null) {
        let css = infobox.getAttribute("class")
        if (browser.device.is_mobile && css.indexOf("infobox_mobi")<0)
            infobox.setAttribute("class", css.replace("infobox", "infobox_mobi"));
    }
    webpath = system_params["__webpath"];
    const lang=system_params["__lang"];
    if (lang!=null) {
        set_language(lang);
    }
    return {}
}
'''

def init_nav_bars(state_params, request: gr.Request):
#   print(f'request.headers:{request.headers}')
    if "__lang" not in state_params.keys():
        state_params.update({"__lang": args.language})
    if "__theme" not in state_params.keys():
        state_params.update({"__theme": args.theme})
    if "__preset" not in state_params.keys():
        state_params.update({"__preset": args.preset})
    if "__session" not in state_params.keys() and "cookie" in request.headers.keys():
        cookies = dict([(s.split('=')[0], s.split('=')[1]) for s in request.headers["cookie"].split('; ')])
        if "SESSION" in cookies.keys():
            state_params.update({"__session": cookies["SESSION"]})
    user_agent = request.headers["user-agent"]
    if "__is_mobile" not in state_params.keys():
        state_params.update({"__is_mobile": True if user_agent.find("Mobile")>0 and user_agent.find("AppleWebKit")>0 else False})
    if "__webpath" not in state_params.keys():
        state_params.update({"__webpath": f'file={os.getcwd()}'})
    if "__max_per_page" not in state_params.keys():
        if state_params["__is_mobile"]:
            state_params.update({"__max_per_page": 9})
        else:
            state_params.update({"__max_per_page": 18})
    if "__max_catalog" not in state_params.keys():
        state_params.update({"__max_catalog": config.default_image_catalog_max_number })
    max_per_page = state_params["__max_per_page"]
    max_catalog = state_params["__max_catalog"]
    output_list, finished_nums, finished_pages = gallery_util.refresh_output_list(max_per_page, max_catalog)
    state_params.update({"__output_list": output_list})
    state_params.update({"__finished_nums_pages": f'{finished_nums},{finished_pages}'})
    state_params.update({"infobox_state": 0})
    state_params.update({"note_box_state": ['',0,0]})
    state_params.update({"array_wildcards_mode": ''})
    state_params.update({"wildcard_in_wildcards": 'root'})
    state_params.update({"bar_button": args.preset})
    state_params.update({"init_process": 'finished'})
    results = refresh_nav_bars(state_params)
    file_welcome = get_welcome_image()
    interpret('[UI Support] Welcome image:')
    if file_welcome == '':
        interpret(' Not found!')
    else:
        print(f' {file_welcome}')
    results += [gr.update(value=f'{file_welcome}')]
    results += [gr.update(value=state_params["__theme"])]
    results += [gr.update(choices=state_params["__output_list"], value=None), gr.update(visible=len(state_params["__output_list"])>0, open=False)]
    results += [gr.update(value=False if state_params["__is_mobile"] else config.default_inpaint_advanced_masking_checkbox)]
    preset = args.preset
    preset_url = get_preset_inc_url(preset)
    state_params.update({"__preset_url":preset_url})
    results += [gr.update(visible=True if 'blank.inc.html' not in preset_url else False)]
    if common.version_update < 5:
        announce_version()
    print()
    return results

def get_preset_inc_url(preset_name='blank'):
    preset_name = f'{preset_name}.inc'
    preset_inc_path = os.path.abspath(f'./presets/html/{preset_name}.html')
    blank_inc_path = os.path.abspath(f'./presets/html/blank.inc.html')
    if os.path.exists(preset_inc_path):
        return f'file={preset_inc_path}'
    else:
        return f'file={blank_inc_path}'

def refresh_nav_bars(state_params):
    state_params.update({"__nav_name_list": PR.get_presetnames_in_folder(common.default_bar_category)})
    preset_name_list = PR.get_presetnames_in_folder(common.default_bar_category)
    results = []
    if state_params["__is_mobile"]:
        results += [gr.update(visible=False)]
    else:
        results += [gr.update(visible=True)]
    preset_count = PR.preset_bar_count()
    padded_list = PR.pad_list(preset_name_list, common.preset_bar_length, '')
    for i in range(common.preset_bar_length):
        name = padded_list[i]
        if i < preset_count:
            visible_flag = True
        else:
            visible_flag = False
        results += [gr.update(value=name, visible=visible_flag)]
    return results


def process_before_generation(state_params, backend_params, backfill_prompt, translation_methods, comfyd_active_checkbox):
    if "__nav_name_list" not in state_params.keys():
        state_params.update({"__nav_name_list": PR.get_all_presetnames()})
    superprompter.remove_superprompt()
    remove_tokenizer()
    backend_params.update({
        'backfill_prompt': backfill_prompt,
        'translation_methods': translation_methods,
        'comfyd_active_checkbox': comfyd_active_checkbox,
        'preset': state_params["__preset"],
        })
    # stop_button, skip_button, generate_button, gallery, state_is_generating, index_radio, image_toolbox, prompt_info_box
    results = [gr.update(value=common.current_AR), \
        gr.update(visible=True, interactive=True), \
        gr.update(visible=True, interactive=True), \
        gr.update(visible=False, interactive=False), [], True, \
        gr.update(visible=False, open=False), \
        gr.update(visible=False), gr.update(visible=False)]
    # preset_nums = len(state_params["__nav_name_list"].split(','))
    preset_nums = PR.preset_count()
    results += [gr.update(interactive=False)] * (preset_nums + 6)
    results += [gr.update()] * (preset_nums)
    results += [backend_params]
    state_params["gallery_state"]='preview'
    return results

def process_after_generation(state_params):
    #if "__max_per_page" not in state_params.keys():
    #    state_params.update({"__max_per_page": 18})
    max_per_page = state_params["__max_per_page"]
    max_catalog = state_params["__max_catalog"]
    output_list, finished_nums, finished_pages = gallery_util.refresh_output_list(max_per_page, max_catalog)
    state_params.update({"__output_list": output_list})
    state_params.update({"__finished_nums_pages": f'{finished_nums},{finished_pages}'})
    # generate_button, stop_button, skip_button, state_is_generating
    results = [gr.update(value='Generate', visible=True, interactive=True)] + [gr.update(visible=False, interactive=False), gr.update(visible=False, interactive=False), False]
    # gallery_index, index_radio
    results += [gr.update(choices=state_params["__output_list"], value=None), gr.update(visible=len(state_params["__output_list"])>0, open=False)]
    # prompt, random_button, translator_button, super_prompter, background_theme, image_tools_checkbox, bar0_button, bar1_button, bar2_button, bar3_button, bar4_button, bar5_button, bar6_button, bar7_button, bar8_button
    preset_nums = PR.preset_count()
    results += [gr.update(interactive=True)] * (preset_nums + 6)
    results += [gr.update()] * (preset_nums)

    if len(state_params["__output_list"]) > 0:
        output_index = state_params["__output_list"][0].split('/')[0]
        gallery_util.refresh_images_catalog(output_index, True)
        gallery_util.parse_html_log(output_index, True)
    return results


def sync_message(state_params):
    state_params.update({"__message":system_message})
    return state_params

preset_down_note_info = 'Loading model files...'

def down_absent_model(state_params):
    state_params.update({'bar_button': state_params["bar_button"].replace('\u2B07', '')})
    return gr.update(visible=False), state_params


def reset_layout_params(prompt, negative_prompt, state_params, is_generating, inpaint_mode, comfyd_active_checkbox):
    global system_message, preset_down_note_info

    state_params.update({"__message": system_message})
    system_message = 'system message was displayed!'
    if '__preset' not in state_params.keys() or 'bar_button' not in state_params.keys() or state_params["__preset"]==state_params['bar_button']:
        return [gr.update()] * (35 + PR.preset_count()) + [state_params] + [gr.update()] * 54
    if '\u2B07' in state_params["bar_button"]:
        gr.Info(preset_down_note_info)
    preset = state_params["bar_button"]
    print()
    interpret('[UI Support] Changed the preset from', state_params["__preset"] + ' → ' + preset)
    state_params.update({"__preset": preset})

    if common.metadata_loading:
        config_preset = common.log_metadata
    else:
        config_preset = PR.get_preset_content(preset, quiet=False)
    preset_prepared = parse_meta_from_preset(config_preset)

    engine = preset_prepared.get('engine', {}).get('backend_engine', 'Fooocus')
    state_params.update({"engine": engine})

    task_method = preset_prepared.get('engine', {}).get('backend_params', modules.flags.get_engine_default_backend_params(engine))
    state_params.update({"task_method": task_method})

    if comfyd_active_checkbox:
        comfyd.stop()

    default_model = preset_prepared.get('base_model')
    previous_default_models = preset_prepared.get('previous_default_models', [])
    checkpoint_downloads = preset_prepared.get('checkpoint_downloads', {})
    embeddings_downloads = preset_prepared.get('embeddings_downloads', {})
    lora_downloads = preset_prepared.get('lora_downloads', {})
    vae_downloads = preset_prepared.get('vae_downloads', {})

    state_params.update({"__prompt": prompt})
    state_params.update({"__negative_prompt": negative_prompt})

    model_dtype = preset_prepared.get('engine', {}).get('backend_params', {}).get('base_model_dtype', '')

    download_models(default_model, previous_default_models, checkpoint_downloads, embeddings_downloads, lora_downloads, vae_downloads)

    preset_url = preset_prepared.get('reference', get_preset_inc_url(preset))
    state_params.update({"__preset_url":preset_url})
    results = refresh_nav_bars(state_params)
    results += meta_parser.switch_layout_template(preset_prepared, state_params, preset_url)
    results += meta_parser.load_parameters(preset_prepared, is_generating, inpaint_mode)
    return results


def download_models(default_model, previous_default_models, checkpoint_downloads, embeddings_downloads, lora_downloads, vae_downloads):
    if args.disable_preset_download:
        interpret('[UI Support] Skipped model download')
        return default_model, checkpoint_downloads

    if not args.always_download_new_model:
        if not os.path.isfile(common.MODELS_INFO.get_file_path_by_name('checkpoints', default_model)):
            for alternative_model_name in previous_default_models:
                if os.path.isfile(common.MODELS_INFO.get_file_path_by_name('checkpoints', alternative_model_name)):
                    interpret(f'[UI Support] You do not have [{default_model}] but you have [{alternative_model_name}].')
                    interpret(f'FooocusPlus will use [{alternative_model_name}] to avoid downloading new models.')
                    interpret('Use --always-download-new-model to avoid fallback and always get new models.')
                    checkpoint_downloads = {}
                    default_model = alternative_model_name
                    break

    for file_name, url in checkpoint_downloads.items():
        model_dir = os.path.dirname(common.MODELS_INFO.get_file_path_by_name('checkpoints', file_name))
        load_file_from_url(url=url, model_dir=model_dir, file_name=os.path.basename(file_name))
    for file_name, url in embeddings_downloads.items():
        load_file_from_url(url=url, model_dir=config.path_embeddings, file_name=file_name)
    for file_name, url in lora_downloads.items():
        model_dir = os.path.dirname(common.MODELS_INFO.get_file_path_by_name('loras', file_name))
        load_file_from_url(url=url, model_dir=model_dir, file_name=os.path.basename(file_name))
    for file_name, url in vae_downloads.items():
        load_file_from_url(url=url, model_dir=config.path_vae, file_name=file_name)
    return default_model, checkpoint_downloads


from transformers import CLIPTokenizer

config_clip_path = Path(config.path_clip_vision)
cur_clip_path = Path(config_clip_path/'clip-vit-large-patch14').resolve()
if cur_clip_path.exists():
    tokenizer = CLIPTokenizer.from_pretrained(cur_clip_path)
else:
    interpret('[UI Support] Cannot load the tokenizer from', cur_clip_path)
    print()

def remove_tokenizer():
    global tokenizer
    if 'tokenizer' in globals():
        del tokenizer
    return

def prompt_token_prediction(text, style_selections):
    global tokenizer, cur_clip_path
    common.positive = text  # save the prompt for preset_resource & meta_parser
    if 'tokenizer' not in globals():
        globals()['tokenizer'] = None
    if tokenizer is None:
        tokenizer = CLIPTokenizer.from_pretrained(cur_clip_path)
    return len(tokenizer.tokenize(text))

    from extras.expansion import safe_str
    from modules.util import remove_empty_str
    import enhanced.translator as translator
    import enhanced.enhanced_parameters as enhanced_parameters
    import enhanced.wildcards as wildcards
    from modules.sdxl_styles import apply_style, fooocus_expansion

    prompt = translator.translate(text, True)
    common.positive = prompt  # save the prompt for preset_resource & meta_parser
    return len(tokenizer.tokenize(prompt))

    print('[UI Support] TERRA INCOGNITA - Here be Dragons')
    print()
    if fooocus_expansion in style_selections:
        use_expansion = True
        style_selections.remove(fooocus_expansion)
    else:
        use_expansion = False

    use_style = len(style_selections) > 0
    prompts = remove_empty_str([safe_str(p) for p in prompt.splitlines()], default='')

    prompt = prompts[0]
    if prompt != '':
        common.positive = prompt
    if negative_prompt != '':
        common.negative = negative_prompt

    extra_positive_prompts = prompts[1:] if len(prompts) > 1 else []
    task_rng = random.Random(random.randint(constants.MIN_SEED, constants.MAX_SEED))
#    prompt, wildcards_arrays, arrays_mult, seed_fixed = wildcards.compile_arrays(prompt, task_rng)
#    task_prompt = wildcards.apply_arrays(prompt, 0, wildcards_arrays, arrays_mult)
    task_prompt = wildcards.replace_wildcard(task_prompt, task_rng)
    task_extra_positive_prompts = [wildcards.apply_wildcards(pmt, task_rng) for pmt in extra_positive_prompts]
    positive_basic_workloads = []
    use_style = False
    if use_style:
        for s in style_selections:
            p, n = apply_style(s, positive=task_prompt)
            positive_basic_workloads = positive_basic_workloads + p
    else:
        positive_basic_workloads.append(task_prompt)
    positive_basic_workloads = positive_basic_workloads + task_extra_positive_prompts
    positive_basic_workloads = remove_empty_str(positive_basic_workloads, default=task_prompt)
    #print(f'positive_basic_workloads:{positive_basic_workloads}')
    return len(tokenizer.tokenize(positive_basic_workloads[0]))


nav_name_list = PR.get_all_presetnames()
system_message = get_system_message()
