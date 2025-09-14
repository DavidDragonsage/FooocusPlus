import json
import os
from pathlib import Path
import enhanced.translator as translator

current_translation = {} # used for testing only


def localization_js(arg_code):
    global current_translation

    full_path, arg_code = translator.find_language_file(arg_code, fallback=True)
    if full_path.is_file():
        try:
            with open(full_path, encoding='utf-8') as f:
                current_translation = json.load(f)
                assert isinstance(current_translation, dict)
                for k, v in current_translation.items():
                    assert isinstance(k, str)
                    assert isinstance(v, str)
        except Exception as e:
            print(str(e))
            translator.interpret('[Localization] Failed to load language file', full_path)

    # current_translation = {k: 'XXX' for k in current_translation.keys()}  # use this to see if all texts are covered

    return f'let locale_lang = "{arg_code}"; window.localization = {json.dumps(current_translation)}'

def dump_english_config(components):
    all_texts = []
    for c in components:
        label = getattr(c, 'label', None)
        value = getattr(c, 'value', None)
        choices = getattr(c, 'choices', None)
        info = getattr(c, 'info', None)

        if isinstance(label, str):
            all_texts.append(label)
        if isinstance(value, str):
            all_texts.append(value)
        if isinstance(info, str):
            all_texts.append(info)
        if isinstance(choices, list):
            for x in choices:
                if isinstance(x, str):
                    all_texts.append(x)
                if isinstance(x, tuple):
                    for y in x:
                        if isinstance(y, str):
                            all_texts.append(y)

    config_dict = {k: k for k in all_texts if k != "" and 'progress-container' not in k}
    full_path = translator.find_language_file('en')

    with open(full_path, "w", encoding="utf-8") as json_file:
        json.dump(config_dict, json_file, indent=4)

    return
