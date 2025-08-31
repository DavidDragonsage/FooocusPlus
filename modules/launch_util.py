import os
import platform
import sys
import importlib          # Python standard library
import importlib.metadata # required by importlib
import importlib.util     # required by importlib
import packaging.version  # Python standard library
import subprocess
from pathlib import Path

default_command_live = (os.environ.get('LAUNCH_LIVE_OUTPUT') == "1")
index_url = os.environ.get('INDEX_URL', "")
python = sys.executable

current_dir = Path.cwd()
win32_root = current_dir.parent.parent.resolve()
python_embedded_path = Path(win32_root/'python_embedded')
is_win32_standalone_build = python_embedded_path.is_dir() and platform.system() == "Windows"

package_path = Path(python_embedded_path/"Lib/site-packages")
if package_path.is_dir():
    target_path_install = f' -t {package_path}'
else:
    target_path_install = ''


def run(command, desc=None, errdesc=None, custom_env=None, live: bool = default_command_live) -> str:
    if desc is not None:
        print(desc)

    run_kwargs = {
        "args": command,
        "shell": True,
        "env": os.environ if custom_env is None else custom_env,
        "encoding": 'utf8',
        "errors": 'ignore',
    }

    if not live:
        run_kwargs["stdout"] = run_kwargs["stderr"] = subprocess.PIPE

    result = subprocess.run(**run_kwargs)

    if result.returncode != 0:
        error_bits = [
            f"{errdesc or 'Error running command'}.",
            f"Command: {command}",
            f"Error code: {result.returncode}",
        ]
        if result.stdout:
            error_bits.append(f"stdout: {result.stdout}")
        if result.stderr:
            error_bits.append(f"stderr: {result.stderr}")
        raise RuntimeError("\n".join(error_bits))

    return (result.stdout or "")


def run_pip(command, desc=None, live=default_command_live):
    result = True
    try:
        index_url_line = f' --index-url {index_url}' if index_url != '' else ''
        return run(f'"{python}" -m pip {command} {target_path_install} --prefer-binary --disable-pip-version-check {index_url_line}', desc=f"Installing {desc}",
                   errdesc=f"Could not install {desc}", live=live)
    except Exception as e:
        print(e)
        print(f'Pip {desc} command failed: {command}')
        result = False
    return result


def is_installed_version(package, version_required):
    try:
        version_installed = importlib.metadata.version(package)
    except Exception:
        print()
        print(f'Installing the required version of {package}: {version_required}')
        return False
    if packaging.version.parse(version_required) != packaging.version.parse(version_installed):
        print()
        print(f'The current version of {package} is: {version_installed}. Installing the required version: {version_required}')
        return False
    return True

def verify_installed_version(package_name, package_ver, dependencies = False, use_index = '', package_url = ''):
    result = True
    index_url_line = f' --index-url {use_index}' if use_index != '' else ''
    if package_url:
        package_line = package_url
    else:
        package_line = f'{package_name}=={package_ver}'
    if not is_installed_version(package_name, package_ver):
        run(f'"{python}" -m pip uninstall -y {package_name}')
        if dependencies:
            result = run_pip(f"install -U -I {package_line} {index_url_line} --no-warn-script-location", {package_name}, live=True)
        else:
            result = run_pip(f"install -U -I --no-deps {package_line} {index_url_line} --no-warn-script-location", {package_name}, live=True)
    return result
