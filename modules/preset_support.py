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
    if arg_sampler in sampler_list:
        common.sampler_name = arg_sampler
        return common.sampler_name
    elif common.sampler_name in sampler_list:
        pass
    else:
        common.sampler_name = config.default_sampler
    interpret('[Preset Support] Sampler not verified:', arg_sampler)
    return common.sampler_name

def verify_scheduler(arg_scheduler):
    if arg_scheduler in scheduler_list:
        common.scheduler_name = arg_scheduler
        return common.scheduler_name
    elif common.scheduler_name in scheduler_list:
        pass
    else:
        common.scheduler_name = config.scheduler_name
    interpret('[Preset Support] Scheduler not verified:', arg_scheduler)
    return common.scheduler_name


def parse_meta_from_preset(preset_content):
    preset_prepared = {}
    if not preset_content:
        preset_content = common.load_metadata
        print
        print('Reloading log metadata')

    if common.metadata_loading:
        preset_content = common.log_metadata
    items = US.verify_dictionary(preset_content)

    for settings_key, meta_key in config.possible_preset_keys.items():
        # for presets that do not have a default prompt or negative prompt
        # and almost all presets do not have an image quantity:
        items.setdefault("default_prompt", common.positive)
        items.setdefault("default_prompt_negative", common.negative)
        items.setdefault("default_image_quantity", common.image_quantity)

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
                if len(lora) == 2:
                    lora[0] = lora[0].replace('\\', os.sep).replace('/', os.sep)
                elif len(lora) == 3:
                    lora[1] = lora[1].replace('\\', os.sep).replace('/', os.sep)
                preset_prepared[f'lora_combined_{index + 1}'] = ' : '.join(map(str, lora))

        elif settings_key == "default_prompt":
            if items[settings_key]:
                common.positive = items[settings_key]
                interpret('[Preset Support] Positive prompt set by preset or metadata')
            else:
                items[settings_key] = common.positive

        elif settings_key == "default_prompt_negative":
            if items[settings_key]:
                common.negative = items[settings_key]
                interpret(f'[Preset Support] Negative prompt set by preset or metadata')
            else:
                items[settings_key] = common.negative

        # do not do this during startup,
        # when called by init_config_preset()
        # only when switching presets,
        # when called by UIS.reset_layout_params()
        elif settings_key == "default_aspect_ratio" and common.current_AR != '0*0':
            if settings_key in items and (items[settings_key] is not None or items[settings_key] != '0*0'):
                default_aspect_ratio = items[settings_key]
                width, height = AR_split(default_aspect_ratio)
            else:
                if common.current_AR:
                    default_aspect_ratio = common.current_AR
                else:
                    if config.enable_shortlist_aspect_ratios:
                        default_aspect_ratio = config.default_shortlist_aspect_ratio
                    else:
                        default_aspect_ratio = config.default_standard_AR
                    interpret('[Preset Support] Fallback to default aspect ratio:', default_aspect_ratio)
                width, height = AR_split(default_aspect_ratio)
            preset_prepared[meta_key] = (width, height)

        elif settings_key == "default_refiner_switch":
            try:
                common.refiner_slider = items[settings_key]
            except:
                if type(common.refiner_slider) != 'float':
                    common.refiner_slider = config.default_refiner_switch

        elif settings_key == "default_sampler" and not common.metadata_loading:
            verify_sampler(items[settings_key])

        elif settings_key == "default_scheduler" and not common.metadata_loading:
            verify_scheduler(items[settings_key])

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
    values = lora_combined.split(' : ')
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
        config.default_refiner_model_name = preset_prepared.get('refiner_model')
        config.default_loras = [get_lora_values(preset_prepared.get("lora_combined_1")),
            get_lora_values(preset_prepared.get("lora_combined_2")),
            get_lora_values(preset_prepared.get("lora_combined_3")),
            get_lora_values(preset_prepared.get("lora_combined_4")),
            get_lora_values(preset_prepared.get("lora_combined_5"))]
        config.default_cfg_scale = preset_prepared.get('guidance_scale')
        config.default_sample_sharpness = preset_prepared.get('sharpness')
        config.default_sampler = common.sampler_name
        config.default_scheduler = common.scheduler_name
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
                common.current_AR = config.default_aspect_ratio
            else:
                config.default_aspect_ratio = config.default_sd1_5_aspect_ratio
                common.current_AR = config.default_sd1_5_aspect_ratio
        elif config.default_aspect_ratio != '0*0':
            if common.current_AR == '0*0':
                if config.enable_shortlist_aspect_ratios:
                    config.default_shortlist_aspect_ratio = config.default_aspect_ratio
                else:
                    config.default_standard_aspect_ratio = config.default_aspect_ratio
            common.current_AR = config.default_aspect_ratio
        else:
            if config.enable_shortlist_aspect_ratios:
                config.default_aspect_ratio = config.default_shortlist_aspect_ratio
            else:
                config.default_aspect_ratio = config.default_standard_aspect_ratio
            common.current_AR = config.default_aspect_ratio

        if flag_AR_default:
            interpret('Using the default aspect ratio from', f'config.txt: {common.current_AR}')

        config.default_aspect_ratio_values = [config.default_standard_aspect_ratio,
            config.default_shortlist_aspect_ratio,
            config.default_sd1_5_aspect_ratio,
            config.default_pixart_aspect_ratio]

        from modules.ar_util import assign_default_by_template
        assign_default_by_template('Init')
        import modules.aspect_ratios as AR
        AR.get_aspect_ratio_title(config.default_aspect_ratio_values)
    else:
        common.is_low_vram_preset = False
        args.preset = 'Default'
    return
