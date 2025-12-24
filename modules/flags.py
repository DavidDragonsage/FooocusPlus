from enum import IntEnum, Enum


disabled = 'Disabled'
enabled = 'Enabled'
subtle_variation = 'Vary'
upscale_15 = 'Upscale (1.5x)'
upscale_2 = 'Upscale (2x)'
upscale_fast = 'Upscale (Fast 2x)'

# set by modules.config:
custom_performance = 15

uov_list = [disabled, subtle_variation, upscale_15, upscale_2, upscale_fast]

enhancement_uov_before = "Before First Enhancement"
enhancement_uov_after = "After Last Enhancement"
enhancement_uov_processing_order = [enhancement_uov_before, enhancement_uov_after]

enhancement_uov_prompt_type_original = 'Original Prompts'
enhancement_uov_prompt_type_last_filled = 'Last Filled Enhancement Prompts'
enhancement_uov_prompt_types = [enhancement_uov_prompt_type_original, enhancement_uov_prompt_type_last_filled]

CIVITAI_NO_KARRAS = ["euler", "euler_ancestral", "heun", "dpm_fast", "dpm_adaptive", "ddim", "uni_pc"]

# fooocus: a1111 (Civitai)
KSAMPLER = {
    "euler": "Euler",
    "euler_ancestral": "Euler a",
    "heun": "Heun",
    "heunpp2": "",
    "dpm_2": "DPM2",
    "dpm_2_ancestral": "DPM2 a",
    "lms": "LMS",
    "dpm_fast": "DPM fast",
    "dpm_adaptive": "DPM adaptive",
    "dpmpp_2s_ancestral": "DPM++ 2S a",
    "dpmpp_sde": "DPM++ SDE",
    "dpmpp_sde_gpu": "DPM++ SDE",
    "dpmpp_2m": "DPM++ 2M",
    "dpmpp_2m_sde": "DPM++ 2M SDE",
    "dpmpp_2m_sde_gpu": "DPM++ 2M SDE",
    "dpmpp_3m_sde": "",
    "dpmpp_3m_sde_gpu": "",
    "ddpm": "",
    "lcm": "LCM",
    "tcd": "TCD",
    "restart": "Restart"
}

SAMPLER_EXTRA = {
    "ddim": "DDIM",
    "uni_pc": "UniPC",
    "uni_pc_bh2": ""
}

SAMPLERS = KSAMPLER | SAMPLER_EXTRA
KSAMPLER_NAMES = list(KSAMPLER.keys())
SAMPLER_NAMES = KSAMPLER_NAMES + list(SAMPLER_EXTRA.keys())
sampler_list = SAMPLER_NAMES

SCHEDULER_NAMES = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform", "lcm", "turbo", "align_your_steps", "tcd", "edm_playground_v2.5"]
scheduler_list = SCHEDULER_NAMES

clip_skip_max = 12

default_vae = 'Default (model)'

refiner_swap_method = 'joint'

default_input_image_tab = 'uov_tab'
input_image_tab_ids = ['uov_tab', 'ip_tab', 'inpaint_tab', 'enhance_tab', 'layer_tab']

cn_ip = "ImagePrompt"
cn_ip_face = "FaceSwap"
cn_canny = "PyraCanny"
cn_cpds = "CPDS"

ip_list = [cn_ip, cn_canny, cn_cpds, cn_ip_face]
default_ip = cn_ip

default_parameters = {
    cn_ip: (0.5, 0.6), cn_ip_face: (0.9, 0.75), cn_canny: (0.5, 1.0), cn_cpds: (0.5, 1.0)
}  # stop, weight

output_formats = ['png', 'jpeg', 'webp']

inpaint_mask_models = ['u2net', 'u2netp', 'u2net_human_seg', 'u2net_cloth_seg', 'silueta', 'isnet-general-use', 'isnet-anime', 'sam']
inpaint_mask_cloth_category = ['full', 'upper', 'lower']
inpaint_mask_sam_model = ['vit_b', 'vit_l', 'vit_h']

inpaint_engine_versions = ['None', 'v2.5', 'v2.6']
inpaint_option_default = 'Inpaint or Outpaint (default)'
inpaint_option_detail = 'Improve Detail (face, hand, eyes, etc.)'
inpaint_option_modify = 'Modify Content (add objects, change background, etc.)'
inpaint_options = [inpaint_option_default, inpaint_option_detail, inpaint_option_modify]

