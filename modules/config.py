import os
import json
import math
import numbers
import args_manager
import common
import enhanced.all_parameters as ads
import modules.constants as constants
import modules.flags
import modules.preset_resource as PR
import modules.user_structure as US
import tempfile

from pathlib import Path
from modules.extra_utils import get_files_from_folder, try_eval_env_var
from modules.flags import OutputFormat, Performance, MetadataScheme
from modules.model_loader import load_file_from_url


current_dir = Path.cwd().resolve()
home_dir = current_dir.parent.parent.resolve()
user_dir = Path(args_manager.args.user_dir).resolve()
config_dict = {}
always_save_keys = []
visited_keys = []
wildcards_max_bfs_depth = 64


def get_dir_or_set_default(key, default_value, as_array=False, make_directory=False):
    global config_dict, visited_keys, always_save_keys

    if key not in visited_keys:
        visited_keys.append(key)

    if key not in always_save_keys:
        always_save_keys.append(key)

    v = os.getenv(key)
    if v is not None:
        print(f"Environment: {key} = {v}")
        config_dict[key] = v
    else:
        v = config_dict.get(key, None)

    if isinstance(v, str):
        if make_directory:
            US.make_dir(v)
        if os.path.exists(v) and os.path.isdir(v):
            return v if not as_array else [v]
    elif isinstance(v, list):
        if make_directory:
            for d in v:
                US.make_dir(d)
        if all([os.path.exists(d) and os.path.isdir(d) for d in v]):
            return v

    if v is not None:
        if not 'Outputs' in v:
            print(f'Failed to load the directory config key: {json.dumps({key:v})} is invalid or does not exist; will use {json.dumps({key:default_value})} instead.')
    if isinstance(default_value, list):
        dp = []
        for path in default_value:
            abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), path))
            dp.append(abs_path)
            US.make_dir(abs_path)
    else:
        if default_value != os.path.abspath(default_value):
            dp = os.path.abspath(os.path.join(os.path.dirname(__file__), default_value))
        else:
            dp = default_value
        US.make_dir(dp)
        if as_array:
            dp = [dp]
    config_dict[key] = dp
    return dp

US.create_user_structure(user_dir)

def get_path_output() -> str:
    global config_dict, user_dir
    path_output = Path(user_dir/'Outputs').resolve()
    path_output = get_dir_or_set_default('path_outputs', path_output, make_directory=True)
    if args_manager.args.output_path:
        config_dict['path_outputs'] = path_output = str(Path(args_manager.args.output_path).resolve())
    print(f'Generated images will be stored in {path_output}')
    return path_output

def get_config_path(config_file):
    global user_dir
    if args_manager.args.config:
        config_path = Path(args_manager.args.config)
    else:
        config_path = user_dir
    config_path = os.path.abspath(f'{config_path}/{config_file}')
    return config_path

config_dict.update(PR.get_initial_preset_content())
theme = args_manager.args.theme

config_path = get_config_path('/config.txt')
config_example_path = get_config_path('/config_modification_tutorial.txt')
print(f'User configurations are stored in {config_path}')

try:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as json_file:
            config_dict.update(json.load(json_file))
        always_save_keys = list(config_dict.keys())
        for key in always_save_keys:
            if key.startswith('default_') and key[8:] in ads.default:
                ads.default[key[8:]] = config_dict[key]
        print(f'Loading config data from {config_path}')
except Exception as e:
    print(f'Failed to load config data from {config_path}')
    print(f'because of {str(e)}')
    print('Please make sure that:')
    print(f'1. The file "{config_path}" is a valid text file, and you have access to read it.')
    print('2. Use "\\\\" instead of "\\" when describing paths.')
    print('3. There is no "," before the last "}".')
    print('4. All key and value formats are correct.')

if args_manager.args.models_root:
    get_dir_or_set_default('path_models_root', Path(args_manager.args.models_root).resolve())
    path_models_root = Path(args_manager.args.models_root).resolve()
else:
    path_models_root = get_dir_or_set_default('path_models_root', Path(user_dir/'models').resolve())
path_models_root = Path(path_models_root).resolve()
print(f'Generative models are stored in {path_models_root}')
print('Models may also be stored in other locations, as defined in config.txt')

paths_checkpoints = get_dir_or_set_default('path_checkpoints', [Path(path_models_root/'checkpoints').resolve(), Path(user_dir/'models/checkpoints').resolve()], True, False)
paths_loras = get_dir_or_set_default('path_loras', [Path(path_models_root/'loras').resolve(), Path(user_dir/'models/loras').resolve()], True, False)
path_embeddings = get_dir_or_set_default('path_embeddings', Path(path_models_root/'embeddings').resolve())
path_vae_approx = get_dir_or_set_default('path_vae_approx', Path(path_models_root/'vae_approx').resolve())
path_vae = get_dir_or_set_default('path_vae', Path(path_models_root/'vae').resolve())
path_upscale_models = get_dir_or_set_default('path_upscale_models', Path(path_models_root/'upscale_models').resolve())
paths_inpaint = get_dir_or_set_default('path_inpaint', [Path(path_models_root/'inpaint').resolve(), Path(user_dir/'models/inpaint').resolve()], True, False)
path_sam = paths_inpaint[0]
paths_controlnet = get_dir_or_set_default('path_controlnet', [Path(path_models_root/'controlnet').resolve(), Path(user_dir/'models/controlnet').resolve()], True, False)
path_clip = get_dir_or_set_default('path_clip', Path(path_models_root/'clip').resolve())
path_clip_vision = get_dir_or_set_default('path_clip_vision', Path(path_models_root/'clip_vision').resolve())
path_fooocus_expansion = get_dir_or_set_default('path_fooocus_expansion', Path(path_models_root/'prompt_expansion/fooocus_expansion').resolve())
paths_llms = get_dir_or_set_default('path_llms', [Path(path_models_root/'llms').resolve()], True, False)
path_safety_checker = get_dir_or_set_default('path_safety_checker', Path(path_models_root/'safety_checker').resolve())
path_unet = get_dir_or_set_default('path_unet', Path(path_models_root/'unet').resolve())
path_rembg = get_dir_or_set_default('path_rembg', Path(path_models_root/'rembg').resolve())
path_layer_model = get_dir_or_set_default('path_layer_model', Path(path_models_root/'layer_model').resolve())
paths_diffusers = get_dir_or_set_default('path_diffusers', [Path(path_models_root/'diffusers').resolve()], True, False)
path_outputs = get_path_output()
path_wildcards = get_dir_or_set_default('path_wildcards', Path(user_dir/'wildcards').resolve())


