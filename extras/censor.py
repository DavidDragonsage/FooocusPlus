import numpy as np
import torch
from pathlib import Path
from transformers import CLIPConfig, CLIPImageProcessor

import ldm_patched.modules.model_management as model_management
import modules.loader as loader
from extras.safety_checker.models.safety_checker import StableDiffusionSafetyChecker
from ldm_patched.modules.model_patcher import ModelPatcher

# Resolve paths cleanly using pathlib.Path and the / operator
current_dir = Path(__file__).resolve().parent
safety_checker_repo_root = current_dir / 'safety_checker'
config_path = safety_checker_repo_root / 'configs' / 'config.json'
preprocessor_config_path = safety_checker_repo_root / 'configs' / 'preprocessor_config.json'


class Censor:
    def __init__(self):
        self.safety_checker_model: ModelPatcher | None = None
        self.clip_image_processor: CLIPImageProcessor | None = None
        self.load_device = torch.device('cpu')
        self.offload_device = torch.device('cpu')

    def init(self):
        if self.safety_checker_model is None and self.clip_image_processor is None:
            safety_checker_model = loader.download_safety_checker_model()
            
            # Cast paths to string inside third-party loaders for robust compatibility
            self.clip_image_processor = CLIPImageProcessor.from_json_file(str(preprocessor_config_path))
            clip_config = CLIPConfig.from_json_file(str(config_path))
            
            model = StableDiffusionSafetyChecker.from_pretrained(safety_checker_model, config=clip_config)
            model.eval()

            self.load_device = model_management.text_encoder_device()
            self.offload_device = model_management.text_encoder_offload_device()

            model.to(self.offload_device)

            self.safety_checker_model = ModelPatcher(model, load_device=self.load_device, offload_device=self.offload_device)

    def censor(self, images: list | np.ndarray) -> list | np.ndarray:
        self.init()
        model_management.load_model_gpu(self.safety_checker_model)

        single = False
        if not isinstance(images, (list, np.ndarray)):
            images = [images]
            single = True

        safety_checker_input = self.clip_image_processor(images, return_tensors='pt')
        safety_checker_input.to(device=self.load_device)
        checked_images, has_nsfw_concept = self.safety_checker_model.model(images=images,
                                                                           clip_input=safety_checker_input.pixel_values)
        checked_images = [image.astype(np.uint8) for image in checked_images]

        if single:
            checked_images = checked_images[0]

        return checked_images


default_censor = Censor().censor