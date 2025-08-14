import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.append(str(ROOT))
os.chdir(ROOT)

import enhanced.version as version

old_version, old_hotfix = version.get_fooocusplus_ver()
print(f'Welcome to FooocusPlus {old_version}: checking for updates...')


try:
    import pygit2
    pygit2.option(pygit2.GIT_OPT_SET_OWNER_VALIDATION, 0)

    repo = pygit2.Repository(os.path.abspath(os.path.dirname(__file__)))

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
        print(f'{branch_name if branch_name!="main" else "FooocusPlus"}: Already up-to-date, {str(local_commit.id)[:7]}')
    elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
        local_branch.set_target(remote_commit.id)
        repo.head.set_target(remote_commit.id)
        repo.checkout_tree(repo.get(remote_commit.id))
        repo.reset(local_branch.target, pygit2.GIT_RESET_HARD)
        print(f'{branch_name if branch_name!="main" else "FooocusPlus"}: Fast-forward merge, {str(local_commit.id)[:7]} <- {str(remote_commit.id)[:7]}')
    elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
        print(f'{branch_name if branch_name!="main" else "FooocusPlus"}: Update failed - Did you modify any files? {str(local_commit.id)[:7]} <- {str(remote_commit.id)[:7]}')
except Exception as e:
    print(f'{branch_name if branch_name!="main" else "FooocusPlus"}: Update failed.')
    print(str(e))

new_version, new_hotfix = version.get_fooocusplus_version()
if new_version != old_version:
    print(f'Updated FooocusPlus from {old_version} to {new_version}')
elif new_hotfix != old_hotfix:
    print(f'Updated FooocusPlus to Hotfix {new_version}')
print()

from launch import *
