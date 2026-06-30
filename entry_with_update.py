import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.append(str(ROOT))
os.chdir(ROOT)

import common

import enhanced.version as version
old_version, old_hotfix, old_hotfix_title = version.get_fooocusplus_ver()
print(f'Welcome to FooocusPlus {old_version}.{old_hotfix_title}: checking for updates...')

try:
    from modules.launch_util import verify_installed_version
except:
    from modules.launch_installer import verify_installed_version

# ensure that pygit2 is available
# pygit2 is needed until dulwich:
verify_installed_version('pygit2', '1.18.0', False)

try:
    import pygit2
    pygit2.option(pygit2.GIT_OPT_SET_OWNER_VALIDATION, 0)
    repo = pygit2.Repository(ROOT)
    branch_name = repo.head.shorthand

    remote_name = 'origin'
    remote = repo.remotes[remote_name]
    remote.fetch()

    origin_name = 'main'
    main_name = 'main'
    local_branch_ref = f'refs/heads/{branch_name}'
    if '--dev' in (sys.argv):
        print(f'Checking the local dev branch: {branch_name}')
        local_branch_ref = f'refs/heads/{branch_name}'
        if local_branch_ref not in list(repo.references):
            remote_reference = f'refs/remotes/{remote_name}/{branch_name}'
            remote_branch = repo.references[remote_reference]
            new_branch = repo.create_branch(branch_name, repo[remote_branch.target])
            new_branch.upstream = remote_branch
        else:
            new_branch = repo.lookup_branch(branch_name)
        repo.checkout(new_branch)
        local_branch_ref = f'refs/heads/{branch_name}'
    else:
        if branch_name != main_name:
            print(f'Ready to checkout {branch_name}')
            branch_name = main_name
            local_branch_ref = f'refs/heads/{branch_name}'
            new_branch = repo.lookup_branch(branch_name)
            repo.checkout(new_branch)

    local_branch = repo.lookup_reference(local_branch_ref)
    local_commit = repo.revparse_single(local_branch_ref)

    remote_reference = f'refs/remotes/{remote_name}/{branch_name}'
    remote_commit = repo.revparse_single(remote_reference)

    merge_result, _ = repo.merge_analysis(remote_commit.id)

    if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
        print(f'{branch_name if branch_name!="main" else "FooocusPlus"} is already up-to-date')
    elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
        local_branch.set_target(remote_commit.id)
        repo.head.set_target(remote_commit.id)
        repo.checkout_tree(repo.get(remote_commit.id))
        repo.reset(local_branch.target, pygit2.GIT_RESET_HARD)
        print(f'{branch_name if branch_name!="main" else "FooocusPlus"}: Fast-forward merge, {str(local_commit.id)[:7]} <- {str(remote_commit.id)[:7]}')
    elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL or merge_result & pygit2.GIT_MERGE_ANALYSIS_NONE:
        # Reconcile diverged or rewritten remote history (force-push protection)
        print(f'{branch_name if branch_name!="main" else "FooocusPlus"}: Reconciling diverged history, resetting to remote head...')
        local_branch.set_target(remote_commit.id)
        repo.head.set_target(remote_commit.id)
        repo.checkout_tree(repo.get(remote_commit.id), strategy=pygit2.GIT_CHECKOUT_FORCE)
        repo.reset(local_branch.target, pygit2.GIT_RESET_HARD)
        print(f'{branch_name if branch_name!="main" else "FooocusPlus"}: Successfully force-updated to {str(remote_commit.id)[:7]}')
except Exception as e:
    print(f'{branch_name if branch_name!="main" else "FooocusPlus"}: Update failed.')
    print(str(e))

# ==========================================
# NEW AUTO-UPDATE & CLEANUP LOGIC FOR NESTED CUSTOM NODES
# ==========================================
print('Checking and cleaning custom_nodes...')

try:
    import subprocess
    import shutil
    import stat
    import pygit2

    # 1. Open repository and dynamically determine the absolute Git root path
    repo = pygit2.Repository(ROOT)
    git_root = Path(repo.workdir)
    # Since the repo is inside FooocusPlusAI, the custom_nodes folder is directly under git_root/comfy/custom_nodes
    custom_nodes_path = git_root.joinpath('comfy', 'custom_nodes')

    # 2. Update all tracked Git submodules to their pinned working commits
    print('Updating official custom node submodules...')
    try:
        subprocess.run(
            ['git', 'submodule', 'update', '--init', '--recursive'],
            cwd=git_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except Exception as sub_err:
        print(f'  -> Submodule update failed or skipped: {sub_err}')

    # 3. Read the current repository index
    index = repo.index
    index.read()  # Load the latest state from disk

    # 4. Identify all custom nodes tracked by the Git repository at current HEAD
    tracked_nodes = set()
    for entry in index:
        # Convert path to lowercase and split by forward slash to ensure absolute robust matching
        path_str = entry.path.replace('\\', '/').lower()
        parts = path_str.split('/')
        try:
            # Find the 'custom_nodes' segment anywhere in the tracked path
            idx = parts.index('custom_nodes')
            if idx > 0 and parts[idx - 1] == 'comfy' and len(parts) > idx + 1:
                tracked_nodes.add(parts[idx + 1])
        except ValueError:
            continue

    print(f'Tracked custom nodes in repository index: {list(tracked_nodes)}')

    if custom_nodes_path.exists() and custom_nodes_path.is_dir():
        def remove_readonly(func, path, _):
            """Clear the readonly bit and retry (crucial for Windows/.git folders)"""
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        # A. Clean up obsolete custom nodes (folders not present in the tracked index)
        if len(tracked_nodes) > 0:
            for item in custom_nodes_path.iterdir():
                if item.is_dir():
                    # Preserve special framework directories if any exist
                    if item.name.lower() in ['.git', '__pycache__']:
                        continue

                    if item.name.lower() not in tracked_nodes:
                        print(f'Removing obsolete custom node folder: {item.name}...')
                        try:
                            shutil.rmtree(item, onerror=remove_readonly)
                        except Exception as rm_err:
                            print(f'  -> Failed to remove {item.name}: {rm_err}')
        else:
            print('Warning: No tracked custom nodes found in repository index. Skipping cleanup.')
    else:
        print(f'Warning: Target custom_nodes path not found: {custom_nodes_path}')

except Exception as e:
    print(f'Error during custom_nodes cleanup/update: {str(e)}')

print()
# ==========================================

new_version, new_hotfix, new_hotfix_title = version.get_fooocusplus_ver()
try:
    if new_version != old_version:
        print(f'Updated FooocusPlus from {old_version} to {new_version}')
        common.version_update = 2
    elif new_hotfix != old_hotfix:
        print(f'Updated FooocusPlus to Hotfix {new_hotfix}')
        common.version_update = 1
except:
    pass
print()

from launch import *
