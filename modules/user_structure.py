import json
import random
import shutil
from pathlib import Path
from enhanced.translator import interpret


# default user_dir_path
# it is set to the actual path by create_user_structure(user_dir)
current_dir = Path.cwd()
user_dir_path = Path(current_dir.resolve().parent/'UserDir')

# these are platform independent functions, for universal use:

def copy_dirs(arg_source, arg_dest): # dirs including files
    source_path = Path(arg_source)
    dest_path = Path(arg_dest)
    shutil.copytree(source_path, dest_path, dirs_exist_ok = True)
    return

def copy_dir_structure(arg_source, arg_dest): # dirs without files
    source_path = Path(arg_source)
    dest_path = Path(arg_dest)
    for item in source_path.glob("**/*"):
        if item.is_dir():
            new_dir = dest_path / item.relative_to(source_path)
            new_dir.mkdir(parents = True, exist_ok = True)

def copy_file(arg_source, arg_dest, overwrite = False):
    # preserves metadata
    # copy one file
    # assumes the destination directory already exists
    # will not overwrite an existing file
    # otherwise use mkdir_copy_file()
    # returns booleans not file path
    file_copy = False
    file_exists = False
    source_path = Path(arg_source)
    dest_path = Path(arg_dest)
    if dest_path.is_file() and not overwrite:
        file_exists = True # file already exists
    else:
        try:
            shutil.copy2(source_path, dest_path)
            file_copy = True # file copy successful
        except:
            interpret('Could not copy', arg_source)
    return file_copy, file_exists

def copy_files(file_list, arg_dest): # preserves metadata
    # copy a list of files
    copy_count = 0
    exists_count = 0
    make_dir(arg_dest)
    for file_path in file_list:
        source_path = Path(file_path)
        dest_path = Path(arg_dest/source_path.name)
        file_copy, file_exists = copy_file(source_path, dest_path)
        if file_copy:
            copy_count += 1
        if file_exists:
            exists_count += 1
    return copy_count, exists_count

def count_files(arg_dir):
    # count files in a directory
    # ignores sub-directories
    path_dir = Path(arg_dir)
    # each time a file is found the integer 1 is produced
    # the sum functions adds all of the 1's together
    count = sum(1 for entry in path_dir.iterdir() if entry.is_file())
    return count

def delete_file(arg_file):
    remove_file_path = Path(arg_file)
    remove_file_path.unlink(missing_ok=True)
    success = not remove_file_path.is_file()
    return success

def empty_dir(arg_dir):
    # remove the directory contents
    # but not the directory itself
    result = True
    empty_path = Path(arg_dir)
    try:
        for item in empty_path.iterdir():
            if item.is_file():
                item.unlink(missing_ok=True)
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
    except Exception as error:
        interpret('Could not delete', empty_path)
        interpret('Reason:', error)
        result = False
    return result

def exists_file(arg_file):
    return Path(arg_file).is_file()

def find_dir_path(search_dir, find_dir):
    search_path = Path(search_dir)
    str_find_dir = str(find_dir)
    for dir_path in search_path.rglob(str_find_dir):
        return Path(dir_path).resolve()
    return '' # empty string for search fail

def find_file_path(search_dir, filename, excluding_dir = ''):
    search_path = Path(search_dir)
    str_filename = str(filename)
    for file_path in search_path.rglob(str_filename):
        if excluding_dir in file_path.parts:
            continue
        return Path(file_path).resolve()
    return '' # empty string for search fail

def list_files_by_patterns(search_dir, arg_pattern1='', arg_pattern2=''):
    # looks in search_dir and its subdirectories
    # returns a list corresponding to the patterns
    # a pattern could be a file extension such as "*.jpg"
    file_list = []
    file_list2 = []
    search_path = Path(search_dir)
    if arg_pattern1:
        file_list = list(search_path.rglob(arg_pattern1))
    if arg_pattern2:
        file_list2 = list(search_path.rglob(arg_pattern2))
    file_list.extend(file_list2)
    return file_list # empty list if no qualifying files found

def list_files_excluding(file_list, excluding_list):
    # file_list must be a list of pathlib objects
    # filters the file_list to omit files from the excluding_list
    # returns a file list without the exclusions
    filtered_list = []
    filtered_list = [f for f in file_list if f.name not in excluding_list]
    return filtered_list # empty list if no qualifying files found

