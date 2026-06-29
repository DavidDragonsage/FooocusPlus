import os

# transformers v5 removed PYTORCH_PRETRAINED_BERT_CACHE and TRANSFORMERS_CACHE
PYTORCH_PRETRAINED_BERT_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")