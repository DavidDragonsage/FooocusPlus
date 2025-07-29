import os
import ldm_patched.modules.args_parser as args_parser
from pathlib import Path

current_dir = Path.cwd()

args_parser.parser.add_argument("--preset", type=str, default='Default',
    help="Apply specified preset parameters.")
args_parser.parser.add_argument("--disable-preset-selection", action='store_true',
    help="Disable preset selection in Gradio.")

args_parser.parser.add_argument("--language", type=str, default='en',
    help="Translate UI using json files in [language] folder. "
    "For example, [--language en_uk] will use [language/en_uk.json] for translation.")

args_parser.parser.add_argument("--gpu-type", type=str, default='auto',
    help="Manual setting for GPU, overriding Torchruntime. "
    "The values are amd64, auto, cu124, cu128, directml, rocm5.2, rocm5.7")

args_parser.parser.add_argument("--webroot", type=str, default='',
    help="Set the webroot path.")

args_parser.parser.add_argument("--location", type=str, default='CN',
    help="Set the access location by country")

# For example, https://github.com/lllyasviel/Fooocus/issues/849
args_parser.parser.add_argument("--disable-offload-from-vram", action="store_true",
    help="Operate in Smart Memory mode: VRAM will be unloaded only when necessary")

args_parser.parser.add_argument("--theme", type=str,
    help="Launch FooocusPlus with a light or dark theme", default='dark')

args_parser.parser.add_argument("--disable-image-log", action='store_true',
    help="Prevent writing image logs to the Outputs folder.")

# args_parser.parser.add_argument("--disable-analytics", action='store_true',
#   help="This is an obsolete argument: Gradio Analytics are always disabled.")
args_parser.args.disable_analytics = True
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False" # Gradio is no longer allowed to call home
os.environ["NO_ALBUMENTATIONS_UPDATE"] = "True" # an update would cause some serious errors

args_parser.parser.add_argument("--disable-metadata", action='store_true',
    help="Disable saving metadata to images.")

args_parser.parser.add_argument("--disable-preset-download", action='store_true',
    help="Disable downloading models for presets", default=False)

args_parser.parser.add_argument("--disable-enhance-output-sorting", action='store_true',
    help="Disable enhanced output sorting of the image gallery.", default=False)

args_parser.parser.add_argument("--enable-auto-describe-image", action='store_true',
    help="Enable automatic description of UOV and enhance image when prompt is empty", default=False)

args_parser.parser.add_argument("--always-download-new-model", action='store_true',
    help="Always download newer models", default=False)

args_parser.parser.add_argument("--rebuild-hash-cache",
    help="Generates missing model and LoRA hashes.",
    type=int, nargs="?", metavar="CPU_NUM_THREADS", const=-1)

args_parser.parser.add_argument("--dev", action='store_true',
    help="Launch the dev branch", default=False)

args_parser.parser.add_argument("--user-dir", type=str,
    help="Set the path to the user directory",
    default = Path(current_dir.resolve().parent/'UserDir'))

args_parser.parser.add_argument("--models-root", type=str,
    help="Set the path to the models directory", default=None)

args_parser.parser.add_argument("--config", type=str,
    help="Set the path for config.txt", default=None)

args_parser.parser.add_argument("--disable-comfyd", action='store_true',
    help="Do not auto-start the Comfy server at launch", default=False)

args_parser.parser.set_defaults(
    disable_cuda_malloc=True,
    in_browser=True,
    port=None
)

args_parser.args = args_parser.parser.parse_args()

# (Disable by default because of issues like https://github.com/lllyasviel/Fooocus/issues/724)
# This "solution" was introduced in mainline Fooocus 2.1.699
# I do not know why the always_offload_from_vram argument was not considered sufficient
# Let's try it without this secret override - David Sage
# args_parser.args.always_offload_from_vram = not args_parser.args.disable_offload_from_vram

if args_parser.args.disable_in_browser:
    args_parser.args.in_browser = False

args = args_parser.args
