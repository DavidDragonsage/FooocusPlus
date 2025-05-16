import os
from modules import config

def create_model_structure():
  # ensure that all the special model directories exist
  os.makedirs(config.paths_checkpoints[0] + '\Alternative', exist_ok=True)
  os.makedirs(config.paths_checkpoints[0] + '\Flux', exist_ok=True)
  os.makedirs(config.paths_checkpoints[0] + '\LowVRAM', exist_ok=True)
  os.makedirs(config.paths_checkpoints[0] + '\Pony', exist_ok=True)
  os.makedirs(config.paths_checkpoints[0] + '\SD1.5', exist_ok=True)
  os.makedirs(config.paths_checkpoints[0] + '\SD3x', exist_ok=True)

  # ensure that the special LoRA directories exist
  os.makedirs(config.paths_loras[0] + '\common\Alternative', exist_ok=True)        
  os.makedirs(config.paths_loras[0] + '\common\Flux', exist_ok=True)
  os.makedirs(config.paths_loras[0] + '\common\Pony', exist_ok=True)
  os.makedirs(config.paths_loras[0] + '\common\SD1.5', exist_ok=True)
  os.makedirs(config.paths_loras[0] + '\common\SD3x', exist_ok=True)

  return
