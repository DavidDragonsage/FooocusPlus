from pathlib import Path

# These pseudo globals are imported by several
# functions and are subject to change
GRADIO_ROOT = None
MODELS_INFO = None

# Store the current prompts and image quantity
# used to restore prompts after a preset change clears them
# Both prompts are initialized by config.txt via modules.config
# The positive prompt is set by UIS.prompt_token_prediction()
# via webui.calculateTokenCounter()
# The negative prompt is set by webui.set_negative_prompt()
# UIS.reset_layout_params() preserves both values
# PR.parse_prompts_from_preset() and meta_parser.parse_meta_from_preset()
# updates the prompts with preset values, if any
# and PR.set_preset_selection() updates the UI with the preset values
positive = ''
negative = ''
image_quantity = 4

# ROOT is used as a constant that
# is referenced by several modules
ROOT = str(Path.cwd())


# Additional parameters recovered from errors in the system dictionary
# likely caused by malfunctioning Gradio functions, especially "state"
# Set by modules.config
# Updated by modules.meta_parser.parse_meta_from_preset(preset_content)
# and also by preset_resource, webui set_slider_switch(x) and dropdowns
# Used by modules.async_worker and enhanced.toolbox
sampler_name = 'dpmpp_2m_sde_gpu'
scheduler_name = 'karras'
refiner_slider = 0.6

# Common support for Translator & Wildcards
prompt_translator = True
wildcard_lines_to_interpret = 50

# Aspect Ratio support in neutral (common) ground
# set by modules.aspect_ratios
current_AR = 1024*1024
full_AR_labels = []

# Preset support in neutral (common) ground
# set by modules.config
default_bar_category = 'Favorite'
preset_bar_length = 8
is_low_vram_preset = False

# used to ensure template update to SD1.5 in meta_parser.get_resolution()
# this value is updated by PR.find_preset_file()
preset_file_path = 'presets\Favorite\Default.json'

# set by modules.preset_resource (PR) get_preset_content(preset)
preset_content = []
