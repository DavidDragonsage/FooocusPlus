import os
import sys
import modules.user_structure as US
from pathlib import Path

from modules.launch_util import is_win32_standalone_build, \
    python_embedded_path


fooocusplus_ver = ''
fooocusplus_line = ''
hotfix = ''
hotfix_line = ''
hotfix_title = ''

required_path = Path('required_library.py')

def get_library_ver():
    global required_path
    if is_win32_standalone_build:
        embedded_version = Path(python_embedded_path/'embedded_version/library_version.py')
        if embedded_version.is_file():
            sys.path.append(str(embedded_version))
            from embedded_version import library_version
            return (library_version.version)
        else:
             return 0.96
    else:
        if required_path.is_file():
            import required_library
            return required_library.version
        else:
            return 1.00

def get_required_library():
    global required_path
    if (not required_path.is_file()) or (not is_win32_standalone_build):
        return True
    import required_library
    if get_library_ver() >= (required_library.version):
        return True
    else:
        return False


def get_fooocusplus_ver():
    global fooocusplus_ver, hotfix, hotfix_title, fooocusplus_line, hotfix_line
    current_dir = Path.cwd().resolve()
    log_txt = US.load_textfile(Path(current_dir/'fooocusplus_log.md'))
    if log_txt == False:
        return '0.9.0', '0', '0'    # fooocusplus_ver fallback
    else:
        fooocusplus_ver = US.locate_value(log_txt, '# ', terminator=' ')
        fooocusplus_line = US.locate_value(log_txt, (f'# {fooocusplus_ver} '), terminator='')
        hotfix = US.locate_value(log_txt, '* Hotfix', terminator=':')
        hotfix_line = US.locate_value(log_txt, f'* Hotfix{hotfix}:', terminator='')
        if fooocusplus_ver == '':
            return '0.9.9', '0', '0' # secondary fallback
    if hotfix == '':
        hotfix = '0'
    if int(hotfix) < 10:
        hotfix_title = '0' + hotfix
    else:
        hotfix_title = hotfix
    return fooocusplus_ver, hotfix, hotfix_title


def check_remote_pinokio_update() -> str | None:
    """
    Checks the remote GitHub repository's fooocusplus_log.md for updates.
    Returns the formatted remote version string if an update is available, otherwise None.
    """
    import httpx
    from packaging.version import parse as parse_version

    raw_log_url = 'https://raw.githubusercontent.com/DavidDragonsage/FooocusPlus/main/fooocusplus_log.md'

    try:
        # Strict 3-second timeout ensures
        # startup is never stalled if offline
        with httpx.Client(timeout=3.0) as client:
            response = client.get(raw_log_url)
            if response.status_code != 200:
                return None
            remote_text = response.text
    except Exception:
        # Fails silently if user has no internet
        # access or GitHub is unreachable
        return None

    # Parse the remote changelog lines
    remote_lines = remote_text.splitlines()
    remote_ver = US.locate_value(remote_lines, '# ', terminator=' ')
    remote_hotfix = US.locate_value(remote_lines, '* Hotfix', terminator=':')

    if not remote_ver:
        return None

    # Calculate full remote version for
    # mathematical comparison
    remote_hotfix_num = int(remote_hotfix) if remote_hotfix.isdigit() else 0
    remote_full_ver = f'{remote_ver}.{remote_hotfix_num:02d}'

    # Calculate full local version
    local_ver, local_hotfix, _ = get_fooocusplus_ver()
    local_hotfix_num = int(local_hotfix) if local_hotfix.isdigit() else 0
    local_full_ver = f'{local_ver}.{local_hotfix_num:02d}'

    # Compare versions using packaging.version
    try:
        if parse_version(remote_full_ver) > parse_version(local_full_ver):
            # Format friendly display label
            # (e.g., '1.1.8' or '1.1.7 Hotfix 03')
            if remote_hotfix_num > 0:
                display_label = f'{remote_ver} Hotfix {remote_hotfix_num:02d}'
            else:
                display_label = remote_ver
            return display_label
    except Exception:
        pass

    return None


def announce_version():
    # 1 = hotfix, 2 = new version
    import common
    import gradio as gr
    from args_manager import args as cli_args
    from enhanced.translator import interpret

    global fooocusplus_ver, fooocusplus_line, hotfix, hotfix_line

    # --- PINOKIO UPDATE NOTIFIER ---
    if getattr(cli_args, 'gpu_type', '') == 'none':
        remote_ver_label = check_remote_pinokio_update()
        if remote_ver_label:
            # Construct multilingual toast using
            # interpret(..., silent=True)
            msg_p1 = interpret('FooocusPlus', '', silent=True)
            msg_p2 = interpret('is now available.', '', silent=True)
            msg_p3 = interpret('Please use the Pinokio dashboard to install the latest release.', '', silent=True)

            gr.Info(f'{msg_p1} {remote_ver_label} {msg_p2}  {msg_p3}')
            return  # Skip standard announce_version
                    # if an update is pending
    # -------------------------------

    # Case 2: New Major/Minor Version Release
    if common.version_update == 2 and fooocusplus_ver[0] != '0':
        # 1. Print announcement to terminal console
        interpret('Welcome to', f'FooocusPlus {fooocusplus_ver}:')

        # 2. Build multi-line message for the UI popup
        welcome_prefix = interpret('Welcome to', '', silent=True)
        header = f'{welcome_prefix} FooocusPlus {fooocusplus_ver}:\n'
        body = interpret(fooocusplus_line, '', silent=True)
        gr.Info(f'{header}{body}')

        if int(hotfix) > 0:
            common.version_update = 1

    # Case 1: Hotfix Update
    if common.version_update == 1:
        # 1. Print announcement to terminal console
        interpret('Updated to', f'FooocusPlus Hotfix {hotfix}:')

        # 2. Build multi-line message for the UI popup
        update_prefix = interpret('Updated to', '', silent=True)
        header = f'{update_prefix} FooocusPlus Hotfix {hotfix}:\n'
        body = interpret(hotfix_line, '', silent=True)
        gr.Info(f'{header}{body}')

    return
