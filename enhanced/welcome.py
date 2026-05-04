import os
import glob
import numpy as np
import random
import time
import uuid

from pathlib import Path
from PIL import Image, ImageFilter, ImageOps

import modules.config as config
import modules.user_structure as US
import modules.util as util
from enhanced.translator import interpret
from modules.config import user_dir


# colour database
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

    # create the 1D gradient line for each channel
    # use np.linspace to interpolate between
    # colorA and colorB
    r_line = np.linspace(colorA[0], colorB[0], width, dtype=np.uint8)
    g_line = np.linspace(colorA[1], colorB[1], width, dtype=np.uint8)
    b_line = np.linspace(colorA[2], colorB[2], width, dtype=np.uint8)

    # stack the 1D lines to fill the height
    # np.tile repeats the gradient for each row
    r_2d = np.tile(r_line, (height, 1))
    g_2d = np.tile(g_line, (height, 1))
    b_2d = np.tile(b_line, (height, 1))

    # Combine the three 2D channels into a single RGB array
    gradient = np.stack([r_2d, g_2d, b_2d], axis=-1)

    background_rgb = Image.fromarray(gradient, 'RGB')

    # randomly rotate to vary the gradient direction
    # (Horizontal vs Vertical)
    if random.choice([True, False]):
        background_rgb = background_rgb.rotate(90, expand=True).resize((width, height))

    return background_rgb


# pil image paste
def add_foreground(background, foreground):
    foreground_file = Path(foreground).resolve()
    foreground_rgba = Image.open(foreground_file).convert("RGBA")

    composite = background.convert("RGBA")
    bg_w, bg_h = composite.size

    # --- resizing ---
    width_max = bg_w / 3
    fg_w, fg_h = foreground_rgba.size

    if fg_w > width_max:
        scale = fg_w / width_max
        foreground_rgba = foreground_rgba.resize((int(fg_w / scale), int(fg_h / scale)), Image.LANCZOS)
        fg_w, fg_h = foreground_rgba.size

    # --- random rotation & shadow variables ---
    is_rotated = False
    shadow_opacity = 160  # Default subtle shadow
    shadow_offset = 5     # Default close-to-surface offset

    if random.random() < 0.25:
        is_rotated = True
        angle = random.uniform(-30, 30)
        foreground_rgba = foreground_rgba.rotate(angle, resample=Image.BICUBIC, expand=True)
        fg_w, fg_h = foreground_rgba.size

        # Refine shadow for "lifted sticker" effect
        shadow_opacity = 210  # Darker
        shadow_offset = 8     # Deeper lift

    # --- random placement ---
    limit_x = max(0, bg_w - fg_w)
    limit_y = max(0, bg_h - fg_h)

    paste_x = random.randint(0, limit_x)
    paste_y = random.randint(0, limit_y)

    # --- shadow logic ---
    alpha = foreground_rgba.split()[-1]

    # make shadow with opacity based on rotation
    # (0,0,0, shadow_opacity) sets the darkness level
    shadow = ImageOps.colorize(alpha, black="black", white="black")

    # adjust shadow transparency using point logic
    shadow_alpha = alpha.point(lambda p: p * (shadow_opacity / 255))
    shadow.putalpha(shadow_alpha)

    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))

    # paste shadow (with offset) then Logo
    composite.paste(shadow, (paste_x + shadow_offset, paste_y + shadow_offset), mask=shadow)
    composite.paste(foreground_rgba, (paste_x, paste_y), mask=foreground_rgba)

    return composite


def process_dynamic_logo(logo_file, width, height):
    try:
        # 1. generate the gradient background
        splash_bg = generate_background(width, height)

        # 2. add the foreground logo
        # add_foreground handles the Image.open
        # and the pasting logic
        composite = add_foreground(splash_bg, logo_file)

        # 3. define the save path
        # This creates a name like dynamic_welcome_7a1b.png
        unique_suffix = str(uuid.uuid4())[:4]
        save_path = Path(user_dir) / 'control_images' / f'dynamic_welcome_{unique_suffix}.png'

        # 4. Cleanup: Delete any OLD dynamic_welcome
        # images before saving the new one
        for old_file in (Path(user_dir) / 'control_images').glob('dynamic_welcome_*.png'):
            try:
                old_file.unlink(missing_ok=True)
            except:
                pass # avoid errors if file is currently being read by Gradio

        # 4. save & return the posix path for Gradio 5
        save_path.parent.mkdir(parents=True, exist_ok=True)
        composite.save(save_path, format="PNG")
        return save_path.resolve().as_posix()

    except Exception as e:
        interpret(f'[Welcome] Logo Error: {str(e)}')
        # if the dynamic generation fails,
        # return the raw logo as a backup
        # or return an empty string as the
        # final UIS fallback.
        if Path(logo_file).is_file():
            return Path(logo_file).resolve().as_posix()
        return ''


def get_welcome_image():
    path_welcome = Path(user_dir/'welcome_images').resolve()
    path_logo = (path_welcome/'FooocusPlus_logo.png').resolve()
    path_default_welcome = (path_welcome/'control_images/invisible_welcome.png').resolve()

    # check PNGs
    welcomes = US.list_files_by_patterns(path_welcome, ['*.png'])
    if welcomes:
        if path_logo.is_file():
            # This returns the .as_posix() path of the composite image
            return process_dynamic_logo(path_logo, 1400, 900)
        else:
            return (path_welcome / random.choice(welcomes)).resolve().as_posix()

    # check JPEGs
    welcomes = US.list_files_by_patterns(path_welcome, patterns=['*.jpg', '*.jpeg'])
    if welcomes:
        return (path_welcome / random.choice(welcomes)).resolve()

    # default fallback
    if path_default_welcome.is_file():
        return path_default_welcome

    # error report
    print(f"\n[Welcome] ERROR: Cannot find {path_default_welcome}\n")
    return ''


def check_active_logo():
    logo_bool = False
    logo_path = Path(config.user_dir / 'welcome_images' / 'FooocusPlus_logo.png')
    if US.exists_file(logo_path):
        logo_bool = True
    return logo_bool
