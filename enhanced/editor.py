import gradio as gr
import copy
from pathlib import Path
from PIL import Image as _Image
from PIL import ImageOps, ImageEnhance, ImageFilter
from PIL.PngImagePlugin import PngInfo
from PIL.Image import Resampling
import base64
from io import BytesIO
import numpy as np
import modules.config as config

# renamed rembg.remove to avoid confusion with function name:
from rembg import remove as remove_background_lib
from enhanced.translator import interpret, interpret_info, interpret_warn
import common
import modules.user_structure as US
from modules.util import generate_temp_filename


def convert_to_rgba(img: _Image.Image) -> _Image.Image:
    # ensure RGBA mode for full compatibility
    if img is None:
        return None
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    return img

def on_upload_trigger(input_image: _Image.Image):
    if input_image is None:
        return None, None
    # load the metadata
    common.input_meta = input_image.info
    print()
    if input_image.mode == 'RGBA':
        rgba_img = input_image
        interpret('[Edit] The input image mode is', 'RGBA:')
    else:
        rgba_img = input_image.convert('RGBA')
        interpret('[Edit] Converted the input image mode to', 'RGBA')
    interpret('Transparency support is enabled')
    if common.input_meta:
        interpret('Loaded input image metadata')
    else:
        interpret('Could not find metadata in the input image')
    return rgba_img, rgba_img


def reset_transforms(arg_image):
    # return default values for all transformation components
    width, height = arg_image.size
    left_update = gr.Slider.update(maximum=width, value = 0)
    right_update = gr.Slider.update(maximum=width, value = width)
    upper_update = gr.Slider.update(maximum=height, value = 0)
    lower_update = gr.Slider.update(maximum=height, value = height)
    width_update = gr.Slider.update(maximum=width*2, value = width)
    height_update = gr.Slider.update(maximum=height*2, value = height)

    return (
        100,            # percent_resize_slider default
        0,              # rotate_slider default
        left_update,    # left_slider (crop) default
        right_update,   # right_slider (crop) default
        upper_update,   # upper_slider (crop) default
        lower_update,   # lower_slider (crop) default
        width_update,   # original image width
        height_update,  # original image height
        False,          # mirror_chk default
        False,          # flip_vertical_chk default
        False           # flip_AR_chk default
    )


def reset_to_defaults(arg_image):
    # return default values for all editing components
    width, height = arg_image.size

    left_update = gr.Slider.update(maximum=width, value = 0)
    right_update = gr.Slider.update(maximum=width, value = width)
    upper_update = gr.Slider.update(maximum=height, value = 0)
    lower_update = gr.Slider.update(maximum=height, value = height)
    width_update = gr.Slider.update(maximum=width*2, value = width)
    height_update = gr.Slider.update(maximum=height*2, value = height)

    return (
        0,              # brighten_slider default
        0,              # contrast_slider default
        0,              # hue_slider default
        0,              # saturation_slider default
        0,              # sharpness_slider default
        False,          # autocontrast_chk default
        False,          # edge_bool default
        False,          # equalize_chk default
        False,          # grayscale_chk default
        100,            # percent_resize_slider default
        0,              # rotate_slider default
        left_update,    # left_slider (crop) default
        right_update,   # right_slider (crop) default
        upper_update,   # upper_slider (crop) default
        lower_update,   # lower_slider (crop) default
        width_update,   # original image width
        height_update,  # original image height
        False,          # mirror_chk default
        False,          # flip_vertical_chk default
        False,          # flip_AR_chk default
        False,          # background_chk default
        False,          # erase_chk default
        0.0,            # transparency percentage default
        0,              # box_blur_slider default
        0,              # gaussian_blur_slider default
        False,          # edge_more_bool default
        8,              # posterize_slider default
        -1              # solarize_int default
    )


