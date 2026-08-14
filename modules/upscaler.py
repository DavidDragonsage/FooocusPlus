from collections import OrderedDict
import torch

import modules.core as core
import modules.loader as loader
from enhanced.translator import interpret
from ldm_patched.contrib.external_upscale_model import ImageUpscaleWithModel
from ldm_patched.pfn.architecture.RRDB import RRDBNet as ESRGAN


opImageUpscaleWithModel = ImageUpscaleWithModel()
model = None


def perform_upscale(img):
    global model

    interpret('Upscaling image with shape', f'{str(img.shape)}...')

    if model is None:
        model_filename = loader.download_upscale_model()
        sd = torch.load(model_filename, weights_only=True)
        sdo = OrderedDict()
        for k, v in sd.items():
            sdo[k.replace('residual_block_', 'RDB')] = v
        del sd
        model = ESRGAN(sdo)
        model.cpu()
        model.eval()

    img = core.numpy_to_pytorch(img)
    img = opImageUpscaleWithModel.upscale(model, img)[0]
    img = core.pytorch_to_numpy(img)[0]

    return img
