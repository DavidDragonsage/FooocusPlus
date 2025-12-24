import os
import modules.config
import glob
import modules.user_structure as US
import modules.util as util
import numpy as np
import random
import time
from args_manager import args
from enhanced.translator import interpret
from pathlib import Path
from PIL import Image

user_dir = Path(args.user_dir).resolve()

def get_welcome_image():
    path_welcome = Path(user_dir/'welcome_images').resolve()
    path_logo = Path(path_welcome/'FooocusPlus_logo.png').resolve()
    path_default_welcome = Path(path_welcome/'control_images/welcome.png').resolve()

    welcomes = US.list_files_by_patterns(path_welcome,
        arg_pattern1='*.png', arg_pattern2='')
    if welcomes:
        if path_logo.is_file():
            # when the fill_background code is ready, activate this line:
            # path_logo = fill_background_png(path_logo, 1344, 756)
            return path_logo
        else:
            file_welcome = Path(path_welcome/random.choice(welcomes)).resolve()
            return file_welcome

    welcomes = US.list_files_by_patterns(path_welcome,
        arg_pattern1='*.jpg', arg_pattern2='*.jpeg')
    if welcomes:
        file_welcome = Path(path_welcome/random.choice(welcomes)).resolve()
        return file_welcome

    if path_default_welcome.is_file():
        return path_default_welcome
    else:
        print()
        interpret('[Welcome] ERROR: Cannot find', path_default_welcome)
        interpret('in', Path(user_dir/'control_images').resolve())
        print()
    return ''


# color database
def get_colors():
    rgb_values = (
        [0,0,0],
        [4,47,128],
        [14,54,96],
        [40,40,40],
        [52,152,219],
        [69,69,69],
        [114,114,114],
        [153,153,153],
        [178,178,178],
        [184,215,249],
        [222,220,230],
        [251,237,199],
        [238,238,238],
        [255,255,255],
    )
    num_colors = len(rgb_values) - 1
    (randA, randB) = random.sample(range(0, num_colors), 2)
    colorA = rgb_values[randA]
    colorB = rgb_values[randB]
    return colorA, colorB


def generate_background(width, height):
    (colorA, colorB) = get_colors()

    # we always generate square to avoid tensor errors
    # size increases to improve output quality on resize
    size_width = width * 2
    size_height = size_width
    axis = size_width

    gradient = np.zeros((size_height, size_width, 3), np.uint8)
    randomizer = random.sample(range(0, 100), 1)
    if (randomizer[0] % 2) == 0:
        axis = size_height
    else:
        axis = size_width

    # Fill R, G and B channels with linear gradient between two end colours
    gradient[:,:,0] = np.linspace(colorA[0], colorB[0], axis, dtype=np.uint8)
    gradient[:,:,1] = np.linspace(colorA[1], colorB[1], axis, dtype=np.uint8)
    gradient[:,:,2] = np.linspace(colorA[2], colorB[2], axis, dtype=np.uint8)
    background_rgb = Image.fromarray(gradient, 'RGB')

    # different gradient direction on some generations
    randomizer = random.sample(range(0, 100), 1)
    if (randomizer[0] % 2) == 0:
        background_rgb = background_rgb.rotate(90)

    # resize to requested resolution
    background_rgb = background_rgb.resize((width, height), Image.LANCZOS)
    return background_rgb

# pil image paste
def add_foreground(background, foreground):
    foreground_file = Path(foreground).resolve()
    foreground_rgb = Image.open(foreground_file).convert("RGBA")

    composite = background.convert("RGBA")
    bg_width, bg_height = composite.size
    foreground_width, foreground_height = foreground_rgb.size

    width_max = bg_width / 3
    height_max = bg_height / 2.25

    if bg_height > bg_width:
        test_width = bg_height
        test_max = height_max
    else:
        test_width = bg_width
        test_max = width_max

    if test_width > test_max:
        resize_scale = foreground_width / test_max
        resize_width = int(foreground_width / resize_scale)
        resize_height = int(foreground_height / resize_scale)
        foreground_rgb = foreground_rgb.resize((resize_width, resize_height), Image.LANCZOS)
        foreground_width, foreground_height = foreground_rgb.size

    if bg_height > bg_width:
        # put the foreground in the centre
        margin_horizontal = int((bg_width - foreground_width) / 2)
        margin_vertical = int(height_max / 5)
    else:
        # put the foreground on the right hand side
        margin_horizontal = int(width_max / 10)
        margin_vertical = int(height_max / 10)

    paste_horizontal = bg_width - foreground_width - margin_horizontal
    paste_vertical = bg_height - foreground_height - margin_vertical

    composite.paste(foreground_rgb, (paste_horizontal, paste_vertical), mask=foreground_rgb)
    return composite

def fill_background_png(filename, width, height):
    splash_bg = generate_background(width, height)
    splash_full = add_foreground(splash_bg, filename)
    return splash_full

def test_splash(width, height):
    test_image = splashscreen(width, height, 'foreground.png')
    test_timestamp = time.strftime("%Y%m%d-%H%M%S")
    test_filename = (test_timestamp + '_' + str(width) + '_' + str(height) + '.png')
    test_image.save(test_filename, format="png", quality=100)

def test_desktop_splash():
    test_splash(1344, 752)

def test_welcome_image(is_mobile=False):
    # define the size
    width = 1152
    height = 896
    # get the foreground file ready
    path_foreground = os.path.join(root, 'foreground.png') # need to put the foreground png someplace
    # generate the temporary filename
    splash_timestamp = time.strftime("%Y%m%d-%H%M%S")
    splash_filename = (splash_timestamp + '_' + str(width) + '_' + str(height) + '.png')
    path_splash = os.path.join(args.temp_path, splash_filename)
    # generate and save the temporary file
    splash_image = splashscreen(width, height, path_foreground)
    splash_image.save(path_splash, format="png", quality=100)
    # return the path to the ui
    return path_splash

