from pathlib import Path

# These pseudo globals are imported by several
# functions and are subject to change
GRADIO_ROOT = None
MODELS_INFO = None

# ROOT is used as a constant that
# is referenced by several modules
ROOT = str(Path.cwd())

# tracks update events
# set by entry_with_update, checked by webui
# and processed by enhanced.version.announce_version()
# 0 = no change, 1 = hotfix, 2 = new version
version_update = 0

# set in UIS.process_before_generation() and
# clear it in UIS.process_after_generation()
# currently used to prevent audio randomization
is_generating = False

# Common support for black_out_nsfw
# if the config setting is False,
# the UI cannot override it.
# Initialized by config,
# may be set to False by webui,
# read by async_worker
black_out_nsfw = False

# Monitor the Input Image tabs:
# initialized by config,
# updated by webui,
# read by ui_support and async_worker
current_tab_name = 'uov'

# Monitor the Features tabs:
# updated by webui
# read by ui_support and async_worker
# The first tab, Image Editor, is the default
features_tab_name = 'edit'
# updated by webui, read by async_worker:
features_checkbox = False

# The image buffer collection:
# stored and cleared by webui
# and/or ui_support,
# read by aysnc_worker
uov_image_buffer = None
inpaint_image_buffer = None
inpaint_mask_buffer = None
enhance_image_buffer = None
layer_image_buffer = None

# Inpainting controls
# set by webui, read by async_worker
inpaint_additional_prompt = ""
outpaint_selections = []

# Inpainting masking mode
# set by ui_support, read by async_worker
# True = Auto-Masking, False = Manual
is_auto_masking = False

# Common support for miscellaneous controls
# set by webui, read by async_worker
iclight_source_radio = 'Top Left Light'
disable_preview = False

# Common support for Translator & Wildcards
prompt_translator = True
read_wildcards_in_order = False
wildcard_lines_to_interpret = 50

# the current resolution is set by modules.aspect_ratios
resolution = '0*0'
full_AR_labels = []

# Used with webui "Make New Preset"
# determines whether the current AR will be saved
# set by save_AR_checkbox
# used by enhanced.toolbox.save_preset()
AR_preset_save = False

# set by webui to control
# UIS.reset_layout_parameters
len_preset_layout = 0
len_preset_func = 0
len_data_outputs = 0

# used to ensure template update to SD1.5 in meta_parser.get_resolution()
# this value is updated by PR.find_preset_file()
preset_file_path = 'presets\Favorite\Default.json'

# set by modules.preset_resource (PR) get_preset_content(preset)
preset_content = []

# set by preset_support.py
# read by async_worker __init__() for specific preset startups
# cleared by PR.set_preset_selection() if UI changes the preset
default_engine = {}
# used by AR.AR_template_init()
task_method = ''

# indicates metadata loading is in progress
# this prevents PR.set_preset_selection from
# overwriting key metadata values
# set by webui.update_preset_info()
# cleared by webui.normalize_preset_loading()
metadata_loading = False
log_metadata = []

# input & base metadata used by the Image Editor
input_meta = ''
base_meta = ''

# batch_count is set by webui.set_batch_count() to determine
# how many times to run the generative cycle
batch_count = 1

# FreeU controls initialized by config,
# updated by webui and read by async_worker
freeu_settings = [False, 1.01, 1.02, 0.99, 0.95]

# performance selection initialized by config,
# updated by webui and read by async_worker
performance_selection = 'Speed'

# seed controls set by webui
# disable_seed_increment and saved_seed are read by async_worker
disable_seed_increment = False # alias Freeze Seed
image_seed = '0'        # initialize working seed
saved_seed = '0'        # initialize seed saver

# Expert Tool settings
# set by webui, read by async_worker
adm_scaler_positive = 1.5
adm_scaler_negative = 0.8
adm_scaler_end = 0.3


