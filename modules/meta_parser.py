import os
import gradio as gr
import json
import re
import time

from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image

import common
import args_manager as args
import enhanced.gallery as gallery
import enhanced.version
import modules.aspect_ratios as AR
import modules.config as config
import modules.loader as loader
import modules.preset_resource as PR
import modules.sdxl_styles
import modules.user_structure as US

from enhanced.translator import interpret, interpret_warn
from modules.flags import MetadataScheme, Performance, Steps, task_class_mapping, get_taskclass_by_fullname
from modules.flags import default_class_params, scheduler_list, sampler_list, SAMPLERS, CIVITAI_NO_KARRAS
from modules.preset_support import normalize_AR, parse_meta_from_preset, verify_sampler, verify_scheduler
from modules.util import quote, unquote, extract_styles_from_prompt, is_json, sha256
from modules.hash_cache import sha256_from_cache

re_param_code = r'\s*(\w[\w \-/]+):\s*("(?:\\.|[^\\"])+"|[^,]*)(?:,|$)'
re_param = re.compile(re_param_code)
re_imagesize = re.compile(r"^(\d+)x(\d+)$")

get_layout_visible_inter = lambda x,y,z:gr.update(visible=x not in y, interactive=x not in z)
get_layout_toggle_visible_inter = lambda x,y,z: gr.update(visible=x not in y, interactive=x not in z) if x not in z else gr.update(value=x not in z, visible=x not in y, interactive=x not in z)
get_layout_choices_visible_inter = lambda l,x,y,z:gr.update(choices=l, visible=x not in y, interactive=x not in z)
get_layout_empty_visible_inter = lambda x,y,z: gr.update(visible=x not in y, interactive=x not in z) if x not in z else gr.update(value='', visible=x not in y, interactive=x not in z)


def get_layout_visible_inter_loras(y,z,max_number):
    x = 'loras'
    y1 = max_number if x in y else -1
    for key in y:
        if '-' in key and x==key.split('-')[0]:
            y1 = int(key.split('-')[1])
            break
    z1 = max_number if x in z else -1
    for key in z:
        if '-' in key and x==key.split('-')[0]:
            z1 = int(key.split('-')[1])
            break
    results = []
    for i in range(max_number):
        results += [gr.update(visible= i+y1<max_number or y1<0, interactive= i+z1<max_number or z1<0)] * 3
    return results


def switch_layout_template(presetdata: dict | str, state_params, preset_url=''):
    presetdata_dict = US.verify_dictionary(presetdata)
    enginedata_dict = presetdata_dict.get('engine', {})

    # Resolve the engine name from
    # any possible metadata field:
    raw_engine = presetdata_dict.get('Backend Engine',
                 presetdata_dict.get('backend_engine',
                 task_class_mapping.get(enginedata_dict.get('backend_engine', 'Fooocus'))))

    template_engine = get_taskclass_by_fullname(raw_engine)

    # Safety: If resolution failed,
    # default to Fooocus to prevent KeyError
    if template_engine is None:
        template_engine = 'Fooocus'

    default_params = default_class_params[template_engine]
    visible = enginedata_dict.get('disvisible', default_params.get('disvisible', default_class_params['Fooocus']['disvisible']))
    inter = enginedata_dict.get('disinteractive', default_params.get('disinteractive', default_class_params['Fooocus']['disinteractive']))
    sampler_list = enginedata_dict.get('available_sampler_name', default_params.get('available_sampler_name', default_class_params['Fooocus']['available_sampler_name']))
    scheduler_list = enginedata_dict.get('available_scheduler_name', default_params.get('available_scheduler_name', default_class_params['Fooocus']['available_scheduler_name']))

    params_backend  = enginedata_dict.get('backend_params', modules.flags.get_engine_default_backend_params(template_engine))
    params_backend.update({'backend_engine': template_engine})

    # Safe Fallback: Check both 'task_method' and
    # 'workflow' before falling back to backend defaults
    task_method = presetdata_dict.get('task_method',
                  presetdata_dict.get('workflow',
                  presetdata_dict.get('Workflow',
                  params_backend.get('task_method', None))))
    params_backend['task_method'] = task_method

    base_model_list = loader.get_base_model_list(template_engine, task_method)

    results = [params_backend]
    results.append(get_layout_visible_inter('performance_selection', visible, inter))
    results.append(get_layout_choices_visible_inter(sampler_list, 'sampler_name', visible, inter))
    results.append(get_layout_choices_visible_inter(scheduler_list, 'scheduler_name', visible, inter))
    results.append(get_layout_toggle_visible_inter('input_image_checkbox', visible, inter))
    results.append(get_layout_toggle_visible_inter('enhance_checkbox', visible, inter))
    results.append(get_layout_choices_visible_inter(base_model_list, 'base_model', visible, inter))
    results.append(get_layout_visible_inter('refiner_model', visible, inter))
    results.append(get_layout_visible_inter('overwrite_step', visible, inter))
    results.append(get_layout_visible_inter('guidance_scale', visible, inter))

    results.append(get_layout_visible_inter('sharpness', visible, inter))
    results.append(get_layout_empty_visible_inter('negative_prompt', visible, inter))

    # Force the obsolete help iFrame to remain hidden.
    # This prevents layout shifting
    results.append(gr.update(visible=False))

    results += get_layout_visible_inter_loras(visible, inter, config.default_max_lora_number)
    #for i in range(config.default_max_lora_number):
    #    results += [get_layout_visible_inter('loras', visible, inter)] * 3

    #[output_format, inpaint_advanced_masking_checkbox, mixing_image_prompt_and_vary_upscale, mixing_image_prompt_and_inpaint, backfill_prompt, input_image_checkbox, state_topbar]
    # if default_X in config_preset then update the value to gr.X else update with default value in config
    update_value_if_existed = lambda x: gr.update() if x not in presetdata_dict else presetdata_dict[x]
    results.append(update_value_if_existed("output_format"))
    results.append(update_value_if_existed("inpaint_advanced_masking_checkbox"))
    results.append(update_value_if_existed("mixing_image_prompt_and_vary_upscale"))
    results.append(update_value_if_existed("mixing_image_prompt_and_inpaint"))
    results.append(update_value_if_existed("backfill_prompt"))
    results.append(update_value_if_existed("translation_methods"))
    results.append(False if template_engine not in ['Fooocus', 'Comfy'] else update_value_if_existed("input_image_checkbox"))
    if 'image_catalog_max_number' in presetdata_dict:
        state_params.update({'__max_catalog': presetdata_dict['image_catalog_max_number']})
    results.append(state_params)

    return results


