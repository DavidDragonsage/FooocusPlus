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


def announce_version():
    # 1 = hotfix, 2 = new version
    import common
    import gradio as gr
    from args_manager import args
    from enhanced.translator import interpret
    global fooocusplus_ver, fooocusplus_line, hotfix, hotfix_line
    if common.version_update == 2 and fooocusplus_ver[0] != '0':
        interpret('Welcome to', f'FooocusPlus {fooocusplus_ver}:')
        temp_str1 = interpret('Welcome to', '', True)
        if args.language.startswith('en') or args.language == 'es' \
            or args.language == 'fr' or args.language == 'pt':
            temp_str2 = f' FooocusPlus {fooocusplus_ver}:      ' + '\n'
        else:
            temp_str2 = f' FooocusPlus {fooocusplus_ver}: ' + '\n'
        temp_str3 = interpret(fooocusplus_line)
        gr.Info(temp_str1 + temp_str2 + temp_str3)
        if int(hotfix) > 0:
            common.version_update = 1
    if common.version_update == 1:
        interpret('Updated to', f'FooocusPlus Hotfix {hotfix}:')
        temp_str1 = interpret('Updated to', '', True)
        if args.language.startswith('en'):
            temp_str2 = f' FooocusPlus Hotfix {hotfix}:     ' + '\n'
        else:
            temp_str2 = f' FooocusPlus Hotfix {hotfix}: ' + '\n'
        temp_str3 = interpret(hotfix_line)
        gr.Info(temp_str1 + temp_str2 + temp_str3)
    return
