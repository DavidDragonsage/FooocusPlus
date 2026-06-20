# Fooocus GPT2 Expansion
# Algorithm created by Lvmin Zhang at 2023, Stanford
# If used inside Fooocus, any use is permitted.
# If used outside Fooocus, only non-commercial use is permitted (CC-By NC 4.0).
# This applies to the word list, vocab, model, and algorithm.

import os
import torch
import math
import common
import modules.config as config
import ldm_patched.modules.model_management as model_management
import modules.user_structure as US

from enhanced.translator import interpret
from transformers.generation.logits_process import LogitsProcessorList
from transformers import AutoTokenizer, AutoModelForCausalLM, set_seed
from ldm_patched.modules.model_patcher import ModelPatcher
from pathlib import Path


# limitation of np.random.seed(), called from transformers.set_seed()
SEED_LIMIT_NUMPY = 2**32
neg_inf = - 8192.0


def safe_str(x):
    x = str(x)
    for _ in range(16):
        x = x.replace('  ', ' ')
    return x.strip(",. \r\n")


def remove_pattern(x, pattern):
    for p in pattern:
        x = x.replace(p, '')
    return x


class FooocusExpansion:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(config.path_fooocus_expansion)
        self.model = AutoModelForCausalLM.from_pretrained(config.path_fooocus_expansion)
        self.model.eval()

        # Hardware Setup
        load_device = model_management.text_encoder_device()
        offload_device = model_management.text_encoder_offload_device()

        if model_management.is_device_mps(load_device):
            load_device = torch.device('cpu')
            offload_device = torch.device('cpu')

        if model_management.should_use_fp16(device=load_device):
            self.model.half()

        self.patcher = ModelPatcher(self.model, load_device=load_device, offload_device=offload_device)

        # Internal state to track the active substyle
        self.current_substyle = None
        self.logits_bias = None

        # Initial load based on substyle state
        self.update_substyle(config.v2_substyle)

        interpret('Fooocus Expansion engine ready on', load_device)
        print()


    def update_substyle(self, substyle_name):
        """Dynamic reload of the expansion vocabulary without reloading the model."""
        if substyle_name == self.current_substyle and self.logits_bias is not None:
            return # Skip if already loaded

        # Pathlib Refactor: Construct path directly from repo structure
        v2_file = f"{substyle_name}.txt"
        v2_substyle_path = US.current_dir/ 'substyles' / v2_file

        if not v2_substyle_path.exists():
            print(f"Warning: Substyle file {v2_substyle_path} not found. Falling back to Default.")
            v2_substyle_path = US.masters_dir / 'master_fooocus_v2' / 'Default.txt'

        try:
            # Load and process word list
            with v2_substyle_path.open('r', encoding='utf-8') as f:
                positive_words = f.read().splitlines()

            # KEEP WORDS CLEAN & LOWERCASE (without the 'Ġ' prefix here)
            cleaned_words = [x.strip().lower() for x in positive_words if x.strip()]

            # Reset Logits Bias (neg_inf forces the model to ignore words NOT in our list)
            neg_inf = -1e18 # Sufficiently small number for masking
            new_bias = torch.zeros((1, len(self.tokenizer.vocab)), dtype=torch.float32) + neg_inf

            count = 0
            # Track which lowercase words from the
            # file were successfully matched in the vocabulary
            accepted_words_set = set()

            for k, v in self.tokenizer.vocab.items():
                # Strictly match tokens that start with the space prefix (representing whole-word entries)
                if k.startswith('Ġ') or k.startswith('ġ'):
                    word = k[1:].lower()

                    # Compare the clean lowercase word
                    if word in cleaned_words:
                        new_bias[0, v] = 0
                        count += 1
                        accepted_words_set.add(word)

            self.logits_bias = new_bias
            self.current_substyle = substyle_name
            interpret(f'[Expansion] Switched to the Fooocus V2 substyle', f'"{substyle_name}"')
            interpret(f'with {len(positive_words)} words and {count} tokens')

            # Real-Time Developer Audit
            # Prints to the console during generation
            if common.debug_substyles:
                # Find which words in the original file did not match any single-token in the vocabulary
                ignored_words = [w for w in positive_words if w.strip().lower() not in accepted_words_set]

                print(f"\n=============================================")
                print(f"Substyle Vocabulary Audit: {substyle_name}")
                print(f"  Total Words in File: {len(positive_words)}")
                print(f"  Active Tokens: {count}")
                print(f"  Ignored/Split Words: {len(ignored_words)}")

                if ignored_words:
                    print("  List of Ignored Words (will not be generated by GPT-2):")
                    # Display the first 100 ignored words with their original casing
                    for iw in ignored_words[:100]:
                        print(f"    - {iw}")
                    if len(ignored_words) > 100:
                        print(f"    - ... and {len(ignored_words) - 100} more.")
                print("=============================================\n")

        except Exception as e:
            interpret('[Expansion] Failed to load V2 substyle:', e)


    @torch.no_grad()
    @torch.inference_mode()
    def logits_processor(self, input_ids, scores):
        assert scores.ndim == 2 and scores.shape[0] == 1
        self.logits_bias = self.logits_bias.to(scores)

        bias = self.logits_bias.clone()
        bias[0, input_ids[0].to(bias.device).long()] = neg_inf
        bias[0, 11] = 0

        return scores + bias

    @torch.no_grad()
    @torch.inference_mode()
    def __call__(self, prompt, seed):
        if prompt == '':
            return ''

        if self.patcher.current_device != self.patcher.load_device:
            print('Fooocus Expansion loaded by itself.')
            model_management.load_model_gpu(self.patcher)

        seed = int(seed) % SEED_LIMIT_NUMPY
        set_seed(seed)
        prompt = safe_str(prompt) + ','

        tokenized_kwargs = self.tokenizer(prompt, return_tensors="pt")
        tokenized_kwargs.data['input_ids'] = tokenized_kwargs.data['input_ids'].to(self.patcher.load_device)
        tokenized_kwargs.data['attention_mask'] = tokenized_kwargs.data['attention_mask'].to(self.patcher.load_device)

        current_token_length = int(tokenized_kwargs.data['input_ids'].shape[1])
        max_token_length = 75 * int(math.ceil(float(current_token_length) / 75.0))
        max_new_tokens = max_token_length - current_token_length

        if max_new_tokens == 0:
            return prompt[:-1]

        # https://huggingface.co/blog/introducing-csearch
        # https://huggingface.co/docs/transformers/generation_strategies
        features = self.model.generate(**tokenized_kwargs,
                                       top_k=100,
                                       max_new_tokens=max_new_tokens,
                                       do_sample=True,
                                       logits_processor=LogitsProcessorList([self.logits_processor]))

        response = self.tokenizer.batch_decode(features, skip_special_tokens=True)
        result = safe_str(response[0])

        return result