def get_sharpness(key: str, fallback: str | None, source_dict: dict, results: list, default=None) -> None:
    """
    Modular helper to parse the sharpness parameter and dynamically manage
    its UI visibility based on whether the active engine is Comfy-based.
    Supports both dynamic preset changes and raw log metadata imports.
    """
    try:
        # 1. Attempt to extract and convert the sharpness value
        h = source_dict.get(key, source_dict.get(fallback, default))
        assert h is not None
        h = float(h)

        # 2. Determine Comfy mode using the global common state
        is_comfy = bool(common.default_engine)

        # 3. Fallback: If global is empty, inspect the local metadata dictionary (critical for log loads)
        if not is_comfy:
            engine_name = source_dict.get('Backend Engine', source_dict.get('backend_engine'))
            if not engine_name and 'engine' in source_dict:
                engine_name = source_dict['engine'].get('backend_engine')

            if engine_name:
                is_comfy = engine_name not in ['Fooocus', 'SDXL-Fooocus']

        # 4. Append the visibility-aware update to results
        results.append(gr.update(value=h, visible=not is_comfy))
    except Exception:
        # Fallback block: Manage visibility even if the value is missing
        is_comfy = bool(common.default_engine)
        if not is_comfy:
            engine_name = source_dict.get('Backend Engine', source_dict.get('backend_engine'))
            if not engine_name and 'engine' in source_dict:
                engine_name = source_dict['engine'].get('backend_engine')
            if engine_name:
                is_comfy = engine_name not in ['Fooocus', 'SDXL-Fooocus']

        results.append(gr.update(visible=not is_comfy))

    return


def process_dictionary(loaded_parameter_dict, is_generating, inpaint_mode, results):

    # Ensure all variant substyle keys
    # map to the internal v2_substyle
    for key in ['substyle', 'Substyle']:
        if key in loaded_parameter_dict:
            loaded_parameter_dict['v2_substyle'] = loaded_parameter_dict.pop(key)

    # Dynamic extension resolver:
    # Match the stem against the real files on disk
    # Wrapped in a try/except block with local
    # imports to prevent any silent NameErrors
    try:
        # Dynamically resolve model filename extensions
        # (.pth, .ckpt, .bin, .safetensors, .fooocus.patch, .gguf)
        valid_extensions = ['.pth', '.ckpt', '.bin', '.safetensors', '.fooocus.patch', '.gguf']
        for model_key in ['base_model', 'Base Model', 'refiner_model', 'Refiner Model']:
            if model_key in loaded_parameter_dict:
                val = loaded_parameter_dict[model_key]
                if isinstance(val, str) and val != 'None' and not any(val.lower().endswith(ext) for ext in valid_extensions):
                    for filename in getattr(loader, 'model_filenames', []):
                        if Path(filename).stem == val:
                            loaded_parameter_dict[model_key] = filename
                            break
    except Exception as e:
        print(f"[MetaParser] Model resolution bypassed: {e}")

    get_image_quantity('image_quantity', 'Image Quantity', loaded_parameter_dict, results)

    prompt_str = get_str('prompt', 'Prompt', loaded_parameter_dict, results)
    get_str('negative_prompt', 'Negative Prompt', loaded_parameter_dict, results)

    get_list('styles', 'Styles', loaded_parameter_dict, results)
    get_str('v2_substyle', 'Substyle', loaded_parameter_dict, results)

    performance = get_str('performance', 'Performance', loaded_parameter_dict, results)
    get_steps('steps', 'Steps', loaded_parameter_dict, results)
    get_number('overwrite_switch', 'Overwrite Switch', loaded_parameter_dict, results)
    get_resolution('resolution', 'Resolution', loaded_parameter_dict, results)
    arg_resolution = ''
    if loaded_parameter_dict.get("resolution"):
        arg_resolution = loaded_parameter_dict.get("resolution")
    elif loaded_parameter_dict.get("Resolution"):
        arg_resolution = loaded_parameter_dict.get("Resolution")
    if arg_resolution:
        arg_resolution = normalize_AR(arg_resolution)
        if arg_resolution != '0*0' and not ',' in arg_resolution:
            common.resolution = arg_resolution
            interpret('[MetaParser] Resolution set by preset or metadata:', arg_resolution)
    get_number('guidance_scale', 'Guidance Scale', loaded_parameter_dict, results)

    get_sharpness('sharpness', 'Sharpness', loaded_parameter_dict, results)

    get_adm_guidance('adm_guidance', 'ADM Guidance', loaded_parameter_dict, results)
    get_str('refiner_swap_method', 'Refiner Swap Method', loaded_parameter_dict, results)
    get_number('adaptive_cfg', 'CFG Mimicking from TSNR', loaded_parameter_dict, results)
    get_number('clip_skip', 'CLIP Skip', loaded_parameter_dict, results, cast_type=int)
    get_str('base_model', 'Base Model', loaded_parameter_dict, results)
    get_str('refiner_model', 'Refiner Model', loaded_parameter_dict, results)
    get_number('refiner_switch', 'Refiner Switch', loaded_parameter_dict, results)
    get_str('sampler', 'Sampler', loaded_parameter_dict, results)
    arg_sampler = loaded_parameter_dict.get("sampler")
    if arg_sampler:
        verify_sampler(arg_sampler)
    get_str('scheduler', 'Scheduler', loaded_parameter_dict, results)
    arg_scheduler = loaded_parameter_dict.get("scheduler")
    if arg_scheduler:
        verify_scheduler(arg_scheduler)
    get_str('vae', 'VAE', loaded_parameter_dict, results)
    get_seed('seed', 'Seed', loaded_parameter_dict, results)
    get_inpaint_engine_version('inpaint_engine_version', 'Inpaint Engine Version', loaded_parameter_dict, results, inpaint_mode)
    get_inpaint_method('inpaint_method', 'Inpaint Mode', loaded_parameter_dict, results)

    if is_generating:
        results.append(gr.update())
    else:
        results.append(gr.update(visible=True))

    results.append(gr.update(visible=False))

    get_freeu('freeu', 'FreeU', loaded_parameter_dict, results)

    # prevent performance LoRAs to be added twice, by performance and by lora
    performance_filename = None
    if performance is not None and performance in Performance.values():
        performance = Performance(performance)
        performance_filename = performance.lora_filename()

    for i in range(config.default_max_lora_number):
        get_lora(f'lora_combined_{i + 1}', f'LoRA {i + 1}', loaded_parameter_dict, results, performance_filename)

    return results