describe_type_photo = 'Photograph'
describe_type_anime = 'Art/Anime'
describe_types = [describe_type_photo, describe_type_anime]


COMFY_KSAMPLER_NAMES = ["euler", "euler_cfg_pp", "euler_ancestral", "euler_ancestral_cfg_pp", "heun", "heunpp2","dpm_2", "dpm_2_ancestral",
                  "lms", "dpm_fast", "dpm_adaptive", "dpmpp_2s_ancestral", "dpmpp_sde", "dpmpp_sde_gpu",
                  "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde", "dpmpp_3m_sde_gpu", "ddpm", "lcm",
                  "ipndm", "ipndm_v", "deis"]
comfy_scheduler_list = COMFY_SCHEDULER_NAMES = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform", "beta"]
comfy_sampler_list = COMFY_SAMPLER_NAMES = COMFY_KSAMPLER_NAMES + ["ddim", "uni_pc", "uni_pc_bh2"]

backend_engines = ['Fooocus', 'Comfy', 'Kolors', 'Kolors+', 'SD3x', 'HyDiT', 'HyDiT+', 'Flux']

model_file_filter = {
        'SD3x'   : ['sd3'],
        'Flux'   : ['flux'],
        'HyDiT'  : ['hunyuan'],
        }
model_file_filter['Fooocus'] = model_file_filter['SD3x'] + model_file_filter['Flux'] + model_file_filter['HyDiT']


task_class_mapping = {
            'Fooocus': 'SDXL-Fooocus',
            'Comfy'  : 'SDXL-Comfy',
            'Kolors' : 'Kwai-Kolors',
            'Kolors+': 'Kwai-Kolors+',
            'SD3m'   : 'SD3m',
            'SD3x'   : 'SD3.5x',
            'HyDiT'  : 'Hunyuan-DiT',
            'HyDiT+' : 'Hunyuan-DiT+',
            'Flux'   : 'Flux.1',
            'SD1'    : 'SD1',
            }
def get_taskclass_by_fullname(fullname):
    for taskclass, fname in task_class_mapping.items():
        if fname == fullname:
            return taskclass
    return None

comfy_classes = ['Comfy', 'Kolors', 'Kolors+', 'SD3x', 'HyDiT+', 'Flux', 'SD1']

default_class_params = {
    'Fooocus': {
        'disvisible': [],
        'disinteractive': [],
        'available_aspect_ratios_selection': 'Standard',
        'available_sampler_name': sampler_list,
        'available_scheduler_name': scheduler_list,
        'backend_params': {},
        },
    'Comfy': {
        'disvisible': [],
        'disinteractive': [],
        'available_aspect_ratios_selection': 'Standard',
        'available_sampler_name': comfy_sampler_list,
        'available_scheduler_name': comfy_scheduler_list,
        'backend_params': {},
        },
    'Kolors': {
        'disvisible': ["backend_selection", "performance_selection", "refiner_model"],
        'disinteractive': ["input_image_checkbox", "enhance_checkbox", "performance_selection", "base_model", "overwrite_step", "refiner_model"],
        'available_aspect_ratios_selection': 'Standard',
        'available_sampler_name': comfy_sampler_list,
        'available_scheduler_name': comfy_scheduler_list,
        'backend_params': {
            "task_method": "kolors_text2image1",
            "llms_model": "quant8",
            },
        },
    'Kolors+': {
        'disvisible': ["backend_selection", "performance_selection", "refiner_model"],
        'disinteractive': ["input_image_checkbox", "enhance_checkbox", "performance_selection", "base_model", "overwrite_step", "refiner_model"],
        'available_aspect_ratios_selection': 'Standard',
        'available_sampler_name': comfy_sampler_list,
        'available_scheduler_name': comfy_scheduler_list,
        'backend_params': {
            "task_method": "kolors_text2image2",
            "llms_model": "quant8",
            },
        },
    'SD3x': {
        'disvisible': ["backend_selection", "performance_selection", "refiner_model"],
        'disinteractive': ["input_image_checkbox", "enhance_checkbox", "performance_selection", "loras", "refiner_model"],
        'available_aspect_ratios_selection': 'Standard',
        'available_sampler_name': comfy_sampler_list,
        'available_scheduler_name': comfy_scheduler_list,
        'backend_params': {
            "task_method": "sd3_base",
            },
        },
    'HyDiT': {
        'disvisible': ["backend_selection", "performance_selection", "refiner_model"],
        'disinteractive': ["input_image_checkbox", "enhance_checkbox", "performance_selection", "base_model", "loras", "refiner_model", "scheduler_name"],
        'available_aspect_ratios_selection': 'Standard',
        'available_sampler_name': ["ddpm", "ddim", "dpmms"],
        'backend_params': {
            "task_method": "hydit_base",
            },
        },
    'HyDiT+': {
        'disvisible': ["backend_selection", "performance_selection", "refiner_model"],
        'disinteractive': ["input_image_checkbox", "enhance_checkbox", "performance_selection", "base_model", "loras" "scheduler_name"],
        'available_aspect_ratios_selection': 'Standard',
        'available_sampler_name': comfy_sampler_list,
        'available_scheduler_name': comfy_scheduler_list,
        'backend_params': {
            "task_method": "hydit_base",
            },
        },
    'Flux': {
        'disvisible': ["backend_selection", "performance_selection", "refiner_model"],
        'disinteractive': ["input_image_checkbox", "enhance_checkbox", "performance_selection", "loras-4", "refiner_model"],
        'available_aspect_ratios_selection': 'Standard',
        'available_sampler_name': comfy_sampler_list,
        'available_scheduler_name': comfy_scheduler_list,
        'backend_params': {
            "task_method": "flux_base",
            "clip_model": "auto",
            "base_model_dtype": "auto",
            },
        },
    'SD1': {
        'disvisible': ["backend_selection", "performance_selection"],
        'disinteractive': ["input_image_checkbox", "enhance_checkbox", "performance_selection", "loras", "refiner_model"],
        'available_aspect_ratios_selection': 'SD1.5',
        'available_sampler_name': sampler_list,
        'available_scheduler_name': scheduler_list,
        "backend_params": {"task_method": "SD_SIMPLE"}
        },
    }

