import modules.user_structure as US
from enhanced.translator import interpret
from pathlib import Path

# new features for the UI
def control_notification(enable_notification):
    if enable_notification:
        masters_path = Path('masters').resolve()
        master_audio_path = Path(masters_path/'master_audio/notification.mp3')
        US.mkdir_copy_file(master_audio_path, Path.cwd())
        user_audio_path = Path(US.user_dir_path/'user_audio')
        US.make_dir(user_audio_path)
        random_source_file = US.random_file_copy(user_audio_path, Path.cwd(), 'notification.mp3')
        if not random_source_file:
            random_source_file = 'notification.mp3'
        interpret('[Features] Enabled audio notification using:', random_source_file)
    else:
        interpret('[Features] Disabled audio notification')
    return


def add_to_favorites(preset_file, category_selection):
    preset_file = f'{preset_file}.json'
    master_presets_path = Path('masters/master_presets')
    source_file = Path(master_presets_path/category_selection/preset_file)
    dest_dir = Path(US.user_dir_path/f'user_presets/Favorite')
    success = US.mkdir_copy_file(source_file, dest_dir)
    if success:
        interpret('[Features] Added to favorites:', preset_file)
    else:
        interpret('[Features] Could not add to favorites:', preset_file)
    return

def remove_from_favorites(preset_file):
    source_file = Path(US.user_dir_path/f'user_presets/Favorite/{preset_file}.json')
    dest_dir = Path(US.user_dir_path/f'user_presets/Old Favorites')
    success = US.move_file(source_file, dest_dir)
    if success:
        interpret('[Features] Removed from favorites:', preset_file)
        interpret('and saved it to', dest_dir)
    else:
        interpret('[Features] Could not remove from favorites:', preset_file)
    return success