def parse_log_text_to_dict(raw_metadata: str) -> dict:
    """
    Parses raw metadata from clipboard. Handles both
    JSON objects and Multiline 'Key: Value' text logs.
    """
    loaded_parameter_dict = {}
    if not isinstance(raw_metadata, str) or not raw_metadata.strip():
        return loaded_parameter_dict

    clean_input = raw_metadata.strip()

    # 1. Handle JSON Clipboard Content
    if clean_input.startswith("{") and clean_input.endswith("}"):
        try:
            data = json.loads(clean_input)
            if isinstance(data, dict):
                loaded_parameter_dict = data
                # Normalize common metadata keys to internal standards
                if "Workflow" in loaded_parameter_dict:
                    loaded_parameter_dict["task_method"] = loaded_parameter_dict.pop("Workflow")
                if "Preset" in loaded_parameter_dict:
                    loaded_parameter_dict["current_preset"] = loaded_parameter_dict.pop("Preset")
                if "substyle" in loaded_parameter_dict:
                    loaded_parameter_dict["v2_substyle"] = loaded_parameter_dict.pop("substyle")
        except Exception as e:
            print(f'[MetaParser] JSON Parse fallback triggered: {e}')

    # 2. Handle Multiline Text Logs (if not JSON or JSON failed)
    if not loaded_parameter_dict:
        for line in clean_input.split("\n"):
            separator = ":" if ":" in line else "\t" if "\t" in line else None
            if separator:
                key, value = line.split(separator, 1)
                clean_key = key.strip().lower().replace(" ", "_")

                if clean_key == "preset": clean_key = "current_preset"
                if clean_key == "workflow": clean_key = "task_method"
                if clean_key == "fooocus_v2_expansion": clean_key = "prompt_expansion"
                if clean_key == "substyle": clean_key = "v2_substyle"

                loaded_parameter_dict[clean_key] = value.strip()

    # CRITICAL: Always run modernization on the resulting dict to ensure
    # Engine/Workflow technical data is fused from the .json file.
    return PR.modernize_legacy_metadata(loaded_parameter_dict)


# Directly called by load metadata from
# log via clipboard and prompt,
# or from Toolbox Load Log Info.
# Also called indirectly by load metadata from image
def read_meta_from_log(raw_metadata: dict | str, is_generating: bool, inpaint_mode: str):
    if isinstance(raw_metadata, str) and not raw_metadata.strip().startswith("{"):
        loaded_parameter_dict = parse_log_text_to_dict(raw_metadata)
    else:
        loaded_parameter_dict = US.verify_dictionary(raw_metadata)
        # Apply modernization to ensure Fusion data is present
        loaded_parameter_dict = PR.modernize_legacy_metadata(loaded_parameter_dict)

    # --- INTELLIGENT CACHE MANAGEMENT ---
    # Detect if this is a 'Real' update
    # (User loading an image)
    # or a 'Hollow' update (Gradio UI artifacts).
    is_real_update = any(k in loaded_parameter_dict for k in ['prompt', 'Prompt', 'seed', 'Seed'])

    if not common.log_metadata or is_real_update:
        # This is either the first pass
        # or a deliberate switch to a new image.
        # We allow it to overwrite the cache entirely.
        common.log_metadata = loaded_parameter_dict
    else:
        # This is a 'Hollow' middle pass.
        # Perform a defensive merge.
        # Only accept updates that aren't
        # trying to downgrade the engine to Fooocus.
        clean_updates = {}
        for k, v in loaded_parameter_dict.items():
            if v in [None, 'None', '']: continue

            if k in ['backend_engine', 'Backend Engine'] and v in ['Fooocus', 'SDXL-Fooocus']:
                existing = common.log_metadata.get('backend_engine', common.log_metadata.get('Backend Engine'))
                if existing and existing not in ['Fooocus', 'SDXL-Fooocus']:
                    # Block the 'Fooocus' flip during middle-passes
                    continue

            clean_updates[k] = v

        common.log_metadata.update(clean_updates)
        loaded_parameter_dict = common.log_metadata
    # ----------------------------------------

    if not isinstance(loaded_parameter_dict, dict):
        print("Dictionary not valid")
        return [gr.update()]

    results = [True] if len(loaded_parameter_dict) > 0 else [gr.update()]

    if not common.metadata_loading:
        arg_preset = loaded_parameter_dict.get("current_preset", loaded_parameter_dict.get("Preset", ""))
        if arg_preset:
            PR.current_preset = arg_preset
            preset_content = PR.get_preset_content(PR.current_preset, quiet=False)
            parse_meta_from_preset(preset_content)
        PR.category_selection = PR.find_preset_category(PR.current_preset)

    return process_dictionary(loaded_parameter_dict, is_generating, inpaint_mode, results)


def load_parameters(raw_metadata: dict | str, is_generating: bool, inpaint_mode: str):
    loaded_parameter_dict = US.verify_dictionary(raw_metadata)

    results = [True] if len(loaded_parameter_dict) > 0 else [gr.update()]

    results = process_dictionary(loaded_parameter_dict, is_generating, inpaint_mode, results)
    return results


def get_str(key: str, fallback: str | None, source_dict: dict, results: list, default=None) -> str | None:
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        assert isinstance(h, str)
        results.append(h)
        return h
    except:
        results.append(gr.update())
        return None

def get_list(key: str, fallback: str | None, source_dict: dict, results: list, default=None):
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        h = eval(h)
        assert isinstance(h, list)
        results.append(h)
    except:
        results.append(gr.update())
    if key in ['styles', 'Styles']:
        if h:
            for k in h:
                if k and 'styles_definition' in source_dict and k not in modules.sdxl_styles.styles and k in source_dict.get('styles_definition', default):
                    modules.sdxl_styles.styles.update({k: source_dict["styles_definition"][k]})


def get_number(key: str, fallback: str | None, source_dict: dict, results: list, default=None, cast_type=float):
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        assert h is not None
        h = cast_type(h)
        results.append(h)
    except:
        results.append(gr.update())


def get_image_quantity(key: str, fallback: str | None, source_dict: dict, results: list, default=None):
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        assert h is not None
        h = int(h)
        h = min(h, config.default_max_image_quantity)
        m = int(source_dict.get('max_image_quantity', config.default_max_image_quantity))
        results.append(gr.update(value=h, maximum=m))
    except:
        results.append(1)


