from transformers.models.bert import modeling_bert

# Re-export all public symbols
for symbol in dir(modeling_bert):
    if not symbol.startswith("_"):
        globals()[symbol] = getattr(modeling_bert, symbol)

# Explicitly export load_tf_weights_in_bert even if it's private/missing from dir()
if hasattr(modeling_bert, 'load_tf_weights_in_bert'):
    load_tf_weights_in_bert = modeling_bert.load_tf_weights_in_bert
elif hasattr(modeling_bert, '_load_tf_weights_in_bert'):
    load_tf_weights_in_bert = modeling_bert._load_tf_weights_in_bert