def apply_hue_adjustment(edit_image, hue_int):
    """Applies hue adjustment using HSV conversion."""
    if hue_int != 0:
        hue_float = (hue_int/180)+1
        edit_image_hsv = edit_image.convert("HSV")
        np_image = np.array(edit_image_hsv)
        # Hue value manipulation (0-255 range), using modulo for cycling
        np_image[..., 0] = (np_image[..., 0] * hue_float) % 256
        output_image = _Image.fromarray(np_image, "HSV").convert("RGB")
    else:
        output_image = edit_image
    return output_image


def percent_resize_logic(input_image_data, percent_val, current_w_val, current_h_val):
    if input_image_data is None:
        return [gr.update()] * 4

    orig_w, orig_h = input_image_data.size
    scale = percent_val / 100

    # calculate NEW maximums based on the original dimensions
    # the ceiling is limited to 2x the base image size
    new_max_w = max(2, min(int(orig_w * scale), 2 * orig_w))
    new_max_h = max(2, min(int(orig_h * scale), 2 * orig_h))

    # Calculate PROPORTIONAL values:
    # for example, if the user had the right crop slider
    # at 50% of the old max, keep it at 50% of the new max
    # Assume the sliders previously had a max of 'orig_w' and 'orig_h'
    ratio_w = current_w_val / orig_w if orig_w > 0 else 0
    ratio_h = current_h_val / orig_h if orig_h > 0 else 0

    # apply ratios to new maximums to ensure they stay within bounds
    new_val_w = max(2, min(int(new_max_w * ratio_w), new_max_w))
    new_val_h = max(2, min(int(new_max_h * ratio_h), new_max_h))

    return (
        new_max_w, # width_slider value
        new_max_h, # height_slider value
        gr.update(maximum=new_max_w, value=new_val_w), # right_slider update
        gr.update(maximum=new_max_h, value=new_val_h), # lower_slider update
    )


def width_image_logic(edit_image, new_width):
    original_width, original_height = edit_image.size
    if new_width != original_width and new_width > 1:
        output_image = edit_image.resize((new_width, original_height), resample=Resampling.LANCZOS,)
    else:
        output_image = edit_image
    return output_image

def height_image_logic(edit_image, new_height):
    original_width, original_height = edit_image.size
    if new_height != original_height and new_height > 1:
        output_image = edit_image.resize((original_width, new_height), resample=Resampling.LANCZOS,)
    else:
        output_image = edit_image
    return output_image


def rotate_image_logic(edit_image, rotate_int):
    # PIL's rotate function takes degrees
    if rotate_int != 0:
        output_image = edit_image.rotate(rotate_int,
            resample=Resampling.BICUBIC, expand=True)
    else:
        output_image = edit_image
    return output_image

def crop_image_logic(processed_image, left_int, right_int, upper_int, lower_int):
    # ensure all parameters are in range
    width, height = processed_image.size
    left = max(0, int(left_int))
    right = min(width, int(right_int))
    upper = max(0, int(upper_int))
    lower = min(height, int(lower_int))
    # validate parameters
    if right_int <= left_int or lower_int <= upper_int:
        output_image = processed_image
    else:
        # make the crop
        output_image = processed_image.crop((left_int, upper_int, right_int, lower_int))
    return output_image


def mirror_image_logic(edit_image, mirror_bool):
    output_image = edit_image
    if mirror_bool:
        # flipping horizontally
        output_image = edit_image.transpose(_Image.FLIP_LEFT_RIGHT)
    else:
        output_image = edit_image
    return output_image

def flip_vertical_image_logic(edit_image, flip_vertical_bool):
    if flip_vertical_bool:
        # flipping vertically
        output_image = edit_image.transpose(_Image.FLIP_TOP_BOTTOM)
    else:
        output_image = edit_image
    return output_image


def remove_background_logic(edit_image, background_bool):
    if background_bool:
        # Call the external library function
        print()
        output_image = remove_background_lib(edit_image)
        if output_image.mode == 'RGBA':
            interpret('A transparent layer was added to the image and the background has been removed')
        else:
            interpret_warn('Could not add transparent layer')
    else:
        output_image = edit_image
    return output_image

