import os
import sys
import modules.user_structure as US
from launch_support import is_win32_standalone_build, python_embedded_path
from pathlib import Path

fooocusplus_ver = ''
hotfix = ''

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
    global fooocusplus_ver, hotfix
    if not fooocusplus_ver:
        current_dir = Path.cwd().resolve()
        log_txt = US.load_textfile(Path(current_dir/'fooocusplus_log.md'))
        if log_txt == False:
            return '0.9.0', ''    # fooocusplus_ver fallback
        else:
            fooocusplus_ver = US.locate_value(log_txt, "# ")
            if fooocusplus_ver == '':
                return '0.9.9', '' # secondary fallback
        if not hotfix or hotfix == '0':
            hotfix = US.locate_value(log_txt, "* Hotfix", terminator=':')
    if hotfix == '':
        hotfix = '0'
    return fooocusplus_ver, hotfix
