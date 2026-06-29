"""
Refactored USD Upscaler batch processing patch.

Preserves original behavior but:
- Organizes imports and helpers
- Replaces prints with logging
- Factors duplicated logic (tile preparation, batching, decoding)
- Uses functools.wraps when monkey-patching methods
- Adds type hints and docstrings for clarity
"""

from __future__ import annotations
from functools import wraps
import logging
import math
from typing import Tuple, List

from PIL import Image
import modules.shared as shared
from modules.processing import process_batch_tiles
from repositories import ultimate_upscale as usdu

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


# Compatibility for older Pillow versions
try:
    Image.Resampling  # type: ignore
except Exception:
    Image.Resampling = Image  # type: ignore


# -------------------------
# Utility helpers
# -------------------------
def round_length(length: int, multiple: int = 8) -> int:
    """Round length to nearest multiple (default 8)."""
    return round(length / multiple) * multiple



# -------------------------
# Monkey patches for USDUpscaler sizing / redraw / seams fix
# -------------------------
def patch_usdu_upscaler_init():
    """Patch USDUpscaler.__init__ to round upscaler p.width/p.height to multiples."""
    old_init = usdu.USDUpscaler.__init__

    @wraps(old_init)
    def new_init(self, p, image, upscaler_index, save_redraw, save_seams_fix, tile_width, tile_height):
        p.width = round_length(image.width * p.upscale_by)
        p.height = round_length(image.height * p.upscale_by)
        return old_init(self, p, image, upscaler_index, save_redraw, save_seams_fix, tile_width, tile_height)

    usdu.USDUpscaler.__init__ = new_init


def patch_usdu_redraw_init():
    """Patch USDURedraw.init_draw to round tile size used for redraw."""
    old_init_draw = usdu.USDURedraw.init_draw

    @wraps(old_init_draw)
    def new_init_draw(self, p, width, height):
        mask, draw = old_init_draw(self, p, width, height)
        p.width = round_length(self.tile_width + self.padding)
        p.height = round_length(self.tile_height + self.padding)
        return mask, draw

    usdu.USDURedraw.init_draw = new_init_draw


def patch_usdu_seams_fix_init():
    old_init = usdu.USDUSeamsFix.init_draw

    @wraps(old_init)
    def new_init(self, p):
        old_init(self, p)
        p.width = round_length(self.tile_width + self.padding)
        p.height = round_length(self.tile_height + self.padding)

    usdu.USDUSeamsFix.init_draw = new_init


def patch_usdu_upscale_method():
    """Patch USDUpscaler.upscale to keep shared.batch resized to p.width/p.height."""
    old_upscale = usdu.USDUpscaler.upscale

    @wraps(old_upscale)
    def new_upscale(self):
        old_upscale(self)
        # Keep shared.batch consistent with the upscaling width/height for subsequent processing.
        shared.batch = [self.image] + [
            img.resize((self.p.width, self.p.height), resample=Image.LANCZOS)
            for img in shared.batch[1:]
        ]

    usdu.USDUpscaler.upscale = new_upscale


# Apply patches
patch_usdu_upscaler_init()
patch_usdu_redraw_init()
patch_usdu_seams_fix_init()
patch_usdu_upscale_method()


# -------------------------
# Patched script.run replacement
# -------------------------
def patched_script_run(self, p, _, tile_width, tile_height, mask_blur, padding, seams_fix_width, seams_fix_denoise, seams_fix_padding,
                      upscaler_index, save_upscaled_image, redraw_mode, save_seams_fix_image, seams_fix_mask_blur,
                      seams_fix_type, target_size_type, custom_width, custom_height, custom_scale):
    """
    Replacement for usdu.Script.run that preserves the original batch_size
    and delegates to the (patched) USDUpscaler and redraw pipeline.
    """
    preserved_batch_size = getattr(p, 'batch_size', 1)
    logger.info("[USDU Batch Debug] Patched script.run() preserving batch_size=%s", preserved_batch_size)

    # Init (matching original code)
    usdu.processing.fix_seed(p)
    usdu.devices.torch_gc()

    # Keep original file-saving flags as in original code
    p.do_not_save_grid = True
    p.do_not_save_samples = True
    p.inpaint_full_res = False

    p.inpainting_fill = 1
    p.n_iter = 1
    p.batch_size = preserved_batch_size

    seed = p.seed

    # Init image
    init_img = p.init_images[0]
    if init_img is None:
        return usdu.processing.Processed(p, [], seed, "Empty image")
    init_img = usdu.images.flatten(init_img, usdu.shared.opts.img2img_background_color)

    # Override size by user choice
    if target_size_type == 1:
        p.width = custom_width
        p.height = custom_height
    elif target_size_type == 2:
        p.width = math.ceil((init_img.width * custom_scale) / 64) * 64
        p.height = math.ceil((init_img.height * custom_scale) / 64) * 64

    # Create and run upscaler
    upscaler = usdu.USDUpscaler(p, init_img, upscaler_index, save_upscaled_image, save_seams_fix_image, tile_width, tile_height)
    upscaler.upscale()

    # Drawing & seams fix setup
    upscaler.setup_redraw(redraw_mode, padding, mask_blur)
    upscaler.setup_seams_fix(seams_fix_padding, seams_fix_denoise, seams_fix_mask_blur, seams_fix_width, seams_fix_type)
    upscaler.print_info()
    upscaler.add_extra_info()
    upscaler.process()
    result_images = upscaler.result_images

    logger.info("[USDU Batch Debug] Patched script.run() complete, batch_size=%s", p.batch_size)
    return usdu.processing.Processed(p, result_images, seed, upscaler.initial_info or "")


