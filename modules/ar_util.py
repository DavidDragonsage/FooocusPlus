#import math
import common
import modules.config as config
import modules.constants as constants
from enhanced.translator import interpret


# Initialize the the current aspect ratio template
def AR_template_init():
    global AR_template
    if common.task_method == 'SD_SIMPLE':
        AR_template = 'SD1.5'
    elif config.enable_shortlist_aspect_ratios:
        AR_template = 'Shortlist'
    else:
        AR_template = 'Standard'
    return AR_template
AR_template = AR_template_init()

def assign_default_by_template(template):
    global AR_template
    try:
        ar_index = constants.aspect_ratios_templates.index(template)
    except:
        AR_template = AR_template_init()
        ar_index = constants.aspect_ratios_templates.index(AR_template)
    return config.default_aspect_ratio_values[ar_index]

def do_the_split(x):
    try:
        x = x.replace("x","*") # entries in config.txt that use "x" instead of "*"
        x = x.replace("×","*") # webui aspect ratio selector uses the raised "×"
        width, height = x.replace('*', ' ').split(' ')[:2]
        test_width = int(width)
        test_height = int(height)
    except:
        width = x
        height = ''
    return width, height

def get_AR_template_values(template):
    global AR_template
    try:
        ar_index = constants.aspect_ratios_templates.index(template)
    except:
        AR_template = AR_template_init()
        ar_index = constants.aspect_ratios_templates.index(AR_template)
    return config.config_aspect_ratios[ar_index]

def find_the_height(arg_width):
    global AR_template
    AR_template_values = get_AR_template_values(AR_template)
    AR_pair = None
    arg_width = str(arg_width)
    arg_width = arg_width.strip("(,")
    height = ''
    print()
    interpret('[AR Util] Checking for a match to the pixel width:', arg_width)
    for AR_value in AR_template_values:
        split_value = AR_value.split('*')
        if arg_width == split_value[0]:
            AR_pair = AR_value
            break
    if AR_pair: # popular size overrides
        if AR_pair == '1152*896':   # 9:7
            AR_pair = '1152*864'    # 4:3
        elif AR_pair == '1344*768': # 7:4
            AR_pair = '1344*756'    # 16:9
        interpret('[AR Util] Restoring the aspect ratio:', AR_pair)
        common.current_AR = AR_pair
        split_value = AR_pair.split('*')
        width = split_value[0]
        height = split_value[1]
        return width, height
    else:
        return arg_width, height

def AR_split(x):
    global AR_template
    width, height = do_the_split(x)
    if width != '' and height == '':
        width, height = find_the_height(width)
        if height != '':
            return width, height
    if (width == '') or (height == ''):
        width, height = do_the_split(common.current_AR)
        if (width == '') or (height == ''):
            common.current_AR = assign_default_by_template(AR_template)
            width, height = do_the_split(common.current_AR)
            print()
            interpret('[AR Util] Reverting to the default aspect ratio:', common.current_AR)
        else:
            print()
            interpret('[AR Util] Adjusting the aspect ratio value to:', common.current_AR)
    return width, height