from enhanced.backend import init_modelsinfo
modelsinfo = init_modelsinfo(path_models_root, dict(
    checkpoints=paths_checkpoints,
    loras=paths_loras,
    embeddings=[path_embeddings],
    diffusers=paths_diffusers,
    DIFFUSERS=paths_diffusers,
    controlnet=paths_controlnet,
    inpaint=paths_inpaint,
    llms=paths_llms,
    unet=[path_unet],
    vae=[path_vae]
    ))

US.create_model_structure(paths_checkpoints, paths_loras)

def get_config_item_or_set_default(key, default_value, validator, disable_empty_as_none=False, expected_type=None):
    global config_dict, visited_keys

    if key not in visited_keys:
        visited_keys.append(key)

    v = os.getenv(key)
    if v is not None:
        v = try_eval_env_var(v, expected_type)
        print(f"Environment: {key} = {v}")
        config_dict[key] = v

    if key not in config_dict:
        config_dict[key] = default_value
        return default_value

    v = config_dict.get(key, None)
    if not disable_empty_as_none:
        if v is None or v == '':
            v = 'None'

    if validator(v):
        return v
    else:
        if v is not None:
            if 'fooocus' in v.lower():
                default_value = MetadataScheme.SIMPLE.value
            elif 'a1111' in v.lower():
                default_value = MetadataScheme.A1111.value
            else:
                print(f'Failed to load config key: {json.dumps({key:v})} is invalid; will use {json.dumps({key:default_value})} instead.')
        config_dict[key] = default_value
        return default_value


def init_temp_path(temp_path: str | None, default_path: str) -> str:
    if args_manager.args.temp_path:
        temp_path = Path(args_manager.args.temp_path)

    if temp_path != '' and \
        (Path(temp_path) != Path(default_path)):
        try:
            temp_path = Path(temp_path).resolve()
            US.make_dir(temp_path)
            print(f'Using temp path {temp_path}')
            return str(temp_path)
        except Exception as e:
            print(f'Could not create temp path {temp_path}. Reason: {e}')
            print(f'Using default temp path {default_path} instead.')

    US.make_dir(default_path)
    return str(default_path)

temp_file = Path(tempfile.gettempdir())
default_temp_path = str(Path(temp_file/'fooocusplus'))
temp_path = init_temp_path(get_config_item_or_set_default(
    key='temp_path',
    default_value=default_temp_path,
    validator=lambda x: isinstance(x, str),
    expected_type=str), default_temp_path)
temp_path_cleanup_on_launch = get_config_item_or_set_default(
    key='temp_path_cleanup_on_launch',
    default_value=True,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)

