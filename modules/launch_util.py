import os
import importlib
import importlib.util
import shutil
import subprocess
import sys
import re
import logging
import importlib.metadata
import packaging.version
import pygit2
from launch_support import is_win32_standalone_build, python_embedded_path
from pathlib import Path

pygit2.option(pygit2.GIT_OPT_SET_OWNER_VALIDATION, 0)

logging.getLogger("torch.distributed.nn").setLevel(logging.ERROR)  # sshh...
logging.getLogger("xformers").addFilter(lambda record: 'A matching Triton is not available' not in record.getMessage())

re_requirement = re.compile(r"\s*([-_a-zA-Z0-9]+)\s*(?:==\s*([-+_.a-zA-Z0-9]+))?\s*")
re_req_local_file = re.compile(r"\S*/([-_a-zA-Z0-9]+)-([0-9]+).([0-9]+).([0-9]+)[-_a-zA-Z0-9]*([\.tar\.gz|\.whl]+)\s*")
#re_requirement = re.compile(r"\s*([-\w]+)\s*(?:==\s*([-+.\w]+))?\s*")

python = sys.executable
default_command_live = (os.environ.get('LAUNCH_LIVE_OUTPUT') == "1")
# the mainline Fooocus and RuinedFooocus statement:
index_url = os.environ.get('INDEX_URL', "")

target_path_install = f' -t {os.path.abspath(os.path.join(python_embedded_path, "Lib/site-packages"))}'\
    if sys.platform.startswith("win") else ''

modules_path = os.path.dirname(os.path.realpath(__file__))
script_path = os.path.dirname(modules_path)
dir_repos = "repos"

def git_clone(url, dir, name=None, hash=None):
    try:
        try:
            repo = pygit2.Repository(dir)
        except:
            Path(dir).parent.mkdir(exist_ok=True)
            repo = pygit2.clone_repository(url, str(dir))

        remote_name = 'origin'
        remote = repo.remotes[remote_name]
        remote.fetch()

        branch_name = repo.head.shorthand
        local_branch_ref = f'refs/heads/{branch_name}'

        if branch_name != name:
            branch_name = name
            local_branch_ref = f'refs/heads/{branch_name}'
            if local_branch_ref not in list(repo.references):
                remote_reference = f'refs/remotes/{remote_name}/{branch_name}'
                remote_branch = repo.references[remote_reference]
                new_branch = repo.create_branch(branch_name, repo[remote_branch.target.hex])
                new_branch.upstream = remote_branch
            else:
                new_branch = repo.lookup_branch(branch_name)
            repo.checkout(new_branch)
            local_branch_ref = f'refs/heads/{branch_name}'

        local_branch = repo.lookup_reference(local_branch_ref)
        if hash is None:
            commit = repo.revparse_single(local_branch_ref)
        else:
            commit = repo.get(hash)

        remote_url = repo.remotes[remote_name].url
        repo_name = remote_url.split('/')[-1].split('.git')[0]

        repo.checkout_tree(commit, strategy=pygit2.GIT_CHECKOUT_FORCE)
        print(f"{repo_name} {str(commit.id)[:7]} update check complete.")
    except Exception as e:
        print(f"Git clone failed for {url}: {str(e)}")


def repo_dir(name):
    return str(Path(script_path) / dir_repos / name)


def is_installed(package):
    if is_win32_standalone_build:
        library_path = os.path.abspath(f'../python_embedded/Lib/site-packages/{package}')
        if not os.path.exists(library_path):
            return False
    try:
        spec = importlib.util.find_spec(package)
    except ModuleNotFoundError:
        return False
    return spec is not None


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

def run_pip_url(command, desc=None, arg_index=index_url, live=default_command_live):
    result = True
    try:
        index_url_line = f' --index-url {arg_index}' if arg_index != '' else ''
        print(f'"{python}" -m pip {command} {target_path_install} --prefer-binary --disable-pip-version-check {index_url_line}')
        return run(f'"{python}" -m pip {command} {target_path_install} --prefer-binary {index_url_line}', desc=f"Installing {desc} from {arg_index}",
                   errdesc=f"Could not install {desc} from {arg_index}", live=live)
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

def verify_installed_version(package_name, package_ver, dependencies = False, use_index = ''):
    result = True
    index_url_line = f' --index-url {use_index}' if use_index != '' else ''
    if not is_installed_version(package_name, package_ver):
        if dependencies:
            run(f'"{python}" -m pip uninstall -y {package_name}')
            result = run_pip(f"install -U -I {package_name}=={package_ver} {index_url_line}", {package_name}, live=True)
        else:
            run(f'"{python}" -m pip uninstall -y {package_name}')
            result = run_pip(f"install -U -I --no-deps {package_name}=={package_ver} {index_url_line}", {package_name}, live=True)
    return result

def windows_patch():
    if is_win32_standalone_build:
        result = verify_installed_version('insightface', '0.7.3', False, use_index = 'https://github.com/Gourieff/Assets/raw/main/Insightface/insightface-0.7.3-cp310-cp310-win_amd64.whl')
        if result:
            print('All required library patch modules are installed')
        else:
            print('Could not install a required library patch module')
    return

met_diff = {}
def requirements_met(requirements_file):
    global met_diff
    met_diff = {}
    result = True
    with open(requirements_file, "r", encoding="utf8") as file:
        for line in file:
            line = line.strip()
            if line == "" or line.startswith("--") or line.startswith("#"):
                continue

            if ">=" in line:
                at_least = True
                # must replace ">=" with "==" for the rest of the logic to work
                line = line.replace(">=","==",1)
            else:
                at_least = False

            m = re.match(re_requirement, line)
            if m:
                package = m.group(1).strip()
                version_required = (m.group(2) or "").strip()
            else:
                m1 = re.match(re_req_local_file, line)
                if m1 is None:
                    continue
                package = m1.group(1).strip()
                if line.strip().endswith('.whl'):
                    package = package.replace('_', '-')
                version_required = f'{m1.group(2)}.{m1.group(3)}.{m1.group(4)}'

            try:
                version_installed = importlib.metadata.version(package)
            except Exception:
                met_diff.update({package:'-'})
                if package == 'cmake' or package=='https':
                    continue
                else:
                    print()
                    print(f'Could not locate the {package} package')
                    result = False

            try:
                if version_required=='' and version_installed:
                    continue
            except:
                pass

            try:
                if at_least:
                    if packaging.version.parse(version_installed) >= packaging.version.parse(version_required):
                        continue
                else:
                    if packaging.version.parse(version_installed) == packaging.version.parse(version_required):
                        continue
            except:
                pass
            result = verify_installed_version(package, version_required, False)
            if result != False:
                result = True
            version_installed = version_required
            met_diff.update({package:version_installed})

    return result
