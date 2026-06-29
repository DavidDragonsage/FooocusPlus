from transformers.modeling_utils import WEIGHTS_NAME, PreTrainedModel
from transformers.pytorch_utils import Conv1D, prune_linear_layer
from transformers.configuration_utils import PretrainedConfig

TF_WEIGHTS_NAME = "model.ckpt"

from transformers.modeling_utils import *


def find_pruneable_heads_and_indices(heads, n_heads, head_size, already_pruned_heads):
    """
    Finds the heads and their indices that can be pruned in an attention layer.
    """
    if len(heads) == 0:
        return [], []

    heads = set(heads) - already_pruned_heads  # Check what heads are left to prune
    if len(heads) == 0:
        return [], []

    # Sort the heads to be pruned
    heads = sorted(list(heads))
    all_indices = torch.arange(n_heads * head_size).view(n_heads, head_size)
    indices = torch.cat([all_indices[i] for i in heads])

    return heads, indices

def prune_layer(layer, index, dim=0):
    """
    Prune a Conv1D or num_heads layer to keep only entries in index.
    A Conv1D work as a Linear layer (see e.g. BERT) but the weights are transposed.
    """
    index = index.to(layer.weight.device)
    W = layer.weight.index_select(0, index).clone().detach()
    if layer.bias is not None:
        b = layer.bias.index_select(0, index).clone().detach()
    new_size = list(layer.weight.size())
    new_size[0] = len(index)
    new_layer = Conv1D(new_size[1], new_size[0])
    new_layer.weight.requires_grad = False
    new_layer.weight.copy_(W.contiguous())
    new_layer.weight.requires_grad = True
    if layer.bias is not None:
        new_layer.bias.requires_grad = False
        new_layer.bias.copy_(b.contiguous())
        new_layer.bias.requires_grad = True
    return new_layer