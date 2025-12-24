import gradio as gr
import math
import args_manager as args
import common
import modules.config as config
import modules.constants as constants
from modules.ar_util import AR_split, AR_template,\
    AR_template_init, assign_default_by_template
from enhanced.translator import interpret


# Used in the webui aspect_info textbox info field
# Set by get_aspect_info_info()
aspect_info_help = 'Vertical (9:16), Portrait (4:3), Landscape (3:2), Widescreen (16:9), Ultrawide (12:5)'
aspect_info_SD1_5 = 'Vertical (9:16), Photo (4:5), Portrait (4:3), Landscape (3:2), Widescreen (16:9)'
aspect_info_PixArt = 'Vertical (9:16), Photo (4:5), Portrait (4:3), Landscape (3:2), Widescreen (16:9), Ultrawide (12:5)'
aspect_info_SDXL = '. For SDXL, 1280*1280 is experimental'


# Store the default aspect ratio selection
# this value is updated by webui & modules.meta_parser
common.current_AR = assign_default_by_template(AR_template)


def add_ratio(x):
    a, b = AR_split(x)
    a, b = int(a), int(b)
    g = math.gcd(a, b)
    c, d = a // g, b // g
    return f'{a}×{b} | {c}:{d}'

def get_full_AR_labels(arg_config_aspect_ratios):
    return {template: [add_ratio(x) for x in ratios]
        for template, ratios in zip(constants.aspect_ratios_templates, arg_config_aspect_ratios)}

common.full_AR_labels = get_full_AR_labels(config.config_aspect_ratios)


def add_template_ratio(x):    # only used to initialize the AR Accordion
    a, b = AR_split(x)
    a, b = int(a), int(b)
    g = math.gcd(a, b)
    c, d = a // g, b // g
    return f'Aspect Ratio: {a}×{b} | {c}:{d}'

def get_aspect_ratio_title(arg_default_aspect_ratio_values):
    return {template: add_ratio(ratio)
        for template, ratio in zip(constants.aspect_ratios_templates, arg_default_aspect_ratio_values)}
aspect_ratio_title = get_aspect_ratio_title(config.default_aspect_ratio_values)

def get_aspect_info_info():
    if AR_template == 'Standard':
        aspect_info_info = aspect_info_help + aspect_info_SDXL
    elif AR_template == 'SD1.5':
        aspect_info_info = aspect_info_SD1_5
    elif AR_template == 'PixArt':
        aspect_info_info = aspect_info_PixArt
    else: # Shortlist
        aspect_info_info = aspect_info_help
    return aspect_info_info

def save_current_aspect(x):
    global AR_template
    if x != '':
        common.current_AR = f'{x.split(",")[0]}'
        x = common.current_AR
    interpret('[AR] Aspect Ratio:', AR_template + ' / ' + common.current_AR)
    aspect_info_info = get_aspect_info_info()
    aspect_info_value = f'{AR_template} Template'
    return gr.update(), gr.update(value=aspect_info_value),\
        gr.update(info=aspect_info_info)

def overwrite_aspect_ratios(width, height):
    if width>0 and height>0:
        common.current_AR = f'{width}*{height}'
        return add_ratio(common.current_AR)
    return gr.update()

def reset_aspect_ratios(arg_AR):
    global AR_template
    if len(arg_AR.split(','))>1:
        template = arg_AR.split(',')[1]
        AR_template = template
    elif not AR_template:
        # fallback if template & AR_template are undefined
        results = [gr.update()] * 4
        return results
    aspect_ratios = arg_AR.split(',')[0]
    if aspect_ratios:
        common.current_AR = aspect_ratios
    if (config.enable_shortlist_aspect_ratios == True) and (AR_template == 'Standard'):
        AR_template = 'Shortlist'
    elif (config.enable_shortlist_aspect_ratios == False) and (AR_template == 'Shortlist'):
        AR_template = 'Standard'
    if AR_template == 'Shortlist':
        results = [gr.update(visible=False), gr.update(value=aspect_ratios, visible=True)] + [gr.update(visible=False)] * 2
    elif AR_template=='SD1.5':
        results = [gr.update(visible=False)] * 2 + [gr.update(value=aspect_ratios, visible=True), gr.update(visible=False)]
    elif AR_template=='PixArt':
        results = [gr.update(visible=False)] * 3 + [gr.update(value=aspect_ratios, visible=True)]
    else:        # Standard template
        results = [gr.update(value=aspect_ratios, visible=True)] + [gr.update(visible=False)] * 3
    interpret('[AR] Using the Template and Aspect Ratio:', AR_template + ' / ' + common.current_AR)
    return results

