import common
from pathlib import Path
from backend_base import backend_base, utils, comfyd, torch_version, xformers_version, cuda_version, comfyclient_pipeline
from backend_base.params_mapper import ComfyTaskParams
from backend_base.models_info import ModelsInfo, sync_model_info
from enhanced.translator import interpret

args_comfyd = [[]]
modelsinfo_filename = 'models_info.json'


# This class is called inline by config.
# The force argument is currently not used but
# would force a hard reset if that were ever needed.
# loader.update_files() performs a soft reload
# using refresh_from_path()
def init_modelsinfo(userdir_models_root, path_map, force=False):
    global modelsinfo_filename
    models_info_path = str(Path(userdir_models_root/modelsinfo_filename))

    if force:
        interpret('[Backend] Forcefully refreshing the models database and scanning local directories')
        common.MODELS_INFO = ModelsInfo(models_info_path, path_map)
    elif not common.MODELS_INFO:
        interpret('[Backend] Initializing the models database and scanning local directories')
        common.MODELS_INFO = ModelsInfo(models_info_path, path_map)
    else:
        interpret('[Backend] The models database is already initialized. Skipping the redundant scan.')

    return common.MODELS_INFO
