import ast # used to convert a style string to a list
import os
import common
import modules.config as config
import modules.user_structure as US
from args_manager import args
from enhanced.translator import interpret
from modules.ar_util import AR_split
from modules.flags import scheduler_list, sampler_list


def verify_sampler(arg_sampler):
    # arg_sampler is valid
    if arg_sampler in sampler_list:
        config.default_sampler = arg_sampler
        return config.default_sampler

    # arg_sampler failed verification:
    interpret('[Preset Support] Sampler not verified:', arg_sampler)
    if config.default_sampler in sampler_list:
        # fallback to current config
        interpret('Using the config default instead:', config.default_sampler)
    else:
        # otherwise fallback to the most popular value:
        config.default_sampler = 'dpmpp_2m_sde_gpu'
        interpret('The sampler and config default values are invalid.')
        interpret('Substituting with:', config.default_sampler)
    print()

    return config.default_sampler


def verify_scheduler(arg_scheduler):
    # arg_scheduler is valid
    if arg_scheduler in scheduler_list:
        config.default_scheduler = arg_scheduler
        return config.default_scheduler

    # arg_scheduler failed verification:
    interpret('[Preset Support] Scheduler not verified:', arg_scheduler)
    if config.default_scheduler in scheduler_list:
        # fallback to current config
        interpret('Using the config default instead:', config.default_scheduler)
    else:
        # otherwise fallback to the most popular value:
        config.default_scheduler = 'karras'
        interpret('The scheduler and config default values are invalid.')
        interpret('Substituting with:', config.default_scheduler)
    print()

    return config.default_scheduler


def parse_meta_from_preset(preset_content):
    preset_prepared = {}
    if not preset_content:
        print()
        if common.log_metadata:
            preset_content = common.log_metadata
            interpret('[Preset Support] Reloading', common.log_metadata)
        else:
            interpret('[Preset Support] Could not find', 'metadata!')
            return ''

    if common.metadata_loading:
        preset_content = common.log_metadata
    items = US.verify_dictionary(preset_content)

    for settings_key, meta_key in config.possible_preset_keys.items():
        # for presets that do not have a default prompt or negative prompt
        # and almost all presets do not have an image quantity:
        items.setdefault("default_prompt",
            config.default_prompt)
        items.setdefault("default_prompt_negative",
            config.default_prompt_negative)
        items.setdefault("default_image_quantity",
            config.default_image_quantity)

        if settings_key == "default_engine":
            try:
            # use Comfy based engine
                common.default_engine = items.get(settings_key)
            except:
            # use Fooocus engine
                common.default_engine = {}
            if common.default_engine:
                # must be cleared to allow for Flux ops:
                config.backend_engine = ''
            else:
                # restore Fooocus operation:
                config.backend_engine = config.default_engine.get("backend_engine", "Fooocus")

        if settings_key == "default_loras" and not common.metadata_loading:
            loras = getattr(config, settings_key)
            if settings_key in items:
                loras = items[settings_key]

            for index, lora in enumerate(loras[:config.default_max_lora_number]):
                lora = list(lora)

                if len(lora) == 2:
                    lora[0] = str(lora[0]).replace('\\', os.sep).replace('/', os.sep)
                elif len(lora) == 3:
                    lora[1] = str(lora[1]).replace('\\', os.sep).replace('/', os.sep)

                preset_prepared[f'lora_combined_{index + 1}'] = ' : '.join(map(str, lora))

        elif settings_key == "default_prompt":
            if items[settings_key]:
                config.default_prompt = items[settings_key]
                interpret('[Preset Support] Positive prompt set by preset or metadata')
            else:
                items[settings_key] = config.default_prompt
            preset_prepared[meta_key] = config.default_prompt

        elif settings_key == "default_prompt_negative":
            if items[settings_key]:
                config.default_prompt_negative = items[settings_key]
                interpret(f'[Preset Support] Negative prompt set by preset or metadata')
            else:
                items[settings_key] = config.default_prompt_negative
            preset_prepared[meta_key] = config.default_prompt_negative

        # do not do this during startup,
        # when called by init_config_preset()
        # only when switching presets,
        # when called by UIS.reset_layout_params()
        elif settings_key == "default_aspect_ratio" and common.resolution != '0*0':
            if settings_key in items and (items[settings_key] is not None or items[settings_key] != '0*0'):
                default_aspect_ratio = items[settings_key]
                width, height = AR_split(default_aspect_ratio)
            else:
                if common.resolution:
                    default_aspect_ratio = common.resolution
                else:
                    if config.enable_shortlist_aspect_ratios:
                        default_aspect_ratio = config.default_shortlist_aspect_ratio
                    else:
                        default_aspect_ratio = config.default_standard_AR
                    interpret('[Preset Support] Fallback to the default resolution and aspect ratio:', default_aspect_ratio)
                width, height = AR_split(default_aspect_ratio)
            preset_prepared[meta_key] = (width, height)

        elif settings_key == "default_refiner_switch":
            try:
                val = float(items[settings_key])
                config.default_refiner_switch = val
                preset_prepared[meta_key] = val
            except (KeyError, ValueError, TypeError):
                pass

        elif settings_key == "default_sampler" and not common.metadata_loading:
            val = items.get(settings_key, getattr(config, settings_key))
            verify_sampler(val)
            preset_prepared[meta_key] = val

        elif settings_key == "default_scheduler" and not common.metadata_loading:
            val = items.get(settings_key, getattr(config, settings_key))
            verify_scheduler(val)
            preset_prepared[meta_key] = val

        elif settings_key not in items and settings_key in config.allow_missing_preset_key:
            continue

        else:
            preset_prepared[meta_key] = items[settings_key] if settings_key in items and items[settings_key] is not None else getattr(config, settings_key)

        if settings_key == "default_styles" or settings_key == "default_aspect_ratio":
            preset_prepared[meta_key] = str(preset_prepared[meta_key])

        if settings_key in ["default_model", "default_refiner"]:
            preset_prepared[meta_key] = preset_prepared[meta_key].replace('\\', os.sep).replace('/', os.sep)

    return preset_prepared