def load_json(arg_json):  # the file is automatically closed
    load_path = Path(arg_json)
    if load_path.is_file():
        try:
            json_string = load_path.read_text(encoding="utf-8")
            json.contents = json.loads(json_string)
        except Exception as error:
            interpret('Could not load', arg_json)
            interpret('because:', error)
            json_contents = False
    else:
        json_contents = False
    return json_contents

def load_textfile(arg_textfile):  # the file is automatically closed
    # the results are returned as a list of text lines
    load_path = Path(arg_textfile)
    if load_path.is_file():
        try:
            text_contents = load_path.read_text(encoding="utf-8")
            text_list = text_contents.splitlines()
        except Exception as error:
            interpret('Could not load', arg_textfile)
            interpret('because:', error)
            text_list = False
    else:
        text_list = False
    return text_list

def locate_value(arg_list, parameter, terminator = ''):
    # find a parameter and value in a list
    # the optional terminator will truncate the value string
    # if used, the terminator is typically a space or a colon
    value = ''
    trans_table = str.maketrans('','','"')
    for line in arg_list:
        if line.startswith(parameter):
            # remove the parameter and ending space:
            value_quote = line.strip(parameter).strip()
            # remove quotation marks, if any:
            value = value_quote.translate(trans_table)
            if terminator != '':
                value_list = value.split(terminator,1)
                value = value_list[0]
            break
    return value

def make_dir(arg_dir):
    make_path = Path(arg_dir)
    if not make_path.is_dir():
        try:
            make_path.mkdir(parents = True, exist_ok = True)
        except Exception as error:
            interpret('Could not create the directory', make_path)
            interpret('because', error)
            make_path = ''
    return make_path

def mkdir_copy_file(arg_source_file, arg_dest_dir):
    # copy a file to a directory
    # ensures destination directory exists before copy
    # makes the directory if does not exist
    # returns the newly created file path if successful
    source_file_path = Path(arg_source_file)
    dest_directory_path = Path(arg_dest_dir)
    dest_file_path = dest_directory_path / source_file_path.name
    make_path = make_dir(dest_directory_path)
    if make_path:
        try:
            dest_path = shutil.copy2(source_file_path, dest_file_path)
        except:
            interpret('Could not copy the file:', arg_source_file)
            dest_path = ''
    else:
        interpret('Could not create the directory:', dest_directory_path)
        dest_path = ''
    return dest_path

def move_file(arg_source_file, arg_dest_dir):
    # makes arg_dest_dir if necessary
    # then copy file to it and delete the original
    success = mkdir_copy_file(arg_source_file, arg_dest_dir)
    if success:
        success = delete_file(arg_source_file)
    else:
        success = ''
    return success

def move_files_excluding(arg_source_dir, arg_dest_dir,
        excluding_list):
    # moves files to a new directory,
    # deleting the originals
    # ignoring files in excluding_list
    source_directory_path = Path(arg_source_dir)
    destination_directory_path = Path(arg_dest_dir)
    all_files = [f for f in source_directory_path.iterdir() if f.is_file()]
    files_to_move = list_files_excluding(all_files, excluding_list)
    moved_count = 0
    for source_file_path in files_to_move:
        success = move_file(source_file_path, destination_directory_path)
        if success:
            moved_count += 1
        else:
            interpret('Did not move', source_file_path.name)
    interpret(f'Moved {moved_count} files out of {len(all_files)}')
    return moved_count

def random_file_copy(from_dir, to_dir, as_file):
    file_list = list_files_by_patterns(from_dir, "*.mp3", "")
    if len(file_list) >0:
        random_index = random.randint(0, (len(file_list)-1))
        random_path = Path(file_list[random_index])
        dest_file = Path(to_dir/as_file)
        copy_file(random_path, dest_file, True)
        random_name = random_path.stem
    else:
        random_name = ''
    return random_name

def rename_path_name(arg_full_path, path_name):
    # renames only the filename within the full path
    # the path_name argument is equivalent to path.name
    # meaning that it is filename with extension
    full_path = Path(arg_full_path)
    parent_path = full_path.parent
    new_path = Path(parent_path/new_name)
    full_path.rename(new_path)
    return new_path

def remove_dirs(arg_dir):
    # remove directory tree, including contents
    remove_path = Path(arg_dir)
    if remove_path.is_dir():
        shutil.rmtree(remove_path, ignore_errors=True)
    return