# a preset change is required to enable a reliable switch between Standard & Shortlist templates
# switch to either the Default preset or Cheyenne when changing presets
# or for LowVRAM switch between 4GB_Default and Vega
def reset_preset():
    working_preset = args.args.preset
    if args.args.preset == '4GB_Default':
        working_preset = 'VegaRT'
    elif args.args.preset == 'VegaRT':
        working_preset = '4GB_Default'
    elif args.args.preset == 'Default':
        working_preset = 'Elsewhere'
    elif common.is_low_vram_preset == True:
        working_preset = '4GB_Default'
    else:
        working_preset = 'Default'
    return working_preset

def get_substrings(arg_list, arg_substring):
    substrings = []
    for text in arg_list:
        if arg_substring in text:
            substrings.append(text)
    return substrings

def validate_AR(arg_AR, arg_template): # when switching between template
    if arg_AR == '':
        arg_AR = assign_default_by_template(arg_template)
        return arg_AR
    AR_labels = common.full_AR_labels[arg_template]
    # test for a perfect match:
    if arg_AR in AR_labels:
        interpret(f'[AR] Found the same {arg_AR} values in:', arg_template)
    else: # test for a match by AR only, not by actual dimensions:
        substrings = []
        split_AR = arg_AR.split('| ')
        if len(split_AR) == 2:
            substrings = get_substrings(AR_labels, split_AR[1])
        if substrings:
            arg_AR = substrings[0]
            interpret(f'[AR] Found the same {split_AR[1]} aspect ratio in:', arg_template)
        else: # default to the default AR for that template:
            arg_AR = assign_default_by_template(arg_template)
            if len(split_AR) == 2:
                interpret(f'[AR] Could not find the same {split_AR[1]} aspect ratio in:', arg_template)
                interpret('Using the default aspect ratio instead:', arg_AR)
    return arg_AR

def toggle_shortlist(arg_shortlist):
    global AR_template, shortlist_default
    config.enable_shortlist_aspect_ratios = arg_shortlist
    working_preset = args.args.preset
    if AR_template == 'Standard' and config.enable_shortlist_aspect_ratios:
        AR_template = 'Shortlist'
        # this ensures that Shortlist does not start with an invalid value:
        common.current_AR = validate_AR(common.current_AR, AR_template)
        print()
        interpret('[AR] Switching to the Shortlist template requires a preset change:')
        working_preset = reset_preset()
    elif AR_template == 'Shortlist' and not config.enable_shortlist_aspect_ratios:
        AR_template = 'Standard'
        # potentially a user could add a value to Shortlist that Standard does not have:
        common.current_AR = validate_AR(common.current_AR, AR_template)
        print()
        interpret('[AR] Switching to the Standard template requires a preset change:')
        working_preset = reset_preset()
    aspect_info_info = get_aspect_info_info()
    return gr.update(), gr.update(value=f'{AR_template} Template'),\
        gr.update(info=aspect_info_info), gr.update(value=working_preset)

def save_AR_template(x):
    global AR_template
    x = AR_template
    aspect_info_info = get_aspect_info_info()
    if (AR_template == 'Standard') or (AR_template == 'Shortlist'):
        return gr.update(), gr.update(value=f'{AR_template} Template'),\
            gr.update(info=aspect_info_info), gr.update(visible=True)
    else:
        return gr.update(), gr.update(value=f'{AR_template} Template'),\
            gr.update(info=aspect_info_info), gr.update(visible=False)