# Replace the original script.run with patched version
usdu.Script.run = patched_script_run


# -------------------------
# Replace USDURedraw.linear_process and chess_process with batched variants
# -------------------------
def patch_usdu_linear_and_chess_process():
    old_linear = usdu.USDURedraw.linear_process
    old_chess = usdu.USDURedraw.chess_process

    @wraps(old_linear)
    def new_linear_process(self, p, image, rows, cols):
        batch_size = getattr(p, 'batch_size', 1)
        logger.info("[USDU Batch Debug] linear_process called batch_size=%s rows=%s cols=%s total_tiles=%s", batch_size, rows, cols, rows * cols)

        if batch_size <= 1:
            logger.info("[USDU Batch Debug] Using original single-tile processing (batch_size=%s)", batch_size)
            return old_linear(self, p, image, rows, cols)

        # Batch mode
        mask_template, draw_template = self.init_draw(p, image.width, image.height)
        tiles_to_process: List[Tuple[int, int]] = []
        batch_count = 0

        for yi in range(rows):
            for xi in range(cols):
                if shared.state.interrupted:
                    break

                tiles_to_process.append((xi, yi))

                if len(tiles_to_process) >= batch_size or (yi == rows - 1 and xi == cols - 1):
                    batch_count += 1
                    logger.info("[USDU Batch Debug] Processing batch #%s with %s tiles: %s", batch_count, len(tiles_to_process), tiles_to_process)
                    shared.batch = process_batch_tiles(p, tiles_to_process, shared.batch, self.calc_rectangle)
                    tiles_to_process = []

        logger.info("[USDU Batch Debug] Linear processing complete. Processed %s batches total.", batch_count)

        p.width = image.width
        p.height = image.height
        return image

    @wraps(old_chess)
    def new_chess_process(self, p, image, rows, cols):
        batch_size = getattr(p, 'batch_size', 1)
        if batch_size <= 1:
            return old_chess(self, p, image, rows, cols)

        mask_template, draw_template = self.init_draw(p, image.width, image.height)

        # Determine tile "white/black" order
        tile_colors = []
        for yi in range(rows):
            row_colors = []
            for xi in range(cols):
                color = xi % 2 == 0
                if yi > 0 and yi % 2 != 0:
                    color = not color
                row_colors.append(color)
            tile_colors.append(row_colors)

        # Helper to iterate tiles in chess order: white first, then black
        def chess_order_iter(white: bool):
            for yi in range(rows):
                for xi in range(cols):
                    if tile_colors[yi][xi] == white:
                        yield (xi, yi)

        # Process white tiles then black tiles
        for color in (True, False):
            tiles_to_process: List[Tuple[int, int]] = []
            for tx, ty in chess_order_iter(color):
                if shared.state.interrupted:
                    break
                tiles_to_process.append((tx, ty))
                if len(tiles_to_process) >= batch_size:
                    shared.batch = process_batch_tiles(p, tiles_to_process, shared.batch, self.calc_rectangle)
                    tiles_to_process = []
            if tiles_to_process:
                shared.batch = process_batch_tiles(p, tiles_to_process, shared.batch, self.calc_rectangle)

        p.width = image.width
        p.height = image.height
        return image

    usdu.USDURedraw.linear_process = new_linear_process
    usdu.USDURedraw.chess_process = new_chess_process


patch_usdu_linear_and_chess_process()
logger.info("USDU batch patches applied successfully.")