def erase_logic(edit_image, erase_bool):
    if erase_bool:
        if edit_image.mode != "RGBA":
            edit_image = edit_image.convert("RGBA")
        r, g, b, a = edit_image.split()
        black = r.point(lambda _: 0)
        clear = r.point(lambda _: 0)
        output_image = _Image.merge("RGBA", (black, black, black, clear))
        interpret('The image has been deleted and replaced with pure transparency')
    else:
        output_image = edit_image
    return output_image

def remove_transparency_logic(edit_image):
    if edit_image.mode == "RGBA":
        edit_image = edit_image.convert("RGB")
        output_image = edit_image.convert("RGBA")
        interpret('Removed all transparency')
    else:
        output_image = edit_image
    # background_chk, erase_chk, transparency_slider
    return  (output_image,
            output_image, output_image,
            gr.update(value=False),
            gr.update(value=False),
            gr.update(value=0.0))

def display_transparency_percentage(transparency_f):
    interpret_info('Image transparency', f'= {transparency_f}%')
    return

def transparency_logic(edit_image, transparency_f):
    # alpha_value = 0 is fully transparent, 255 is fully opaque
    # ensure the image has an alpha channel:

    if edit_image.mode != "RGBA":
        output_image = edit_image.convert("RGBA")
    else:
        output_image = edit_image

    # convert the 0-100% transparency to 0-255 opacity:
    opacity_value = 255 - int((transparency_f / 100.0) * 255.0)
    # get existing alpha channel:
    alpha = output_image.getchannel('A')

    # prevent data loss by ensuring a minimum value of 1
    # this prevents the 'clean transparent pixels to black' optimization
    alpha = alpha.point(lambda i: max(1, int(i * (opacity_value / 255))))

    output_image.putalpha(alpha)
    return output_image


def apply_enhancements(
    input_image: _Image.Image,
    brightness_int: int,
    contrast_int: int,
    saturation_int: int,
    hue_int: int,
    sharpness_int: int,
    autocontrast_bool: bool,
    edge_bool: bool,
    equalize_bool: bool,
    grayscale_bool: bool,
    rotate_int: int,
    left_int: int,
    right_int: int,
    upper_int: int,
    lower_int: int,
    width_int: int,
    height_int: int,
    mirror_bool: bool,
    flip_vertical_bool: bool,
    background_bool: bool,
    erase_bool: bool,
    transparency_f: float,
    box_blur_int: int,
    gaussian_blur_int: int,
    edge_more_bool: bool,
    posterize_int: int,
    solarize_int: int
) -> _Image.Image:
    """
    Apply all enhancements sequentially to the provided image.
    """
    if input_image is None:
        return None

    if input_image.mode == 'RGBA':
        processed_image = input_image
    else:
        processed_image = input_image.convert('RGBA')

    # --- Step 0: Initial Transformations (Rotation, Mirror, Invert) ---
    processed_image = rotate_image_logic(processed_image, rotate_int)
    processed_image = mirror_image_logic(processed_image, mirror_bool)
    processed_image = flip_vertical_image_logic(processed_image, flip_vertical_bool)
    processed_image = width_image_logic(processed_image, width_int)
    processed_image = height_image_logic(processed_image, height_int)
    processed_image = crop_image_logic(processed_image, left_int, right_int, upper_int, lower_int)

    # --- Step 1: Tonal Adjustments ---
    processed_image = ImageEnhance.Brightness(processed_image).enhance((brightness_int/100)+1)
    processed_image = ImageEnhance.Contrast(processed_image).enhance((contrast_int/100)+1)

    # --- Step 2: Colour Adjustments ---
    # 2a. Apply Hue adjustment using the new function
    processed_image = apply_hue_adjustment(processed_image, hue_int)

    # 2b. Apply Saturation adjustment
    processed_image = ImageEnhance.Color(processed_image).enhance((saturation_int/100)+1)

    # --- Step 3: Detail Adjustments ---
    processed_image = ImageEnhance.Sharpness(processed_image).enhance((sharpness_int/100)+1)

    # --- Step 4: Final Composition and Transparency Logic ---
    processed_image = remove_background_logic(processed_image, background_bool)

    processed_image = erase_logic(processed_image, erase_bool)

    processed_image = transparency_logic(processed_image, transparency_f)

    # --- Step 5: Effects & Filters ---
    if processed_image.mode == 'RGBA':
        # split the image into individual bands (R, G, B, A)
        # then recombine without the alpha
        r, g, b, a = processed_image.split()
        RGB_image = _Image.merge('RGB', (r, g, b))
    else:
        RGB_image = processed_image

    if autocontrast_bool:
        RGB_image = ImageOps.autocontrast(RGB_image,
            cutoff=5, ignore = None, mask = None, preserve_tone = True)

    if equalize_bool:
        RGB_image = ImageOps.equalize(RGB_image, mask=None)

    if grayscale_bool:
        RGB_image = RGB_image.convert("L").convert("RGB")

    if box_blur_int > 0:
        RGB_image = RGB_image.filter(ImageFilter.BoxBlur(box_blur_int))

    if gaussian_blur_int > 0:
        RGB_image = RGB_image.filter(ImageFilter.GaussianBlur(gaussian_blur_int))

    if edge_bool:
        RGB_image = RGB_image.filter(ImageFilter.EDGE_ENHANCE)

    if edge_more_bool:
        RGB_image = RGB_image.filter(ImageFilter.EDGE_ENHANCE_MORE)

    if posterize_int < 8:
        RGB_image = ImageOps.posterize(RGB_image, posterize_int)

    if solarize_int >= 0:
        RGB_image = ImageOps.solarize(RGB_image, threshold=solarize_int)

    if processed_image.mode == 'RGBA':
        RGB_image.putalpha(a)
    processed_image = RGB_image

    return processed_image, width_int, height_int