get_engine_default_params = lambda x: default_class_params['Fooocus'] if x not in default_class_params else default_class_params[x]
get_engine_default_backend_params = lambda x: get_engine_default_params(x).get('backend_params', default_class_params['Fooocus']['backend_params'])

class MetadataScheme(Enum):
    FOOOCUS = 'fooocus'
    SIMPLE = 'simple'
    A1111 = 'a1111'

metadata_scheme = [
    ('Fooocus', MetadataScheme.SIMPLE.value),
    ('A1111', MetadataScheme.A1111.value),
]

class OutputFormat(Enum):
    PNG = 'png'
    JPEG = 'jpeg'
    WEBP = 'webp'

    @classmethod
    def list(cls) -> list:
        return list(map(lambda c: c.value, cls))


class PerformanceLoRA(Enum):
    Quality = None
    Speed = None
    Custom = None
    Extreme_Speed = 'sdxl_lcm_lora.safetensors'
    Lightning = 'sdxl_lightning_4step_lora.safetensors'
    Hyper_SD = 'sdxl_hyper_sd_4step_lora.safetensors'


class Steps(IntEnum):
    Quality = 60
    Speed = 30
    Custom = custom_performance # from modules.config
    Extreme_Speed = 8
    Lightning = 4
    Hyper_SD = 4

    @classmethod
    def keys(cls) -> list:
        return list(map(lambda c: c, Steps.__members__))


class StepsUOV(IntEnum):
    Quality = 36
    Speed = 18
    Custom = 12
    Extreme_Speed = 8
    Lightning = 4
    Hyper_SD = 4


class Performance(Enum):
    Quality = 'Quality'
    Speed = 'Speed'
    Custom = 'Custom'
    Extreme_Speed = 'Extreme Speed'
    Lightning = 'Lightning'
    Hyper_SD = 'Hyper-SD'

    @classmethod
    def list(cls) -> list:
        return list(map(lambda c: (c.name, c.value), cls))

    @classmethod
    def values(cls) -> list:
        return list(map(lambda c: c.value, cls))

    @classmethod
    def by_steps(cls, steps: int | str):
        return cls[Steps(int(steps)).name]

    @classmethod
    def has_restricted_features(cls, x) -> bool:
        if isinstance(x, Performance):
            x = x.value
        return x in [cls.Extreme_Speed.value, cls.Lightning.value, cls.Hyper_SD.value]

    def steps(self) -> int | None:
        return Steps[self.name].value if self.name in Steps.__members__ else None

    def steps_uov(self) -> int | None:
        return StepsUOV[self.name].value if self.name in StepsUOV.__members__ else None

    def lora_filename(self) -> str | None:
        return PerformanceLoRA[self.name].value if self.name in PerformanceLoRA.__members__ else None
