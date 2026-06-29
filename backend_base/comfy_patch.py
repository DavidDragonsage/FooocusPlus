# backend_base/comfy_patch.py
import re
from pathlib import Path
from common import ROOT


def apply_comfy_patch():
    """
    Executes all automated path injections, selective logging mutes,
    and file patching required to keep ComfyUI fully stable under CUDA 13.
    """
    try:
        comfy_dir = (Path(ROOT) / 'comfy').resolve()
        comfy_main = comfy_dir / 'main.py'

        # [Debug Print] Confirm the launcher is calling the patcher and checking main.py
        # print(f"[Debug] Patcher loaded. Checking comfy_main: {comfy_main}, exists: {comfy_main.exists()}")

        if comfy_main.exists():
            # 1. Self-Healing Disk Patch: Prepend the version override directly into main.py
            content = comfy_main.read_text(encoding='utf-8')
            patch_marker = '# FooocusPlus ComfyUI path injection'

            # Revert to our standard surgical filter marker to trigger the automatic silent overwrite on disk
            logging_marker = '# FooocusPlus ComfyUI surgical logging filter'
            if patch_marker not in content or logging_marker not in content:
                # Strip out any legacy debug patches first to prevent duplication
                clean_content = content.replace(patch_marker, '').replace('# FooocusPlus ComfyUI method-level logging mute - DEBUGRUN', '').replace('# FooocusPlus ComfyUI verbose logging active', '') if patch_marker in content else content

                patch_code = (
                    f"{patch_marker}\n"
                    f"{logging_marker}\n"
                    "import sys\n"
                    "from pathlib import Path\n"
                    "import logging\n"
                    "comfy_dir = Path(__file__).parent.resolve()\n"
                    "if str(comfy_dir) not in sys.path:\n"
                    "    sys.path.insert(0, str(comfy_dir))\n"
                    "\n"
                    "# 1. Surgical Logging Filter: Mute comfy_kitchen while preserving standard [INFO] logs\n"
                    "# We ONLY patch logging.Logger class methods to prevent circular recursion deadlocks!\n"
                    "_orig_logger_info = logging.Logger.info\n"
                    "def _safe_logger_info(self, msg, *args, **kwargs):\n"
                    "    msg_str = str(msg)\n"
                    "    # Filter out noisy comfy_kitchen and asset seeder logs\n"
                    "    if 'comfy_kitchen' in msg_str or 'comfy-kitchen' in msg_str or 'Asset seeder' in msg_str:\n"
                    "        return\n"
                    "    _orig_logger_info(self, msg, *args, **kwargs)\n"
                    "logging.Logger.info = _safe_logger_info\n"
                    "\n"
                    "# 2. Filter out noisy, non-fatal CUDA/PyTorch warnings while preserving other system warnings\n"
                    "_orig_logger_warning = logging.Logger.warning\n"
                    "def _safe_logger_warning(self, msg, *args, **kwargs):\n"
                    "    msg_str = str(msg)\n"
                    "    if 'Unsupported Pytorch' in msg_str or 'cu130' in msg_str or 'VRAM estimates' in msg_str or 'IMPORT FAILED' in msg_str or 'comfy_extras' in msg_str:\n"
                    "        return\n"
                    "    _orig_logger_warning(self, msg, *args, **kwargs)\n"
                    "logging.Logger.warning = _safe_logger_warning\n\n"
                )
                comfy_main.write_text(patch_code + clean_content, encoding='utf-8')
                print('[ComfyPatch] Successfully applied ComfyUI path and silent logging patch!')

            # 2. Self-Healing Placeholder: Write a valid, empty node mapping to satisfy Comfy's loader and silence GLSL/OpenGL errors
            glsl_nodes = comfy_dir / 'comfy_extras' / 'nodes_glsl.py'
            placeholder_text = (
                "# FooocusPlus placeholder to silence unused OpenGL nodes\n"
                "NODE_CLASS_MAPPINGS = {}\n"
                "NODE_DISPLAY_NAME_MAPPINGS = {}\n"
            )
            if not glsl_nodes.exists() or glsl_nodes.read_text(encoding='utf-8') != placeholder_text:
                try:
                    glsl_nodes.write_text(placeholder_text, encoding='utf-8')
                    print('[ComfyPatch] Created empty placeholder for unused OpenGL nodes.')
                except Exception as e:
                    print(f"[ComfyPatch] Warning: Failed to create placeholder for OpenGL nodes: {e}")

            # 3. Self-Healing rgthree-comfy Patch: Mute the tedious "Nodes 2.0" warning inside __init__.py
            rgthree_dir = comfy_dir / 'custom_nodes' / 'rgthree-comfy'
            rgthree_init = rgthree_dir / '__init__.py'

            # [Debug Print] Check the physical path to rgthree's __init__.py
            # print(f"[Debug] Checking rgthree_init: {rgthree_init}, exists: {rgthree_init.exists()}")

            if rgthree_init.exists():
                rgthree_content = rgthree_init.read_text(encoding='utf-8')
                rgthree_marker = '# FooocusPlus rgthree-comfy Nodes 2.0 warning mute'
                if rgthree_marker not in rgthree_content:
                    # Clean out any old patch attempts
                    rgthree_content = rgthree_content.replace(rgthree_marker, '')

                    # Target the conditional statement directly to make it always fail (if False:)
                    old_line = "if get_config_value('announcements.comfy-nodes-20.incompatible', True):"
                    new_line = f"if False:  {rgthree_marker}"

                    if old_line in rgthree_content:
                        rgthree_content = rgthree_content.replace(old_line, new_line)
                        rgthree_init.write_text(rgthree_content, encoding='utf-8')
                        print('[ComfyPatch] Successfully muted rgthree-comfy Nodes 2.0 warning!')
                    else:
                        print('[ComfyPatch] Warning: Failed to find Nodes 2.0 warning condition in rgthree-comfy __init__.py')

    except Exception as e:
        print(f"[ComfyPatch] Warning: Failed to apply CUDA 13 / Comfy compatibility patch: {e}")

    return
