import gradio as gr
import modules.localization as localization
import json
from pathlib import Path

all_styles = []
SORT_FILE = Path('sorted_styles.json')
V2_STYLE = "Fooocus V2"


def _anchor_v2(styles_list):
    """Internal helper to ensure Fooocus V2 is always at index 0."""
    if V2_STYLE in styles_list:
        styles_list.remove(V2_STYLE)
        return [V2_STYLE] + styles_list
    return styles_list


def try_load_sorted_styles(style_names, default_selected):
    global all_styles
    all_styles = style_names

    try:
        if SORT_FILE.exists():
            with SORT_FILE.open('r', encoding='utf-8') as fp:
                loaded_data = json.load(fp)
                sorted_styles = [x for x in loaded_data if x in all_styles]

                # Append any new styles found in all_styles that weren't in the JSON
                for x in all_styles:
                    if x not in sorted_styles:
                        sorted_styles.append(x)

                all_styles = sorted_styles
    except Exception as e:
        print(f'Load style sorting failed: {e}')

    # Move defaults to top, but then force V2 to the absolute top
    unselected = [y for y in all_styles if y not in default_selected]
    all_styles = _anchor_v2(default_selected + unselected)
    return


def sort_styles(selected):
    global all_styles

    # Maintain the user's "selection-first" sorting
    unselected = [y for y in all_styles if y not in selected]

    # Anchor Fooocus V2 to the top of the entire list
    sorted_styles = _anchor_v2(selected + unselected)

    try:
        with SORT_FILE.open('w', encoding='utf-8') as fp:
            json.dump(sorted_styles, fp, indent=4)
    except Exception as e:
        print(f'Write style sorting failed: {e}')

    all_styles = sorted_styles
    return gr.CheckboxGroup.update(choices=sorted_styles)


def localization_key(x):
    return x + localization.current_translation.get(x, '')


def search_styles(selected, query):
    unselected = [y for y in all_styles if y not in selected]
    matched = [y for y in unselected if query.lower() in localization_key(y).lower()] if len(query.replace(' ', '')) > 0 else []
    unmatched = [y for y in unselected if y not in matched]
    sorted_styles = matched + selected + unmatched
    return gr.CheckboxGroup.update(choices=sorted_styles)