def remove_empty_dir(arg_dir):
    # remove directory only if it is empty
    remove_empty_path = Path(arg_dir)
    success = True
    if remove_empty_path.is_dir() and not any(remove_empty_path.iterdir()):
        remove_empty_path.rmdir()
    else:
        success = False
    return success

def replace_dir(arg_old_dir, arg_new_dir):
    old_dir = Path(arg_old_dir)
    new_dir = Path(arg_new_dir)
    success = True
    if old_dir.is_dir():
        try:
            remove_dirs(new_dir)
            old_dir.replace(new_dir)
        except:
            success = False
    return success

def save_json(arg_data, arg_json):
    # the file is automatically closed
    save_path = Path(arg_json)
    try:
        with save_path.open("w", encoding="utf-8") as json_file:
            json.dump(arg_data, json_file, indent=4, ensure_ascii=False)
        success = True
    except Exception as error:
        interpret('Could not write to', arg_json)
        interpret('because:', error)
        success = False
    return success

def save_textfile(arg_data, arg_textfile):
    # the file is automatically closed
    save_path = Path(arg_textfile)
    try:
        save_path.write_text(arg_data, encoding="utf-8")
        success = True
    except Exception as error:
        interpret('Could not write to', arg_textfile)
        interpret('because:', error)
        success = False
    return success

def verify_dictionary(arg_source):
    # if it's not a dictionary, make it one
    if isinstance(arg_source, dict):
        verified_dictionary = arg_source
    elif isinstance(arg_source, str):
        try:
            verified_dictionary = json.loads(arg_source)
        except json.JSONDecodeError:
            # if the string is not a valid JSON:
            verified_dictionary = 'Invalid JSON format'
    else:
        verified_dictionary = 'Unsupported input type'
    return verified_dictionary


# file structure section
def cleanup_structure(directml=False, user_dir = '',
    python_embedded_path='', win32_root=''):
    # cleanup an error condition from version 1.0.0
    remove_dirs('python_embedded')

    # if python_embedded, remove directml if not required, 1.0.3
    if python_embedded_path.is_dir() and not directml:
        site_packages = Path(python_embedded_path/'Lib/site-packages')
        remove_path = find_dir_path(site_packages, 'torch_directml-0.2.5.dev240914.dist-info')
        if remove_path:
            interpret('Removing obsolete torch_directml files')
            remove_dirs(remove_path)
            remove_dirs(Path(site_packages/'torch_directml'))
            delete_file(Path(site_packages/'torch_directml_native.cp310-win_amd64.pyd'))

    # remove UserDir from repo, an error from 1.0.3
    remove_dirs('UserDir')
    # remove a phantom FooocusPlus from repo, and error from 1.0.5
    remove_dirs('FooocusPlus')

    # cleanup batch file clutter, effective 1.0.6
    delete_file(Path(win32_root/'run_FooocusPlus_commit.bat'))
    delete_file(Path(win32_root/'run_FooocusPlus_dev.bat'))

    # remove unused translator dir, from 1.0.7
    user_dir_path = Path(user_dir).resolve()
    remove_dirs(Path(user_dir_path/'translator_packs'))

    # removed obsolete logo & default image from welcome_images, 1.08
    delete_file(Path(user_dir_path/'welcome_images/FooocusPlusLogo.png'))

    return


def remove_obsolete_flux_folder(arg_parent_str):
    # remove obsolete Flux folder if empty, from 1.0.1
    checkpoint_path = Path(arg_parent_str)
    old_flux_path = Path(checkpoint_path/'Flux')
    old_flux_file = Path(old_flux_path/'put_flux_base_models_here')
    delete_file(old_flux_file)
    remove_empty_dir(old_flux_path)
    return