def if_alpha_required(src_image):
    # determine if we actually use the alpha channel
    src_image_mode = (src_image.mode).upper()
    src_image = src_image.convert('RGBA')

    # the last channel (index 3) is the alpha channel
    alpha_channel_extrema = src_image.getextrema()[3]

    # check if the minimum alpha value is less than 255 (fully opaque)
    # 0 = fully transparent, 255 = fully opaque
    if alpha_channel_extrema[0] < 255:
        output_image = src_image # transparency is used
    else:
        output_image = src_image.convert("RGB")
        interpret('[Edit] Transparency is not in use so the transparent layer will not be saved.')
        interpret('Converted the image mode:', f'{src_image_mode} → RGB')
    return output_image


def save_image(output_image, format_str, save_meta):
    print()
    if output_image is None:
        interpret_warn('The output image is not available')

    output_image = if_alpha_required(output_image)

    if output_image.mode == 'RGBA' and format_str != 'png' and format_str != 'gif':
        interpret_warn('To preserve transparency, converted the file format:', '{format_str.upper} → PNG')
        format_str = 'png'

    # check if the image content is visually grayscale
    # i.e. it only contains gray tones
    if output_image.mode == 'RGB':
        # Split channels and check if R == G and G == B for all pixels
        r, g, b = output_image.split()
        if r.tobytes() == g.tobytes() == b.tobytes():
            # if so, convert to single-channel 'L' mode
            # for efficient storage
            output_image = output_image.convert('L')
            interpret('Detected only grayscale content, saving as a true grayscale image')
    if save_meta:
        # initiate a PngInto object
        metadata = PngInfo()
        for key, value in save_meta.items():
            # only add text-based metadata
            if isinstance(value, str):
                metadata.add_text(key, value)

    path_outputs = Path(config.path_outputs)
    date_string, file_dest, only_name = generate_temp_filename(f'{path_outputs}/', '')
    path_today = Path(path_outputs/date_string)
    US.make_dir(path_today)
    path_full = Path(path_outputs/date_string/only_name).resolve()
    # Save the image using the most appropriate mode
    save_path = f"{path_full}{format_str.lower()}"
    if save_meta:
        output_image.save(save_path, format=format_str.upper(), pnginfo=metadata)
    else:
        output_image.save(save_path, format=format_str.upper())
    interpret_info('Saved edited image to', save_path)
    interpret('Using image mode:', output_image.mode)
    if save_meta:
        interpret('Saved with metadata')
    else:
        interpret('Saved without metadata')
    return str(save_path)