def get_lora_values(lora_combined):
    # Safety check for None or empty strings
    if not lora_combined or not isinstance(lora_combined, str):
        return False, 'None', 1.0

    values = lora_combined.split(' : ')

    # Ensure we have all 3 parts (Enabled, Name, Weight)
    if len(values) < 3:
        return False, 'None', 1.0

    bool_value = 'true' in values[0].lower()
    float_value = float(values[2])
    return bool_value, values[1], float_value


def normalize_AR(arg_AR):
    if not arg_AR:
        return ''
    if ',' in arg_AR:
        table = str.maketrans({"(": "", ")": "", ",": "", " ": "*", "'": ""})
        arg_AR = arg_AR.translate(table)
    return arg_AR

def init_config_preset():
    # called by launch.py
    # adapts to startup preset command line arguments, including Flux
    interpret('[Preset Support] Initializing the preset:', args.preset)
    if common.preset_content != '' and args.preset != 'initial':
        preset_prepared = parse_meta_from_preset(common.preset_content)
        default_model = preset_prepared.get('base_model')
        config.default_base_model_name = default_model
        config.default_refiner = preset_prepared.get('refiner_model')
        
        new_loras = []
        for i in range(1, config.default_max_lora_number + 1):
            lora_key = f"lora_combined_{i}"
            lora_data = preset_prepared.get(lora_key)
            # This will now return (False, 'None', 1.0)
            # if the key is missing
            new_loras.append(get_lora_values(lora_data))
        config.default_loras = new_loras

        config.default_cfg_scale = preset_prepared.get('guidance_scale')
        config.default_sample_sharpness = preset_prepared.get('sharpness')
        config.default_sampler = preset_prepared.get(
            'sampler', config.default_sampler)
        config.default_scheduler = preset_prepared.get(
            'scheduler', config.default_scheduler)
        config.default_cfg_tsnr = preset_prepared.get('adaptive_cfg')
        config.default_clip_skip = preset_prepared.get('clip_skip')
        config.default_overwrite_step = preset_prepared.get('steps')
        config.default_overwrite_switch = preset_prepared.get('overwrite_switch')
        config.default_performance = preset_prepared.get('performance')
        config.default_styles = ast.literal_eval(preset_prepared.get('styles'))
        config.default_vae = preset_prepared.get('vae')
        if config.default_vae == None:
            config.default_vae = 'Default (model)'
        config.default_image_quantity = preset_prepared.get('image_quantity')
        config.default_aspect_ratio = normalize_AR(preset_prepared.get('resolution'))
        if not config.default_aspect_ratio:
            config.default_aspect_ratio = '0*0'
        if config.default_aspect_ratio == '0*0':
            print_AR = interpret('None', '', True)
        else:
            print_AR = config.default_aspect_ratio
        interpret('Initial preset resolution:', print_AR)
        flag_AR_default = config.default_aspect_ratio == '0*0'

        previous_default_models = preset_prepared.get('previous_default_models', [])
        checkpoint_downloads = preset_prepared.get('checkpoint_downloads', {})
        embeddings_downloads = preset_prepared.get('embeddings_downloads', {})
        lora_downloads = preset_prepared.get('lora_downloads', {})
        vae_downloads = preset_prepared.get('vae_downloads', {})

        if common.default_engine:
            common.task_method = common.default_engine.get("backend_params", {}).get("task_method")
        if common.task_method == 'SD_SIMPLE':
            if config.default_aspect_ratio != '0*0':
                config.default_sd1_5_aspect_ratio = config.default_aspect_ratio
                common.resolution = config.default_aspect_ratio
            else:
                config.default_aspect_ratio = config.default_sd1_5_aspect_ratio
                common.resolution = config.default_sd1_5_aspect_ratio
        elif config.default_aspect_ratio != '0*0':
            if common.resolution == '0*0':
                if config.enable_shortlist_aspect_ratios:
                    config.default_shortlist_aspect_ratio = config.default_aspect_ratio
                else:
                    config.default_standard_aspect_ratio = config.default_aspect_ratio
            common.resolution = config.default_aspect_ratio
        else:
            if config.enable_shortlist_aspect_ratios:
                config.default_aspect_ratio = config.default_shortlist_aspect_ratio
            else:
                config.default_aspect_ratio = config.default_standard_aspect_ratio
            common.resolution = config.default_aspect_ratio

        if flag_AR_default:
            interpret('Using the default resolution from', f'config.txt: {common.resolution}')

        config.default_aspect_ratio_values = [config.default_standard_aspect_ratio,
            config.default_shortlist_aspect_ratio,
            config.default_sd1_5_aspect_ratio,
            config.default_pixart_aspect_ratio]

        from modules.ar_util import assign_default_by_template
        assign_default_by_template('Init')
        import modules.aspect_ratios as AR
        AR.get_aspect_ratio_title(config.default_aspect_ratio_values)
    else:
        config.default_low_vram_presets = False
        args.preset = 'Default'
    return
