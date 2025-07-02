from pathlib import Path

# These pseudo globals are imported by several
# functions and are subject to change
GRADIO_ROOT = None
MODELS_INFO = None

# Store the current prompts
# used to restore prompts after a preset change clears them
POSITIVE = ''
NEGATIVE = ''

# ROOT is used as a constant that
# is referenced by several modules
ROOT = str(Path.cwd())


# Additional parameters recovered from errors in the system dictionary
# likely caused by malfunctioning Gradio functions
# set by modules.config
# updated by modules.meta_parser.parse_meta_from_preset(preset_content)
# and also by webui sampler dropdown & set_slider_switch(x)
default_sampler = 'dpmpp_2m_sde_gpu'
refiner_slider = 0.6