def on_save_output_click(output_image_state, current_save_format_value):
    if output_image_state is None:
        interpret("No image to save.")
        # return None if nothing was saved
        return None
    # Uses edit.py save_image function,
    # which returns the temporary
    # filename/path
    filename = save_image(output_image_state,
        current_save_format_value, common.input_meta)
    # returns the path string e.g. "my_output_image.png"
    return filename

# --- Overlay Section ---

def calculate_centred_position_and_bounds(base_img: _Image.Image, overlay_img: _Image.Image):
    # calculate the initial centre coordinates
    # and maximums for the webui sliders
    if base_img is None or overlay_img is None:
        # return safe defaults if images aren't loaded yet:
        return 0, 0, 512, 512 # Default half-ranges

    base_w, base_h = base_img.size
    over_w, over_h = overlay_img.size

    # The maximum distance the overlay can move from the centre
    # while staying contained within the base image boundaries

    # Set the slider limits to 75% of base dimensions
    # to allow the overlay to be moved mostly off-screen
    max_offset_x = int(base_w * 0.75)
    max_offset_y = int(base_h * 0.75)

    # start_x/y are now 0 (the centre)
    return 0, 0, max_offset_x, max_offset_y


def update_composite_image(
    horizontal_pos: int,
    vertical_pos: int,
    rotation_angle: int,
    base_img_data: _Image.Image,
    overlay_img_data: _Image.Image,
    contain_chk: bool = True  # parameter for clamping toggle
) -> _Image.Image:
    if base_img_data is None or overlay_img_data is None:
        return None

    # Ensure the images are RGBA for transparency support
    base_img_data = base_img_data.convert('RGBA')
    overlay_img_data = overlay_img_data.convert('RGBA')

    # 1. Rotate the overlay image
    rotated_overlay = overlay_img_data.rotate(
        angle=rotation_angle,
        resample=Resampling.BICUBIC,
        expand=True
    )

    # 2. Create a fresh copy of the base image
    # using deepcopy for high reliability
    composite_image = copy.deepcopy(base_img_data)

    # 3. Calculate positioning
    base_width, base_height = composite_image.size
    fg_width_rotated, fg_height_rotated = rotated_overlay.size

    # Calculate the visual center-point coordinates
    center_x = (base_width - fg_width_rotated) // 2
    center_y = (base_height - fg_height_rotated) // 2

    # Final position is the center-point plus the slider offset
    x_pos = center_x + horizontal_pos
    # Y: Inverted (Positive slider moves UP, so we subtract from the screen Y)
    y_pos = center_y - vertical_pos

    # 4. Optional Clamping (Containment) logic
    if contain_chk:
        # Define the strict top-left bounds
        strict_max_x = max(0, base_width - fg_width_rotated)
        strict_max_y = max(0, base_height - fg_height_rotated)

        # Clamp the calculated position
        x_pos = max(0, min(x_pos, strict_max_x))
        y_pos = max(0, min(y_pos, strict_max_y))


    position = (x_pos, y_pos)

    # 5. Paste using alpha channel as a mask
    composite_image.paste(rotated_overlay, position, mask=rotated_overlay)

    return composite_image


def on_save_composite_click(output_image_state, current_save_format_value):
    if output_image_state is None:
        interpret("No image to save.")
        # return None if nothing was saved
        return None
    # Uses edit.py save_image function,
    # which returns the temporary
    # filename/path
    filename = save_image(output_image_state,
        current_save_format_value, common.base_meta)
    # returns the path string e.g. "my_output_image.png"
    return filename
