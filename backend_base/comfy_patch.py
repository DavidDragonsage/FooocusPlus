# backend_base/comfy_patch.py
import os
import re
from pathlib import Path
from common import ROOT


def apply_comfy_patch():
    """
    Executes all automated path injections,
    selective logging mutes, and file patching
    required to keep ComfyUI fully stable under CUDA 13.
    """
    #  Clean the local system PATH to prevent
    #  PyTorch/CUDA from resolving obsolete PhysX DLLs
    try:
        path_env = os.environ.get('PATH', '')
        if 'PhysX' in path_env:
            cleaned_paths = [p for p in path_env.split(os.pathsep) if 'PhysX' not in p]
            os.environ['PATH'] = os.pathsep.join(cleaned_paths)
    except Exception as e:
        print('[ComfyPatch] Warning: Failed to clean local PATH environment: ' + str(e))

    try:
        comfy_dir = (Path(ROOT) / 'comfy').resolve()
        comfy_main = comfy_dir / 'main.py'

        if comfy_main.exists():
            content = comfy_main.read_text(encoding='utf-8')
            patch_marker = '# FooocusPlus ComfyUI path injection'
            end_marker = '# FooocusPlus ComfyUI path injection end'

            # 1. Surgical Self-Healing Recovery Block
            # If the file contains a legacy patch, slice out the entire polluted block
            if patch_marker in content:
                start_idx = content.find(patch_marker)
                
                # Check for our clean end marker first
                if end_marker in content:
                    end_idx = content.rfind(end_marker)
                    clean_content = content[:start_idx] + content[end_idx + len(end_marker):]
                else:
                    # Legacy Recovery: Search from the end to find the absolute end of any old hooks
                    hook_end = 'logging.Logger.warning = _safe_logger_warning'
                    end_idx = content.rfind(hook_end)
                    if end_idx != -1:
                        clean_content = content[:start_idx] + content[end_idx + len(hook_end):]
                    else:
                        clean_content = content.replace(patch_marker, '')
                
                # Strip out leading whitespace/newlines
                clean_content = clean_content.lstrip()
            else:
                clean_content = content

            # 2. Re-apply the clean, non-recursive patch block
            patch_code = (
                f"{patch_marker}\n"
                "import sys\n"
                "from pathlib import Path\n"
                "import logging\n"
                "comfy_dir = Path(__file__).parent.resolve()\n"
                "if str(comfy_dir) not in sys.path:\n"
                "    sys.path.insert(0, str(comfy_dir))\n"
                "\n"
                "# 1. Surgical Logging Filter: Mute comfy_kitchen while preserving standard [INFO] logs\n"
                "_orig_logger_info = logging.Logger.info\n"
                "def _safe_logger_info(self, msg, *args, **kwargs):\n"
                "    msg_str = str(msg)\n"
                "    # Filter out noisy comfy_kitchen, asset seeder, and partial torch compile logs\n"
                "    if 'comfy_kitchen' in msg_str or 'comfy-kitchen' in msg_str or 'Asset seeder' in msg_str or 'Partial torch compile' in msg_str:\n"
                "        return\n"
                "    # Intercept and rewrite the raw Comfy GUI URL with a clean status message\n"
                "    if 'To see the GUI go to' in msg_str:\n"
                "        _orig_logger_info(self, 'Comfy loading complete!', *args, **kwargs)\n"
                "        return\n"
                "    _orig_logger_info(self, msg, *args, **kwargs)\n"
                "logging.Logger.info = _safe_logger_info\n"
                "\n"
                "# 2. Filter out noisy, non-fatal CUDA/PyTorch warnings while preserving other system warnings\n"
                "_orig_logger_warning = logging.Logger.warning\n"
                "def _safe_logger_warning(self, msg, *args, **kwargs):\n"
                "    msg_str = str(msg)\n"
                "    # Added 'comfyui-workflow-templates' to silently swallow the version mismatch box\n"
                "    if 'Unsupported Pytorch' in msg_str or 'cu130' in msg_str or 'VRAM estimates' in msg_str or 'IMPORT FAILED' in msg_str or 'comfy_extras' in msg_str or 'comfyui-workflow-templates' in msg_str:\n"
                "        return\n"
                "    _orig_logger_warning(self, msg, *args, **kwargs)\n"
                "logging.Logger.warning = _safe_logger_warning\n"
                f"{end_marker}\n\n"
            )

            new_content = patch_code + clean_content
            # Only write to disk if the file differs (prevents unnecessary SSD wear-and-tear)
            if content != new_content:
                comfy_main.write_text(new_content, encoding='utf-8')
                print('[ComfyPatch] Successfully applied ComfyUI path and silent logging patch!')

            # 3. Self-Healing Placeholder: Write a valid, empty node mapping to satisfy Comfy's loader and silence GLSL/OpenGL errors
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

            # 4. Self-Healing rgthree-comfy Patch: Mute the tedious "Nodes 2.0" warning inside __init__.py
            rgthree_dir = comfy_dir / 'custom_nodes' / 'rgthree-comfy'
            rgthree_init = rgthree_dir / '__init__.py'

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

    # 5. Programmatic System Patch:
    # Automatically remove the obsolete NVIDIA NGC
    # extra-index-url from the untracked local
    # pip.ini file to solve DNS warnings for
    # existing users.
    python_embedded_dir = Path(ROOT).parent / 'python_embedded'
    if python_embedded_dir.is_dir():
        try:
            pip_ini = python_embedded_dir / 'pip.ini'
            if pip_ini.is_file():
                content = pip_ini.read_text(encoding='utf-8')
                if 'pypi.ngc.nvidia.com' in content:
                    lines = content.splitlines()
                    # Strip out any line containing the obsolete NVIDIA package index
                    cleaned_lines = [l for l in lines if 'pypi.ngc.nvidia.com' not in l]
                    pip_ini.write_text('\n'.join(cleaned_lines), encoding='utf-8')
                    print('[ComfyPatch] Successfully removed obsolete NVIDIA package index from python_embedded pip.ini!')
        except Exception as e:
            print(f"[ComfyPatch] Warning: Failed to sanitize python_embedded pip.ini: {e}")

    return