def create_model_structure(paths_checkpoints, paths_loras):

    # remove obsolete Flux folders if empty, effective 1.0.1
    remove_obsolete_flux_folder(paths_checkpoints[0])
    if len(paths_checkpoints) > 1:
        remove_obsolete_flux_folder(paths_checkpoints[1])

    # ensure that all the special model directories exist
    # and this will initialize shared model storage outside of UserDir
    checkpoint0_path = Path(paths_checkpoints[0])
    make_dir(checkpoint0_path/'Alternative')
    make_dir(checkpoint0_path/'FluxDev')
    make_dir(checkpoint0_path/'FluxKrea')
    make_dir(checkpoint0_path/'FluxSchnell')
    make_dir(checkpoint0_path/'LowVRAM')
    make_dir(checkpoint0_path/'Pony')
    make_dir(checkpoint0_path/'SD1.5')
    make_dir(checkpoint0_path/'SD3x')

    # ensure that the special LoRA directories exist
    loras0_path = Path(paths_loras[0])
    make_dir(loras0_path/'Alternative')
    make_dir(loras0_path/'Flux')
    make_dir(loras0_path/'Pony')
    make_dir(loras0_path/'SD1.5')
    make_dir(loras0_path/'SD3x')

    return


def replace_obsolete_categories(user_presets_path):
    # from 1.0.9
    arg_old_dir = Path(user_presets_path/'Flux1D')
    arg_new_dir = Path(user_presets_path/'Flux1Dev')
    replace_dir(arg_old_dir, arg_new_dir)

    arg_old_dir = Path(user_presets_path/'Flux1S')
    arg_new_dir = Path(user_presets_path/'Flux1Schnell')
    replace_dir(arg_old_dir, arg_new_dir)

    arg_old_dir = Path(user_presets_path/'HyperFlux')
    arg_new_dir = Path(user_presets_path/'HyperFlux1D')
    replace_dir(arg_old_dir, arg_new_dir)
    return


def init_starter_presets(user_presets_path, restore=False):
    # from 1.0.9
    starter_presets_path = Path('masters/starter_presets')
    user_favorites_path = Path(user_presets_path/'Favorite')
    # add starter presets to user favorites
    # but only for a new installation
    # or the "Restore Favorites" button was selected
    if not user_favorites_path.is_dir() or restore==True:
        copy_dirs(starter_presets_path, user_favorites_path)
        print()
        interpret('The Favorite directory has been initialized with five starter presets. When FooocusPlus is running, they can be added to or removed using the button under the Extras tab.')
        print()
    return

def clear_user_favorites(user_presets_path):
    source_dir = Path(user_dir_path/f'user_presets/Favorite/')
    dest_dir = Path(user_dir_path/f'user_presets/Old Favorites')
    success = move_files_excluding(source_dir, dest_dir, '')
    return success

def init_preset_structure(init=False, restore_favorites=False,
        clear_favorites=False):
    master_presets_path = Path('masters/master_presets')
    ref_master_presets_path = Path(user_dir_path/'master_presets')
    remove_dirs(ref_master_presets_path)
    copy_dirs(master_presets_path, ref_master_presets_path)

    working_presets_path = Path('presets').resolve()
    remove_dirs(working_presets_path)
    copy_dirs(master_presets_path, working_presets_path)

    user_presets_path = Path(user_dir_path/'user_presets')
    make_dir(user_presets_path)
    if init:
        replace_obsolete_categories(user_presets_path)
        init_starter_presets(user_presets_path, restore=restore_favorites)
    elif clear_favorites:
        clear_user_favorites(user_presets_path)

    # if count>0 then clear_favorites_button is Interactive:
    count=count_files(Path(user_dir_path/f'user_presets/Favorite/'))

    copy_dir_structure(master_presets_path, user_presets_path)
    copy_dirs(user_presets_path, working_presets_path)
    old_favourites_path = Path(working_presets_path/'Old Favorites')
    remove_dirs(old_favourites_path)
    # do not announce a simple call for favourites count:
    if any([init, restore_favorites, clear_favorites]):
        interpret('Verified the working preset directory:', working_presets_path)
    return count


