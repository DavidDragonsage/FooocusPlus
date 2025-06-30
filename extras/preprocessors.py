import cv2
import numpy as np


def centered_canny(x: np.ndarray, canny_low_threshold, canny_high_threshold):
    assert isinstance(x, np.ndarray)
    assert x.ndim == 2 and x.dtype == np.uint8

    y = cv2.Canny(x, int(canny_low_threshold), int(canny_high_threshold))
    y = y.astype(np.float32) / 255.0
    return y


def centered_canny_color(x: np.ndarray, canny_low_threshold, canny_high_threshold):
    assert isinstance(x, np.ndarray)
    assert x.ndim == 3 and x.shape[2] == 3

    result = [centered_canny(x[..., i], canny_low_threshold, canny_high_threshold) for i in range(3)]
    result = np.stack(result, axis=2)
    return result


def pyramid_canny_color(x: np.ndarray, canny_low_threshold, canny_high_threshold):
    assert isinstance(x, np.ndarray)
    assert x.ndim == 3 and x.shape[2] == 3

    H, W, C = x.shape
    acc_edge = None

    for k in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        Hs, Ws = int(H * k), int(W * k)
        small = cv2.resize(x, (Ws, Hs), interpolation=cv2.INTER_AREA)
        edge = centered_canny_color(small, canny_low_threshold, canny_high_threshold)
        if acc_edge is None:
            acc_edge = edge
        else:
            acc_edge = cv2.resize(acc_edge, (edge.shape[1], edge.shape[0]), interpolation=cv2.INTER_LINEAR)
            acc_edge = acc_edge * 0.75 + edge * 0.25

    return acc_edge


def norm255(x, low=4, high=96):
    assert isinstance(x, np.ndarray)
    assert x.ndim == 2 and x.dtype == np.float32

    v_min = np.percentile(x, low)
    v_max = np.percentile(x, high)

    x -= v_min
    x /= v_max - v_min

    return x * 255.0


def canny_pyramid(x, canny_low_threshold, canny_high_threshold):
    # For some reasons, SAI's Control-lora Canny seems to be trained on canny maps with non-standard resolutions.
    # Then we use pyramid to use all resolutions to avoid missing any structure in specific resolutions.

    color_canny = pyramid_canny_color(x, canny_low_threshold, canny_high_threshold)
    result = np.sum(color_canny, axis=2)

    return norm255(result, low=1, high=99).clip(0, 255).astype(np.uint8)

def canny_standard(x, canny_low_threshold, canny_high_threshold):
    return cv2.Canny(x, int(canny_low_threshold), int(canny_high_threshold))

def cpds(x):
    # cv2.decolor is not "decolor", it is Cewu Lu's method
    # See http://www.cse.cuhk.edu.hk/leojia/projects/color2gray/index.html
    # See https://docs.opencv.org/3.0-beta/modules/photo/doc/decolor.html

    raw = cv2.GaussianBlur(x, (0, 0), 0.8)
    density, boost = cv2.decolor(raw)

    raw = raw.astype(np.float32)
    density = density.astype(np.float32)
    boost = boost.astype(np.float32)

    offset = np.sum((raw - boost) ** 2.0, axis=2) ** 0.5
    result = density + offset

    return norm255(result, low=4, high=96).clip(0, 255).astype(np.uint8)



def simple_scribble_detector(ndarray_image, threshold=127):
    """
    Scribble detector that mimics ComfyUI's 'Scribble' node behavior.

    Args:
        ndarray_image (numpy.ndarray): HWC format, uint8, RGB or BGR.
        threshold (int): Brightness threshold to detect dark lines (default=127).

    Returns:
        numpy.ndarray: Binary scribble image, HWC, uint8, white background with black lines.
    """
    # Ensure image is uint8
    if ndarray_image.dtype != np.uint8:
        img = (np.clip(ndarray_image, 0, 1) * 255).astype(np.uint8)
    else:
        img = ndarray_image.copy()

    # If image is BGR (OpenCV style), convert to RGB if needed
    if img.shape[2] == 3:
        rgb = img
    else:
        raise ValueError("Input image must have 3 channels (RGB or BGR).")

    # Create blank image
    detected_map = np.zeros((rgb.shape[0], rgb.shape[1]), dtype=np.uint8)

    # Apply brightness threshold (line detection)
    mask = (np.min(rgb, axis=2) < threshold)
    detected_map[mask] = 255  # White lines on black

    # Invert to get black lines on white background
    detected_map = 255 - detected_map

    # Convert back to 3-channel
    scribble = cv2.merge([detected_map, detected_map, detected_map])

    return scribble