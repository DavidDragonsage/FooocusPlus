import os

# These pseudo globals are imported by several
# functions and are subject to change
GRADIO_ROOT = None
MODELS_INFO = None
# SDXL aspect ratio selection
ASPECT_SDXL = ''

# ROOT is used as a constant that
# is referenced by several modules
ROOT = os.path.dirname(os.path.abspath(__file__))
