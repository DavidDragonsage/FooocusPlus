import argparse
import enum
from pathlib import Path

current_dir = Path.cwd()


class EnumAction(argparse.Action):
    """
    Argparse action for handling Enums
    """
    def __init__(self, **kwargs):
        # Pop off the type value
        enum_type = kwargs.pop("type", None)

        # Ensure an Enum subclass is provided
        if enum_type is None:
            raise ValueError("type must be assigned an Enum when using EnumAction")
        if not issubclass(enum_type, enum.Enum):
            raise TypeError("type must be an Enum when using EnumAction")

        # Generate choices from the Enum
        choices = tuple(e.value for e in enum_type)
        kwargs.setdefault("choices", choices)
        kwargs.setdefault("metavar", f"[{','.join(list(choices))}]")

        super(EnumAction, self).__init__(**kwargs)

        self._enum = enum_type

    def __call__(self, parser, namespace, values, option_string=None):
        # Convert value back into an Enum
        value = self._enum(values)
        setattr(namespace, self.dest, value)

parser = argparse.ArgumentParser()

parser.set_defaults(
    disable_cuda_malloc=True,
    in_browser=True,
    port=None
)


parser.add_argument("--user-dir", type=str,
    default = Path(current_dir.resolve().parent/'UserDir'),
    help="This specifies the location of the user directory. "
    "It defaults to FooocusPlus/UserDir")

parser.add_argument("--config", type=str, default=None,
    help="The location of config.txt. "
    "By default it is found in FooocusPlus/UserDir")

parser.add_argument("--models-root", type=str, default=None,
    help="the primary location for generative AI models. "
    "Typically set by the config.txt 'path_models_root' option.")

parser.add_argument("--temp-path", type=str, default=None,
    help="The location for temporary image files. "
    "Also set by config.txt 'temp_path'."
    "Arguments always take priority.")

parser.add_argument("--output-path", type=str, default=None,
    help="The storage location for generated images. "
    "This can also be set with the config.txt 'path_outputs' option.")

parser.add_argument("--disable-metadata", action='store_true',
    help="Do not save metadata info. to images. "
    "Also set by config.txt 'default_save_metadata_to_images'")


parser.add_argument("--language", type=str, default='en',
    help="Set to any of the two letter codes in the "
    "Language Pack Codes table: "
    "https://github.com/DavidDragonsage/FooocusPlus/wiki/Language-Packs-for-Prompt-Translation#language-pack-codes "
    "Defaults to 'en' (US English).")

parser.add_argument("--hf-mirror", type=str, default=None,
    help="An alternate source for Hugging Face downloads, "
    "for use in East Asia. "
    "Set to https://hf-mirror.com/ to activate.")


parser.add_argument("--preset", type=str, default='Default',
    help="Start FooocusPlus with a specific preset.")

parser.add_argument("--disable-preset-selection", action='store_true',
    help="Do not allow presets to be changed in the user interface (UI).")

parser.add_argument("--always-download-new-model",
    action='store_true', default=False,
    help="Allow presets to download new models when required.")

parser.add_argument("--disable-preset-download",
    action='store_true', default=False,
    help="Prevent presets from downloading new models.")


parser.add_argument("--theme", type=str, default='dark',
    help="Launch FooocusPlus with a light or dark theme")


parser.add_argument("--always-offload-from-vram", action="store_true",
    help="Unload video memory (VRAM) whenever possible."
    "May be needed if there is limited VRAM.")

parser.add_argument("--disable-offload-from-vram", action="store_true",
    help="Operate in Smart Memory mode: VRAM will be unloaded only when necessary")


parser.add_argument("--gpu-type", type=str, default='auto',
    help="Manual setting for GPU, overriding Torchruntime. "
    "The values are amd64, auto, cu124, cu128, directml, rocm5.2, rocm5.7")

parser.add_argument("--gpu-device-id", type=int, default=None, metavar="DEVICE_ID",
    help="Sets the device ID if you have more than one NVIDIA GPU")

