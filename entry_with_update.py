import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.append(str(ROOT))
os.chdir(ROOT)

import common
#try:
import enhanced.version as version
old_version, old_hotfix, old_hotfix_title = version.get_fooocusplus_ver()
print(f'Welcome to FooocusPlus {old_version}.{old_hotfix_title}: checking for updates...')
#except:
#    print('Please restart FooocusPlus to finish the update')
#    print()
#    quit()

# transition between the two possible locations
# for verify_installed_version
# modules.launch_util was where it was
# originally and where it should be now
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
custom_nodes_path = ROOT.joinpath('FooocusPlusAI', 'comfy', 'custom_nodes')

try:
    # 1. Open the repository and read the current active index
    repo = pygit2.Repository(ROOT)
    index = repo.index
    index.read()  # Ensure we have the fresh post-checkout index state

    # 2. Identify all custom nodes tracked by the repository at the current HEAD
    tracked_nodes = set()
    for entry in index:
        # entry.path uses forward slashes; Path.parts parses it correctly on all OS
        parts = Path(entry.path).parts
        if (len(parts) >= 4 and
            parts[0] == 'FooocusPlusAI' and
            parts[1] == 'comfy' and
            parts[2] == 'custom_nodes'):
            tracked_nodes.add(parts[3])

    if custom_nodes_path.exists() and custom_nodes_path.is_dir():
        import shutil
        import stat
        import subprocess

        def remove_readonly(func, path, _):
            """Clear the readonly bit and retry (crucial for Windows/.git folders)"""
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        # A. Clean up obsolete custom nodes
        if len(tracked_nodes) > 0:
            for item in custom_nodes_path.iterdir():
                if item.is_dir():
                    # Preserve special framework directories if any exist
                    if item.name in ['.git', '__pycache__']:
                        continue

                    if item.name not in tracked_nodes:
                        print(f'Removing obsolete custom node folder: {item.name}...')
                        try:
                            shutil.rmtree(item, onerror=remove_readonly)
                        except Exception as rm_err:
                            print(f'  -> Failed to remove {item.name}: {rm_err}')
        else:
            print('Warning: No tracked custom nodes found in repository index. Skipping cleanup.')

        # B. Auto-update active nested custom node repositories
        for item in custom_nodes_path.iterdir():
            if item.is_dir() and item.name in tracked_nodes:
                if item.joinpath('.git').exists():
                    node_name = item.name
                    try:
                        print(f'Auto-updating custom node: {node_name}...')
                        subprocess.run(
                            ['git', 'pull'],
                            cwd=item,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True
                        )
                    except Exception as sub_err:
                        print(f'  -> Could not auto-update {node_name} (skipping).')

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