def get_steps(key: str, fallback: str | None, source_dict: dict, results: list, default=None):
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        assert h is not None
        h = int(h)
        # if not in steps or in steps and performance is not the same
        performance_name = source_dict.get('performance', '').replace(' ', '_').replace('-', '_').casefold()
        performance_candidates = [key for key in Steps.keys() if key.casefold() == performance_name and Steps[key] == h]
        if len(performance_candidates) == 0:
            results.append(h)
            return
        results.append(-1)
    except:
        results.append(-1)


def get_resolution(key: str, fallback: str | None, source_dict: dict, results: list, default=None):
    preset_filename = Path(common.preset_file_path).name
    try:
        width, height = 0, 0
        h = source_dict.get(key, source_dict.get(fallback, default))
        engine = get_taskclass_by_fullname(source_dict.get('Backend Engine',\
                source_dict.get('backend_engine', task_class_mapping['Fooocus'])))
        if 'engine' in source_dict:
            engine = source_dict['engine'].get('backend_engine', engine)
            template = source_dict['engine'].get('available_aspect_ratios_selection',\
                default_class_params[engine].get('available_aspect_ratios_selection',\
                default_class_params['Fooocus']['available_aspect_ratios_selection']))
        else:
            template = default_class_params[engine].get('available_aspect_ratios_selection',\
                default_class_params['Fooocus']['available_aspect_ratios_selection'])

        if preset_filename.startswith('SD1.5') and template!='SD1.5':
            template = 'SD1.5'
            interpret(f'Selected the SD1.5 template for the {common.preset_file_path} file')

        if template == 'Standard' and config.enable_shortlist_aspect_ratios:
            template = 'Shortlist'
        elif template == 'Shortlist' and not config.enable_shortlist_aspect_ratios:
            template = 'Standard'

        if h != '':
            width, height = eval(h)

        if AR.AR_template != template:    # i.e. the template has changed
            common.resolution = AR.validate_AR(common.resolution, template)
            h = ''
        AR.AR_template = template

        if (width == '0') or (height == '0') or (h == ''):
            if common.resolution == '':
                common.resolution = AR.assign_default_by_template(template)
            h = common.resolution
            width, height = AR.AR_split(h)
        common.resolution = h

        formatted = AR.add_ratio(f'{width}*{height}')
        if formatted in common.full_AR_labels[template]:
            h = f'{formatted},{template}'
            results.append(h)
            results.append(-1)
            results.append(-1)
        else:
            results.append(gr.update())
            results.append(int(width))
            results.append(int(height))
    except Exception as e:
        interpret('[MetaParser] The image metadata is not available!')
        results.append(gr.update())
        results.append(gr.update())
        results.append(gr.update())
    return


def get_seed(key: str, fallback: str | None, source_dict: dict, results: list, default=None):
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        assert h is not None
        h = int(h)
        results.append(False)
        results.append(h)
    except:
        results.append(gr.update())
        results.append(gr.update())


def get_inpaint_engine_version(key: str, fallback: str | None, source_dict: dict, results: list, inpaint_mode: str, default=None) -> str | None:
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        assert isinstance(h, str) and h in modules.flags.inpaint_engine_versions
        if inpaint_mode != modules.flags.inpaint_option_detail:
            results.append(h)
        else:
            results.append(gr.update())
        results.append(h)
        return h
    except:
        results.append(gr.update())
        results.append('empty')
        return None


def get_inpaint_method(key: str, fallback: str | None, source_dict: dict, results: list, default=None) -> str | None:
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        assert isinstance(h, str) and h in modules.flags.inpaint_options
        results.append(h)
        for i in range(config.default_enhance_tabs):
            results.append(h)
        return h
    except:
        results.append(gr.update())
        for i in range(config.default_enhance_tabs):
            results.append(gr.update())


def get_adm_guidance(key: str, fallback: str | None, source_dict: dict, results: list, default=None):
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        p, n, e = eval(h)
        results.append(float(p))
        results.append(float(n))
        results.append(float(e))
    except:
        results.append(gr.update())
        results.append(gr.update())
        results.append(gr.update())


def get_freeu(key: str, fallback: str | None, source_dict: dict, results: list, default=None):
    try:
        h = source_dict.get(key, source_dict.get(fallback, default))
        b1, b2, s1, s2 = eval(h)
        results.append(True)
        results.append(float(b1))
        results.append(float(b2))
        results.append(float(s1))
        results.append(float(s2))
    except:
        results.append(False)
        results.append(gr.update())
        results.append(gr.update())
        results.append(gr.update())
        results.append(gr.update())


def get_lora(key: str, fallback: str | None, source_dict: dict, results: list, performance_filename: str | None) -> None:
    try:
        split_data = source_dict.get(key, source_dict.get(fallback)).split(' : ')
        enabled = True
        name = split_data[0]
        weight = split_data[1]

        if len(split_data) == 3:
            enabled = split_data[0] == 'True'
            name = split_data[1]
            weight = split_data[2]

        if name == performance_filename:
            raise Exception
        w_min = float(source_dict.get('loras_min_weight', config.default_loras_min_weight))
        w_max = float(source_dict.get('loras_max_weight', config.default_loras_max_weight))
        weight = float(weight)

        results.append(enabled)

        # --- DYNAMIC CHOICES UPDATE ---
        # Instead of a raw string, we return a gr.update containing the active filtered choices
        results.append(gr.update(choices=['None'] + loader.lora_filenames, value=name))
        # ------------------------------

        results.append(gr.update(value=weight, minimum=w_min, maximum=w_max))
    except Exception:
        results.append(True)
        # Update empty fallback slots with the filtered choices as well
        results.append(gr.update(choices=['None'] + loader.lora_filenames, value='None'))
        results.append(1)

    return


def get_sha256(filepath):
    global hash_cache
    if not os.path.isfile(filepath):
        return ''
    if filepath not in hash_cache:
        filehash = common.MODELS_INFO.get_file_muid(filepath)
        if not filehash:
            filehash = sha256(filepath)
        hash_cache[filepath] = filehash
    return hash_cache[filepath]