enable_preset_bar = get_config_item_or_set_default(
    key='enable_preset_bar',
    default_value=True,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_bar_category = get_config_item_or_set_default(
    key='default_bar_category',
    default_value='Favorite',
    validator=lambda x: isinstance(x, str),
    expected_type=str
)
preset_bar_category_tracking = get_config_item_or_set_default(
    key='preset_bar_category_tracking',
    default_value=True,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
preset_bar_length = get_config_item_or_set_default(
    key='preset_bar_length',
    default_value=8,
    validator=lambda x: isinstance(x, int) and 1 <= x <= 30,
    expected_type=int
)
enable_random_preset_in_category = get_config_item_or_set_default(
    key='enable_random_preset_in_category',
    default_value=True,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_list_all_presets = get_config_item_or_set_default(
    key='default_list_all_presets',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_low_vram_presets = get_config_item_or_set_default(
    key='default_low_vram_presets',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)

default_image_prompt_checkbox = get_config_item_or_set_default(
    key='default_image_prompt_checkbox',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_enhance_checkbox = get_config_item_or_set_default(
    key='default_enhance_checkbox',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_advanced_checkbox = get_config_item_or_set_default(
    key='default_advanced_checkbox',
    default_value=ads.default['advanced_checkbox'],
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_expert_mode_checkbox = get_config_item_or_set_default(
    key='default_expert_mode_checkbox',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_image_prompt_advanced_checkbox = get_config_item_or_set_default(
    key='default_image_prompt_advanced_checkbox',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)

default_performance = get_config_item_or_set_default(
    key='default_performance',
    default_value=Performance.Speed.value,
    validator=lambda x: x in Performance.values(),
    expected_type=str
)
custom_performance_steps = get_config_item_or_set_default(
    key='custom_performance_steps',
    default_value=15,
    validator=lambda x: isinstance(x, int) and 1 <= x <= 200,
    expected_type=int
)
default_overwrite_step = get_config_item_or_set_default(
    key='default_overwrite_step',
    default_value=ads.default['overwrite_step'],
    validator=lambda x: isinstance(x, int),
    expected_type=int
)

default_max_image_quantity = get_config_item_or_set_default(
    key='default_max_image_quantity',
    default_value=ads.default['max_image_quantity'],
    validator=lambda x: isinstance(x, int) and x >= 1,
    expected_type=int
)
default_image_quantity = get_config_item_or_set_default(
    key='default_image_quantity',
    default_value=ads.default['image_quantity'],
    validator=lambda x: isinstance(x, int) and 1 <= x <= default_max_image_quantity,
    expected_type=int
)

enable_random_aspect_ratios = get_config_item_or_set_default(
    key='enable_random_aspect_ratios',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
enable_shortlist_aspect_ratios = get_config_item_or_set_default(
    key='enable_shortlist_aspect_ratios',
    default_value=True,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
available_standard_aspect_ratios = get_config_item_or_set_default(
    key='available_standard_aspect_ratios',
    default_value=constants.template_aspect_ratios[0],
    validator=lambda x: isinstance(x, list) and all('*' in v for v in x) and len(x) > 1,
    expected_type=list
)
default_standard_aspect_ratio = get_config_item_or_set_default(
    key='default_standard_aspect_ratio',
    default_value='1024*1024',
    validator=lambda x: x in available_standard_aspect_ratios,
    expected_type=str
)
available_shortlist_aspect_ratios = get_config_item_or_set_default(
    key='available_shortlist_aspect_ratios',
    default_value=constants.template_aspect_ratios[1],
    validator=lambda x: isinstance(x, list) and all('*' in v for v in x) and len(x) > 1,
    expected_type=list
)
default_shortlist_aspect_ratio = get_config_item_or_set_default(
    key='default_shortlist_aspect_ratio',
    default_value='1024*1024',
    validator=lambda x: x in available_shortlist_aspect_ratios,
    expected_type=str
)
available_sd1_5_aspect_ratios = get_config_item_or_set_default(
    key='available_sd1_5_aspect_ratios',
    default_value=constants.template_aspect_ratios[2],
    validator=lambda x: isinstance(x, list) and all('*' in v for v in x) and len(x) > 1,
    expected_type=list
)
default_sd1_5_aspect_ratio = get_config_item_or_set_default(
    key='default_sd1_5_aspect_ratio',
    default_value='768*768',
    validator=lambda x: x in available_sd1_5_aspect_ratios,
    expected_type=str
)
available_pixart_aspect_ratios = get_config_item_or_set_default(
    key='available_pixart_aspect_ratios',
    default_value=constants.template_aspect_ratios[3],
    validator=lambda x: isinstance(x, list) and all('*' in v for v in x) and len(x) > 1,
    expected_type=list
)
default_pixart_aspect_ratio = get_config_item_or_set_default(
    key='default_pixart_aspect_ratio',
    default_value='3840*2160',
    validator=lambda x: x in available_pixart_aspect_ratios,
    expected_type=str
)

default_output_format = get_config_item_or_set_default(
    key='default_output_format',
    default_value=ads.default['output_format'],
    validator=lambda x: x in OutputFormat.list(),
    expected_type=str
)

default_prompt = get_config_item_or_set_default(
    key='default_prompt',
    default_value='',
    validator=lambda x: isinstance(x, str),
    disable_empty_as_none=True,
    expected_type=str
)
default_prompt_negative = get_config_item_or_set_default(
    key='default_prompt_negative',
    default_value='',
    validator=lambda x: isinstance(x, str),
    disable_empty_as_none=True,
    expected_type=str
)
default_extra_variation = get_config_item_or_set_default(
    key='default_extra_variation',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)

default_describe_apply_prompts_checkbox = get_config_item_or_set_default(
    key='default_describe_apply_prompts_checkbox',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_describe_content_type = get_config_item_or_set_default(
    key='default_describe_content_type',
    default_value=[modules.flags.describe_type_photo, modules.flags.describe_type_anime],
    validator=lambda x: all(k in modules.flags.describe_types for k in x),
    expected_type=list
)
enable_auto_describe_image = get_config_item_or_set_default(
    key='enable_auto_describe_image',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)

import modules.sdxl_styles
default_styles = get_config_item_or_set_default(
    key='default_styles',
    default_value=[
        "Fooocus V2",
        "Fooocus Enhance"
    ],
    validator=lambda x: isinstance(x, list) and all(y in modules.sdxl_styles.legal_style_names for y in x),
    expected_type=list
)

default_engine = get_config_item_or_set_default(
    key='default_engine',
    default_value={},
    validator=lambda x: isinstance(x, dict),
    expected_type=dict
)
backend_engine = default_engine.get("backend_engine", "Fooocus")

default_base_model_name = default_model = get_config_item_or_set_default(
    key='default_model',
    default_value='model.safetensors',
    validator=lambda x: isinstance(x, str),
    expected_type=str
).replace('\\', os.sep).replace('/', os.sep)

previous_default_models = get_config_item_or_set_default(
    key='previous_default_models',
    default_value=[],
    validator=lambda x: isinstance(x, list) and all(isinstance(k, str) for k in x),
    expected_type=list
)

default_refiner_model_name = default_refiner = get_config_item_or_set_default(
    key='default_refiner',
    default_value='None',
    validator=lambda x: isinstance(x, str),
    expected_type=str
).replace('\\', os.sep).replace('/', os.sep)
default_refiner_switch = get_config_item_or_set_default(
    key='default_refiner_switch',
    default_value=0.60,
    validator=lambda x: isinstance(x, numbers.Number) and 0 <= x <= 1,
    expected_type=numbers.Number
)

default_loras = get_config_item_or_set_default(
    key='default_loras',
    default_value=[
        [
            True,
            "None",
            1.0
        ],
        [
            True,
            "None",
            1.0
        ],
        [
            True,
            "None",
            1.0
        ],
        [
            True,
            "None",
            1.0
        ],
        [
            True,
            "None",
            1.0
        ]
    ],
    validator=lambda x: isinstance(x, list) and all(
        len(y) == 3 and isinstance(y[0], bool) and isinstance(y[1], str) and isinstance(y[2], numbers.Number)
        or len(y) == 2 and isinstance(y[0], str) and isinstance(y[1], numbers.Number)
        for y in x)
)
default_loras = [(y[0], y[1].replace('\\', os.sep).replace('/', os.sep), y[2]) if len(y) == 3 else (True, y[0].replace('\\', os.sep).replace('/', os.sep), y[1]) for y in default_loras]

default_max_lora_number = get_config_item_or_set_default(
    key='default_max_lora_number',
    default_value=len(default_loras) if isinstance(default_loras, list) and len(default_loras) > 0 else ads.default['max_lora_number'],
    validator=lambda x: isinstance(x, int) and x >= 1
)

ads.init_all_params_index(default_max_lora_number, args_manager.args.disable_metadata)

default_loras_min_weight = get_config_item_or_set_default(
    key='default_loras_min_weight',
    default_value=ads.default['loras_min_weight'],
    validator=lambda x: isinstance(x, numbers.Number) and -10 <= x <= 10,
    expected_type=numbers.Number
)
default_loras_max_weight = get_config_item_or_set_default(
    key='default_loras_max_weight',
    default_value=ads.default['loras_max_weight'],
    validator=lambda x: isinstance(x, numbers.Number) and -10 <= x <= 10,
    expected_type=numbers.Number
)

default_cfg_scale = get_config_item_or_set_default(
    key='default_cfg_scale',
    default_value=7.0,
    validator=lambda x: isinstance(x, numbers.Number),
    expected_type=numbers.Number
)
default_sample_sharpness = get_config_item_or_set_default(
    key='default_sample_sharpness',
    default_value=2.0,
    validator=lambda x: isinstance(x, numbers.Number),
    expected_type=numbers.Number
)

default_sampler = get_config_item_or_set_default(
    key='default_sampler',
    default_value='dpmpp_2m_sde_gpu',
    validator=lambda x: x in modules.flags.sampler_list if backend_engine == 'Fooocus' else modules.flags.comfy_sampler_list,
    expected_type=str
)
default_scheduler = get_config_item_or_set_default(
    key='default_scheduler',
    default_value=ads.default['scheduler_name'],
    validator=lambda x: x in modules.flags.scheduler_list if backend_engine == 'Fooocus' else modules.flags.comfy_scheduler_list,
    expected_type=str
)
default_vae = get_config_item_or_set_default(
    key='default_vae',
    default_value=modules.flags.default_vae,
    validator=lambda x: isinstance(x, str),
    expected_type=str
)
default_clip_skip = get_config_item_or_set_default(
    key='default_clip_skip',
    default_value=2,
    validator=lambda x: isinstance(x, int) and 1 <= x <= modules.flags.clip_skip_max,
    expected_type=int
)

default_cfg_tsnr = get_config_item_or_set_default(
    key='default_cfg_tsnr',
    default_value=ads.default['adaptive_cfg'],
    validator=lambda x: isinstance(x, numbers.Number),
    expected_type=numbers.Number
)
default_overwrite_switch = get_config_item_or_set_default(
    key='default_overwrite_switch',
    default_value=ads.default['overwrite_switch'],
    validator=lambda x: isinstance(x, int),
    expected_type=int
)

checkpoint_downloads = get_config_item_or_set_default(
    key='checkpoint_downloads',
    default_value={},
    validator=lambda x: isinstance(x, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in x.items()),
    expected_type=dict
)
lora_downloads = get_config_item_or_set_default(
    key='lora_downloads',
    default_value={},
    validator=lambda x: isinstance(x, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in x.items()),
    expected_type=dict
)
embeddings_downloads = get_config_item_or_set_default(
    key='embeddings_downloads',
    default_value={},
    validator=lambda x: isinstance(x, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in x.items()),
    expected_type=dict
)
vae_downloads = get_config_item_or_set_default(
    key='vae_downloads',
    default_value={},
    validator=lambda x: isinstance(x, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in x.items()),
    expected_type=dict
)

default_inpaint_engine_version = get_config_item_or_set_default(
    key='default_inpaint_engine_version',
    default_value=ads.default['inpaint_engine'],
    validator=lambda x: x in modules.flags.inpaint_engine_versions,
    expected_type=str
)
default_selected_image_input_tab_id = get_config_item_or_set_default(
    key='default_selected_image_input_tab_id',
    default_value=modules.flags.default_input_image_tab,
    validator=lambda x: x in modules.flags.input_image_tab_ids,
    expected_type=str
)
default_uov_method = get_config_item_or_set_default(
    key='default_uov_method',
    default_value=modules.flags.disabled,
    validator=lambda x: x in modules.flags.uov_list,
    expected_type=str
)
default_controlnet_image_count = get_config_item_or_set_default(
    key='default_controlnet_image_count',
    default_value=4,
    validator=lambda x: isinstance(x, int) and x > 0,
    expected_type=int
)
default_ip_images = {}
default_ip_stop_ats = {}
default_ip_weights = {}
default_ip_types = {}

for image_count in range(default_controlnet_image_count):
    image_count += 1
    default_ip_images[image_count] = get_config_item_or_set_default(
        key=f'default_ip_image_{image_count}',
        default_value='None',
        validator=lambda x: x == 'None' or isinstance(x, str) and os.path.exists(x),
        expected_type=str
    )

    if default_ip_images[image_count] == 'None':
        default_ip_images[image_count] = None

    default_ip_types[image_count] = get_config_item_or_set_default(
        key=f'default_ip_type_{image_count}',
        default_value=modules.flags.default_ip,
        validator=lambda x: x in modules.flags.ip_list,
        expected_type=str
    )

    default_end, default_weight = modules.flags.default_parameters[default_ip_types[image_count]]

    default_ip_stop_ats[image_count] = get_config_item_or_set_default(
        key=f'default_ip_stop_at_{image_count}',
        default_value=default_end,
        validator=lambda x: isinstance(x, float) and 0 <= x <= 1,
        expected_type=float
    )
    default_ip_weights[image_count] = get_config_item_or_set_default(
        key=f'default_ip_weight_{image_count}',
        default_value=default_weight,
        validator=lambda x: isinstance(x, float) and 0 <= x <= 2,
        expected_type=float
    )

default_inpaint_advanced_masking_checkbox = get_config_item_or_set_default(
    key='default_inpaint_advanced_masking_checkbox',
    default_value=ads.default['inpaint_advanced_masking_checkbox'],
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_inpaint_method = get_config_item_or_set_default(
    key='default_inpaint_method',
    default_value=modules.flags.inpaint_option_default,
    validator=lambda x: x in modules.flags.inpaint_options,
    expected_type=str
)

default_overwrite_upscale = get_config_item_or_set_default(
    key='default_overwrite_upscale',
    default_value=0.382,
    validator=lambda x: isinstance(x, numbers.Number)
)

example_inpaint_prompts = get_config_item_or_set_default(
    key='example_inpaint_prompts',
    default_value=[
        "highly detailed face", "detailed woman's face", "detailed man's face", "detailed hand", "beautiful eyes"
    ],
    validator=lambda x: isinstance(x, list) and all(isinstance(v, str) for v in x),
    expected_type=list
)
example_enhance_detection_prompts = get_config_item_or_set_default(
    key='example_enhance_detection_prompts',
    default_value=[
        "face", "eye", "mouth", "hair", "hand", "body"
    ],
    validator=lambda x: isinstance(x, list) and all(isinstance(v, str) for v in x),
    expected_type=list
)
default_enhance_tabs = get_config_item_or_set_default(
    key='default_enhance_tabs',
    default_value=3,
    validator=lambda x: isinstance(x, int) and 1 <= x <= 5,
    expected_type=int
)
default_enhance_uov_method = get_config_item_or_set_default(
    key='default_enhance_uov_method',
    default_value=modules.flags.disabled,
    validator=lambda x: x in modules.flags.uov_list,
    expected_type=int
)
default_enhance_uov_processing_order = get_config_item_or_set_default(
    key='default_enhance_uov_processing_order',
    default_value=modules.flags.enhancement_uov_before,
    validator=lambda x: x in modules.flags.enhancement_uov_processing_order,
    expected_type=int
)
default_enhance_uov_prompt_type = get_config_item_or_set_default(
    key='default_enhance_uov_prompt_type',
    default_value=modules.flags.enhancement_uov_prompt_type_original,
    validator=lambda x: x in modules.flags.enhancement_uov_prompt_types,
    expected_type=int
)
default_sam_max_detections = get_config_item_or_set_default(
    key='default_sam_max_detections',
    default_value=0,
    validator=lambda x: isinstance(x, int) and 0 <= x <= 10,
    expected_type=int
)
default_black_out_nsfw = get_config_item_or_set_default(
    key='default_black_out_nsfw',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_save_only_final_enhanced_image = get_config_item_or_set_default(
    key='default_save_only_final_enhanced_image',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_save_metadata_to_images = get_config_item_or_set_default(
    key='default_save_metadata_to_images',
    default_value=ads.default['save_metadata_to_images'],
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_metadata_scheme = get_config_item_or_set_default(
    key='default_metadata_scheme',
    default_value='Fooocus',
    validator=lambda x: x in [y[1] for y in modules.flags.metadata_scheme if y[1] == x],
    expected_type=str
)
metadata_created_by = get_config_item_or_set_default(
    key='metadata_created_by',
    default_value='FooocusPlus',
    validator=lambda x: isinstance(x, str),
    expected_type=str
)
show_newest_images_first = get_config_item_or_set_default(
    key='show_newest_images_first',
    default_value=True,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)

example_inpaint_prompts = [[x] for x in example_inpaint_prompts]
example_enhance_detection_prompts = [[x] for x in example_enhance_detection_prompts]

default_comfyd_active_checkbox = get_config_item_or_set_default(
    key='default_comfyd_active_checkbox',
    default_value=ads.default['comfyd_active_checkbox'],
    validator=lambda x: isinstance(x, bool)
)
default_image_catalog_checkbox = get_config_item_or_set_default(
    key='default_image_catalog_checkbox',
    default_value=True,
    validator=lambda x: isinstance(x, bool)
)
default_image_catalog_max_number = get_config_item_or_set_default(
    key='default_image_catalog_max_number',
    default_value=ads.default['image_catalog_max_number'],
    validator=lambda x: isinstance(x, int),
    expected_type=int
)
default_backfill_prompt = get_config_item_or_set_default(
    key='default_backfill_prompt',
    default_value=ads.default['backfill_prompt'],
    validator=lambda x: isinstance(x, bool)
)
default_translation_methods = get_config_item_or_set_default(
    key='default_translation_methods',
    default_value=ads.default['translation_methods'],
    validator=lambda x: x in modules.flags.translation_methods
)

default_invert_mask_checkbox = get_config_item_or_set_default(
    key='default_invert_mask_checkbox',
    default_value=False,
    validator=lambda x: isinstance(x, bool),
    expected_type=bool
)
default_inpaint_mask_model = get_config_item_or_set_default(
    key='default_inpaint_mask_model',
    default_value='isnet-general-use',
    validator=lambda x: x in modules.flags.inpaint_mask_models,
    expected_type=str
)
default_enhance_inpaint_mask_model = get_config_item_or_set_default(
    key='default_enhance_inpaint_mask_model',
    default_value='sam',
    validator=lambda x: x in modules.flags.inpaint_mask_models,
    expected_type=str
)
default_inpaint_mask_cloth_category = get_config_item_or_set_default(
    key='default_inpaint_mask_cloth_category',
    default_value='full',
    validator=lambda x: x in modules.flags.inpaint_mask_cloth_category,
    expected_type=str
)
default_inpaint_mask_sam_model = get_config_item_or_set_default(
    key='default_inpaint_mask_sam_model',
    default_value='vit_b',
    validator=lambda x: x in modules.flags.inpaint_mask_sam_model,
    expected_type=str
)
default_inpaint_mask_model = get_config_item_or_set_default(
    key='default_inpaint_mask_model',
    default_value='isnet-general-use',
    validator=lambda x: x in modules.flags.inpaint_mask_models
)
default_inpaint_mask_cloth_category = get_config_item_or_set_default(
    key='default_inpaint_mask_cloth_category',
    default_value='full',
    validator=lambda x: x in modules.flags.inpaint_mask_cloth_category
)
default_inpaint_mask_sam_model = get_config_item_or_set_default(
    key='default_inpaint_mask_sam_model',
    default_value='sam_vit_b_01ec64',
    validator=lambda x: x in modules.flags.inpaint_mask_sam_model
)
default_mixing_image_prompt_and_vary_upscale = get_config_item_or_set_default(
    key='default_mixing_image_prompt_and_vary_upscale',
    default_value=ads.default['mixing_image_prompt_and_vary_upscale'],
    validator=lambda x: isinstance(x, bool)
)
default_mixing_image_prompt_and_inpaint = get_config_item_or_set_default(
    key='default_mixing_image_prompt_and_inpaint',
    default_value=ads.default['mixing_image_prompt_and_inpaint'],
    validator=lambda x: isinstance(x, bool)
)

default_freeu = ads.default['freeu']
default_adm_guidance = [ads.default['adm_scaler_positive'], ads.default['adm_scaler_negative'], ads.default['adm_scaler_end']]
styles_definition = {}
instruction = ''
reference = ''

config_dict["default_loras"] = default_loras = default_loras[:default_max_lora_number] + [[True, 'None', 1.0] for _ in range(default_max_lora_number - len(default_loras))]


# mapping config to meta parameter
possible_preset_keys = {
    "default_engine": "engine",
    "default_model": "base_model",
    "default_refiner": "refiner_model",
    "default_refiner_switch": "refiner_switch",
    "previous_default_models": "previous_default_models",
    "default_loras_min_weight": "loras_min_weight",
    "default_loras_max_weight": "loras_max_weight",
    "default_loras": "<processed>",
    "default_cfg_scale": "guidance_scale",
    "default_sample_sharpness": "sharpness",
    "default_cfg_tsnr": "adaptive_cfg",
    "default_clip_skip": "clip_skip",
    "default_sampler": "sampler",
    "default_scheduler": "scheduler",
    "default_overwrite_step": "steps",
    "default_overwrite_switch": "overwrite_switch",
    "default_performance": "performance",

    "default_prompt": "prompt",
    "default_prompt_negative": "negative_prompt",
    "default_extra_variation": "extra_variation",
    "default_styles": "styles",
    "default_aspect_ratio": "resolution",
    "default_save_metadata_to_images": "save_metadata_to_images",
    "checkpoint_downloads": "checkpoint_downloads",
    "embeddings_downloads": "embeddings_downloads",
    "lora_downloads": "lora_downloads",
    "vae_downloads": "vae_downloads",
    "default_vae": "vae",
    # "default_inpaint_method": "inpaint_method", # disabled so inpaint mode doesn't refresh after every preset change
    "default_inpaint_engine_version": "inpaint_engine_version",

    "default_image_quantity": "image_quantity",
    "default_max_image_quantity": "max_image_quantity",
    "default_freeu": "freeu",
    "default_adm_guidance": "adm_guidance",
    "default_output_format": "output_format",
    #"default_controlnet_softness": "controlnet_softness",
    #"default_overwrite_vary_strength": "overwrite_vary_strength",
    #"default_overwrite_upscale_strength": "overwrite_upscale_strength",
    "default_inpaint_advanced_masking_checkbox": "inpaint_advanced_masking_checkbox",
    "default_mixing_image_prompt_and_vary_upscale": "mixing_image_prompt_and_vary_upscale",
    "default_mixing_image_prompt_and_inpaint": "mixing_image_prompt_and_inpaint",
    "default_backfill_prompt": "backfill_prompt",
    "default_translation_methods": "translation_methods",
    "default_image_catalog_max_number": "image_catalog_max_number",
    "styles_definition": "styles_definition",
    "instruction": "instruction",
    "reference": "reference",
}

allow_missing_preset_key = [
    "default_prompt",
    "default_prompt_negative",
    "default_extra_variation",
    "default_aspect_ratio",
    "default_save_metadata_to_images",
    "default_vae",
    "vae_downloads",
    "default_inpaint_engine_version",
    "default_image_quantity",
    "default_max_image_quantity",
    "default_freeu",
    "default_adm_guidance",
    "default_output_format",
    "default_inpaint_advanced_masking_checkbox",
    "default_mixing_image_prompt_and_vary_upscale",
    "default_mixing_image_prompt_and_inpaint",
    "default_backfill_prompt",
    "default_translation_methods",
    "default_image_catalog_max_number",
    "styles_definition",
    "instruction",
    "reference",
    "previous_default_models",
    ]


# Only write to config.txt in the first launch
if not os.path.exists(config_path):
    with open(config_path, "w", encoding="utf-8") as json_file:
        # write all the parameters to config.txt, just like the tutorial
        json.dump({k: config_dict[k] for k in visited_keys}, json_file, indent=4)
#        json.dump({k: config_dict[k] for k in always_save_keys}, json_file, indent=4)

# Always write to the tutorial
with open(config_example_path, "w", encoding="utf-8") as json_file:
    cpa = config_path.replace("\\", "\\\\")
    json_file.write(f'You can modify your "{cpa}" using the examples below.\n'
                    f'This file is an example tutorial and modifications to this file will have no effect.\n'
                    f'Please edit "{cpa}" to actually change the settings.\n'
                    'Remember to split the paths with "\\\\" rather than "\\", '
                    'and there is no "," before the last "}". \n\n')
    json.dump({k: config_dict[k] for k in visited_keys}, json_file, indent=4)


config_comfy_path = os.path.join(common.ROOT,'comfy/extra_model_paths.yaml')
config_comfy_formatted_text = '''
comfyui:
     models_root: {models_root}
     checkpoints: {checkpoints}
     clip_vision: {clip_vision}
     clip: {clip}
     controlnet: {controlnets}
     diffusers: {diffusers}
     embeddings: {embeddings}
     loras: {loras}
     upscale_models: {upscale_models}
     unet: {unet}
     rembg: {rembg}
     layer_model: {layer_model}
     vae: {vae}
     '''

paths2str = lambda p,n: p[0] if len(p)<=1 else '|\n'+''.join([' ']*(5+len(n)))+''.join(['\n']+[' ']*(5+len(n))).join(p)
config_comfy_text = config_comfy_formatted_text.format(models_root=path_models_root, checkpoints=paths2str(paths_checkpoints,'checkpoints'), clip_vision=path_clip_vision, clip=path_clip, controlnets=paths2str(paths_controlnet,'controlnet'), diffusers=paths2str(paths_diffusers,'diffusers'), embeddings=path_embeddings, loras=paths2str(paths_loras, 'loras'), upscale_models=path_upscale_models, unet=paths2str([path_unet]+paths_checkpoints, 'unet'), rembg=path_rembg, layer_model=path_layer_model, vae=path_vae)
with open(config_comfy_path, "w", encoding="utf-8") as comfy_file:
    comfy_file.write(config_comfy_text)

model_filenames = []
lora_filenames = []
vae_filenames = []
wildcard_filenames = []

def get_model_filenames(folder_paths, extensions=None, name_filter=None):
    if extensions is None:
        extensions = ['.pth', '.ckpt', '.bin', '.safetensors', '.fooocus.patch', '.gguf']
    files = []

    if not isinstance(folder_paths, list):
        folder_paths = [folder_paths]
    for folder in folder_paths:
        files += get_files_from_folder(folder, extensions, name_filter)

    return files


def get_base_model_list(engine='Fooocus', task_method=None):
    global modelsinfo
    file_filter = modules.flags.model_file_filter.get(engine, [])
    base_model_list = modelsinfo.get_model_names('checkpoints', file_filter)
    if engine in ['Fooocus', 'Comfy']:
        base_model_list = modelsinfo.get_model_names('checkpoints', modules.flags.model_file_filter['Fooocus'], reverse=True)
    elif task_method == 'flux_base2_gguf':
        # adjusted the GGUF filter to include "flux" and "schnell",
        # not just "hyperflux"
        base_model_list = [f for f in base_model_list if ("hyp8" in f or "hyp16" in f or "flux" in f or "schnell" in f) and f.endswith("gguf")]
    return base_model_list

def update_files(engine='Fooocus', task_method=None):    # called by the webui update button & by launch.py
    global modelsinfo, model_filenames, lora_filenames, vae_filenames, wildcard_filenames
    modelsinfo.refresh_from_path()
    model_filenames = get_base_model_list(engine, task_method)
    lora_filenames = modelsinfo.get_model_names('loras')
    vae_filenames = modelsinfo.get_model_names('vae')
    wildcard_filenames = get_files_from_folder(path_wildcards, ['.txt'])
    available_presets = PR.get_preset_list()
    return model_filenames, lora_filenames, vae_filenames

def downloading_inpaint_models(v):
    if not v:
        v = 'v2.6'

    load_file_from_url(
        url='https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/fooocus_inpaint_head.pth',
        model_dir=paths_inpaint[0],
        file_name='fooocus_inpaint_head.pth'
    )
    head_file = os.path.join(paths_inpaint[0], 'fooocus_inpaint_head.pth')
    patch_file = None

    if v == 'v2.5':
        load_file_from_url(
            url='https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/inpaint_v25.fooocus.patch',
            model_dir=paths_inpaint[0],
            file_name='inpaint_v25.fooocus.patch'
        )
        patch_file = os.path.join(paths_inpaint[0], 'inpaint_v25.fooocus.patch')
    else:   # i.e. v=='v2.6'
        load_file_from_url(
            url='https://huggingface.co/lllyasviel/fooocus_inpaint/resolve/main/inpaint_v26.fooocus.patch',
            model_dir=paths_inpaint[0],
            file_name='inpaint_v26.fooocus.patch'
        )
        patch_file = os.path.join(paths_inpaint[0], 'inpaint_v26.fooocus.patch')

    return head_file, patch_file


def downloading_sdxl_lcm_lora():
    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/sdxl_lcm_lora.safetensors',
        model_dir=paths_loras[0],
        file_name=modules.flags.PerformanceLoRA.Extreme_Speed.value
    )
    return modules.flags.PerformanceLoRA.Extreme_Speed.value


def downloading_sdxl_lightning_lora():
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sdxl_lightning_4step_lora.safetensors',
        model_dir=paths_loras[0],
        file_name=modules.flags.PerformanceLoRA.Lightning.value
    )
    return modules.flags.PerformanceLoRA.Lightning.value


def downloading_sdxl_hyper_sd_lora():
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sdxl_hyper_sd_4step_lora.safetensors',
        model_dir=paths_loras[0],
        file_name=modules.flags.PerformanceLoRA.Hyper_SD.value
    )
    return modules.flags.PerformanceLoRA.Hyper_SD.value


def downloading_controlnet_canny():
    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/control-lora-canny-rank128.safetensors',
        model_dir=paths_controlnet[0],
        file_name='control-lora-canny-rank128.safetensors'
    )
    return os.path.join(paths_controlnet[0], 'control-lora-canny-rank128.safetensors')


def downloading_controlnet_cpds():
    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/fooocus_xl_cpds_128.safetensors',
        model_dir=paths_controlnet[0],
        file_name='fooocus_xl_cpds_128.safetensors'
    )
    return os.path.join(paths_controlnet[0], 'fooocus_xl_cpds_128.safetensors')


def downloading_ip_adapters(v):
    assert v in ['ip', 'face']

    results = []

    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/clip_vision_vit_h.safetensors',
        model_dir=path_clip_vision,
        file_name='clip_vision_vit_h.safetensors'
    )
    results += [os.path.join(path_clip_vision, 'clip_vision_vit_h.safetensors')]

    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/fooocus_ip_negative.safetensors',
        model_dir=paths_controlnet[0],
        file_name='fooocus_ip_negative.safetensors'
    )
    results += [os.path.join(paths_controlnet[0], 'fooocus_ip_negative.safetensors')]

    if v == 'ip':
        load_file_from_url(
            url='https://huggingface.co/lllyasviel/misc/resolve/main/ip-adapter-plus_sdxl_vit-h.bin',
            model_dir=paths_controlnet[0],
            file_name='ip-adapter-plus_sdxl_vit-h.bin'
        )
        results += [os.path.join(paths_controlnet[0], 'ip-adapter-plus_sdxl_vit-h.bin')]

    if v == 'face':
        load_file_from_url(
            url='https://huggingface.co/lllyasviel/misc/resolve/main/ip-adapter-plus-face_sdxl_vit-h.bin',
            model_dir=paths_controlnet[0],
            file_name='ip-adapter-plus-face_sdxl_vit-h.bin'
        )
        results += [os.path.join(paths_controlnet[0], 'ip-adapter-plus-face_sdxl_vit-h.bin')]

    return results


def downloading_upscale_model():
    load_file_from_url(
        url='https://huggingface.co/lllyasviel/misc/resolve/main/fooocus_upscaler_s409985e5.bin',
        model_dir=path_upscale_models,
        file_name='fooocus_upscaler_s409985e5.bin'
    )
    return os.path.join(path_upscale_models, 'fooocus_upscaler_s409985e5.bin')

def downloading_safety_checker_model():
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/stable-diffusion-safety-checker.bin',
        model_dir=path_safety_checker,
        file_name='stable-diffusion-safety-checker.bin'
    )
    return os.path.join(path_safety_checker, 'stable-diffusion-safety-checker.bin')

def download_sam_model(sam_model: str) -> str:
    match sam_model:
        case 'vit_b':
            return downloading_sam_vit_b()
        case 'vit_l':
            return downloading_sam_vit_l()
        case 'vit_h':
            return downloading_sam_vit_h()
        case _:
            raise ValueError(f"sam model {sam_model} does not exist.")


def downloading_sam_vit_b():
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sam_vit_b_01ec64.pth',
        model_dir=path_sam,
        file_name='sam_vit_b_01ec64.pth'
    )
    return os.path.join(path_sam, 'sam_vit_b_01ec64.pth')


def downloading_sam_vit_l():
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sam_vit_l_0b3195.pth',
        model_dir=path_sam,
        file_name='sam_vit_l_0b3195.pth'
    )
    return os.path.join(path_sam, 'sam_vit_l_0b3195.pth')


def downloading_sam_vit_h():
    load_file_from_url(
        url='https://huggingface.co/mashb1t/misc/resolve/main/sam_vit_h_4b8939.pth',
        model_dir=path_sam,
        file_name='sam_vit_h_4b8939.pth'
    )
    return os.path.join(path_sam, 'sam_vit_h_4b8939.pth')

def downloading_superprompter_model():
    path_superprompter = os.path.join(paths_llms[0], "superprompt-v1")
    load_file_from_url(
        url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/model.safetensors',
        model_dir=path_superprompter,
        file_name='model.safetensors'
    )
    load_file_from_url(
    url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/config.json',
    model_dir=path_superprompter,
    file_name='config.json'
    )
    load_file_from_url(
    url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/generation_config.json',
    model_dir=path_superprompter,
    file_name='generation_config.json'
    )
    load_file_from_url(
    url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/README.md',
    model_dir=path_superprompter,
    file_name='README.md'
    )
    load_file_from_url(
    url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/spiece.model',
    model_dir=path_superprompter,
    file_name='spiece.model'
    )
    load_file_from_url(
    url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/tokenizer.json',
    model_dir=path_superprompter,
    file_name='tokenizer.json'
    )
    load_file_from_url(
    url='https://huggingface.co/roborovski/superprompt-v1/resolve/main/tokenizer_config.json',
    model_dir=path_superprompter,
    file_name='tokenizer_config.json'
    )
    return os.path.join(path_superprompter, 'model.safetensors')


def downloading_hydit_model():
    load_file_from_url(
        url='https://huggingface.co/comfyanonymous/hunyuan_dit_comfyui/resolve/main/hunyuan_dit_1.2.safetensors',
        model_dir=paths_checkpoints[0] + '\Alternative',
        file_name='hunyuan_dit_1.2.safetensors'
    )
    return os.path.join(paths_checkpoints[0] + '\Alternative', 'hunyuan_dit_1.2.safetensors')

def downloading_base_sd15_model():
    model_path = Path(user_dir/'models/checkpoints/SD1.5/')
    model_file_name = 'realisticVisionV60B1_v51VAE.safetensors'
    load_file_from_url(
        url= 'https://huggingface.co/moiu2998/mymo/resolve/3c3093fa083909be34a10714c93874ce5c9dabc4/realisticVisionV60B1_v51VAE.safetensors?download=true',
        model_dir = model_path,
        file_name = model_file_name
    )
    return str(Path(model_path/model_file_name))

def downloading_sd3_medium_model():
    load_file_from_url(
        url='https://huggingface.co/lone682/sd3/resolve/2d024507b65a18772e10825f4dd383cdc3800a9f/sd3_medium_incl_clips_t5xxlfp8.safetensors?download=true',
        model_dir=paths_checkpoints[0] + '\SD3x',
        file_name='sd3_medium_incl_clips_t5xxlfp8.safetensors'
    )
    return os.path.join(paths_checkpoints[0] + '\SD3x', 'sd3_medium_incl_clips_t5xxlfp8.safetensors')

def downloading_sd35_large_model():
    load_file_from_url(
        url='https://civitai.com/api/download/models/983309?type=Model&format=SafeTensor&size=full&fp=fp32',
        model_dir=paths_checkpoints[0] + '\SD3x',
        file_name='stableDiffusion35_large.safetensors'
    )
    return os.path.join(paths_checkpoints[0] + '\SD3x', 'stableDiffusion35_large.safetensors')


update_files()


# Aspect Ratio support
default_aspect_ratio_values = [default_standard_aspect_ratio, default_shortlist_aspect_ratio,\
    default_sd1_5_aspect_ratio, default_pixart_aspect_ratio]

config_aspect_ratios = [available_standard_aspect_ratios, available_shortlist_aspect_ratios,\
    available_sd1_5_aspect_ratios, available_pixart_aspect_ratios,]

# Common support for prompt & image quantity preservation
# during preset switching
common.positive = default_prompt
common.negative = default_prompt_negative
common.image_quantity = default_image_quantity

# Common support, typically for Gradio errors in updating system dictionary
common.refiner_slider = default_refiner_switch
common.sampler_name = default_sampler
common.scheduler_name = default_scheduler

# Preset support in neutral (common) ground
common.default_bar_category = default_bar_category
common.preset_bar_length = preset_bar_length
common.is_low_vram_preset = default_low_vram_presets

# Flags support
modules.flags.custom_performance = custom_performance_steps
