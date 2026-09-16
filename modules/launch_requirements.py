import os
import importlib
import importlib.metadata
import importlib.util
import shutil
import sys
import re
import logging
import packaging.version
import pygit2
from pathlib import Path

from modules.launch_util import is_win32_standalone_build, \
    python_embedded_path, run, verify_installed_version

met_diff = {}
pygit2.option(pygit2.GIT_OPT_SET_OWNER_VALIDATION, 0)

logging.getLogger("torch.distributed.nn").setLevel(logging.ERROR)  # sshh...
logging.getLogger("xformers").addFilter(lambda record: 'A matching Triton is not available' not in record.getMessage())


# Regex to parse PEP 508 direct wheel URLs
# (e.g. package @ https://.../package-1.0.0.whl)
re_req_direct_url = re.compile(r"^\s*([-_a-zA-Z0-9]+)\s*@\s*(\S+)\s*$")

# Regex for standard name==version or name>=version
re_requirement = re.compile(r"^\s*([-_a-zA-Z0-9]+)\s*(?:(==|>=)\s*([-+_.a-zA-Z0-9]+))?\s*$")

# Legacy fallback regex for raw wheel URLs without '@'
re_req_local_file = re.compile(r"\S*/([-_a-zA-Z0-9]+)-([0-9]+)\.([0-9]+)\.([0-9]+)[-_a-zA-Z0-9]*([\.tar\.gz|\.whl]+)\s*")


python = sys.executable
default_command_live = (os.environ.get('LAUNCH_LIVE_OUTPUT') == "1")
# the mainline Fooocus and RuinedFooocus statement:
index_url = os.environ.get('INDEX_URL', "")

package_path = Path(python_embedded_path/"Lib/site-packages")
target_path_install = f' -t {package_path}'\
    if sys.platform.startswith("win") else ''

modules_path = Path(__file__).resolve().parent
script_path = modules_path.parent
dir_repos = 'repos'


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
    return str(script_path / dir_repos / name)


def is_installed(package):
    if is_win32_standalone_build:
        library_path = (Path('../python_embedded/Lib/site-packages') / package).resolve()
        if not library_path.exists():
            return False
    try:
        spec = importlib.util.find_spec(package)
    except ModuleNotFoundError:
        return False
    return spec is not None


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



def requirements_met(requirements_file: str | Path) -> bool:
    global met_diff
    met_diff = {}
    result = True

    req_path = Path(requirements_file)
    if not req_path.exists():
        return True

    # 1. Check for command-line Comfy lockout
    try:
        from args_manager import args as cli_args
        comfy_lockout = getattr(cli_args, 'disable_comfyd', False)
    except Exception:
        comfy_lockout = False

    # 2. Check for legacy GPU Comfy lockout
    if not comfy_lockout:
        try:
            installed_torch = importlib.metadata.version('torch')
            torch_ver = [int(x) for x in installed_torch.split('+')[0].split('.')[:2]]
            comfy_lockout = (torch_ver < [2, 7])
        except Exception:
            # If Torch is not installed or detectable yet,
            # do not trigger hardware detection here.
            # Default to False so core dependencies are
            # not skipped during early setup.
            comfy_lockout = False

    # 3. Process requirements line-by-line
    with open(req_path, 'r', encoding='utf-8') as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith('--') or line.startswith('#'):
                continue

            package = ''
            version_required = ''
            package_url = ''
            at_least = False

            # Pattern A: PEP 508 direct reference
            # (package @ url)
            m_direct = re.match(re_req_direct_url, line)
            if m_direct:
                package = m_direct.group(1).strip()
                package_url = m_direct.group(2).strip()

            # Pattern B: Standard version constraint
            # (package==version or package>=version)
            elif re.match(re_requirement, line):
                m = re.match(re_requirement, line)
                package = m.group(1).strip()
                operator = m.group(2) or '=='
                at_least = (operator == '>=')
                version_required = (m.group(3) or '').strip()

            # Pattern C: Legacy raw URL
            else:
                m_legacy = re.match(re_req_local_file, line)
                if m_legacy is None:
                    continue
                package = m_legacy.group(1).strip()
                if line.endswith('.whl'):
                    package = package.replace('_', '-')
                version_required = f'{m_legacy.group(2)}.{m_legacy.group(3)}.{m_legacy.group(4)}'
                package_url = line

            # If Comfy is locked out, skip
            # ComfyUI-specific packages
            if comfy_lockout and (package.startswith('comfy') or package.startswith('comfyui')):
                continue

            # Check if package is installed in
            # the active environment
            try:
                version_installed = importlib.metadata.version(package)
            except Exception:
                version_installed = None
                met_diff.update({package: '-'})

            # Handle special system libraries that
            # should not trigger missing errors
            if version_installed is None:
                if package in ['cmake', 'https'] or (package == 'insightface' and sys.platform != 'win32'):
                    continue

            # Compare versions if already installed
            if version_installed is not None:
                if not version_required:
                    # Package exists and no specific
                    # version was demanded
                    continue

                try:
                    parsed_installed = packaging.version.parse(version_installed)
                    parsed_required = packaging.version.parse(version_required)
                    if at_least and parsed_installed >= parsed_required:
                        continue
                    elif not at_least and parsed_installed == parsed_required:
                        continue
                except Exception:
                    pass

            # Package missing or version mismatch:
            # verify and install
            install_success = verify_installed_version(
                package_name=package,
                package_ver=version_required,
                dependencies=False,
                package_url=package_url
            )

            if not install_success:
                result = False
                met_diff.update({package: version_required if version_required else 'missing'})
            else:
                met_diff.update({package: version_required if version_required else 'installed'})

    return result