def create_user_structure(user_dir):
    global user_dir_path
    # initialize the user directory, user_dir
    masters_path = Path('masters').resolve()
    user_dir_path = Path(user_dir).resolve()
    interpret('Initialized the user directory at:', user_dir_path)


    # initialize the user mp3 audio directory
    # which hold notification audio file options
    master_audio_path = Path(masters_path/'master_audio')
    ref_master_audio_path = Path(user_dir_path/'master_audio')
    remove_dirs(ref_master_audio_path)
    copy_dirs(master_audio_path, ref_master_audio_path)
    user_audio_path = Path(user_dir_path/'user_audio')
    make_dir(user_audio_path)
    interpret('Verified the working notification audio directory:', user_audio_path)


    # Ensure that all reference batch files
    # are current and correctly named.
    # Copy the contents of
    # masters/master_batch_startups
    # to user_dir/batch_startups.
    # The user must copy the batch file they
    # want from "FooocusPlus\UserDir\batch_startups"
    # to the parent directory, "FooocusPlus" to use it
    master_batch_path = Path(masters_path/'master_batch_startups')
    ref_master_batch_path = Path(user_dir_path/'batch_startups')
    remove_dirs(ref_master_batch_path)
    copy_dirs(master_batch_path, ref_master_batch_path)
    interpret('Verified the batch file startup directory:', ref_master_batch_path)


    # initialize the Language structure delete
    # the contents of user_dir/master_language
    # to get a clean start copy the contents of
    # '.masters/master_language' to UserDir
    # for the user's reference only
    master_language_path = Path('masters/master_language')
    ref_master_language_path = Path(user_dir_path/'master_language')
    remove_dirs(ref_master_language_path)
    copy_dirs(master_language_path, ref_master_language_path)

    # delete '.language', i.e. FooocusPlusAI/language'
    # which is used as a temporary working folder
    # initialize '.language' with the contents
    # of '.masters/master_language'
    working_language_path = Path('language').resolve()
    remove_dirs(working_language_path)
    copy_dirs(master_language_path, working_language_path)

    # overwrite '.language' with the contents
    # of user_dir './user_language'.
    # This allows a user to completely customize
    # the available languages, if desired
    user_language_path = Path(user_dir_path/'user_language')
    make_dir(user_language_path)
    copy_dir_structure(master_language_path, user_language_path)
    copy_dirs(user_language_path, working_language_path)
    interpret('Verified the working language directory:', working_language_path)


    # also initialize the Presets structure
    init_preset_structure(init=True)


    # initialize the Styles structure
    master_styles_path = Path('masters/master_styles')
    ref_master_styles_path = Path(user_dir_path/'master_styles')
    remove_dirs(ref_master_styles_path)
    copy_dirs(master_styles_path, ref_master_styles_path)

    working_styles_path = Path('sdxl_styles').resolve()
    remove_dirs(working_styles_path)
    copy_dirs(master_styles_path, working_styles_path)

    user_styles_path = Path(user_dir_path/'user_styles')
    make_dir(user_styles_path)
    samples_path = Path(user_styles_path/'samples')
    make_dir(samples_path)
    copy_dirs(user_styles_path, working_styles_path)
    interpret('Verified the working styles directory:', working_styles_path)


    # delete the contents of user_dir/master_topics to get a clean start
    # copy the contents of '.masters/master_topics' to user_dir
    # for the user's reference only
    master_topics_path = Path('masters/master_topics')
    ref_master_topics_path = Path(user_dir_path/'master_topics')
    remove_dirs(ref_master_topics_path)
    copy_dirs(master_topics_path, ref_master_topics_path)

    # delete './custom/OneButtonPrompt/random_prompt/userfiles'
    # which is used as a temporary working folder
    # initialize 'userfiles' with the contents of '.masters/master_topics'
    working_topics_path = Path('custom/OneButtonPrompt/random_prompt/userfiles')
    remove_dirs(working_topics_path)
    copy_dirs(master_topics_path, working_topics_path)

    # overwrite 'userfiles' with the contents of user_dir './user_topics'
    # this allows a user to completely customize the available topics, if desired
    user_topics_path = Path(user_dir_path/'user_topics')
    make_dir(user_topics_path)
    copy_dirs(user_topics_path, working_topics_path)
    interpret('Verfied the working Random Prompt (OneButtonPrompt) topics directory:')
    print(f' {working_topics_path.resolve()}')


    working_welcome_path = Path(user_dir_path/'welcome_images')
    copy_dirs(Path(masters_path/'master_control_images'), Path(user_dir_path/'control_images'))
    copy_dirs(Path(masters_path/'master_welcome_images'), working_welcome_path)
    # welcome.png is required in masters
    # but must not available to the random png selector:
    delete_file(Path(working_welcome_path/'welcome.png'))
    interpret('Verified the working welcome directory:', working_welcome_path)

    working_wildcards_path = Path(user_dir_path/'wildcards')
    copy_dirs(Path(masters_path/'master_wildcards'), working_wildcards_path)
    interpret('Verified the working wildcards directory:', working_wildcards_path)

    return