class MetadataParser(ABC):
    def __init__(self):
        self.raw_prompt: str = ''
        self.full_prompt: str = ''
        self.raw_negative_prompt: str = ''
        self.full_negative_prompt: str = ''
        self.steps: int = Steps.Speed.value
        self.base_model_name: str = ''
        self.base_model_hash: str = ''
        self.refiner_model_name: str = ''
        self.refiner_model_hash: str = ''
        self.loras: list = []
        self.vae_name: str = ''
        self.styles_definition = {}

    @abstractmethod
    def get_scheme(self) -> MetadataScheme:
        raise NotImplementedError

    @abstractmethod
    def to_json(self, metadata: dict | str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def to_string(self, metadata: dict) -> str:
        raise NotImplementedError

    def set_data(self, raw_prompt, full_prompt,
        raw_negative_prompt, full_negative_prompt,
        steps, base_model_name, refiner_model_name,
        loras, vae_name, styles_definition):
        self.raw_prompt = raw_prompt
        interpret('Metadata raw_prompt:', raw_prompt)
        self.full_prompt = full_prompt
        interpret('Metadata full_prompt:', full_prompt)
        self.raw_negative_prompt = raw_negative_prompt
        self.full_negative_prompt = full_negative_prompt
        self.steps = steps
        self.base_model_name = Path(base_model_name).stem

        if base_model_name not in ['', 'None']:
            base_model_path = common.MODELS_INFO.get_model_filepath('checkpoints', base_model_name)
            self.base_model_hash = common.MODELS_INFO.get_file_muid(base_model_path)

        if refiner_model_name not in ['', 'None']:
            self.refiner_model_name = Path(refiner_model_name).stem
            refiner_model_path = common.MODELS_INFO.get_model_filepath('checkpoints', refiner_model_name)
            self.refiner_model_hash = common.MODELS_INFO.get_file_muid(refiner_model_path)

        self.loras = []
        for (lora_name, lora_weight) in loras:
            if lora_name != 'None':
                lora_path = common.MODELS_INFO.get_model_filepath('loras', lora_name)
                lora_hash = common.MODELS_INFO.get_file_muid(lora_path)
                self.loras.append((Path(lora_name).stem, lora_weight, lora_hash))
        self.vae_name = Path(vae_name).stem
        if styles_definition != 'None':
            self.styles_definition = styles_definition


class A1111MetadataParser(MetadataParser):
    def get_scheme(self) -> MetadataScheme:
        return MetadataScheme.A1111

    fooocus_to_a1111 = {
        'raw_prompt': 'Raw prompt',
        'raw_negative_prompt': 'Raw negative prompt',
        'negative_prompt': 'Negative prompt',
        'styles': 'Styles',
        'performance': 'Performance',
        'steps': 'Steps',
        'sampler': 'Sampler',
        'scheduler': 'Scheduler',
        'vae': 'VAE',
        'guidance_scale': 'CFG scale',
        'seed': 'Seed',
        'resolution': 'Size',
        'sharpness': 'Sharpness',
        'adm_guidance': 'ADM Guidance',
        'refiner_swap_method': 'Refiner Swap Method',
        'adaptive_cfg': 'Adaptive CFG',
        'clip_skip': 'Clip skip',
        'overwrite_switch': 'Overwrite Switch',
        'freeu': 'FreeU',
        'base_model': 'Model',
        'base_model_hash': 'Model hash',
        'refiner_model': 'Refiner',
        'refiner_model_hash': 'Refiner hash',
        'lora_hashes': 'Lora hashes',
        'lora_weights': 'Lora weights',
        'created_by': 'User',
        'version': 'Version',
        'backend_engine': 'Backend Engine'
    }

    def to_json(self, metadata: str) -> dict:
        metadata_prompt = ''
        metadata_negative_prompt = ''

        done_with_prompt = False

        *lines, lastline = metadata.strip().split("\n")
        if len(re_param.findall(lastline)) < 3:
            lines.append(lastline)
            lastline = ''

        for line in lines:
            line = line.strip()
            if line.startswith(f"{self.fooocus_to_a1111['negative_prompt']}:"):
                done_with_prompt = True
                line = line[len(f"{self.fooocus_to_a1111['negative_prompt']}:"):].strip()
            if done_with_prompt:
                metadata_negative_prompt += ('' if metadata_negative_prompt == '' else "\n") + line
            else:
                metadata_prompt += ('' if metadata_prompt == '' else "\n") + line

        found_styles, prompt, negative_prompt = extract_styles_from_prompt(metadata_prompt, metadata_negative_prompt)

        data = {
            'prompt': prompt,
            'negative_prompt': negative_prompt
        }

        for k, v in re_param.findall(lastline):
            try:
                if v != '' and v[0] == '"' and v[-1] == '"':
                    v = unquote(v)

                m = re_imagesize.match(v)
                if m is not None:
                    data['resolution'] = str((m.group(1), m.group(2)))
                else:
                    data[list(self.fooocus_to_a1111.keys())[list(self.fooocus_to_a1111.values()).index(k)]] = v
            except Exception:
                print(f"Error parsing \"{k}: {v}\"")

        # workaround for multiline prompts
        if 'raw_prompt' in data:
            data['prompt'] = data['raw_prompt']
            raw_prompt = data['raw_prompt'].replace("\n", ', ')
            if metadata_prompt != raw_prompt and modules.sdxl_styles.fooocus_expansion not in found_styles:
                found_styles.append(modules.sdxl_styles.fooocus_expansion)

        if 'raw_negative_prompt' in data:
            data['negative_prompt'] = data['raw_negative_prompt']

        data['styles'] = str(found_styles)

        # try to load performance based on steps, fallback for direct A1111 imports
        if 'steps' in data and 'performance' in data is None:
            try:
                data['performance'] = Performance.by_steps(data['steps']).value
            except ValueError | KeyError:
                pass

        if 'sampler' in data:
            data['sampler'] = data['sampler'].replace(' Karras', '')
            # get key
            for k, v in SAMPLERS.items():
                if v == data['sampler']:
                    data['sampler'] = k
                    break

        for key in ['base_model', 'refiner_model', 'vae']:
            if key in data:
                if key == 'vae':
                    self.add_extension_to_filename(data, loader.vae_filenames, 'vae')
                else:
                    self.add_extension_to_filename(data, loader.model_filenames, key)

        lora_data = ''
        if 'lora_weights' in data and data['lora_weights'] != '':
            lora_data = data['lora_weights']
        elif 'lora_hashes' in data and data['lora_hashes'] != '' and data['lora_hashes'].split(', ')[0].count(':') == 2:
            lora_data = data['lora_hashes']

        if lora_data != '':
            for li, lora in enumerate(lora_data.split(', ')):
                lora_split = lora.split(': ')
                lora_name = lora_split[0]
                lora_weight = lora_split[2] if len(lora_split) == 3 else lora_split[1]
                for filename in loader.lora_filenames:
                    path = Path(filename)
                    if lora_name == path.stem:
                        data[f'lora_combined_{li + 1}'] = f'{filename} : {lora_weight}'
                        break

        return data

    def to_string(self, metadata: dict) -> str:
        data = {k: v for _, k, v in metadata}

        width, height = eval(data['resolution'])

        sampler = data['sampler']
        scheduler = data['scheduler']

        if sampler in SAMPLERS and SAMPLERS[sampler] != '':
            sampler = SAMPLERS[sampler]
            if sampler not in CIVITAI_NO_KARRAS and scheduler == 'karras':
                sampler += f' Karras'

        generation_params = {
            self.fooocus_to_a1111['steps']: self.steps,
            self.fooocus_to_a1111['sampler']: sampler,
            self.fooocus_to_a1111['seed']: data['seed'],
            self.fooocus_to_a1111['resolution']: f'{width}x{height}',
            self.fooocus_to_a1111['guidance_scale']: data['guidance_scale'],
            self.fooocus_to_a1111['sharpness']: data['sharpness'],
            self.fooocus_to_a1111['adm_guidance']: data['adm_guidance'],
            self.fooocus_to_a1111['base_model']: Path(data['base_model']).stem,
            self.fooocus_to_a1111['base_model_hash']: self.base_model_hash,

            self.fooocus_to_a1111['performance']: data['performance'],
            self.fooocus_to_a1111['scheduler']: scheduler,
            self.fooocus_to_a1111['vae']: Path(data['vae']).stem,
            # workaround for multiline prompts
            self.fooocus_to_a1111['raw_prompt']: self.raw_prompt,
            self.fooocus_to_a1111['raw_negative_prompt']: self.raw_negative_prompt,
        }

        if self.refiner_model_name not in ['', 'None']:
            generation_params |= {
                self.fooocus_to_a1111['refiner_model']: self.refiner_model_name,
                self.fooocus_to_a1111['refiner_model_hash']: self.refiner_model_hash
            }

        for key in ['adaptive_cfg', 'clip_skip', 'overwrite_switch', 'refiner_swap_method', 'freeu']:
            if key in data:
                generation_params[self.fooocus_to_a1111[key]] = data[key]

        if len(self.loras) > 0:
            lora_hashes = []
            lora_weights = []
            for index, (lora_name, lora_weight, lora_hash) in enumerate(self.loras):
                # workaround for Fooocus not knowing LoRA name in LoRA metadata
                lora_hashes.append(f'{lora_name}: {lora_hash}')
                lora_weights.append(f'{lora_name}: {lora_weight}')
            lora_hashes_string = ', '.join(lora_hashes)
            lora_weights_string = ', '.join(lora_weights)
            generation_params[self.fooocus_to_a1111['lora_hashes']] = lora_hashes_string
            generation_params[self.fooocus_to_a1111['lora_weights']] = lora_weights_string

        generation_params[self.fooocus_to_a1111['version']] = data['version']

        if config.metadata_created_by != '':
            generation_params[self.fooocus_to_a1111['created_by']] = config.metadata_created_by

        generation_params_text = ", ".join(
            [k if k == v else f'{k}: {quote(v)}' for k, v in generation_params.items() if
             v is not None])
        positive_prompt_resolved = ', '.join(self.full_prompt)
        negative_prompt_resolved = ', '.join(self.full_negative_prompt)
        negative_prompt_text = f"\nNegative prompt: {negative_prompt_resolved}" if negative_prompt_resolved else ""
        return f"{positive_prompt_resolved}{negative_prompt_text}\n{generation_params_text}".strip()

    @staticmethod
    def add_extension_to_filename(data, filenames, key):
        for filename in filenames:
            path = Path(filename)
            if data[key] == path.stem:
                data[key] = filename
                break


class FooocusMetadataParser(MetadataParser):
    def get_scheme(self) -> MetadataScheme:
        return MetadataScheme.FOOOCUS

    def to_json(self, metadata: dict) -> dict:

        for key, value in metadata.items():
            if value in ['', 'None']:
                continue
            if key in ['base_model', 'refiner_model']:
                metadata[key] = self.replace_value_with_filename(key, value, loader.model_filenames)
            elif key.startswith('lora_combined_'):
                metadata[key] = self.replace_value_with_filename(key, value, loader.lora_filenames)
            elif key == 'vae':
                metadata[key] = self.replace_value_with_filename(key, value, loader.vae_filenames)
            else:
                continue

        return metadata

    def to_string(self, metadata: list) -> str:
        for li, (label, key, value) in enumerate(metadata):
            # remove model folder paths from metadata
            if key.startswith('lora_combined_'):
                name, weight = value.split(' : ')
                name = Path(name).stem
                value = f'{name} : {weight}'
                metadata[li] = (label, key, value)

        res = {k: v for _, k, v in metadata}

        res['full_prompt'] = self.full_prompt
        res['full_negative_prompt'] = self.full_negative_prompt
        res['steps'] = self.steps
        res['base_model'] = self.base_model_name
        res['base_model_hash'] = self.base_model_hash

        if self.refiner_model_name not in ['', 'None']:
            res['refiner_model'] = self.refiner_model_name
            res['refiner_model_hash'] = self.refiner_model_hash

        res['vae'] = self.vae_name
        res['loras'] = self.loras

        if res['Metadata Scheme'].lower() == 'simple':
            res['Metadata Scheme'] = 'Fooocus'

        if config.metadata_created_by != '':
            res['created_by'] = config.metadata_created_by

        return json.dumps(dict(sorted(res.items())))

    @staticmethod
    def replace_value_with_filename(key, value, filenames):
        if not value or value == 'None': return 'None'
        if key in ['vae', 'VAE'] and value == 'Default (model)': return value

        # Handle LoRA format: "True : lora_name : 1.0"
        if key.startswith('LoRA '):
            try:
                parts = value.split(' : ')
                name = parts[1] if len(parts) == 3 else parts[0]
                weight_suffix = f" : {parts[2]}" if len(parts) == 3 else f" : {parts[1]}"
                enabled_prefix = f"{parts[0]} : " if len(parts) == 3 else ""

                for filename in filenames:
                    if Path(name).stem == Path(filename).stem or name == filename:
                        return f"{enabled_prefix}{filename}{weight_suffix}"
                return 'None'
            except:
                return 'None'

        # Handle Standard Models
        for filename in filenames:
            # Check if the stems match (e.g., 'model' == 'SDXL/model.safetensors')
            if Path(value).stem == Path(filename).stem or value == filename:
                return filename

        return 'None'


class SIMPLEMetadataParser(MetadataParser):
    def get_scheme(self) -> MetadataScheme:
        return MetadataScheme.SIMPLE

    def to_json(self, metadata: dict) -> dict:
        def safe_get(d, keys, default=None):
            if not isinstance(d, dict): return default
            for k in keys:
                val = d.get(k)
                if val and str(val) not in [None, 'None', '', 'NoneType']:
                    return val
            return default

        # Resolve Engine and Workflow keys
        task_method_val = safe_get(metadata, ['task_method', 'Workflow'])
        if not task_method_val:
            task_method_val = metadata.get('default_engine', {}).get('backend_params', {}).get('task_method')

        engine_name = safe_get(metadata, ['backend_engine', 'Backend Engine'])
        if not engine_name:
             engine_name = metadata.get('default_engine', {}).get('backend_engine', 'Fooocus')

        engine = get_taskclass_by_fullname(engine_name)
        metadata['backend_engine'] = engine_name
        metadata['task_method'] = task_method_val

        # Find 'CLIP Skip' or 'clip_skip'
        clip_skip = safe_get(metadata, ['clip_skip', 'CLIP Skip'])

        # Fallback: to 2 SDXL standard
        if clip_skip is None:
            clip_skip = config.default_clip_skip

        # If found, ensure it is an integer
        # for the Gradio Slider
        if clip_skip is not None:
            try:
                metadata['clip_skip'] = int(float(clip_skip))
            except:
                metadata['clip_skip'] = 2

        # fetch the lists required to turn
        # stems back into full paths
        model_filenames = loader.get_base_model_list(engine, task_method_val, for_import=True)
        lora_filenames = loader.get_lora_model_list(engine, task_method_val, for_import=True)
        vae_filenames = loader.vae_filenames

        for key in list(metadata.keys()):
            val = metadata[key]
            if val in ['', 'None', None]: continue

            if key in ['Base Model', 'base_model']:
                resolved = self.replace_value_with_filename(key, val, model_filenames)
                metadata['base_model'] = resolved if resolved != 'None' else val

            elif key in ['Refiner Model', 'refiner_model']:
                resolved = self.replace_value_with_filename(key, val, model_filenames)
                metadata['refiner_model'] = resolved if resolved != 'None' else val

            elif key.startswith('LoRA '):
                resolved = self.replace_value_with_filename(key, val, lora_filenames)
                metadata[key] = resolved if resolved != 'None' else val

            elif key in ['VAE', 'vae']:
                resolved = self.replace_value_with_filename(key, val, vae_filenames)
                metadata['vae'] = resolved if resolved != 'None' else val

        return metadata


    def to_string(self, metadata: list) -> str:
        for li, (label, key, value) in enumerate(metadata):
            # remove model folder paths from metadata
            if key.startswith('lora_combined_'):
                name, weight = value.split(' : ')
                name = Path(name).stem
                value = f'{name} : {weight}'
                metadata[li] = (label, key, value)

        res = {k: v for k, _, v in metadata}

        res['Full Prompt'] = self.full_prompt
        res['Full Negative Prompt'] = self.full_negative_prompt
        res['Steps'] = self.steps
        res['Base Model'] = self.base_model_name
        res['Base Model Hash'] = self.base_model_hash

        if res['Metadata Scheme'] == MetadataScheme.SIMPLE.value:
            res['Metadata Scheme'] = 'Fooocus'

        if self.refiner_model_name not in ['', 'None']:
            res['Refiner Model'] = self.refiner_model_name
            res['Refiner Model Hash'] = self.refiner_model_hash

        res['VAE'] = self.vae_name
        res['LoRAs'] = self.loras
        res['styles_definition'] = self.styles_definition

        if config.metadata_created_by != '':
            res['User'] = config.metadata_created_by

        return json.dumps(dict(sorted(res.items())))

    @staticmethod
    def replace_value_with_filename(key, value, filenames):
        if key in ['vae', 'VAE'] and value=='Default (model)':
            return value
        for filename in filenames:
            path = Path(filename)
            if key.startswith('LoRA '):
                name, weight = value.split(' : ')
                if Path(name).stem == path.stem or name == path.stem:
                    return f'{filename} : {weight}'
            elif Path(value).stem == path.stem or value == path.stem:
                return filename
        return 'None'


def get_metadata_parser(metadata_scheme: MetadataScheme) -> MetadataParser:
    match metadata_scheme:
        case MetadataScheme.FOOOCUS:
            return FooocusMetadataParser()
        case MetadataScheme.A1111:
            return A1111MetadataParser()
        case MetadataScheme.SIMPLE:
            return SIMPLEMetadataParser()
        case _:
            raise NotImplementedError


def read_meta_from_image(file) -> tuple[str | None, MetadataScheme | None]:
    items = (file.info or {}).copy()

    parameters = items.pop('parameters', None)
    metadata_scheme = items.pop('fooocus_scheme', None)
    exif = items.pop('exif', None)
    if not parameters and 'Comment' in items:
        metadata_scheme = 'simple'
        parameters = items.pop('Comment', None)

    if parameters is not None and is_json(parameters):
        parameters = json.loads(parameters)
        parameters = params_lora_fixed(parameters)
    elif exif is not None:
        exif = file.getexif()
        # 0x9286 = UserComment
        parameters = exif.get(0x9286, None)
        # 0x927C = MakerNote
        metadata_scheme = exif.get(0x927C, None)

        if parameters and is_json(parameters):
            parameters = json.loads(parameters)
            parameters = params_lora_fixed(parameters)

    try:
        if metadata_scheme == 'fooocus':
            metadata_scheme = 'simple'
            parameters.update({'metadata_scheme': 'simple'})
        metadata_scheme = MetadataScheme(metadata_scheme)
    except ValueError:
        metadata_scheme = None

        # broad fallback
        #if isinstance(parameters, dict):
        #    metadata_scheme = MetadataScheme.FOOOCUS

        if isinstance(parameters, str):
            metadata_scheme = MetadataScheme.A1111
    return parameters, metadata_scheme


def trigger_metadata_preview(file):

    parameters, metadata_scheme = read_meta_from_image(file)
    results = {}
    if parameters is not None:
        results['parameters'] = parameters

    if isinstance(metadata_scheme, MetadataScheme):
        results['metadata_scheme'] = metadata_scheme.value
        if metadata_scheme.value.lower() == 'simple':
            results['metadata_scheme'] = 'Fooocus'
        if metadata_scheme.value.lower() == 'a1111':
            results['metadata_scheme'] = 'A1111'
            parameters = None

    # Resolve validation using the newly routed gallery helper
    is_comfy_required = gallery.is_comfy_metadata(parameters, metadata_scheme)
    if is_comfy_required and not common.comfy_active:
        button_interactive = False
        interpret_warn('This image requires Comfy to be available for regeneration.')
    else:
        button_interactive = (parameters is not None)

    return [results, gr.update(interactive=button_interactive)]


def extract_preset_name_from_image(image_file):
    # Extracts and modernizes metadata from an image
    # Updates the UI preset components

    common.log_metadata = {}

    if image_file is None:
        return gr.update(), gr.update(), gr.update()

    # 1. If image_file is a path (string),
    # open it as an Image object.
    # If it's already an image object,
    # use it directly.
    try:
        if isinstance(image_file, str):
            with Image.open(image_file) as img:
                parameters, scheme = read_meta_from_image(img)
        else:
            parameters, scheme = read_meta_from_image(image_file)
    except Exception as e:
        interpret(f'[MetaParser] ⚠️ Failed to read image file: {e}')
        return gr.update(), gr.update(), gr.update()

    if parameters is None:
        interpret('[MetaParser] ⚠️ No valid metadata found in image.')
        return gr.update(), gr.update(), gr.update()

    # 2. Convert to dictionary and Modernize/Fuse
    # SIMPLEMetadataParser.to_json handles the normalization for us
    metadata_scheme = MetadataScheme('simple')
    metadata_parser = get_metadata_parser(metadata_scheme)
    loaded_dict = metadata_parser.to_json(parameters)

    # Ensure Z-Image renaming and technical fusion occurs
    loaded_dict = PR.modernize_legacy_metadata(loaded_dict)

    # 3. Resolve the Name
    preset_name = loaded_dict.get('current_preset', 'Default')

    # 4. Sync global state
    common.log_metadata = loaded_dict
    common.metadata_loading = True
    PR.current_preset = preset_name

    # 5. Resolve UI categories/choices
    category = PR.find_preset_category(preset_name)
    PR.category_selection = category
    preset_choices = PR.get_presetnames_in_folder(category)

    return (
        gr.update(value=category),
        gr.update(choices=preset_choices, value=preset_name),
        gr.update(value=preset_name)
    )


def extract_preset_name_from_log(raw_metadata: str):
    # Extracts and modernizes metadata from the log
    # Updates the UI preset components

    # 1. Clear previous cache
    common.log_metadata = {}

    # 2. Parse and Modernize
    # parse_log_text_to_dict now handles JSON and Multiline robustly
    loaded_dict = parse_log_text_to_dict(raw_metadata)

    # 3. Resolve the Name (Checks every key we've ever used)
    preset_name = loaded_dict.get('current_preset',
                  loaded_dict.get('Preset',
                  loaded_dict.get('preset', 'Default')))

    # 4. Sync global state
    common.log_metadata = loaded_dict
    common.metadata_loading = True
    PR.current_preset = preset_name

    # 5. Resolve category and list choices for the UI
    category = PR.find_preset_category(preset_name)
    PR.category_selection = category
    preset_choices = PR.get_presetnames_in_folder(category)

    # Return the triplet for immediate UI synchronization
    return (
        gr.update(value=category),
        gr.update(choices=preset_choices, value=preset_name),
        gr.update(value=preset_name)
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
    # 1. Convert string to dict immediately
    if isinstance(metadata, str) and not metadata.strip().startswith("{"):
        metadata = parse_log_text_to_dict(metadata)

    elif isinstance(metadata, str) and metadata.strip().startswith("{"):

        metadata = json.loads(metadata)

    if metadata is None or metadata == {}:
        metadata = {}

    # --- THE CRITICAL FIX: Modernize BEFORE Parsing ---
    # This ensures to_json() has access to fused Workflow/Engine data
    metadata = PR.modernize_legacy_metadata(metadata)
    # --------------------------------------------------

    metadata_scheme = MetadataScheme('simple')
    metadata_parser = get_metadata_parser(metadata_scheme)

    # 2. Run the Parser (now restored with safe_get)
    parsed_parameters = metadata_parser.to_json(metadata)

    # 3. Synchronize UI
    results = switch_layout_template(parsed_parameters, state_params)

    # replace the technical dict with
    # a neutral update to fix the shif:
    if results and isinstance(results[0], dict) and 'backend_engine' in results[0]:
        results[0] = gr.update()

    results += read_meta_from_log(parsed_parameters, is_generating, inpaint_mode)

    engine_name = parsed_parameters.get("Backend Engine", parsed_parameters.get("backend_engine", "SDXL-Fooocus"))
    wf_name = parsed_parameters.get("task_method", "None")
    interpret('[MetaParser] The image was created with the engine:', engine_name)
    interpret('using the Workflow:', wf_name)
    return results


def params_lora_fixed(parameters):
    loras_p = {k: v for k, v in parameters.items() if k.startswith("LoRA [")}
    if loras_p:
        for k, _ in loras_p.items():
            del parameters[k]
        loras_p = {f'LoRA {i}': f'{k[6:-8]} : {v}' for i, (k, v) in enumerate(loras_p.items(), 1)}
        parameters.update(loras_p)
    return parameters

def get_exif(metadata: str | None, metadata_scheme: str):
    exif = Image.Exif()
    fooocusplus_ver, hotfix, hotfix_title = enhanced.version.get_fooocusplus_ver()
    # tags see see https://github.com/python-pillow/Pillow/blob/9.2.x/src/PIL/ExifTags.py
    # 0x9286 = UserComment
    exif[0x9286] = metadata
    # 0x0131 = Software
    exif[0x0131] = f'FooocusPlus {fooocusplus_ver}.{hotfix_title}, Preset: {args.args.preset}'
    # 0x927C = MakerNote
    exif[0x927C] = metadata_scheme
    return exif