parser.add_argument("--directml", type=int, nargs="?",
    metavar="DIRECTML_DEVICE", const=-1,
    help="Specifies the device ID for DirectML compatible GPUs, "
    "if you have more than one.")


parser.add_argument("--disable-attention-upcast", action="store_true",
    help="Reduces stability during attention calculations. "
    "Only used for debugging.")

parser.add_argument("--disable-ipex-hijack", action="store_true",
    help="An option used with some Intel XPUs.")

parser.add_argument("--disable-server-info", action="store_true",
    help="Used with external images in ldm_patched, function unknown.")

parser.add_argument("--disable-xformers", action="store_true",
    help="Disable the xformers library for debugging purposes. Rarely used.")

parser.add_argument("--pytorch-deterministic", action="store_true",
    help="Can produce identical results but reduces image generation speed.")

parser.add_argument("--vae-in-cpu", action="store_true",
    help="Reduces VRAM usage but significantly slows down image generation.")


parser.add_argument("--dev", action='store_true', default=False,
    help="Use the developer branch, if available. "
    "FooocusPlus typically does not deploy a developer branch.")

parser.add_argument("--disable-comfyd", action='store_true', default=False,
    help="Prevent FooocusPlus from using Comfy")

parser.add_argument("--in-browser", action="store_true",
    help="These two browser related arguments determine "
    "whether FooocusPlus will use a user interface.")

parser.add_argument("--disable-in-browser", action="store_true",
    help="Either or both of these browser arguments "
    "may be removed in the future.")

parser.add_argument("--rebuild-hash-cache",
    type=int, nargs="?", metavar="CPU_NUM_THREADS", const=-1,
    help="Generates missing model and LoRA hashes. "
    "This is normally an automatic function.")


fp_group = parser.add_mutually_exclusive_group()
fp_group.add_argument("--all-in-fp32", action="store_true")
fp_group.add_argument("--all-in-fp16", action="store_true")

attn_group = parser.add_mutually_exclusive_group()
attn_group.add_argument("--attention-pytorch", action="store_true")
attn_group.add_argument("--attention-split", action="store_true")
attn_group.add_argument("--attention-quad", action="store_true")

cm_group = parser.add_mutually_exclusive_group()
cm_group.add_argument("--async-cuda-allocation", action="store_true")
cm_group.add_argument("--disable-async-cuda-allocation", action="store_true")

fpte_group = parser.add_mutually_exclusive_group()
fpte_group.add_argument("--clip-in-fp8-e4m3fn", action="store_true")
fpte_group.add_argument("--clip-in-fp8-e5m2", action="store_true")
fpte_group.add_argument("--clip-in-fp16", action="store_true")
fpte_group.add_argument("--clip-in-fp32", action="store_true")

fpunet_group = parser.add_mutually_exclusive_group()
fpunet_group.add_argument("--unet-in-fp8-e4m3fn", action="store_true")
fpunet_group.add_argument("--unet-in-fp8-e5m2", action="store_true")
fpunet_group.add_argument("--unet-in-bf16", action="store_true")
fpunet_group.add_argument("--unet-in-fp16", action="store_true")

fpvae_group = parser.add_mutually_exclusive_group()
fpvae_group.add_argument("--vae-in-bf16", action="store_true")
fpvae_group.add_argument("--vae-in-fp16", action="store_true")
fpvae_group.add_argument("--vae-in-fp32", action="store_true")

vram_group = parser.add_mutually_exclusive_group()
vram_group.add_argument("--always-gpu", action="store_true")
vram_group.add_argument("--always-high-vram", action="store_true")
vram_group.add_argument("--always-normal-vram", action="store_true")
vram_group.add_argument("--always-low-vram", action="store_true")
vram_group.add_argument("--always-no-vram", action="store_true")
vram_group.add_argument("--always-cpu", type=int, nargs="?", metavar="CPU_NUM_THREADS", const=-1)

args = parser.parse_args([])
args = parser.parse_args()

if args.disable_in_browser:
   args.in_browser = False
