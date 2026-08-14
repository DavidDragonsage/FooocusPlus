import random
import shutil
import torch
from pathlib import Path
from transformers import T5Tokenizer, T5ForConditionalGeneration

import modules.loader as loader
from common import ROOT
from common import torch_device
from enhanced.superprompt import *
from enhanced.translator import interpret


def load_models():
    global tokenizer, model, modelDir

    if tokenizer is None or model is None:
        if not modelDir.exists():
            org_modelDir = Path(ROOT) / 'models' / 'llms' / 'superprompt-v1'
            shutil.copytree(org_modelDir, modelDir)

        if not (modelDir / 'model.safetensors').exists():
            interpret('[SuperPrompter] Downloading the model files for superprompter. \n')
            loader.download_superprompter_model()

        # Cast Path objects to string inside HuggingFace methods for robust compatibility
        tokenizer = T5Tokenizer.from_pretrained(str(modelDir))
        model = T5ForConditionalGeneration.from_pretrained(str(modelDir), torch_dtype=torch.float16).to(torch_device)
