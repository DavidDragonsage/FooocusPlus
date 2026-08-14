import random
import torch
from pathlib import Path
from transformers import T5Tokenizer, T5ForConditionalGeneration

import common
import modules.loader as loader
from enhanced.translator import interpret

tokenizer = None
model = None
modelDir = Path(common.paths_llms[0]) / 'superprompt-v1'


def answer(input_text='', max_new_tokens=256, repetition_penalty=1.2, temperature=0.5, top_p=1, top_k=1, seed=-1):
    global tokenizer, model, modelDir

    if 'tokenizer' not in globals() or 'model' not in globals():
        globals()['tokenizer'] = None
        globals()['model'] = None

    if tokenizer is None or model is None:
        if not (modelDir / 'model.safetensors').exists():
            interpret('[SuperPrompt] Downloading the model files for Superprompter. \n')
            loader.download_superprompter_model()

        # Cast Path objects to string inside HuggingFace methods for robust compatibility
        tokenizer = T5Tokenizer.from_pretrained(str(modelDir))
        model = T5ForConditionalGeneration.from_pretrained(str(modelDir), torch_dtype=torch.float16).to(common.torch_device)

    input_ids = tokenizer(input_text, return_tensors='pt').input_ids.to(common.torch_device)

    outputs = model.generate(input_ids, max_new_tokens=max_new_tokens, repetition_penalty=repetition_penalty,
        do_sample=True,
        temperature=temperature,
        top_p=top_p, top_k=top_k)

    dirty_text = tokenizer.decode(outputs[0])
    text = dirty_text.replace('<pad>', '').replace('</s>', '').strip()

    return text


def remove_superprompt():
    global tokenizer, model

    if 'tokenizer' in globals():
        del tokenizer
    if 'model' in globals():
        del model
    return
