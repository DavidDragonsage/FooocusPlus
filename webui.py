import gradio as gr
import os
import sys
import platform
import copy
import json
import random
import re
import time
import args_manager as args
import comfy.comfy_version
import common
import enhanced.superprompter
import ldm_patched.modules.model_management as model_management
import modules.aspect_ratios as AR
import modules.async_worker as worker
import modules.config as config
import modules.constants as constants
import modules.flags as flags
import modules.gradio_hijack as grh
import modules.html
import modules.meta_parser
import modules.preset_resource as PR
import modules.style_sorter as style_sorter
import modules.ui_support as UIS
import modules.ui_util as UIU
import modules.user_structure as US

from functools import partial
from pathlib import Path
from json import dumps
from PIL import Image as _Image

import enhanced.editor as edit
import enhanced.gallery as gallery_util
import enhanced.toolbox as toolbox
import enhanced.translator as translator
import enhanced.enhanced_parameters as enhanced_parameters
import enhanced.version as version
import enhanced.wildcards as wildcards
import enhanced.comfy_task as comfy_task

from backend_base.__init__ import get_torch_xformers_cuda_version as torch_info
from enhanced.translator import interpret, \
    interpret_info, interpret_warn
from enhanced.backend import comfyd
from enhanced.welcome import get_welcome_image, \
    check_active_logo
from extras.inpaint_mask import SAMOptions, \
    generate_mask_from_image
from modules.ar_util import AR_template_init
from modules.sdxl_styles import legal_style_names, \
    fooocus_expansion
from modules.private_logger import get_current_html_path
from modules.ui_features import control_notification
from modules.ui_gradio_extensions import reload_javascript
from modules.util import is_json, recover_images

allow_inpaint_max = False

btn_torch_value = interpret(
    'Reconfigure', 'PyTorch', silent = True)

btn_cancel_value = interpret(
    'Cancel',silent = True)

btn_close_value = interpret(
    'Close',silent = True)


interpret('[UI] Initializing the user interface...')
print()
import modules.lme4fp_civitai
modules.lme4fp_civitai.main()


def get_task(*args):
    args = list(args)
    args.pop(0)
    return worker.AsyncTask(args=args)

reload_javascript()

fooocusplus_ver, hotfix, hotfix_title = version.get_fooocusplus_ver()
title = f'FooocusPlus {fooocusplus_ver}.{hotfix_title}'
common.GRADIO_ROOT = gr.Blocks(title=title).queue()

with common.GRADIO_ROOT:
    state_topbar = gr.State({})
    # obsolete parameter
    params_backend = gr.State({'translation_methods': ''})
    currentTask = gr.State(worker.AsyncTask(args=[]))

    inpaint_engine_state = gr.State('empty')
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Group():
                with gr.Row(visible=config.enable_preset_bar) as preset_row:
                    if not args.args.disable_preset_selection:
                        # obsolete hidden preset code
                        # disable the iFrame display of help for preset selections:
                        preset_instruction = gr.HTML(visible=False,
                        value=UIS.preset_no_instruction())

                        bar_buttons = []
                        preset_bar_list = PR.get_presetnames_in_folder(config.default_bar_category)
                        with gr.Column(scale=0, min_width=75):
                            real_bar_title = gr.Markdown(f'<b>{config.default_bar_category}:</b>',
                            elem_id='bar_title')
                            bar_title = gr.Markdown('',
                                elem_classes='invisible')
                        padded_list = PR.pad_list(preset_bar_list, config.preset_bar_length, '')
                        for i in range(config.preset_bar_length):
                            bar_buttons.append(
                                gr.Button(value=padded_list[i],
                                size='sm',
                                elem_id=f'bar{i}',
                                elem_classes='bar_button'))

                with gr.Row(elem_classes="canvas_container") as canvas_row:
                    welcome_window = grh.Image(
                        label='Welcome', show_label=False,
                        visible=True, height=520,
                        elem_id='welcome_image',
                        elem_classes=['main_canvas'],
                        type="pil",
                        value=None,
                        interactive=False)

                    preview_window = grh.Image(
                        label='Preview', show_label=False,
                        visible=False, height=768,
                        elem_id='preview_generating',
                        elem_classes=['main_view','main_canvas'],
                        value=None,
                        interactive=False)

                    progress_gallery = gr.Gallery(
                        label='Image Gallery',
                        show_label=True,
                        object_fit='contain',
                        elem_id='finished_gallery',
                        height=520, visible=False,
                        elem_classes=['main_view', 'image_gallery'])

                progress_html = gr.HTML(value=modules.html.make_progress_html(32, 'Progress 32%'), visible=False,
                    elem_id='progress-bar', elem_classes='progress-bar')

                history_gallery = gr.Gallery(label='Gallery',
                    show_label=True, object_fit='contain',
                    visible=False, height=768,
                    elem_classes=['resizable_area', 'main_view', 'final_gallery', 'image_gallery'],
                    elem_id='final_gallery', preview=True )

                toolbox_info_box = gr.HTML(
                    toolbox.make_infobox_HTML(None, args.args.mode),
                    visible=False, elem_id='infobox',
                    elem_classes='infobox')

                with gr.Group(visible=False, elem_classes='toolbox_note') as toolbox_note_box:
                    toolbox_note_info = gr.Markdown(elem_classes='note_info')
                    toolbox_note_input_name = gr.Textbox(show_label=False, placeholder="Type preset name here.", \
                        min_width=100, elem_classes='preset_input', visible=False)

                    with gr.Row():
                        toolbox_note_delete_button = gr.Button(
                            value='OK',
                            visible=False, scale=1,
                            elem_classes='toolbox_note_button')
                        toolbox_note_load_button = gr.Button(
                            value='OK',
                            visible=False, scale=1,
                            elem_classes='toolbox_note_button')
                        toolbox_note_preset_button = gr.Button(
                            value='Save',
                            visible=False, scale=1,
                            elem_classes='toolbox_note_button')
                        toolbox_note_cancel_button = gr.Button(
                            value='Cancel',
                            visible=True, scale=1,
                            elem_classes='toolbox_note_button')

                with gr.Row():
                    # show FooocusPlus title string on main canvas
                    # the title fades in, is visible for <1 min, then fades out
                    prog_name = gr.Markdown(value=f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;FooocusPlus {fooocusplus_ver}.{hotfix_title}',
                        container=False, visible=True,
                        elem_id='program_name')

                    if config.audio_notification and US.exists_file('notification.mp3'):
                        value_audio = 'notification.mp3'
                    else:
                        value_audio = None
                    audio_output = gr.Audio(interactive=False,
                        value=value_audio,
                        elem_id='audio_notification', visible=False)

                    # the accordion label will be filled in
                    # during common.GRADIO_ROOT.load()
                    # with the latest stats and in the
                    # defined language
                    with gr.Accordion(
                        "Generated Images Catalog",
                        open=False,
                        visible=config.default_image_catalog_checkbox,
                        elem_id='finished_images_catalog') as catalogue_accordion:

                        gallery_index_stat = gr.Textbox(
                            value='', visible=False)

                        gallery_index = gr.Radio(
                            choices=None, label="Gallery Index",
                            value=None, show_label=False)

            with gr.Group():
                with gr.Row():
                    with gr.Column(scale=12):
                        prompt = gr.Textbox(
                            show_label=False,
                            placeholder="Type the main prompt here or paste parameters",
                            elem_id='positive_prompt',
                            elem_classes='text-arial',
                            autofocus=True,
                            value=config.default_prompt,
                            lines=4)

                        prompt_token_counter = gr.HTML(
                            visible=True,
                            value=0,
                            elem_classes=["tokenCounter"],
                            elem_id='token_counter',)

                        default_prompt = config.default_prompt
                        if isinstance(default_prompt, str) and default_prompt != '':
                            common.GRADIO_ROOT.load(
                            lambda: default_prompt,
                            outputs=prompt)

                    with gr.Column(scale=2, min_width=75):
                        # Note: the en_master.json reference file will display "Translate"
                        # although no translation will occur
                        if args.args.language == 'en' or args.args.language == 'en_uk':
                            random_button = gr.Button(value="Random Prompt",
                                elem_classes='type_row_half',
                                size="sm", min_width = 75)
                            super_prompter = gr.Button(value="Super Prompt",
                                elem_classes='type_row_half',
                                size="sm", min_width = 75)
                            translator_button = gr.Button(value="Translate",
                                elem_classes='type_row_third',
                                size='sm', min_width = 75, visible=False,)
                        else:
                            random_button = gr.Button(value="Random Prompt",
                                elem_classes='type_row_third',
                                size="sm", min_width = 75)
                            super_prompter = gr.Button(value="Super Prompt",
                                elem_classes='type_row_third',
                                size="sm", min_width = 75)
                            translator_button = gr.Button(value="Translate",
                                elem_classes='type_row_third',
                                size='sm', min_width = 75, visible=config.default_prompt_translator_enable)

                    with gr.Column(scale=2, min_width=75):
                        generate_button = gr.Button(
                            value="Generate",
                            elem_classes='type_row',
                            elem_id='generate_button',
                            visible=True, min_width = 75)

                        reset_button = gr.Button(
                            value="Reconnect",
                            elem_classes='type_row',
                            elem_id='reset_button',
                            visible=False, min_width = 75)

                        load_parameter_button = gr.Button(
                            value="Load Parameters",
                            elem_classes='type_row',
                            elem_id='load_parameter_button',
                            visible=False, min_width = 75)

                        skip_button = gr.Button(
                            value="Skip",
                            elem_classes='type_row_half',
                            elem_id='skip_button',
                            visible=False, min_width = 75)

                        stop_button = gr.Button(
                            value="Stop",
                            elem_classes='type_row_half',
                            elem_id='stop_button',
                            visible=False, min_width = 75)

                with gr.Row(equal_height=True, elem_id='advanced_check_row'):
                    with gr.Column(min_width=0, scale=1):
                        advanced_checkbox = gr.Checkbox(
                            label='Advanced',
                            value=config.default_advanced_checkbox,
                            container=False, elem_id='advanced_check')
                    with gr.Column(min_width=0, scale=1):
                        features_checkbox = gr.Checkbox(
                            label='Features',
                            value=False,
                            container=False)
                    with gr.Column(min_width=0, scale=1):
                        input_image_checkbox = gr.Checkbox(
                            label='Input Image',
                            value = config.default_input_image_checkbox,
                            interactive = not common.default_engine,
                            container=False)
                    with gr.Column(min_width=0, scale=1):
                        preset_bar_checkbox = gr.Checkbox(
                            label='Preset Bar',
                            value=config.enable_preset_bar,
                            container=False)
                    with gr.Column(min_width=0, scale=0,
                            elem_id='preset_wrapper_col'):
                        with gr.Row(elem_id='preset_inner_row'):
                            preset_label = gr.Markdown(
                                value=f'<b>Current Preset:</b>',
                                container=False, visible=True,
                                elem_id='preset_label')
                            preset_info = gr.Markdown(
                                value=f'<b>{args.args.preset}</b>',
                                container=False, visible=True,
                                elem_id='preset_info')

            with gr.Group(visible=False, elem_classes='toolbox') as image_toolbox:
                image_tools_box_title = gr.Markdown('<b>Toolbox</b>', visible=True)
                toolbox_info_button = gr.Button(value='View Log Info', size='sm', visible=True)
                toolbox_load_button = gr.Button(value='Load Log Info', size='sm', visible=True)
                toolbox_delete_button = gr.Button(value='Delete Image', size='sm', visible=True)

            with gr.Group(visible=False,
                elem_classes='perf_modal_box') as perf_modal_box:
                with gr.Row():
                    # Displays either status information or the upgrade confirmation text
                    perf_modal_header_msg = gr.Markdown(value='')

                # Action Buttons Row
                # placed DIRECTLY below the question
                with gr.Row(elem_classes='elem_centre'):
                    # Action Confirmation Buttons (Two Options)
                    perf_upgrade_btn = gr.Button(
                        value=btn_torch_value,
                        elem_classes='torch_note_button',
                        visible=False, scale=1
                    )
                    perf_cancel_btn = gr.Button(
                        value=btn_close_value,
                        elem_classes='torch_note_button',
                        visible=False, scale=1
                    )

                # Metrics Message
                # Optional, placed below the action buttons
                perf_modal_metrics_msg = gr.Markdown(value='')

                # Informational OK Row
                # placed at the very bottom, below the metrics
                with gr.Row(elem_classes='elem_centre'):
                    perf_ok_btn = gr.Button(
                        value='OK',
                        elem_classes='torch_note_button',
                        visible=False)

            with gr.Group(visible=False,
                elem_classes=['remove_torch_box']) as remove_torch_modal_box:
                with gr.Row():
                    # Displays warning message or success instructions
                    remove_torch_modal_msg = gr.Markdown(value='')

                with gr.Row():
                    # Action Confirmation Buttons (Two Options)
                    remove_torch_proceed_btn = gr.Button(
                        value=btn_torch_value,
                        elem_classes='torch_note_button',
                        visible=False, scale=1)
                    remove_torch_cancel_btn = gr.Button(
                        value=btn_cancel_value,
                        elem_classes='torch_note_button',
                        visible=False, scale=1)

            with gr.Row(visible=False) as features_panel:
                with gr.Tabs():
                    with gr.Tab(label='Image Editor', id='edit_tab') as edit_tab:
                        with gr.Row():
                            with gr.Column():
                                input_image_display = grh.Image(
                                    label='Place image here',
                                    source='upload',
                                    image_mode='RGBA',
                                    type='pil',
                                    height=350,
                                    interactive=True,
                                    visible=True)

                            with gr.Column():
                                output_image_display = grh.Image(
                                    label='Output',
                                    source='upload',
                                    image_mode='RGBA',
                                    type='pil',
                                    height=350,
                                    interactive=False,
                                    show_download_button=False,
                                    visible=True)

                        with gr.Accordion(label='Adjustments',
                            visible=True, open=False):
                            with gr.Row():
                                autocontrast_chk = gr.Checkbox(
                                    label="Auto Contrast",
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True)
                                edge_chk = gr.Checkbox(
                                    label="Edge Enhance",
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True)
                                equalize_chk = gr.Checkbox(
                                    label="Equalize",
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True)
                                grayscale_chk = gr.Checkbox(
                                    label="Grayscale",
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True)

                            with gr.Row():
                                brighten_slider = gr.Slider(
                                    label="Brightness",
                                    minimum=-100, maximum=+100,
                                    value=0, step=1,
                                    interactive=True)
                                contrast_slider = gr.Slider(
                                    label="Contrast",
                                    minimum=-100, maximum=+100,
                                    value=0, step=1,
                                    interactive=True)

                            with gr.Row():
                                hue_slider = gr.Slider(
                                    label="Hue",
                                    minimum=-180, maximum=+180,
                                    value=0, step=1,
                                    interactive=True)
                                saturation_slider = gr.Slider(
                                    label="Saturation",
                                    minimum=-100, maximum=+200,
                                    value=0, step=1,
                                    interactive=True)
                                sharpness_slider = gr.Slider(
                                    label="Sharpness",
                                    minimum=-100, maximum=+1000,
                                    value=0, step=1,
                                    interactive=True)

                        with gr.Accordion(label='Transformations', visible=True, open=False):
                            with gr.Row():
                                percent_resize_slider = gr.Slider(
                                    label='Percent Resize (%)',
                                    minimum=2, maximum=200,
                                    value=100, step=0.5,
                                    interactive=True,
                                    info='Preserves the aspect ratio: 50% = half-size, 200% = double-size. Resize Width & Resize Height operate independently and can introduce distortion.')

                            with gr.Row():
                                width_slider = gr.Slider(
                                    label='Resize Width',
                                    minimum=2, maximum=2048,
                                    value=1024, step=1,
                                    interactive=True)
                                height_slider = gr.Slider(
                                    label='Resize Height',
                                    minimum=2, maximum=2048,
                                    value=1024, step=1,
                                    interactive=True)

                            with gr.Row():
                                left_slider = gr.Slider(
                                    label="Left Crop",
                                    minimum=0, maximum=1024,
                                    value=0, step=1,
                                    interactive=True)
                                right_slider = gr.Slider(
                                    label="Right Crop",
                                    minimum=0, maximum=1024,
                                    value=1024, step=1,
                                    interactive=True)

                            with gr.Row():
                                upper_slider = gr.Slider(
                                    label="Upper Crop",
                                    minimum=0, maximum=1024,
                                    value=0, step=1,
                                    interactive=True)
                                lower_slider = gr.Slider(
                                    label="Lower Crop",
                                    minimum=0, maximum=1024,
                                    value=1024, step=1,
                                    interactive=True)

                            with gr.Row():
                                mirror_chk = gr.Checkbox(
                                    label='Flip Horizontally',
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True,
                                    info='Mirror Image')
                                flip_vertical_chk = gr.Checkbox(
                                    label='Flip Vertically',
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True,
                                    info='Turn Upside-Down')
                                crop_width = gr.Textbox(
                                    label='Crop Width',
                                    value=1024,
                                    interactive=False)
                                crop_height = gr.Textbox(
                                    label='Crop Height',
                                    value=1024,
                                    interactive=False)

                            with gr.Row():
                                reset_transforms_btn = gr.Button(
                                    value = "Reset Transforms",
                                    elem_classes='button_classic3')
                                rotate_slider = gr.Slider(
                                    label='Rotate (Degrees)',
                                    minimum=-180, maximum=+180,
                                    value=0, step=90,
                                    elem_classes='edit_check',
                                    interactive=True,
                                    info='Use Flip Aspect Ratio to correct faulty rotations')
                                flip_AR_chk = gr.Checkbox(
                                    label='Flip Aspect Ratio',
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True,
                                    info='Inverting the Aspect Ratio swaps the width and height dimensions.')

                        with gr.Accordion(
                            label='Transparency & Composition', visible=True, open=False):
                            with gr.Row():
                                gr.Markdown(value='These transparency tools are operating in preview mode and any modifications are temporary. Press <b>Apply Transparency</b> to finalize the changes',
                                elem_classes='dropdown_info')

                            with gr.Row():
                                background_chk = gr.Checkbox(
                                    label="Remove Background",
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True,
                                    info='Make the background invisible')

                                bg_model_dropdown = gr.Dropdown(
                                    label='Background Masking Model',
                                    choices=flags.edit_bg_mask_models,
                                    value=config.edit_background_mask_model)

                                alpha_mat_chk = gr.Checkbox(
                                    label="Use Alpha Matting",
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True,
                                    info='Apply advanced edge detection during background removal')

                                erase_chk = gr.Checkbox(
                                    label="Erase Image",
                                    value = False, container=True,
                                    elem_classes='edit_check',
                                    interactive=True,
                                    info='Create a blank transparent image')

                            with gr.Row():
                                remove_transparency_btn = gr.Button(
                                    value = "Remove All Transparency",
                                    elem_classes='button_edit')

                                transparency_slider = gr.Slider(
                                    label="Percent Transparency",
                                    minimum=0, maximum=100,
                                    value=0.0, step=0.5,
                                    interactive=True,
                                    info='At 100% the whole image is invisible')

                                apply_transparency_btn = gr.Button(
                                    value = "Apply Transparency",
                                    elem_classes='button_edit')

                            with gr.Accordion(label='Overlay the Output Image onto a Base', visible=True, open=False):
                                with gr.Row():
                                    gr.Markdown(value='If a Position slider cannot be moved from zero, the overlay is as large as the base in that dimension. Either crop the overlay or uncheck "Contain Overlay" to move it.',
                                    elem_classes='dropdown_info')

                                with gr.Row():
                                    base_image_display = grh.Image(
                                        label='Load Base Image',
                                        source='upload',
                                        image_mode='RGBA',
                                        type='pil',
                                        height=350,
                                        interactive=True,
                                        visible=True)

                                    composite_image_display = grh.Image(
                                        label="Composite Image Output",
                                        source='upload',
                                        image_mode='RGBA',
                                        type='pil',
                                        height=350,
                                        interactive=True,
                                        visible=True)

                                with gr.Row():
                                    horizontal_slider = gr.Slider(
                                        label='Horizontal Position',
                                        minimum=-512, maximum=+512,
                                        value=0, step=1,
                                        interactive=True)

                                    vertical_slider = gr.Slider(
                                        label='Vertical Position',
                                        minimum=-512, maximum=+512,
                                        value=0, step=1,
                                        interactive=True)

                                with gr.Row():
                                    reload_overlay_btn = gr.Button(
                                        value = "Reload Overlay",
                                        elem_classes='button_edit')
                                    with gr.Column():
                                        with gr.Row():
                                            contain_chk = gr.Checkbox(
                                                label='Contain Overlay',
                                                value = config.edit_contain_overlay,
                                                container=True,
                                                elem_classes='edit_check',
                                                interactive=True,
                                                info='Keep the overlay within the base image')
                                        with gr.Row():
                                            rotate_overlay_slider = gr.Slider(
                                                label='Rotate Overlay',
                                                minimum=-180, maximum=+180,
                                                value=0, step=1,
                                                interactive=True,
                                                min_width=320)
                                    save_composite_btn = gr.Button(
                                        value = "Save Composite Image",
                                        elem_classes='button_edit')

                        with gr.Accordion(label='Effects', visible=True, open=False):
                            with gr.Row():
                                gr.Markdown(value='If an effects slider does not react properly to a large change, move it one step up or down and it should respond correctly.',
                                elem_classes='dropdown_info')

                            with gr.Row():
                                box_blur_slider = gr.Slider(
                                    label="Box Blur Radius",
                                    minimum=0, maximum=50,
                                    value=0, step=1,
                                    interactive=True)
                                gaussian_blur_slider = gr.Slider(
                                    label="Guassian Blur Radius",
                                    minimum=0, maximum=50,
                                    value=0, step=1,
                                    interactive=True)
                                with gr.Column(elem_classes=['column_chkbox']):
                                    with gr.Row():
                                        edge_more_chk = gr.Checkbox(
                                            label="Edge Enhance 2",
                                            value = False, container=True,
                                            elem_classes='edit_check',
                                            interactive=True)

                            with gr.Row():
                                posterize_slider = gr.Slider(
                                    label="Posterize (Reduce Color Resolution)",
                                    minimum=1, maximum=8,
                                    value=8, step=1,
                                    interactive=True,
                                    info='8-bit/channel=True Color, 1-bit/channel=8 possible colors')
                                solarize_slider = gr.Slider(
                                    label="Solarize Threshold (Selective Invert)",
                                    minimum=-1, maximum=255,
                                    value=-1, step=1,
                                    interactive=True,
                                    info='-1=Off, 0=Full Inversion, 255=No Inversion')

                        with gr.Group():
                            with gr.Row():
                                reset_image = gr.Button(
                                    value='Reset to Defaults',
                                    elem_classes='button_classic3')
                                save_format = gr.Dropdown(
                                    label="Save Format",
                                    choices=flags.EditFormat.list(),
                                    value=config.edit_output_format,
                                    visible=True, interactive=True)
                                save_image = gr.Button(
                                    value='Save Image',
                                    elem_classes='button_classic3')

                            with gr.Row():
                                restore_original = gr.Button(
                                    value='Restore Original',
                                    elem_classes='button_edit')
                                copy_to_source = gr.Button(
                                    value='Copy Output to Source',
                                    elem_classes='button_edit')
                                copy_to_base = gr.Button(
                                    value='Copy Output to Base',
                                    elem_classes='button_edit')

                                edit_save_metadata_chk = gr.Checkbox(
                                label="Save Metadata",
                                value = config.edit_save_metadata_to_images,
                                container=False,
                                elem_classes=['edit_check_padded',
                                    'edit_check_full'],
                                interactive=True,
                                info='Save image parameters for the Output and Composite images')

                            # preserves the untouched original in memory
                            original_image_state = gr.State(value=None)

                            # mirror of output_image_display
                            # used to preserve RGBA values
                            output_image_state = gr.State(value=None)

                            # Copy of input_image_display
                            # that includes transparency edits only
                            # Used for updating the source image
                            # with transparency values
                            output_transparency_state = gr.State(value=None)

                            # a hidden file component specifically
                            # for download
                            download_file = gr.File(
                                label="Download Image",
                                visible=False)

                        with gr.Row(
                            elem_classes='elem_centre'):
                            with gr.Column():
                                gr.HTML('<font size="3">&emsp;<a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Image-Editor-Backgrounds" target="_blank">\U0001F4DA Background Replacement</a>')

                    with gr.Tab(label='IC-Light', id='layer_tab') as layer_tab:

                        with gr.Row():
                            with gr.Column():
                                layer_input_image = grh.Image(
                                label='Place image here',
                                source='upload', type='numpy', visible=True)

                            with gr.Column():
                                with gr.Group():
                                    iclight_source_radio = gr.Radio(
                                        show_label=False,
                                        choices=comfy_task.iclight_source_names,
                                        value=comfy_task.iclight_source_names[0],
                                        elem_classes='iclight_source',
                                        elem_id='iclight_source')

                        with gr.Row():
                            example_quick_subjects = gr.Dataset(
                                samples=comfy_task.quick_subjects,
                                label='Subject Quick List',
                                samples_per_page=1000,
                                components=[prompt])

                        with gr.Row():
                            example_quick_prompts = gr.Dataset(
                                samples=comfy_task.quick_prompts,
                                label='Lighting Quick List',
                                samples_per_page=1000,
                                components=[prompt])

                        with gr.Row(
                            elem_classes='elem_centre'):
                            with gr.Column():
                                gr.HTML('<font size="3">&emsp;<a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/IC%E2%80%90Light" target="_blank">\U0001F4DA IC-Light</a>')

                            with gr.Column():
                                gr.HTML('* The IC-Light project page: <a href="https://github.com/lllyasviel/IC-Light" target="_blank">IC-Light</a>')

            with gr.Row(visible=config.default_input_image_checkbox) as image_input_panel:
                with gr.Tabs(selected=config.default_selected_image_input_tab_id):
                    with gr.Tab(label='Upscale or Variation', id='uov_tab') as uov_tab:
                        with gr.Row():
                            with gr.Column():
                                uov_input_image = grh.Image(
                                label='Image', source='upload',
                                type='numpy', show_label=False)

                            with gr.Column():
                                mixing_uov_checkbox = gr.Checkbox(
                                label='Mix Image Prompt & Vary/Upscale',
                                value=False)

                                uov_method = gr.Radio(
                                    label='Upscale or Variation:',
                                    choices=flags.uov_list,
                                    value=config.default_uov_method)

                        with gr.Row():
                            overwrite_upscale_strength = gr.Slider(label='Adjust the Strength of Upscale Variation',
                                minimum=0, maximum=1.0, step=0.001,
                                value=config.default_overwrite_upscale,
                                info='Variation Strength is also called "Denoising Strength"')

                            overwrite_vary_strength = gr.Slider(label='Adjust the Strength of Image Variation',
                                minimum=0, maximum=1.0, step=0.001, value=0.50,
                                info='0.0="None", 0.50="Subtle", 0.85="Strong", 1.0="Max"')

                        gr.HTML('<a href="https://github.com/lllyasviel/Fooocus/discussions/390" target="_blank">\U0001F4DA Documentation</a>')

                    def update_ip_slot(slot_index, key, value):
                        # Ensure the slot exists before
                        # trying to write to it
                        while len(config.ip_slots) <= slot_index:
                            config.ip_slots.append({})

                        config.ip_slots[slot_index][key] = value

                    with gr.Tab(label='Image Prompt', id='ip_tab') as ip_tab:
                        with gr.Row():
                            clear_ip_help = interpret('"Clear Image Prompts" deletes the reference images to maintain system performance and sets the parameters to their default values.', silent = True)

                            gr.Markdown(value=clear_ip_help,
                            elem_classes='dropdown_info')

                        with gr.Row():
                            clear_image_prompts_button = gr.Button(
                                value='Clear Image Prompts',
                                elem_classes='button_classic4')

                            ip_advanced = gr.Checkbox(
                                label='Advanced Control',
                                value= config.default_image_prompt_advanced_checkbox,
                                container=False)

                        with gr.Row():
                            ip_images = []
                            ip_types = []
                            ip_stops = []
                            ip_weights = []
                            ip_ad_cols = []

                        for image_count in range(config.default_controlnet_image_count):
                            # for config lookups and display:
                            display_index = image_count + 1

                            with gr.Column():
                                # 1. Define the Image Component
                                ip_image = grh.Image(
                                    label='Image',
                                    source='upload',
                                    type='numpy',
                                    show_label=False,
                                    height=300,
                                    value=config.default_ip_images[display_index])

                                # This tells this specific image
                                # 'x' button to clear the slot:
                                ip_image.clear(
                                    fn=partial(
                                        UIS.manage_ip_image_clear,
                                        image_count),
                                    inputs=None,
                                    outputs=ip_image,
                                    queue=False,
                                    show_progress=False
                                )

                                ip_images.append(ip_image)

                                # 2. Define the Advanced Sliders and Radio
                                with gr.Column(visible=config.default_image_prompt_advanced_checkbox) as ad_col:
                                    with gr.Row():
                                        ip_stop = gr.Slider(
                                            label='Stop At',
                                            minimum=0.0,
                                            maximum=1.0,
                                            step=0.001,
                                            value=config.default_ip_stop_ats[display_index])
                                        ip_stops.append(ip_stop)

                                        ip_weight = gr.Slider(
                                            label='Weight',
                                            minimum=0.0,
                                            maximum=2.0,
                                            step=0.001,
                                            value=config.default_ip_weights[display_index])
                                        ip_weights.append(ip_weight)

                                    ip_type = gr.Radio(
                                        label='Type',
                                        choices=flags.ip_list,
                                        value=config.default_ip_types[display_index], container=False)

                                    UIU.bind_ip_slot_logic(
                                        image_comp=ip_image,
                                        radio_comp=ip_type,
                                        stop_slider=ip_stop,
                                        weight_slider=ip_weight,
                                        slot_idx=image_count,
                                        update_func=update_ip_slot
                                    )

                                    ip_types.append(ip_type)

                                ip_ad_cols.append(ad_col)

                        with gr.Row():
                            controlnet_softness = gr.Slider(
                                label='Softness of ControlNet',
                                minimum=0.0, maximum=1.0,
                                step=0.001, value=0.25,
                                info='Higher values allow more deviation from the original structure.')

                            canny_low_threshold = gr.Slider(
                                label='PyraCanny Low Threshold',
                                minimum=1, maximum=255,
                                step=1, value=64,
                                info='Higher values eliminate subtle edge details but reduce background texture noise.')

                            canny_high_threshold = gr.Slider(
                                label='PyraCanny High Threshold',
                                minimum=1, maximum=255,
                                step=1, value=128,
                                info='Higher values restrict edge detection to only the boldest outlines.')

                        with gr.Row():
                            gr.HTML('<a href="https://github.com/lllyasviel/Fooocus/discussions/557" target="_blank">\U0001F4DA Documentation</a>&emsp; * \"Image Prompt\" is powered by the Fooocus Image Mixture Engine (v1.0.1)')

                    with gr.Tab(label='Inpaint or Outpaint',
                        id='inpaint_tab') as inpaint_tab:
                        with gr.Row():
                            with gr.Column():
                                with gr.Group():
                                    inpaint_input_image = grh.Image(
                                        label='Image',
                                        source='upload',
                                        type='numpy',
                                        tool='sketch',
                                        height=350,
                                        brush_color="#FFFFFF",
                                        elem_id='inpaint_canvas',
                                        show_label=False)

                                    inpaint_mode = gr.Dropdown(
                                        choices=modules.flags.inpaint_options,
                                        value=config.default_inpaint_method,
                                        label='Method')

                                    inpaint_additional_prompt = gr.Textbox(
                                        placeholder="Describe what you want to inpaint.",
                                        elem_id='inpaint_additional_prompt',
                                        label='Inpaint Additional Prompt',
                                        visible=False)

                                    example_inpaint_prompts = gr.Dataset(
                                        samples=config.example_inpaint_prompts,
                                        label='Additional Prompt Quick List',
                                        components=[inpaint_additional_prompt],
                                        visible=False)

                                    outpaint_selections = gr.CheckboxGroup(
                                        choices=['Left', 'Right', 'Top', 'Bottom'],
                                        value=[],
                                        label='Outpaint Direction',
                                        info='The Outpaint Maximum Extension feature is not available for oversized images.')

                                    outpaint_extension = gr.Checkbox(
                                        label='Apply Variable Outpaint Extension',
                                        elem_classes= 'edit_check',
                                        value= False,
                                        container=True,
                                        visible = False,
                                        info='The default extension is 30%. If enabled, the extension in a single direction is up to 100% and for two directions it is up to 50% each.')

                                    with gr.Row():
                                        left_extension = gr.Slider(
                                                label="% Left Extension",
                                                minimum=20, maximum=100,
                                                value=100,
                                                step=0.1,
                                                visible= False)

                                        right_extension = gr.Slider(
                                                label="% Right Extension",
                                                minimum=20, maximum=100,
                                                value=100,
                                                step=0.1,
                                                visible= False)

                                        top_extension = gr.Slider(
                                                label="% Top Extension",
                                                minimum=20, maximum=100,
                                                value=100,
                                                step=0.1,
                                                visible= False)

                                        bottom_extension = gr.Slider(
                                                label="% Bottom Extension",
                                                minimum=20, maximum=100,
                                                value=100,
                                                step=0.1,
                                                visible= False)

                            with gr.Column(visible=config.default_inpaint_advanced_masking_checkbox) as inpaint_mask_generation_col:
                                with gr.Group():

                                    inpaint_mask_image = grh.Image(
                                        label='Mask Upload',
                                        source='upload',
                                        type='numpy',
                                        tool='sketch',
                                        height=350,
                                        brush_color="#FFFFFF",
                                        mask_opacity=1,
                                        elem_id='inpaint_mask_canvas')

                                    generate_mask_button = gr.Button(
                                        value='Generate Mask from Image')

                                    inpaint_mask_model = gr.Dropdown(
                                        label='Mask Generation Model',
                                        choices=flags.inpaint_mask_models,
                                        value=config.default_inpaint_mask_model)

                                    inpaint_mask_cloth_category = gr.Dropdown(
                                        label='Cloth Category',
                                        choices=flags.inpaint_mask_cloth_category,
                                        value=config.default_inpaint_mask_cloth_category,
                                        visible=False)

                                    inpaint_mask_dino_prompt_text = gr.Textbox(
                                        label='Detection Prompt',
                                        value='', visible=False,
                                        info='Use singular whenever possible',
                                        placeholder='Describe what you want to detect.')

                                    example_inpaint_mask_dino_prompt_text = gr.Dataset(
                                        samples=config.example_enhance_detection_prompts,
                                        label='Detection Prompt Quick List',
                                        components=[inpaint_mask_dino_prompt_text],
                                        visible= config.default_inpaint_mask_model == 'sam')

                                    with gr.Accordion("Advanced SAM Options",
                                        visible=False, open=False) as inpaint_mask_advanced_options:
                                        inpaint_mask_sam_model = gr.Dropdown(
                                            label='SAM Model',
                                            choices=flags.inpaint_mask_sam_model,
                                            value= config.default_inpaint_mask_sam_model)

                                        inpaint_mask_box_threshold = gr.Slider(
                                            label="Box Threshold",
                                            minimum=0.0, maximum=1.0,
                                            value=0.3, step=0.05)

                                        inpaint_mask_text_threshold = gr.Slider(
                                            label="Text Threshold",
                                            minimum=0.0, maximum=1.0,
                                            value=0.25, step=0.05)

                                        inpaint_mask_sam_max_detections = gr.Slider(
                                            label="Maximum Number of Detections",
                                            info="Set to 0 to detect all",
                                            minimum=0, maximum=10,
                                            value= config.default_sam_max_detections,
                                            step=1, interactive=True)

                                        dino_erode_or_dilate = gr.Slider(
                                            label='GroundingDINO Box Erode or Dilate',
                                            minimum=-64, maximum=64, step=1, value=0,
                                            info= 'Expands or shrinks the automatic detection area to ensure that SAM captures the entire object without missing edges.')

                        with gr.Row():
                            mixing_inpaint_checkbox = gr.Checkbox(
                                label='Mix Image Prompt & Inpaint',
                                elem_classes='edit_check',
                                value=False, container=True,
                                info='For example, set Image Prompt to FaceSwap and use it to fill an Inpainted face')

                            invert_mask_checkbox = gr.Checkbox(
                                label='Invert Mask When Generating',
                                elem_classes='edit_check',
                                value= config.default_invert_mask_checkbox,
                                container=True,
                                info='Use for background replacement')

                            inpaint_advanced_masking_checkbox = gr.Checkbox(
                                label='Enable Advanced Masking',
                                value=config.default_inpaint_advanced_masking_checkbox,
                                container=True,
                                elem_classes='edit_check',
                                info='Disable Advanced Masking when manual Inpainting')

                        with gr.Accordion(
                            "Expert Inpainting Tools",
                            visible=True,
                            open=False):
                            with gr.Row():
                                inpaint_mask_color = gr.ColorPicker(
                                    label='Inpaint Brush Color',
                                    value='#FFFFFF',
                                    elem_id='inpaint_brush_color',
                                    container=True,
                                    info='Change the color for use with predominantly white images')

                                inpaint_engine = gr.Dropdown(
                                    label='Inpaint Engine',
                                    value=config.default_inpaint_engine_version,
                                    choices=flags.inpaint_engine_versions,
                                    info='Version of Fooocus Inpaint model. If set, use performance Quality or Speed (no performance LoRAs) for best results')

                                inpaint_disable_initial_latent = gr.Checkbox(
                                    label='Disable Initial Latent in Inpaint',
                                    value=False,
                                    info = 'Used by default with the "Modify Content" Inpaint Method: replace objects or backgrounds.')

                            with gr.Row():
                                inpaint_strength = gr.Slider(
                                    label='Inpainting Strength',
                                    minimum=0.0, maximum=1.0,
                                    step=0.001, value=1.0,
                                    info='Adjusts the amount that Inpainting changes the image. '
                                    'Inpainting Strength is also called "Denoising Strength". '
                                    'Outpainting is at full strength: 1.0')

                                inpaint_respective_field = gr.Slider(
                                    label='Inpainting Area',
                                    minimum=0.0, maximum=1.0,
                                    step=0.001, value=0.618,
                                    info='An area of 0.0 means "Only the Masked Area". '
                                    'An area of 1.0 means "The Whole Image". '
                                    'Outpainting affects the whole area and uses a value of 1.0')

                                inpaint_erode_or_dilate = gr.Slider(
                                    label='Mask Erode or Dilate',
                                    minimum=-64, maximum=64,
                                    step=1, value=0, visible = True,
                                    info='Positive values will make white area in the mask larger, '
                                    'negative values will make white area smaller. '
                                    '(Default is 0, always processed before any mask invert)')

                        with gr.Row():
                            with gr.Column(
                            min_width=0, scale=1):
                                gr.HTML('<a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Inpainting-Backgrounds" target="_blank">\U0001F4DA Inpainting Backgrounds</a>&emsp;')

                            with gr.Column(
                            min_width=0, scale=1):
                                gr.HTML('<a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Inpainting-with-FaceSwap" target="_blank">\U0001F4DA Inpainting with FaceSwap</a>&emsp;')

                            with gr.Column(
                            min_width=0, scale=1):
                                gr.HTML('<a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Outpainting" target="_blank">\U0001F4DA Outpainting</a>&emsp;')


                    with gr.Tab(label='Enhance', id='enhance_tab') as enhance_tab:
                        with gr.Row():
                            with gr.Column():
                                enhance_checkbox = gr.Checkbox(
                                    label='Enhance',
                                value= config.default_enhance_checkbox,
                                container=False,
                                info='If enabled, Enhance will remain active when the tab is closed')

                                enhance_input_image = grh.Image(label='Use with Enhance, Skips Image Generation',
                                source='upload', type='numpy')
                                gr.HTML('<a href="https://github.com/lllyasviel/Fooocus/discussions/3281" target="_blank">\U0001F4DA Documentation</a>')

                            with gr.Column():
                                with gr.Row(visible=True) as enhance_input_panel:
                                    with gr.Tabs():
                                        with gr.Tab(label='Upscale or Variation'):
                                            with gr.Row():
                                                with gr.Column():
                                                    enhance_uov_method = gr.Radio(
                                                        label = 'Upscale or Variation',
                                                        choices = flags.uov_list,
                                                        value = config.default_enhance_uov_method)

                                                    enhance_uov_processing_order = gr.Radio(
                                                        label = 'Processing Order',
                                                        info = 'Use before to enhance small details and after to enhance large areas',
                                                        choices = flags.enhancement_uov_processing_order,
                                                        value = config.default_enhance_uov_processing_order)

                                                    enhance_uov_prompt_type = gr.Radio(
                                                        label='Prompt',
                                                        info='Choose which prompt to use for Upscale or Variation',
                                                        choices = flags.enhancement_uov_prompt_types,
                                                        value = config.default_enhance_uov_prompt_type,
                                                        visible = config.default_enhance_uov_processing_order == flags.enhancement_uov_after)


                                        enhance_ctrls = []
                                        enhance_inpaint_mode_ctrls = []
                                        enhance_inpaint_engine_ctrls = []
                                        enhance_inpaint_update_ctrls = []
                                        for index in range(config.default_enhance_tabs):
                                            with gr.Tab(label=f'Region #{index + 1}') as enhance_tab_item:
                                                enhance_enabled = gr.Checkbox(
                                                    label='Enable',
                                                    value=False if index not in [0,1] else True,
                                                    elem_classes='min_check', container=False)

                                                enhance_mask_dino_prompt_text = gr.Textbox(
                                                    label='Detection prompt',
                                                    info='Use singular whenever possible',
                                                    placeholder='Describe what you want to detect',
                                                    interactive=True,
                                                    value = '' if index not in [0,1] else 'face' if index==0 else 'hand',
                                                    visible=config.default_enhance_inpaint_mask_model == 'sam')

                                                example_enhance_mask_dino_prompt_text = gr.Dataset(
                                                    samples=config.example_enhance_detection_prompts,
                                                    label='Detection Prompt Quick List',
                                                    components=[enhance_mask_dino_prompt_text],
                                                    visible=config.default_enhance_inpaint_mask_model == 'sam')

                                                enhance_prompt = gr.Textbox(
                                                    label="Enhancement Positive Prompt",
                                                    placeholder="Uses original prompt instead if empty",
                                                    elem_id='enhance_prompt')

                                                enhance_negative_prompt = gr.Textbox(
                                                    label="Enhancement Negative Prompt",
                                                    placeholder="Uses original negative prompt instead if empty",
                                                    elem_id='enhance_negative_prompt')

                                                with gr.Accordion("Detection", open=False):
                                                    enhance_mask_model = gr.Dropdown(label='Mask Generation Model',
                                                        choices=flags.inpaint_mask_models,
                                                        value= config.default_enhance_inpaint_mask_model)
                                                    enhance_mask_cloth_category = gr.Dropdown(label='Cloth Category',
                                                        choices=flags.inpaint_mask_cloth_category,
                                                        value= config.default_inpaint_mask_cloth_category,
                                                        visible= config.default_enhance_inpaint_mask_model == 'u2net_cloth_seg',
                                                        interactive=True)

                                                    with gr.Accordion("SAM Options",
                                                        visible=config.default_enhance_inpaint_mask_model == 'sam',
                                                        open=False) as sam_options:
                                                        enhance_mask_sam_model = gr.Dropdown(label='SAM model',
                                                            choices=flags.inpaint_mask_sam_model,
                                                            value= config.default_inpaint_mask_sam_model,
                                                            interactive=True)

                                                        enhance_mask_box_threshold = gr.Slider(
                                                            label="Box Threshold",
                                                            minimum=0.0,
                                                            maximum=1.0,
                                                            value=0.3,
                                                            step=0.05,
                                                            interactive=True)
                                                        enhance_mask_text_threshold = gr.Slider(
                                                            label="Text Threshold",
                                                            minimum=0.0,
                                                            maximum=1.0,
                                                            value=0.25,
                                                            step=0.05,
                                                            interactive=True)
                                                        enhance_mask_sam_max_detections = gr.Slider(label="Maximum Number of Detections",
                                                            info="Set to 0 to detect all",
                                                            minimum=0, maximum=10,
                                                            value=config.default_sam_max_detections,
                                                            step=1, interactive=True)

                                                with gr.Accordion("Inpaint", visible=True, open=False):
                                                    enhance_inpaint_mode = gr.Dropdown(choices= modules.flags.inpaint_options,
                                                    value= config.default_inpaint_method if index not in [0,1] else modules.flags.inpaint_option_detail,
                                                        label='Method', interactive=True)
                                                    enhance_inpaint_disable_initial_latent = gr.Checkbox(
                                                        label='Disable Initial Latent in Inpaint', value=False)
                                                    enhance_inpaint_engine = gr.Dropdown(label='Inpaint Engine',
                                                        value=config.default_inpaint_engine_version,
                                                        choices=flags.inpaint_engine_versions,
                                                        info='Version of Fooocus Inpaint model. If set, use performance Quality or Speed (no performance LoRAs) for best results')
                                                    enhance_inpaint_strength = gr.Slider(label='Inpaint Denoising Strength',
                                                        minimum=0.0, maximum=1.0, step=0.001,
                                                        value=1.0,
                                                        info='Adjusts the amount that Inpainting changes the image')
                                                    enhance_inpaint_respective_field = gr.Slider(label='Inpaint Respective Field',
                                                        minimum=0.0, maximum=1.0, step=0.001,
                                                        value=0.618,
                                                        info='An area of 0.0 means "Only the Masked Area". '
                                                        'An area of 1.0 means "The Whole Image". '
                                                        'Outpainting affects the whole area and uses a value of 1.0')
                                                    enhance_inpaint_erode_or_dilate = gr.Slider(label='Mask Erode or Dilate',
                                                        minimum=-64, maximum=64, step=1, value=0,
                                                        info='Positive value will make white area in the mask larger, '
                                                             'negative value will make white area smaller. '
                                                             '(Default is 0, always processed before any mask invert)')
                                                    enhance_mask_invert = gr.Checkbox(label='Invert Mask', value=False)

                                            enhance_ctrls += [
                                                enhance_enabled,
                                                enhance_mask_dino_prompt_text,
                                                enhance_prompt,
                                                enhance_negative_prompt,
                                                enhance_mask_model,
                                                enhance_mask_cloth_category,
                                                enhance_mask_sam_model,
                                                enhance_mask_text_threshold,
                                                enhance_mask_box_threshold,
                                                enhance_mask_sam_max_detections,
                                                enhance_inpaint_disable_initial_latent,
                                                enhance_inpaint_engine,
                                                enhance_inpaint_strength,
                                                enhance_inpaint_respective_field,
                                                enhance_inpaint_erode_or_dilate,
                                                enhance_mask_invert
                                            ]

                                            enhance_inpaint_mode_ctrls += [enhance_inpaint_mode]
                                            enhance_inpaint_engine_ctrls += [enhance_inpaint_engine]

                                            enhance_inpaint_update_ctrls += [[
                                                enhance_inpaint_mode,
                                                enhance_inpaint_disable_initial_latent, enhance_inpaint_engine,
                                                enhance_inpaint_strength,
                                                enhance_inpaint_respective_field
                                            ]]

                    with gr.Tab(label='Fooocus FreeU'):
                        with gr.Row():
                            gr.Markdown(value='Fooocus FreeU is a variation option for SDXL and SD1.5 models, available during text-to-image generation and all the Input Image modes',
                                elem_classes='dropdown_info')

                        with gr.Row():
                            freeu_preset = gr.Dropdown(
                                label='FreeU Preset',
                                choices=list(flags.FREEU_DATA.keys()),
                                value=flags.DEFAULT_FREEU_KEY,
                                elem_classes='dropdown_50',
                                container=False
                            )
                            freeu_enabled = gr.Checkbox(
                                label='Enabled',
                                value=False,
                                elem_classes='min_check',
                                container=False,
                                info= 'If enabled, FreeU will remain active when the tab is closed'
                            )
                            freeu_restore_btn = gr.Button(
                                value="Restore Preset Values",
                                elem_classes='button_edit',
                                container=True,
                                interactive=False
                            )

                        # use the list values from config:
                        with gr.Row():
                            freeu_b1 = gr.Slider(label='B1',
                                minimum=0, maximum=2, step=0.01,
                                value=config.default_freeu[0],
                                info='Backbone Stage 1: Enhance composition and color'
                            )
                            freeu_b2 = gr.Slider(label='B2',
                                minimum=0, maximum=2, step=0.01,
                                value=config.default_freeu[1],
                                info='Backbone Stage 2: Enhance composition and color'
                            )
                        with gr.Row():
                            freeu_s1 = gr.Slider(label='S1',
                                minimum=0, maximum=4, step=0.01,
                                value=config.default_freeu[2],
                                info='Skip Connection Stage 1: Enhance texture and detail'
                            )
                            freeu_s2 = gr.Slider(label='S2',
                                minimum=0, maximum=4, step=0.01,
                                value=config.default_freeu[3],
                                info='Skip Connection Stage 2: Enhance texture and detail'
                            )
                        freeu_ctrls = [freeu_enabled, freeu_b1, freeu_b2, freeu_s1, freeu_s2]

                        with gr.Row(
                            elem_classes='elem_centre'):
                            with gr.Column():
                                gr.HTML('<font size="3">&emsp;<a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Fooocus-FreeU" target="_blank">\U0001F4DA Documentaion</a>')

                            with gr.Column():
                                gr.HTML('* The FreeU project page: <a href="https://github.com/ChenyangSi/FreeU" target="_blank">Free Lunch in Diffusion U-Net</a>')


            with gr.Accordion(label='Wildcards', visible=True, open=False) as prompt_wildcards:
                wildcards_list = gr.Dataset(components=[prompt], type='index',
                    label='Wildcard Filenames',
                    samples=wildcards.get_wildcards_samples(),
                    visible=True, samples_per_page=35)

                with gr.Row(equal_height=False):
                    gr.HTML(
                        '<font size="3"><a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Wildcards" target="_blank">\U0001F4DA Wildcards</a>',
                        elem_classes='link_trim')

                    read_wildcards_in_order = gr.Checkbox(
                        label="Generate Wildcard Contents in Order",
                        value = False, container=False,
                        elem_classes='left_align_check',
                        interactive=True)

                with gr.Accordion(label='Wildcard Contents',
                    visible=True, open=False) as words_in_wildcard:
                    wildcard_tag_name_selection = gr.Dataset(components=[prompt],
                    label='Words in the Wildcards',
                        samples=wildcards.get_words_of_wildcard_samples(),
                        visible=True, samples_per_page=30, type='index')

                wildcards_array = [prompt_wildcards, words_in_wildcard,
                    wildcards_list, wildcard_tag_name_selection]

                wildcards_array_show =lambda x: [gr.update(visible=True)] * 2 \
                    + [gr.Dataset.update(visible=True,\
                        samples=wildcards.get_wildcards_samples()),\
                        gr.Dataset.update(visible=True,\
                        samples=wildcards.get_words_of_wildcard_samples(x))]

                wildcards_array_hidden = [gr.update(visible=False)] * 2 +\
                    [gr.Dataset.update(visible=False,\
                    samples=wildcards.get_wildcards_samples()),\
                    gr.Dataset.update(visible=False,\
                    samples=wildcards.get_words_of_wildcard_samples())]

                wildcards_array_hold = [gr.update()] * 4

            switch_js = "(x) => {if(x){viewer_to_bottom(100);viewer_to_bottom(500);}else{viewer_to_top();} return x;}"
            down_js = "() => {viewer_to_bottom();}"


        with gr.Column(scale=1, visible=config.default_advanced_checkbox, elem_id="scrollable-box-hidden") as advanced_column:
            with gr.Tab(label='Settings', elem_id="scrollable-box"):
                if not args.args.disable_preset_selection and PR.get_preset_list():
                    with gr.Group():

                        if config.default_list_all_presets:
                            PR.category_selection = 'All'
                        category_selection = gr.Dropdown(label='Preset Categories',
                            choices=PR.get_preset_categories(),
                            value=PR.category_selection,
                            elem_id = 'cat_select',
                            visible=True, interactive=True)

                        preset_selection = gr.Dropdown(label='Presets',
                            choices=PR.get_presetnames_in_folder(PR.category_selection),
                            value=args.args.preset if args.args.preset else "initial",
                            elem_id = 'preset_select',
                            visible=True, interactive=True)

                with gr.Group():

                    negative_prompt = gr.Textbox(
                        label='Negative Prompt',
                        elem_classes="text-arial",
                        placeholder="Describe what you do not want to see",
                        elem_id='negative_prompt',
                        value=config.default_prompt_negative,
                        visible = not common.default_engine,
                        lines=2)

                    with gr.Accordion(label='Performance Options', visible=True, open=False):
                        performance_selection = gr.Radio(
                            label='Performance',
                            choices=flags.Performance.values(),
                            value=config.default_performance,
                            visible = not common.default_engine,
                            info='Quality=60 Steps, Speed=30 Steps, Custom=15 Steps default',
                            elem_classes=['performance_selection'])

                        overwrite_step = gr.Slider(label='Forced Overwrite of Sampling Step',
                            minimum=-1, maximum=200, step=1,
                            value=config.default_overwrite_step,
                            info='Set to -1 to disable')

                    image_quantity = gr.Slider(
                        label='Image Quantity',
                        minimum=1, step=1,
                        maximum=config.default_max_image_quantity,
                        value=config.default_image_quantity)

                    with gr.Accordion(label='Batch Control', visible=True,
                    open=False):

                            gr.Markdown(value='Create a new set of images several times, each batch starting with a new seed:',
                                elem_classes='button_info2')

                            with gr.Row(elem_classes='elem_centre'):
                                batch_generate_button = gr.Button(value='Batch Generate',
                                elem_classes='button_classic')

                                # hidden button, triggered by Javascript
                                # script.init_batchCounter()
                                batch_counter_button = gr.Button(value='Hidden Batch Counter',
                                elem_id='batch_counter_button', visible=False)

                            batch_count = gr.Slider(label='Batch Count',
                                minimum=1, step=1,
                                value=common.batch_count,
                                maximum=config.default_max_image_quantity//2,
                                info='Specify how many sets of images to generate. Use to create several image grids.')

                            generate_image_grid = gr.Checkbox(label='Generate an Image Grid for Each Batch',
                                value=config.default_generate_image_grid,
                                info='Group together two or more images to form one. Image Quantity determines the number of images in the grid, to a maximum of 16.')

                            with gr.Row(elem_classes='elem_centre'):
                                gr.HTML('<font size="3"><a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Batch-Generate-&-Image-Quantity" target="_blank">\U0001F4DA Batch Generate</a>')

                                gr.HTML('<font size="3"><a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Image-Grid" target="_blank">\U0001F4DA Image Grid</a>')

                    AR_template_init()
                    with gr.Accordion(label=AR.add_template_ratio(common.resolution),
                        open=False,
                        elem_id='aspect_ratios_accordion') as aspect_ratios_accordion:

                        aspect_info = gr.Textbox(value=f'{AR.AR_template} Template',\
                        info = AR.get_aspect_info_info(), elem_classes='aspect_info',\
                        container=False, interactive = False, visible=True)

                        aspect_ratios_selection = gr.Textbox(label='',
                            value=f'{AR.add_ratio(common.resolution)}, {AR.AR_template}',
                            elem_id='AR_selection', visible=False)

                        aspect_ratios_selections = []
                        for template in constants.aspect_ratios_templates:
                            aspect_ratios_selections.append(gr.Radio(label='',
                            choices=common.full_AR_labels[template],
                            value=AR.aspect_ratio_title[template],
                            visible=template==AR.AR_template,
                            elem_classes='aspect_ratios'))

                        for aspect_ratios_select in aspect_ratios_selections:
                            aspect_ratios_select.change(AR.save_current_aspect,
                            inputs=aspect_ratios_select,
                            outputs=[aspect_ratios_selection, aspect_info, aspect_info],
                            queue=False, show_progress=False)\
                            .then(lambda x: None, inputs=aspect_ratios_select,
                            queue=False, show_progress=False,
                            _js='(x)=>{refresh_aspect_ratios_label(x);}')

                        enable_shortlist_checkbox = gr.Checkbox(label='Use the Resolution Shortlist',\
                            info='List the most popular resolutions and aspect ratios only',
                            value=config.enable_shortlist_aspect_ratios,
                            visible = (AR.AR_template=="Standard") or (AR.AR_template=="Shortlist"))

                        overwrite_width = gr.Slider(label='Forced Overwrite of Generating Width',
                            minimum=-1, maximum=2048, step=1, value=-1,
                            info='Set to -1 to disable. '
                            'Results may be worse for non-standard numbers that the model is not trained on.')
                        overwrite_height = gr.Slider(label='Forced Overwrite of Generating Height',
                                            minimum=-1, maximum=2048, step=1, value=-1)

                    with gr.Accordion(label='Image Seed Control', visible=True, open=False):
                        seed_random = gr.Checkbox(
                            label='Random Seed',
                            info='Generate a random series of images', value=True)

                        image_seed = gr.Textbox(
                            label='Specific Seed',
                            info='Reuse a particular seed value to recreate images. Seeds can be no longer than 19 digits',\
                            value=0, max_lines=1,
                            visible=False)

                        extra_variation = gr.Checkbox(
                            label='Extra Variation',
                            info='Increase the randomness of image creation',
                            value=config.default_extra_variation,
                            visible=True)

                        disable_seed_increment = gr.Checkbox(
                            label='Freeze Seed',
                            info='Make similar images while processing an array or wildcards',
                            value=common.disable_seed_increment)

                        with gr.Row(elem_classes='elem_centre'):
                            gr.HTML('<font size="3"><a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Image-Seed-Control" target="_blank">\U0001F4DA Image Seed Control</a>')

                def update_history_link():
                    return gr.update(value=f'<font size="3">&emsp;<a href="file={get_current_html_path(output_format)}"\
                    target="_blank">\U0001F4DA Image Log</a>\
                    &emsp;<a href="https://www.facebook.com/groups/fooocus" target="_blank">\U0001F4D4 Forum</a>\
                    &emsp;<a href="https://github.com/DavidDragonsage/FooocusPlus/wiki" target="_blank">\U0001F4DA Wiki</a>')

                history_link = gr.HTML()
                common.GRADIO_ROOT.load(update_history_link, outputs=history_link,
                    queue=False, show_progress=False, elem_classes='centre')


                with gr.Tabs():
                    with gr.Tab(label='Describe Image', id='describe_tab', visible=True) as image_describe:
                        with gr.Row():
                            with gr.Column():
                                describe_input_image = grh.Image(
                                    label='Image to be Described',     source='upload',
                                    type='numpy',
                                    show_label=True)
                            with gr.Column():
                                describe_methods = gr.CheckboxGroup(
                                    label='Content Type',
                                    choices=flags.describe_types,
                                    value=config.default_describe_content_type)
                                describe_apply_styles = gr.Checkbox(label='Apply Styles', value=config.default_describe_apply_prompts_checkbox)
                                auto_describe_checkbox = gr.Checkbox(label='Auto-Describe', value=config.enable_auto_describe_image)
                            with gr.Column():
                                describe_image_size = gr.Textbox(label='Original Size / Recommended Size', elem_id='describe_image_size', visible=False)
                                describe_btn = gr.Button(value='Describe this Image into Prompt')
                                gr.HTML('<a href="https://github.com/lllyasviel/Fooocus/discussions/1363" target="_blank">\U0001F4DA Documentation</a>')

                    with gr.Tab(label='Image Metadata', id='metadata_tab', visible=True) as metadata_tab:
                        with gr.Column():
                            metadata_input_image = grh.Image(
                                label='Place a Fooocus Image Here',
                                source='upload',
                                image_mode='RGBA',
                                type='pil')

                            metadata_import_button = gr.Button(
                                value='Apply Metadata',
                                interactive=False)

                            with gr.Row(elem_classes='elem_centre'):
                                gr.HTML('<font size="3"><a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Image-Regeneration" target="_blank">\U0001F4DA Image Regeneration</a>')

                            with gr.Accordion("Preview Metadata", open=False, visible=True) as metadata_preview:
                                metadata_json = gr.JSON(label='Metadata')

            with gr.Tab(label='Styles', elem_classes="style_selections_tab"):
                style_sorter.try_load_sorted_styles(
                    style_names=legal_style_names,
                    default_selected=config.default_styles)

                with gr.Row():
                    gr.HTML('<font size="3"><a href="https://daviddragonsage-fooocusplus.static.hf.space/index.html" target="_blank">\U0001F4DA Help</a>')

                    style_search_bar = gr.Textbox(
                        show_label=False, container=False,
                        placeholder="\U0001F50E Type here to search styles...",
                        value="",
                        label='Search Styles',
                        elem_id='style_search_bar')

                style_selections = gr.CheckboxGroup(
                    show_label=False, container=False,
                    choices=copy.deepcopy(style_sorter.all_styles),
                    value=copy.deepcopy(config.default_styles),
                    label='Selected Styles',
                    elem_classes=['style_selections'])

                is_v2_default = 'Fooocus V2' in config.default_styles
                substyle_choices = US.list_files_by_patterns(
                    './substyles', patterns=['*.txt'],
                    names_only=True)
                with gr.Row():
                    v2_substyle = gr.Dropdown(
                        label='Fooocus V2 Substyle',
                        choices=substyle_choices,
                        value=config.v2_substyle,
                        visible=is_v2_default,
                        container='True'
                    )

                with gr.Row():
                    with gr.Column(
                    min_width=0, scale=1):
                        gr.HTML('<font size="3">&emsp;<a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Styles" target="_blank">\U0001F4DA Styles</a>')

                    with gr.Column(
                    min_width=0, scale=1):
                        gr.HTML('<font size="3">&emsp;<a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Styles:-Fooocus-V2-&-Substyles" target="_blank">\U0001F4DA Substyles</a>')

                gradio_receiver_style_selections = gr.Textbox(elem_id='gradio_receiver_style_selections', visible=False)

                common.GRADIO_ROOT.load(lambda: gr.update(choices=copy.deepcopy(style_sorter.all_styles)),
                    outputs=style_selections)


            with gr.Tab(label='Models', elem_id="scrollable-box"):
                with gr.Group():
                    base_model = gr.Dropdown(
                        label='Base Model',
                        choices=config.model_filenames,
                        value=config.default_base_model_name,
                        show_label=True,)

                    refiner_model = gr.Dropdown(
                        label='Refiner (SDXL or SD 1.5)',
                        choices=['None'] + config.model_filenames, value=config.default_refiner,
                        show_label=True,
                        visible = not common.default_engine)

                    # the replacement refiner switch slider
                    refiner_slider = gr.Slider(
                        label='Refiner Switch At',
                        minimum=0.1, maximum=1.0, step=0.001,
                        info='Use 0.4 for SD1.5 realistic models; '
                            'or 0.667 for SD1.5 anime models; '
                            'or 0.8 for XL-refiners; '
                            'or any value for switching two SDXL models.',
                        value=config.default_refiner_switch,
                        visible=config.default_refiner != 'None')

                # Sync common state with config defaults on startup
                for i, (enabled, filename, weight) in enumerate(config.default_loras):
                    if i < config.default_max_lora_number:
                        config.lora_data[i] = [enabled, filename, weight]

                # --- Helper for LoRA Handlers ---
                def make_lora_handler(index):
                    def handler(en, name, wt):
                        config.lora_data[index] = [en, name, wt]
                    return handler

                lora_ctrls = []
                for i, (enabled, filename, weight) in enumerate(config.default_loras):
                    with gr.Group():
                        with gr.Row():
                            lora_enabled = gr.Checkbox(label=f'LoRA {i + 1} Enable',
                                value=enabled,
                                elem_classes='min_check',
                                interactive = not common.default_engine or i<2)
                        with gr.Row():
                            lora_model = gr.Dropdown(label='',
                                choices=['None'] + config.lora_filenames,
                                value=filename,
                                interactive = not common.default_engine or i<2)
                        with gr.Row():
                            lora_weight = gr.Slider(label='Weight',
                                minimum=config.default_loras_min_weight,
                                maximum=config.default_loras_max_weight,
                                step=0.01, value=weight,
                                interactive = not common.default_engine or i<2)

                        # whenever any component in this row changes,
                        # update config.lora_data[i] using make_lora_handler()
                        current_handler = make_lora_handler(i)
                        for comp in [lora_enabled, lora_model, lora_weight]:
                            comp.change(fn=current_handler, inputs=[lora_enabled, lora_model, lora_weight])

                        lora_ctrls += [lora_enabled, lora_model, lora_weight]

#                        with gr.Row():
#                            trigger_info = gr.Markdown(value=f' Trigger Words: unknown',
#                            container=False, visible=True)

                with gr.Row():
                    refresh_files = gr.Button(
                        value='\U0001f504 Refresh All Files')
#                with gr.Row():
#                    refresh_files = gr.Button(
#                        value='\U0001f504 Load LoRA Trigger Words')

            with gr.Tab(label='Advanced', elem_id="scrollable-box"):
                guidance_scale = gr.Slider(
                    label='Guidance Scale (CFG)',
                    minimum=0.1, maximum=30.0, step=0.1,
                    value=config.default_cfg_scale,
                    info='Higher values create vivid and glossy images that may follow the prompt more closely')

                sharpness = gr.Slider(
                    label='Image Sharpness',
                    minimum=0.0, maximum=30.0, step=0.1,
                    value=config.default_sample_sharpness,
                    info='Higher values create images with more detailed textures')

                with gr.Accordion(label='Image Control', visible=True, open=False):

                    gr.Markdown(value='Save images after a crash or deletion. Images are only available prior to a new generative cycle.',
                        elem_classes='button_info')
                    recover_images_button = gr.Button(value='Recover Images')

                    with gr.Row(elem_classes='elem_centre'):
                        gr.HTML('<font size="3"><a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Image-Recovery" target="_blank">\U0001F4DA Image Recovery</a>')

                    with gr.Group():
                        output_format = gr.Radio(
                            label='Image Format',
                            choices=flags.OutputFormat.list(),
                            value=config.default_output_format)

                        if not args.args.disable_metadata:
                            save_metadata_to_images = gr.Checkbox(
                                label='Save Metadata to Images',
                                value=config.default_save_metadata_to_images,
                                info='Add parameters to an image for regeneration or upload to Civitai. A Metadata Scheme is not in effect unless this box is checked.')

                            metadata_scheme = gr.Radio(
                                label='Metadata Scheme',
                                choices=flags.metadata_scheme,
                                value=config.default_metadata_scheme,
                                info='Use "Fooocus" to regenerate images and "A1111" for upload to Civitai', visible=True)

                        disable_image_log_checkbox = gr.Checkbox(label='Disable Image Log',
                            value=config.disable_image_log,
                            info='Do not save image logs to the Outputs directory')

                        newest_images_first_checkbox = gr.Checkbox(
                            label='Show Newest Images First',
                            value=config.show_newest_images_first,
                            visible = True,
                            info='Create the Image Log with the newest images at the top')

                        disable_preview = gr.Checkbox(
                            label='Disable Preview',
                            value=config.default_black_out_nsfw,
                            interactive= not config.default_black_out_nsfw,
                            info='Disable preview during generation')

                        black_out_nsfw = gr.Checkbox(
                            label='Black Out NSFW', value=config.default_black_out_nsfw,
                            interactive=not config.default_black_out_nsfw,
                            info='Use black image if NSFW is detected')

                        save_only_final_enhanced_image = gr.Checkbox(
                            label='Save Only the Final Enhanced Image',
                            value = config.default_save_only_final_enhanced_image,
                            info='When in Enhance mode, display intermediate images but save only the last one')

                with gr.Accordion(
                    label='Catalog Control',
                    visible=True, open=False):

                    catalog_enable_checkbox = gr.Checkbox(
                        label='Enable the Images Catalog',
                        value=config.default_image_catalog_checkbox,
                        info='Display the catalog of generated images',
                        interactive = True)

                    quantity_pages = gr.Slider(
                        label='Quantity of Catalog Pages',
                        minimum=10, maximum=100, step=1,
                        value=config.default_image_catalog_max_number,
                        info='Large values become cumbersome',
                        interactive = True)

                    images_per_page = gr.Slider(
                        label='Quantity of Images per Page',
                        minimum=10, maximum=100, step=1,
                        value=config.default_image_catalog_max_per_page,
                        info='Large values can cause long response times',
                        interactive = True)

                    backfill_prompt = gr.Checkbox(
                        label='Copy Prompts While Switching Images',
                        value=config.default_backfill_prompt,
                        info='Fill the positive and negative prompts from the catalog images',
                        interactive = True)

                    image_tools_checkbox = gr.Checkbox(label='Enable Catalog Toolbox',
                        value=True,
                        info='Located on the main canvas, use the Toolbox to View or Load Log metadata information, or to Delete an image',
                        visible=True)


                dev_mode = gr.Checkbox(label='Expert Mode', value=config.default_expert_mode_checkbox, container=False)

                with gr.Column(visible=config.default_expert_mode_checkbox) as dev_tools:
                    with gr.Tab(label='Expert Tools'):

                        sampler_selector = gr.Dropdown(
                            label='Sampler',
                            choices=flags.sampler_list,
                            value=config.default_sampler,
                            interactive=True, visible=True)

                        scheduler_selector = gr.Dropdown(
                            label='Scheduler',
                            choices=flags.scheduler_list,
                            value=config.default_scheduler,
                            interactive=True, visible=True)

                        vae_name = gr.Dropdown(
                            label='VAE',
                            choices=[modules.flags.default_vae] + config.vae_filenames,
                            value=config.default_vae,
                            show_label=True)

                        clip_skip = gr.Slider(
                            label='CLIP Skip',
                            minimum=1,
                            maximum=flags.clip_skip_max,
                            step=1,
                            value=config.default_clip_skip,
                            info='Bypass CLIP layers to avoid overfitting (use 1 to not skip any layers, 2 is recommended).')

                        adaptive_cfg = gr.Slider(
                            label='CFG Mimicking from TSNR',
                            minimum=1.0, maximum=30.0, step=0.01,
                            value=config.default_cfg_tsnr,
                            info='Enabling Fooocus\'s implementation of CFG mimicking for TSNR ' \
                                '(effective when real CFG > mimicked CFG)')

                        refiner_swap_method = gr.Dropdown(label='Refiner Swap Method',
                            value=flags.refiner_swap_method,
                            choices=['joint', 'separate', 'vae'])

                        overwrite_switch = gr.Slider(label='Forced Overwrite of Refiner Switch Step',
                            minimum=-1, maximum=200, step=1,
                            value=config.default_overwrite_switch,
                            info='Set to -1 to disable')

                        adm_scaler_positive = gr.Slider(
                            label='Positive ADM Guidance Scaler', minimum=0.1, maximum=3.0,
                            step=0.001, value=1.5,
                            info='The scaler multiplied to positive ADM (use 1.0 to disable). ')

                        adm_scaler_negative = gr.Slider(
                            label='Negative ADM Guidance Scaler', minimum=0.1, maximum=3.0,
                            step=0.001, value=0.8,
                            info='The scaler multiplied to negative ADM (use 1.0 to disable). ')

                        adm_scaler_end = gr.Slider(
                            label='ADM Guidance End At Step',
                            minimum=0.0, maximum=1.0,
                            step=0.001, value=0.3,
                            info='When to end the guidance from positive/negative ADM. ')


                    with gr.Tab(label='Debugging'):
                        with gr.Group():
                            debugging_cn_preprocessor = gr.Checkbox(
                                label='Debug ControlNet Preprocessors',
                                value=False,
                                info='See the results from preprocessors')

                            skipping_cn_preprocessor = gr.Checkbox(
                                label='Skip ControlNet Preprocessors',
                                value=False,
                                info='Do not preprocess images. (Inputs are already canny/depth/cropped-face/etc.)')

                            debugging_inpaint_preprocessor = gr.Checkbox(
                                label='Debug Inpaint Preprocessing',
                                value=False)

                            debugging_dino = gr.Checkbox(
                                label='Debug GroundingDINO',
                                value=False,
                                info='Use GroundingDINO boxes instead of more detailed SAM masks')

                            debugging_enhance_masks_checkbox = gr.Checkbox(
                                label='Debug Enhance Masks',
                                value=False,
                                info='Show enhance masks in preview and final results')

                            debug_substyles_checkbox = gr.Checkbox(
                                label='Debug Substyles',
                                value=False,
                                info='Check for inactive words')

                            with gr.Row():
                                remove_info = interpret(
                                    'Remove dynamic PyTorch components and configs',
                                    '', silent=True)
                                gr.Markdown(value=remove_info,
                                    elem_classes='button_info2')
                            with gr.Row(
                                elem_classes='elem_centre'):
                                remove_value = interpret(
                                    'Remove Torch Components',
                                    '', silent=True)
                                remove_torch_btn = gr.Button(
                                    value=remove_value,
                                    elem_classes= 'button_classic')

                        common.GRADIO_ROOT.load(
                            UIU.inpaint_mode_change,
                            inputs=[inpaint_mode, inpaint_engine_state],
                            outputs=[inpaint_additional_prompt,
                                     outpaint_selections,
                                     example_inpaint_prompts,
                                     inpaint_disable_initial_latent,
                                     inpaint_engine,
                                     inpaint_strength,
                                     inpaint_respective_field],
                            show_progress=False, queue=False)

                        for mode, disable_initial_latent, engine, strength, respective_field in enhance_inpaint_update_ctrls:
                            common.GRADIO_ROOT.load(
                                UIU.enhance_inpaint_mode_change,
                                inputs=[mode, inpaint_engine_state],
                                outputs=[disable_initial_latent,
                                        engine, strength,
                                        respective_field],
                                show_progress=False, queue=False)

            with gr.Tab(label='Extras', elem_id="scrollable-box"):
                with gr.Group():
                    with gr.Row():
                        gr.Markdown(value='All current parameters will be saved. Clear the positive and negative prompts unless you want them to be part of the preset.',
                            elem_classes='button_info2')
                    with gr.Row(elem_classes='elem_centre'):
                        preset_save_button = gr.Button(value='Make New Preset',
                            elem_classes='button_classic')
                    with gr.Row():
                        save_res_checkbox = gr.Checkbox(label='Save the Current Resolution',
                            value = common.save_resolution,
                            info='Do not save the resolution and aspect ratio unless you want it to change when switching presets')
                    with gr.Row():
                        overwrite_prompts_checkbox = gr.Checkbox(label='Overwrite the Current Prompts',
                            value = common.overwrite_prompts,
                            info='Do now use this option unless you want the new preset to specify the positive and negative prompts')

                if not args.args.disable_preset_selection and PR.get_preset_list():
                    with gr.Accordion(label='Favorite Preset Control', visible=True, open=False):
                        with gr.Row():
                            gr.Markdown(value='Add or remove the current preset from the Favorite category. Removed favorites are saved in "UserDir/user_presets/Old Favorites". The Default preset cannot be removed.',
                                elem_classes='button_info2')
                        with gr.Row(elem_classes='elem_centre'):
                            preset_favorite_button = gr.Button(value=PR.preset_favorite_value,
                            elem_classes='button_classic2',
                            interactive = PR.current_preset != 'Default')
                        with gr.Row():
                            gr.Markdown(value='Add the default Favorites. This may override preset modifications.',
                                elem_classes='button_info2')
                        with gr.Row(elem_classes='elem_centre'):
                            restore_favorites_button = gr.Button(value='Restore Favorites',
                            elem_classes='button_classic2')
                        with gr.Row():
                            gr.Markdown(value='Remove all Favorites except the Default and store them in "UserDir/user_presets/Old Favorites".',
                                elem_classes='button_info2')
                        try:
                            init_interactive=US.init_preset_structure()>0
                        except:
                            init_interactive=interactive=False
                        with gr.Row(elem_classes='elem_centre'):
                            clear_favorites_button = gr.Button(
                            value='Clear Favorites',
                            interactive=init_interactive,
                            elem_classes='button_classic2')

                with gr.Group():
                    with gr.Row():
                        language_ui = gr.Radio(visible=False,
                            label='Language of UI',
                            choices=[''], value='', interactive=False)
                        background_mode = gr.Radio(label='Background Mode',
                            choices=['light', 'dark'],
                            value=args.args.mode, interactive=True)

                    audio_notification_checkbox = gr.Checkbox(label='Enable Audio Notification',
                        value=config.audio_notification,
                        elem_id = 'enable_notification',
                        info='Play a sound at the end of the generative cycle')

                    welcome_logo_checkbox = gr.Checkbox(
                        label='Use Logo Welcome Image',
                        value=check_active_logo(),
                        info='The FooocusPlus logo will suppress all other welcome images',
                        interactive = True,
                        visible = True)

                    if not args.args.disable_comfyd:
                        comfyd_active_checkbox = gr.Checkbox(label='Enable Comfyd Always Active',
                            value=config.default_comfy_active_checkbox,
                            info='Enabling will improve execution speed but occupy some memory')


                    prompt_translator_checkbox = gr.Checkbox(label='Enable Prompt Translator',
                        value=config.default_prompt_translator_enable,
                        info='If disabled, all prompts must be entered in English',
                        visible = args.args.language != 'en' and args.args.language != 'en_uk')

                    wildcard_line_slider = gr.Slider(label='Wildcard Lines to Interpret',
                        minimum=0, maximum=380, step=5,
                        value=config.wildcard_lines_to_interpret,
                        info='Set to 0 to disable. Large numbers can cause long delays',
                        visible = args.args.language != 'en' and args.args.language != 'en_uk')

                    translation_methods = gr.Radio(label='', choices='',
                        value='', interactive=False, visible = False)
                    mobile_url = gr.Checkbox(label='',
                        value=False, interactive=False, visible=False)
                    prompt_panel_checkbox = gr.Checkbox(label='Secret',
                        interactive = False, value=True,
                        container=False, visible=False)

                # custom plugin "OneButtonPrompt"
                import custom.OneButtonPrompt.ui_onebutton as ui_onebutton
                run_event = gr.Number(visible=False, value=0)
                ui_onebutton.ui_onebutton(prompt, run_event, random_button)
                super_prompter_prompt = gr.Textbox(label='', value='',
                    info='', lines=1, visible=False)

                if UIU.security_alert():
                    with gr.Row():
                        if args.args.listen != "127.0.0.1":
                            listen_str = f'The --listen argument has changed the network address from the default "127.0.0.1" to \"{args.args.listen}\"<br>'
                        else:
                            listen_str = ''
                        if args.args.port != 7860:
                            port_str = f'The --port argument has changed the network listening port number from the default 7860 to {args.args.port}<br>'
                        else:
                            port_str = ''
                        gr.Markdown(value=f'<h3>Security Report</h3>\
                        One or more command line arguments have adjusted the security settings.<br> \
                        {listen_str}{port_str}')

                with gr.Group():
                    with gr.Row():
                        perform_info = interpret(
                            'Verify video system',
                            '(GPU):', silent=True)
                        gr.Markdown(value=perform_info,
                            elem_classes='button_info2')
                    with gr.Row(
                        elem_classes='elem_centre'):
                        perform_value = interpret(
                            'Check Performance',
                            '', silent=True)
                        perform_btn = gr.Button(value=perform_value,
                            elem_classes='button_classic')

                with gr.Row(elem_classes='elem_up'):
                    if args.args.always_offload_from_vram:
                        smart_memory = interpret(
                            'Disabled (VRAM unloaded whenever possible)',
                            '', silent=True)
                    else:
                        smart_memory = interpret(
                            'Enabled (VRAM unloaded only when necessary',
                            '', silent=True)
                    video_system = model_management.get_torch_device_name\
                        (model_management.get_torch_device())
                    torch_ver, xformers_ver, cuda_ver = torch_info()
                    if xformers_ver == '':
                        xformers_ver = "not installed"

                    fooocusplus_ver, hotfix, hotfix_title = version.get_fooocusplus_ver()
                    gr.Markdown(value=f'<h3>System Information</h3>\
                    System RAM: {int(model_management.get_sysram())} MB,\
                    Video RAM: {int(model_management.get_vram())} MB<br>\
                    Smart Memory: {smart_memory}<br>\
                    Video System: {video_system}<br>\
                    Python {platform.python_version()}, Library {version.get_library_ver()}, \
                    Comfy {comfy.comfy_version.version}<br>\
                    Gradio {gr.__version__}, Torch {torch_ver}{cuda_ver}, Xformers {xformers_ver}<br>\
                    FooocusPlus {fooocusplus_ver}, Hotfix {hotfix}')


                with gr.Row(elem_classes='elem_centre'):
                    gr.HTML('<font size="3"><a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/System-Information" target="_blank">\U0001F4DA System Information</a>')

                    gr.HTML('<font size="3"><a href="https://github.com/DavidDragonsage/FooocusPlus/wiki/Updates-&-Versions" target="_blank">\U0001F4DA Updates & Versions</a>')

                with gr.Row(elem_classes='elem_centre'):
                    gr.HTML('<font size="3">&emsp;<a href="https://github.com/DavidDragonsage/FooocusPlus/blob/main/fooocusplus_log.md" target="_blank">\U0001F4DA Version Info</a>')

# END OF UI COMPONENT DEFINITIONS

    # The Stack Transfer Section
    # Pulls values from the UI to transfer
    # via a stack to async_worker
    # where the items are accessed via args.pop()
    # This is an obsolete and unreliable transfer
    # method that has been greatly reduced.

    ctrls = [currentTask]

    ctrls += [style_selections]

    ctrls += [params_backend]

    ctrls += enhance_ctrls


    def wildcard_line_control(wildcard_line_slider):
        config.wildcard_lines_to_interpret = wildcard_line_slider
        common.wildcard_lines_to_interpret = wildcard_line_slider
        return wildcard_line_slider

    wildcard_line_slider.release(wildcard_line_control,
        inputs=wildcard_line_slider,
        outputs=wildcard_line_slider,
        queue=False, show_progress=False)

    ehps = [backfill_prompt, translation_methods, comfyd_active_checkbox]

    def update_state_topbar(name, value, state):
        state.update({name: value})
        return state

    state_is_generating = gr.State(False)

   # language_ui.select(lambda x,y: update_state_topbar('__lang',x,y), inputs=[language_ui, state_topbar],\
   #     outputs=state_topbar).then(None, inputs=language_ui, _js="(x) => set_language_by_ui(x)")

    # set_theme_by_ui is located in javascript.topbar.js
    background_mode.select(lambda x,y: update_state_topbar('__theme',x,y), inputs=[background_mode, state_topbar],\
        outputs=state_topbar).then(None, inputs=background_mode, _js="(x) => set_theme_by_ui(x)")


    # Prompt Group Event Handlers & Helpers

    system_params = gr.JSON({}, visible=False)

    def parse_meta(raw_prompt_txt, is_generating, state_params, panel_status):
        loaded_json = None
        if len(raw_prompt_txt)>=1 and (raw_prompt_txt[-1]=='[' or raw_prompt_txt[-1]=='_'):
            return [gr.update()] * 3 + [True]
        try:
            if '{' in raw_prompt_txt:
                if '}' in raw_prompt_txt:
                    if ':' in raw_prompt_txt:
                        loaded_json = json.loads(raw_prompt_txt)
                        assert isinstance(loaded_json, dict)
        except:
            loaded_json = None

        if loaded_json is None:
            if is_generating:
                return [gr.update()] * 4
            else:
                return [gr.update(), gr.update(visible=True), gr.update(visible=False), gr.update()]

        return [json.dumps(loaded_json), gr.update(visible=False), gr.update(visible=True), gr.update()]


    def calculateTokenCounter(
        text, style_selections):
        if len(text) < 1:
            return 0
        num = UIS.prompt_token_prediction(
            text, style_selections)
        return str(num)

    prompt.change(
        lambda x,y: calculateTokenCounter(x,y),
        inputs=[prompt, style_selections],
        outputs=prompt_token_counter)

    prompt.input(parse_meta,
        inputs=[prompt, state_is_generating,
            state_topbar, prompt_panel_checkbox],
        outputs=[prompt, generate_button,
            load_parameter_button, prompt_panel_checkbox],
        queue=False, show_progress=False)


    super_prompter.click(
        lambda x, y, z: enhanced.superprompter.answer(
            input_text=translator.translate(f'{y}{x}', True),
        seed=image_seed),
        inputs=[prompt, super_prompter_prompt, translation_methods],
        outputs=prompt,
        queue=False,
        show_progress=True)

    translator_button.click(
        enhanced.translator.translate,
        inputs=prompt,
        outputs=prompt,
        queue=False,
        show_progress=True)


    # substituted prompt_panel_checkbox for advanced_checkbox
    # to avoid toggling Advanced tab visibility
    load_data_outputs = [prompt_panel_checkbox, image_quantity,
        prompt, negative_prompt,
        style_selections, v2_substyle,
        performance_selection,
        overwrite_step, overwrite_switch,
        aspect_ratios_selection,
        overwrite_width, overwrite_height,
        guidance_scale, sharpness,
        adm_scaler_positive, adm_scaler_negative,
        adm_scaler_end,
        refiner_swap_method,
        adaptive_cfg, clip_skip,
        base_model, refiner_model,
        refiner_slider, sampler_selector,
        scheduler_selector, vae_name,
        seed_random, image_seed,
        inpaint_engine, inpaint_engine_state,
        inpaint_mode] + enhance_inpaint_mode_ctrls +\
        [generate_button, load_parameter_button] +\
        freeu_ctrls + lora_ctrls


    # Performance Selection Event Handlers and Helpers

    def on_performance_change(selection):
        # write data to common for async_worker to read
        common.performance_selection = selection

        # check for speed restrictions (Lightning/Hyper-SD etc.)
        is_restricted = flags.Performance.has_restricted_features(selection)

        # the first 9 items (sliders/dropdowns) get an interactivity toggle
        ui_updates = [gr.update(interactive=not is_restricted)] * 9

        # the 10th item (negative_prompt) gets a visibility toggle
        ui_updates.append(gr.update(visible=not is_restricted))
        return ui_updates

    performance_selection.change(
        fn=on_performance_change,
        inputs=performance_selection,
        outputs=[
            guidance_scale, sharpness,
            adm_scaler_end, adm_scaler_positive,
            adm_scaler_negative, refiner_slider,
            scheduler_selector, adaptive_cfg,
            refiner_swap_method, negative_prompt
        ],
        queue=False,
        show_progress=False
    )

    def overwrite_step_change(arg_steps):
        config.default_overwrite_step = arg_steps
        return gr.update(value=config.default_overwrite_step)

    overwrite_step.change(
        fn=overwrite_step_change,
        inputs=overwrite_step,
        outputs=overwrite_step,
        queue=False, show_progress=False)


    # Resolution Handlers & Helpers

    aspect_ratios_selection.change(
        AR.reset_aspect_ratios,
        inputs=aspect_ratios_selection,
        outputs=aspect_ratios_selections,
        queue=False, show_progress=False
    ).then(
        AR.save_AR_template,
        inputs=aspect_ratios_selection,
        outputs=[aspect_ratios_selection,
            aspect_info, aspect_info,
            enable_shortlist_checkbox],
        queue=False, show_progress=False,
        _js='(x)=>{refresh_aspect_ratios_label(x);}')

    enable_shortlist_checkbox.change(
        AR.toggle_shortlist,
        inputs=enable_shortlist_checkbox,
        outputs=[enable_shortlist_checkbox,
            aspect_info, aspect_info, preset_selection],
        queue=False, show_progress=False
    )

    def overwrite_width_change(arg_width):
        common.overwrite_width = arg_width
        return gr.update(
            value=common.overwrite_width
    )

    overwrite_width.release(
        AR.overwrite_aspect_ratios,
        inputs=[overwrite_width, overwrite_height],
        outputs=aspect_ratios_selection,
        queue=False, show_progress=False
    ).then(
        fn=overwrite_width_change,
        inputs=overwrite_width,
        outputs=overwrite_width,
        queue=False, show_progress=False
    ).then(
        lambda x: None,
        inputs=aspect_ratios_select,
        queue=False,
        show_progress=False,
        _js='(x)=>{window.refresh_aspect_ratios_label(x);}'
    )

    def overwrite_height_change(arg_height):
        common.overwrite_height = arg_height
        return gr.update(
            value=common.overwrite_height
    )

    overwrite_height.release(
        AR.overwrite_aspect_ratios,
        inputs=[overwrite_width, overwrite_height],
        outputs=aspect_ratios_selection,
        queue=False, show_progress=False
    ).then(
        fn=overwrite_height_change,
        inputs=overwrite_height,
        outputs=overwrite_height,
        queue=False, show_progress=False
    ).then(
        lambda x: None,
        inputs=aspect_ratios_select,
        queue=False,
        show_progress=False,
        _js='(x)=>{window.refresh_aspect_ratios_label(x);}'
    )


    advanced_checkbox.change(
        lambda x: gr.update(visible=x), advanced_checkbox,
        advanced_column,
        queue=False, show_progress=False
    ).then(
        fn=lambda: None,
        queue=False, show_progress=False,
        _js='refresh_grid_delayed')


    def preset_bar_menu_change(
        enable_presetbar):
        config.enable_preset_bar = enable_presetbar
        return (gr.update(value=enable_presetbar),
                gr.update(visible=enable_presetbar))

    preset_bar_checkbox.change(
        preset_bar_menu_change,
        inputs=preset_bar_checkbox,
        outputs=[preset_bar_checkbox, preset_row],
        queue=False, show_progress=False)

    reset_preset_layout = [params_backend,
        performance_selection,
        sampler_selector, scheduler_selector,
        input_image_checkbox, enhance_checkbox,
        base_model, refiner_model, overwrite_step,
        guidance_scale, negative_prompt,
        preset_instruction] + lora_ctrls
    common.len_preset_layout = len(reset_preset_layout)

    reset_preset_func = [output_format,
        inpaint_advanced_masking_checkbox,
        mixing_uov_checkbox,
        mixing_inpaint_checkbox,
        backfill_prompt, translation_methods,
        input_image_checkbox, state_topbar]
    common.len_preset_func = len(reset_preset_func)

    def update_preset_info():
        common.metadata_loading = True
        return PR.current_preset

    def normalize_preset_loading():
        time.sleep(2)
        common.metadata_loading = False
        if common.log_metadata:
            interpret('Finished loading metadata')
            print()
        common.log_metadata = ''
        return

    def prepare_UI_for_metadata():
        return (gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value=False))

    # shared by copy/paste from log
    # and Toolbox Load Log Info
    def attach_load_log_pipeline(trigger_event):
        return(
            trigger_event
    ).then(
        fn=lambda: interpret_info('Loading log metadata...'),
        outputs=None,
    ).then(
        lambda: None,
        inputs=None,
        outputs=None,
        queue=False, show_progress=False,
        _js='()=>{window.close_finished_images_catalog();}'
    ).then(
        fn=prepare_UI_for_metadata,
        inputs=None,
        outputs= [toolbox_note_load_button,
                  toolbox_note_box,
                  input_image_checkbox],
        queue=False, show_progress=False
    ).then(
        fn=modules.meta_parser.read_meta_from_log,
        inputs=[prompt, state_is_generating, inpaint_mode],
        outputs=load_data_outputs,
        queue=False, show_progress=False
    ).then(
        style_sorter.sort_styles,
        inputs=style_selections,
        outputs=style_selections,
        queue=False, show_progress=False
    ).then(
        fn=update_preset_info,
        inputs=None,
        outputs=preset_selection,
        queue=False, show_progress=False
    ).then(
        fn=modules.meta_parser.read_meta_from_log,
        inputs=[prompt, state_is_generating, inpaint_mode],
        outputs=load_data_outputs,
        queue=False, show_progress=False
    ).then(
        fn=lambda: time.sleep(6),
        outputs=None
    ).then(
        fn=modules.meta_parser.read_meta_from_log,
        inputs=[prompt, state_is_generating, inpaint_mode],
        outputs=load_data_outputs,
        queue=False, show_progress=False
    ).then(
        fn=lambda: time.sleep(6),
        outputs=None
    ).then(
        fn=modules.meta_parser.read_meta_from_log,
        inputs=[prompt, state_is_generating, inpaint_mode],
        outputs=load_data_outputs,
        queue=False, show_progress=False
    ).then(
        fn=normalize_preset_loading,
        inputs=None, outputs=None,
        queue=False, show_progress=False)

    # Load Parameters from log via clipboard
    main_load_event = load_parameter_button.click(
        fn=lambda: None)
    attach_load_log_pipeline(main_load_event)

    # Load Parameters directly from the log
    toolbox_load_event = toolbox_note_load_button.click(
        fn=toolbox.load_log_info_into_prompt,
        inputs=state_topbar,
        outputs=prompt # the Virtual paste
    )
    attach_load_log_pipeline(toolbox_load_event)


    def image_metadata_import(file, state_is_generating, state_params):
        parameters, metadata_scheme = modules.meta_parser.read_meta_from_image(file)
        if parameters is None:
            interpret_warn('Could not find valid metadata in the image!')
        return toolbox.reset_params_by_meta(parameters,
            state_params, state_is_generating, inpaint_mode)


    # Apply Metadata after image load
    metadata_import_button.click(
        fn=lambda: interpret_info('Loading image metadata...'),
        outputs=None
    ).then(
        lambda: None,
        inputs=None,
        outputs=None,
        queue=False, show_progress=False,
        _js='()=>{window.close_finished_images_catalog();}'
    ).then(
        fn=prepare_UI_for_metadata,
        inputs=None,
        outputs= [toolbox_note_load_button,
                  toolbox_note_box,
                  input_image_checkbox],
        queue=False, show_progress=False
    ).then(
        fn=image_metadata_import,
        inputs=[metadata_input_image,
        state_is_generating, state_topbar],
        outputs=reset_preset_layout +
            reset_preset_func + load_data_outputs,
        queue=False, show_progress=False
    ).then(
        style_sorter.sort_styles,
        inputs=style_selections,
        outputs=style_selections,
        queue=False, show_progress=False
    ).then(
        fn=update_preset_info,
        inputs=None, outputs=preset_selection,
        queue=False, show_progress=False
    ).then(
        fn=image_metadata_import,
        inputs=[metadata_input_image,
        state_is_generating, state_topbar],
        outputs=reset_preset_layout +
          reset_preset_func + load_data_outputs,
        queue=False, show_progress=False
    ).then(
        fn=lambda: time.sleep(6),
        outputs=None
    ).then(
        fn=image_metadata_import,
        inputs=[metadata_input_image,
        state_is_generating, state_topbar],
        outputs=reset_preset_layout +
          reset_preset_func + load_data_outputs,
        queue=False, show_progress=False
    ).then(
        fn=lambda: time.sleep(6),
        outputs=None
    ).then(
        fn=image_metadata_import,
        inputs=[metadata_input_image,
        state_is_generating, state_topbar],
        outputs=reset_preset_layout +
          reset_preset_func + load_data_outputs,
        queue=False, show_progress=False
    ).then(
        fn=normalize_preset_loading,
        inputs=None, outputs=None,
        queue=False, show_progress=False)


    def trigger_metadata_preview(file):
        parameters, metadata_scheme = modules.meta_parser.read_meta_from_image(file)
        results = {}
        if parameters is not None:
            results['parameters'] = parameters

        if isinstance(metadata_scheme, flags.MetadataScheme):
            results['metadata_scheme'] = metadata_scheme.value
            if metadata_scheme.value.lower() == 'simple':
                results['metadata_scheme'] = 'Fooocus'
            if metadata_scheme.value.lower() == 'a1111':
                results['metadata_scheme'] = 'A1111'
                parameters = None

        return [results, gr.update(interactive=parameters is not None)]

    metadata_input_image.upload(trigger_metadata_preview,
        inputs=metadata_input_image,
        outputs=[metadata_json, metadata_import_button],
        queue=False, show_progress=True)

    model_check = [prompt, negative_prompt, base_model, refiner_model] + lora_ctrls
    nav_bars = [bar_title] + bar_buttons
    protections = [random_button, translator_button, super_prompter, background_mode, image_tools_checkbox]


    # Catalogue Event Handlers and Helpers

    gallery_index.select(
        gallery_util.select_index,
        inputs=[gallery_index,
            image_tools_checkbox, state_topbar],
        outputs=[history_gallery, image_toolbox,
            preview_window, progress_gallery,
            toolbox_info_box, toolbox_note_box,
            toolbox_note_info, toolbox_note_input_name,
            toolbox_note_load_button,
            toolbox_note_preset_button, state_topbar],
            show_progress=False)

    history_gallery.select(
        gallery_util.select_history_gallery,
        inputs=[gallery_index,
            state_topbar, backfill_prompt],\
        outputs=[toolbox_info_box,
            prompt,
            negative_prompt,
            toolbox_note_info,
            toolbox_note_input_name,
            toolbox_note_load_button,
            toolbox_note_preset_button,
            state_topbar],
        show_progress=False)

    gallery_index_stat.change(
        fn=None,
        inputs=[gallery_index_stat],
        outputs=None,
        _js='refresh_finished_images_catalog_label'
    )

    gallery_index.change(
        gallery_util.images_list_update,
        inputs=[gallery_index, state_topbar],
        outputs=[history_gallery,
            catalogue_accordion,
            state_topbar,
            progress_gallery,
            welcome_window],
        show_progress=False)

    progress_gallery.select(
        gallery_util.select_gallery_progress,
        inputs=state_topbar,
        outputs=[toolbox_info_box,
            toolbox_note_info,
            toolbox_note_input_name,
            toolbox_note_load_button,
            toolbox_note_preset_button,
            state_topbar],
        show_progress=False)


    # Catalogue Toolbox Event Handlers & Helpers

    toolbox_info_button.click(
        toolbox.toggle_toolbox_info,
        inputs=state_topbar,
        outputs=[toolbox_info_box, state_topbar],
        show_progress=False)

    toolbox_load_button.click(
        toolbox.toggle_note_box_load,
        inputs=model_check + [state_topbar],
        outputs=[
            toolbox_note_info,
            toolbox_note_load_button,
            toolbox_note_cancel_button, # Added!
            toolbox_note_box,
            state_topbar
        ],
        show_progress=False)

    toolbox_delete_button.click(
        toolbox.toggle_note_box_delete,
        inputs=state_topbar,
        outputs=[
            toolbox_note_info,
            toolbox_note_delete_button,
            toolbox_note_cancel_button,
            toolbox_note_box,
            state_topbar
        ],
        show_progress=False)

    toolbox_note_delete_button.click(
        toolbox.delete_image,
        inputs=state_topbar,
        outputs=[history_gallery,
            gallery_index,
            toolbox_note_delete_button,
            toolbox_note_box,
            state_topbar,
            preview_window,
            welcome_window,
            image_toolbox],
            show_progress=False
        ).then(
            fn=gallery_util.get_gallery_label,
            inputs=state_topbar,
            outputs=[gallery_index, gallery_index_stat, history_gallery],
            queue=False, show_progress=False
        ).then(
            fn=None,
            inputs=[gallery_index_stat],
            queue=False, show_progress=False,
            _js='(x)=>{window.refresh_finished_images_catalog_label(x);}'
        )

    # One handler to rule them all
    toolbox_note_cancel_button.click(
        toolbox.cancel_note_box,
        inputs=state_topbar,
        outputs=[
            toolbox_note_info,
            toolbox_note_input_name,
            toolbox_note_delete_button,
            toolbox_note_load_button,
            toolbox_note_preset_button,
            toolbox_note_cancel_button,
            toolbox_note_box,
            state_topbar,
            toolbox_note_input_name # Reset the text field value as well
        ],
        show_progress=False
    )


    # Performance Check Handlers

    # 1. Trigger the Performance Check
    # Conditional Dialog
    perform_btn.click(
        fn=UIU.check_performance_handler,
        inputs=None,
        outputs=[
            perf_modal_box,
            perf_modal_header_msg,
            perf_modal_metrics_msg,
            perf_ok_btn,
            perf_upgrade_btn,
            perf_cancel_btn
        ],
        queue=False, show_progress=False
    )

    # 2. Informational Dismiss (Single OK Button)
    perf_ok_btn.click(
        fn=UIU.close_performance_modal,
        inputs=None,
        outputs=perf_modal_box,
        queue=False, show_progress=False
    )

    # 3. Action Cancel (Close Box without doing anything)
    perf_cancel_btn.click(
        fn=UIU.close_performance_modal,
        inputs=None,
        outputs=perf_modal_box,
        queue=False, show_progress=False
    )

    # 4. Action Confirmation
    # Execute Upgrade, then show final OK instructions
    perf_upgrade_btn.click(
        fn=UIU.execute_cuda13_upgrade,
        inputs=None,
        outputs=[
            perf_modal_box,
            perf_modal_header_msg,
            perf_modal_metrics_msg,
            perf_ok_btn,
            perf_upgrade_btn,
            perf_cancel_btn
        ],
        queue=False, show_progress=False
    )


    # Aspect Ratio Event Handlers and Helpers

    overwrite_width.release(
        AR.overwrite_aspect_ratios,
        inputs=[overwrite_width, overwrite_height],
        outputs=aspect_ratios_selection,
        queue=False, show_progress=False
    ).then(
        lambda x: None,
        inputs=aspect_ratios_select,
        queue=False,
        show_progress=False,
        _js='(x)=>{window.refresh_aspect_ratios_label(x);}'
    )

    overwrite_height.release(
        AR.overwrite_aspect_ratios,
        inputs=[overwrite_width, overwrite_height],
        outputs=aspect_ratios_selection,
        queue=False, show_progress=False
    ).then(
        lambda x: None,
        inputs=aspect_ratios_select,
        queue=False,
        show_progress=False,
        _js='(x)=>{window.refresh_aspect_ratios_label(x);}'
    )


    # Seed Control Event Handlers & Helpers

    def image_seed_change(arg_image_seed):
        if arg_image_seed.isdigit():
            common.saved_seed = arg_image_seed
        else:
            common.image_seed = common.saved_seed
        return gr.update(value=common.saved_seed)

    image_seed.change(
        fn=image_seed_change,
        inputs=[image_seed],
        outputs=[image_seed],
        queue=False, show_progress=False)

    def random_checked(bool_random):
        return (gr.update(visible=not bool_random),
                gr.update(value=common.saved_seed))

    seed_random.change(
        fn=random_checked,
        inputs=[seed_random],
        outputs=[image_seed, image_seed],
        queue=False, show_progress=False)

    def extra_variation_change(bool_extra_variation):
        config.default_extra_variation = bool_extra_variation
        return gr.update(value=config.default_extra_variation)

    extra_variation.change(
        fn=extra_variation_change,
        inputs=extra_variation,
        outputs=extra_variation,
        queue=False, show_progress=False)

    def disable_increment(disable_checked):
        common.disable_seed_increment = disable_checked
        return (gr.update(value=common.disable_seed_increment),
                gr.update(visible=not common.disable_seed_increment))

    disable_seed_increment.change(
        fn=disable_increment,
        inputs=disable_seed_increment,
        outputs=[disable_seed_increment, extra_variation],
        queue=False, show_progress=False)

    def refresh_seed(bool_random, seed_string):
        # called by generate_button.click()
        if bool_random:
            common.saved_seed = random.randint(constants.MIN_SEED, constants.MAX_SEED)
            return common.saved_seed
        else:
            try:
                seed_value = int(seed_string)
                if constants.MIN_SEED <= seed_value <= constants.MAX_SEED:
                    common.saved_seed = seed_value
                    return common.saved_seed
            except:
                pass
            common.saved_seed = random.randint(constants.MIN_SEED, constants.MAX_SEED)
            return common.saved_seed


    # Describe Event Handlers and Helpers

    def toggle_auto_describe():
      config.enable_auto_describe_image = not config.enable_auto_describe_image
      if config.enable_auto_describe_image == True:
        bool_string = 'Enabled'
      else:
        bool_string = 'Disabled'
      print()
      interpret(f'Auto-Describe {bool_string}')
      return

    auto_describe_checkbox.change(
        lambda x: toggle_auto_describe(), inputs=auto_describe_checkbox)


    def trigger_describe(modes, img, apply_styles):
        describe_prompts = []
        styles = set()

        if flags.describe_type_photo in modes:
            from extras.interrogate import default_interrogator as default_interrogator_photo
            describe_prompts.append(default_interrogator_photo(img))
            styles.update(["Fooocus V2", "Fooocus Enhance", "Fooocus Sharp"])

        if flags.describe_type_anime in modes:
            from extras.wd14tagger import default_interrogator as default_interrogator_anime
            describe_prompts.append(default_interrogator_anime(img))
            styles.update(["Fooocus V2", "Fooocus Masterpiece"])

        if len(styles) == 0 or not apply_styles:
            styles = gr.update()
        else:
            styles = list(styles)

        if len(describe_prompts) == 0:
            describe_prompt = gr.update()
        else:
            describe_prompt = ', '.join(describe_prompts)

        return describe_prompt, styles

    describe_btn.click(
        fn=trigger_describe,
        inputs=[describe_methods,
            describe_input_image,
            describe_apply_styles],
        outputs=[prompt, style_selections],
        show_progress=True, queue=True
    ).then(
        fn=style_sorter.sort_styles,
        inputs=style_selections,
        outputs=style_selections,
        queue=False, show_progress=False
    ).then(
        lambda: None, _js='()=>{refresh_style_localization();}')

    def trigger_show_image_properties(image):
        image_size = modules.util.get_image_size_info(image,
            config.config_aspect_ratios[0])
        return gr.update(value=image_size, visible=True)

    def trigger_auto_describe(mode, img, prompt, apply_styles):
        # keep prompt if not empty
        show_progress=False
        if prompt == '' and config.enable_auto_describe_image:
            show_progress=True
            return trigger_describe(mode, img, apply_styles)
        return gr.update(), gr.update()

    describe_input_image.upload(
        fn=trigger_show_image_properties,
        inputs=describe_input_image,
        outputs=describe_image_size,
        show_progress=False, queue=False
    ).then(
        fn=trigger_auto_describe,
        inputs=[describe_methods,
            describe_input_image,
            prompt,
            describe_apply_styles],
        outputs=[prompt,
                 style_selections],
        queue=True
    ).then(
        fn=style_sorter.sort_styles,
        inputs=style_selections,
        outputs=style_selections,
        queue=False, show_progress=False
    ).then(
        lambda: None,
        _js='()=>{refresh_style_localization();}')


    # Input Image & Features Event Handlers and Helpers

    layout_image_tab = [performance_selection,
        style_selections, freeu_enabled,
        refiner_model, refiner_slider] + lora_ctrls

    def features_trigger(features_chk, input_image_chk):
        if features_chk:
            if common.features_tab_name == '':
                common.features_tab_name = 'edit'
            common.features_checkbox = features_chk
            config.default_input_image_checkbox = False
            if input_image_chk:
                input_image_chk = False
        return (gr.update(value=features_chk),
                gr.update(visible=features_chk),
                gr.update(value=input_image_chk))

    features_checkbox.change(
        fn=features_trigger,
        inputs=[features_checkbox, input_image_checkbox],
        outputs=[features_checkbox, features_panel,
            input_image_checkbox],
        queue=False, show_progress=False)

    def input_image_trigger(input_image_chk, features_chk):
        config.default_input_image_checkbox = input_image_chk
        if config.default_input_image_checkbox and features_chk:
            features_chk = False
            common.features_checkbox = False
        return (gr.update(value=config.default_input_image_checkbox),
                gr.update(value=features_chk))

    input_image_checkbox.change(
        lambda x: [gr.update(visible=x),
        gr.update(choices=flags.Performance.list()),
        gr.update()] + [gr.update(interactive=True)]*18,
        inputs=input_image_checkbox,
        outputs=[image_input_panel] + layout_image_tab,
            queue=False, show_progress=False, _js=switch_js
    ).then(
        fn=input_image_trigger,
        inputs=[input_image_checkbox, features_checkbox],
        outputs=[input_image_checkbox, features_checkbox],
        queue=False, show_progress=False)

    def toggle_image_tab(styles):
        result = [gr.update(choices=flags.Performance.list()), gr.update()]
        result += [gr.update(interactive=True)] * 18
        return result


    # Upscale or Variation Prompt Event Handlers and Helpers

    uov_tab.select(
        fn=lambda: setattr(
            common, 'current_tab_name', 'uov'),
        outputs=None,
        queue=False, show_progress=False,
        _js=down_js,
    ).then(
        toggle_image_tab,
        inputs=[style_selections],
        outputs=layout_image_tab,
        show_progress=False, queue=False)

    def uov_method_change(arg_uov):
        config.default_uov_method = arg_uov
        return gr.update(value=config.default_uov_method)

    uov_method.change(
        fn=uov_method_change,
        inputs = uov_method,
        outputs = uov_method,
        queue=False, show_progress=False)

    def overwrite_upscale_strength_release(arg_strength):
        config.default_overwrite_upscale = arg_strength
        return gr.update(value=config.default_overwrite_upscale)

    overwrite_upscale_strength.release(
        fn=overwrite_upscale_strength_release,
        inputs=overwrite_upscale_strength,
        outputs=overwrite_upscale_strength,
        queue=False, show_progress=False
    )

    def overwrite_vary_strength_release(arg_vary):
        common.vary_strength = arg_vary
        return gr.update(value=common.vary_strength)

    overwrite_vary_strength.release(
        fn=overwrite_vary_strength_release,
        inputs=overwrite_vary_strength,
        outputs=overwrite_vary_strength,
        queue=False, show_progress=False
    )

    uov_input_image.upload(
        fn=trigger_auto_describe,
        inputs=[describe_methods,
            uov_input_image, prompt,
            describe_apply_styles],
        outputs=[prompt, style_selections],
        queue=True
    ).then(
        fn=style_sorter.sort_styles,
        inputs=style_selections,
        outputs=style_selections,
        queue=False, show_progress=False
    ).then(
        fn=lambda x: setattr(common,
            'uov_image_buffer', x),
        inputs=uov_input_image,
        outputs=None
    ).then(
        lambda: None,
        _js='()=>{refresh_style_localization();}')

    def mixing_uov_checkbox_change(arg_mix_uov):
        common.mixing_ip_uov = arg_mix_uov
        return gr.update(value=common.mixing_ip_uov)

    mixing_uov_checkbox.change(
        fn=mixing_uov_checkbox_change,
        inputs=mixing_uov_checkbox,
        outputs=mixing_uov_checkbox,
        queue=False
    )

    uov_input_image.clear(
        fn=lambda: setattr(common,
            'uov_image_buffer', None),
        inputs=None,
        outputs=None)


    # Image Prompt Event Handlers and Helpers

    ip_tab.select(
        fn=lambda: setattr(
            common, 'current_tab_name', 'ip'),
        outputs=None,
        queue=False, show_progress=False,
        _js=down_js
    ).then(
        fn=toggle_image_tab,
        inputs=[style_selections],
        outputs=layout_image_tab,
        show_progress=False, queue=False)

    clear_image_prompts_button.click(
        fn=UIS.manage_ip_image_clear,
        inputs=None,
        outputs=ip_images + ip_types + ip_stops + ip_weights + [
            controlnet_softness,
            canny_low_threshold,
            canny_high_threshold
        ],
        queue=False,
        show_progress=False
    )

    def ip_advance_checked(x):
        # 1. Fetch defaults for slot arrays
        default_stop, default_weight = flags.default_parameters[flags.default_ip]

        # 2. Fetch defaults for the standalone controls
        common.default_softness = 0.25
        common.default_canny_low = 64
        common.default_canny_high = 128

        # Build the return list cleanly step-by-step
        ui_updates = []

        # Add the list-based slot components (.extend flattens the lists)
        ui_updates.extend([gr.update(visible=x)] * len(ip_ad_cols))
        ui_updates.extend([gr.update(value=flags.default_ip, interactive=True)] * len(ip_types))
        ui_updates.extend([gr.update(value=default_stop, interactive=True)] * len(ip_stops))
        ui_updates.extend([gr.update(value=default_weight, interactive=True)] * len(ip_weights))

        # Append adds single items
        ui_updates.append(gr.update(visible=x, value=common.default_softness, interactive=True))
        ui_updates.append(gr.update(visible=x, value=common.default_canny_low, interactive=True))
        ui_updates.append(gr.update(visible=x, value=common.default_canny_high, interactive=True))

        return ui_updates

    ip_advanced.change(
        fn=ip_advance_checked,
        inputs=ip_advanced,
        # The order here must EXACTLY mirror the order we built inside ui_updates!
        outputs=ip_ad_cols + ip_types + ip_stops + ip_weights + [
            controlnet_softness,
            canny_low_threshold,
            canny_high_threshold
        ],
        queue=False,
        show_progress=False
    ).then(
        fn=lambda: None,
        queue=False,
        show_progress=False,
        _js=down_js
    )

    def controlnet_softness_change(arg_softness):
        common.controlnet_softness = arg_softness
        return gr.update(value=common.controlnet_softness)

    controlnet_softness.change(
        fn=controlnet_softness_change,
        inputs=controlnet_softness,
        outputs=controlnet_softness,
        queue=False,
        show_progress=False
    )

    def canny_low_threshold_change(arg_canny_low):
        common.canny_low_threshold = arg_canny_low
        return gr.update(value=common.canny_low_threshold)

    canny_low_threshold.change(
        fn=canny_low_threshold_change,
        inputs=canny_low_threshold,
        outputs=canny_low_threshold,
        queue=False,
        show_progress=False
    )

    def canny_high_threshold_change(arg_canny_high):
        common.canny_high_threshold = arg_canny_high
        return gr.update(value=common.canny_high_threshold)

    canny_high_threshold.change(
        fn=canny_high_threshold_change,
        inputs=canny_high_threshold,
        outputs=canny_high_threshold,
        queue=False,
        show_progress=False
    )


    # Inpaint Event Handlers and Helpers

    inpaint_tab.select(
        fn=lambda: setattr(
            common, 'current_tab_name', 'inpaint'),
        outputs=None,
        queue=False,
        show_progress=False,
        _js=down_js,
    ).then(
        toggle_image_tab,
        inputs=[style_selections],
        outputs=layout_image_tab,
        show_progress=False, queue=False)


    def inpaint_image_upload(arg_inpaint_image):
        global allow_inpaint_max

        # extract the NumPy image array
        if isinstance(arg_inpaint_image, dict):
            img_arr = arg_inpaint_image.get('image')
        else:
            img_arr = arg_inpaint_image
        if img_arr is None:
            return gr.update(visible=False)

        height, width = img_arr.shape[:2]
        image_area = height*width
        allow_inpaint_max = image_area <= constants.max_resolution
        if not allow_inpaint_max:
            common.outpaint_extension = False
        return gr.update(visible=allow_inpaint_max)

    inpaint_input_image.upload(
        fn=inpaint_image_upload,
        inputs=inpaint_input_image,
        outputs=outpaint_extension,
        show_progress=False, queue=False)

    inpaint_input_image.clear(
        fn=lambda: setattr(common,
            'inpaint_image_buffer', None))

    inpaint_mask_image.clear(
        fn=lambda: setattr(common,
            'inpaint_mask_buffer', None))

    inpaint_mode.change(
        UIU.inpaint_mode_change,
        inputs=[inpaint_mode,
                inpaint_engine_state],
        outputs=[inpaint_additional_prompt,
                 outpaint_selections,
                 example_inpaint_prompts,
                 inpaint_disable_initial_latent,
                 inpaint_engine,
                 inpaint_strength,
                 inpaint_respective_field],
        show_progress=False, queue=False)


    def outpaint_selections_change(arg_outpaint):
        global allow_inpaint_max
        common.outpaint_selections = arg_outpaint
        len_select = len(common.outpaint_selections)
        extension = len_select > 0 and len_select < 3 and allow_inpaint_max
        if not extension:
            common.outpaint_extension = False
        return (gr.update(value=common.outpaint_selections),
                gr.update(value=common.outpaint_extension, visible=extension))

    outpaint_selections.change(
        fn=outpaint_selections_change,
        inputs=outpaint_selections,
        outputs=[outpaint_selections,
                 outpaint_extension],
        show_progress=False, queue=False)

    def outpaint_extension_change(arg_extension):
        common.outpaint_extension = arg_extension
        return gr.update(value=
            common.outpaint_extension)

    outpaint_extension.change(
        fn=outpaint_extension_change,
        inputs=outpaint_extension,
        outputs=outpaint_extension,
        show_progress=False, queue=False)

    def update_left_percent(val):
        common.outpaint_left_percent = val

    def update_right_percent(val):
        common.outpaint_right_percent = val

    def update_top_percent(val):
        common.outpaint_top_percent = val

    def update_bottom_percent(val):
        common.outpaint_bottom_percent = val

    # 2. Unified handler to manage slider visibility, maximums, and values
    def update_extension_sliders(selections, extension_enabled):
        # Initialize all 4 sliders as hidden by default
        updates = {
            'Left': gr.update(visible=False),
            'Right': gr.update(visible=False),
            'Top': gr.update(visible=False),
            'Bottom': gr.update(visible=False)
        }

        # If maximum extension is checked and we have exactly 1 or 2 directions:
        if extension_enabled and len(selections) in [1, 2]:
            # Determine max ceiling and default starting position
            max_val = 100.0 if len(selections) == 1 else 50.0

            # Show the selected sliders and dynamically cap their maximums
            for direction in selections:
                if direction in updates:
                    updates[direction] = gr.update(
                        visible=True,
                        maximum=max_val,
                        value=max_val
                    )
        return (
            updates['Left'],
            updates['Right'],
            updates['Top'],
            updates['Bottom']
        )

    # Bind the state-syncing helpers to the sliders
    left_extension.change(fn=update_left_percent, inputs=left_extension, queue=False)
    right_extension.change(fn=update_right_percent, inputs=right_extension, queue=False)
    top_extension.change(fn=update_top_percent, inputs=top_extension, queue=False)
    bottom_extension.change(fn=update_bottom_percent, inputs=bottom_extension, queue=False)

    # Chain the slider updates to outpaint selections changing
    outpaint_selections.change(
        fn=outpaint_selections_change,
        inputs=outpaint_selections,
        outputs=[outpaint_selections, outpaint_extension],
        show_progress=False, queue=False
    ).then(
        fn=update_extension_sliders,
        inputs=[outpaint_selections, outpaint_extension],
        outputs=[left_extension, right_extension, top_extension, bottom_extension],
        show_progress=False, queue=False
    )

    # Chain the slider updates to the outpaint extension checkbox toggling
    outpaint_extension.change(
        fn=outpaint_extension_change,
        inputs=outpaint_extension,
        outputs=outpaint_extension,
        show_progress=False, queue=False
    ).then(
        fn=update_extension_sliders,
        inputs=[outpaint_selections, outpaint_extension],
        outputs=[left_extension, right_extension, top_extension, bottom_extension],
        show_progress=False, queue=False
    )

    inpaint_additional_prompt.change(
        fn=lambda x: setattr(
            common, 'inpaint_additional_prompt', x),
        inputs=inpaint_additional_prompt,
        outputs=None)

    example_inpaint_prompts.click(
        lambda x: x[0],
        inputs=example_inpaint_prompts,
        outputs=inpaint_additional_prompt,
        show_progress=False, queue=False)


    def generate_mask(image, mask_model,
        cloth_category, dino_prompt_text,
        sam_model, box_threshold,
        text_threshold, sam_max_detections,
        dino_erode_or_dilate, dino_debug, params_extra):

        extras = {}
        sam_options = None
        if mask_model == 'u2net_cloth_seg':
            extras['cloth_category'] = cloth_category
        elif mask_model == 'sam':
            sam_options = SAMOptions(
                dino_prompt=dino_prompt_text,
                dino_box_threshold=box_threshold,
                dino_text_threshold=text_threshold,
                dino_erode_or_dilate=dino_erode_or_dilate,
                dino_debug=dino_debug,
                max_detections=sam_max_detections,
                model_type=sam_model
            )

        mask, _, _, _ = generate_mask_from_image(
            image, mask_model, extras, sam_options)

        return mask

    generate_mask_button.click(
        fn=generate_mask,
        inputs=[inpaint_input_image, inpaint_mask_model,
            inpaint_mask_cloth_category,
            inpaint_mask_dino_prompt_text,
            inpaint_mask_sam_model,
            inpaint_mask_box_threshold,
            inpaint_mask_text_threshold,
            inpaint_mask_sam_max_detections,
            dino_erode_or_dilate,
            debugging_dino, params_backend],
        outputs=inpaint_mask_image,
        show_progress=True, queue=True)

    inpaint_mask_model.change(lambda x: [gr.update(visible=x == 'u2net_cloth_seg')] +
        [gr.update(visible=x == 'sam')] * 2 + [gr.Dataset.update(visible=x == 'sam',
        samples=config.example_enhance_detection_prompts)],
            inputs=inpaint_mask_model,
            outputs=[inpaint_mask_cloth_category,
            inpaint_mask_dino_prompt_text,
            inpaint_mask_advanced_options,
            example_inpaint_mask_dino_prompt_text],
            queue=False, show_progress=False)


    def dino_erode_or_dilate_change(arg_dino_erode):
        dino_erode_or_dilate = arg_dino_erode,
        return gr.update(value=dino_erode_or_dilate)

    dino_erode_or_dilate.release(
        fn=dino_erode_or_dilate_change,
        inputs=dino_erode_or_dilate,
        outputs=dino_erode_or_dilate,
        queue=False, show_progress=False)


    def mixing_inpaint_checkbox_change(arg_mix_inpaint):
        common.mixing_ip_inpaint = arg_mix_inpaint
        return gr.update(value=common.mixing_ip_inpaint)

    mixing_inpaint_checkbox.change(
        fn=mixing_inpaint_checkbox_change,
        inputs=mixing_inpaint_checkbox,
        outputs=mixing_inpaint_checkbox,
        queue=False
    )

    def invert_mask_checkbox_change(arg_invert_mask):
        config.default_invert_mask_checkbox = arg_invert_mask
        return gr.update(value=config.default_invert_mask_checkbox)

    invert_mask_checkbox.change(
        fn=invert_mask_checkbox_change,
        inputs=invert_mask_checkbox,
        outputs=invert_mask_checkbox,
        queue=False
    )

    def toggle_advanced_masking(is_checked):
        # 1. Prepare the visibility updates
        config.default_inpaint_advanced_masking_checkbox = is_checked
        updates = [gr.update(visible=is_checked)] * 2

        # 2. Prepare the value update for the mask canvas
        # If the user unchecks the box, we send None to wipe the image data
        mask_value = gr.update() # Do nothing if checking the box
        if not is_checked:
            mask_value = None
            common.inpaint_mask_buffer = None

        # Return everything in the order of the 'outputs' list
        return [is_checked] + updates + [mask_value]

    inpaint_advanced_masking_checkbox.change(
        fn=toggle_advanced_masking,
        inputs=inpaint_advanced_masking_checkbox,
        outputs=[
            inpaint_advanced_masking_checkbox,
            inpaint_mask_image,            # visibility control
            inpaint_mask_generation_col,   # visibility control
            inpaint_mask_image             # mask value control
        ],
        queue=False,
        show_progress=False
    )

    inpaint_mask_color.change(
        lambda x: gr.update(brush_color=x),
        inputs=inpaint_mask_color,
        outputs=inpaint_input_image,
        queue=False, show_progress=False)

    def inpaint_engine_change(arg_engine):
        common.inpaint_engine = arg_engine
        return gr.update(value=common.inpaint_engine)

    inpaint_engine.change(
        fn=inpaint_engine_change,
        inputs=inpaint_engine,
        outputs=[inpaint_engine],
        show_progress=False, queue=False)

    def inpaint_disable_initial_latent_change(arg_latent):
        common.inpaint_disable_initial_latent = arg_latent
        return gr.update(value=common.inpaint_disable_initial_latent)

    inpaint_disable_initial_latent.change(
        fn=inpaint_disable_initial_latent_change,
        inputs=inpaint_disable_initial_latent,
        outputs=inpaint_disable_initial_latent,
        show_progress=False, queue=False)

    def inpaint_strength_change(arg_strength):
        common.inpaint_strength = arg_strength
        return gr.update(value=common.inpaint_strength)

    inpaint_strength.change(
        fn=inpaint_strength_change,
        inputs=inpaint_strength,
        outputs=inpaint_strength,
        queue=False
    )

    def inpaint_respective_field_change(arg_respective):
        common.inpaint_respective_field = arg_respective
        return gr.update(value=common.inpaint_respective_field)

    inpaint_respective_field.change(
        fn=inpaint_respective_field_change,
        inputs=inpaint_respective_field,
        outputs=inpaint_respective_field,
        queue=False
    )

    def inpaint_erode_or_dilate_change(arg_erode_dilate):
        common.inpaint_erode_or_dilate = arg_erode_dilate
        return gr.update(value=common.inpaint_erode_or_dilate)

    inpaint_erode_or_dilate.change(
        fn=inpaint_erode_or_dilate_change,
        inputs=inpaint_erode_or_dilate,
        outputs=inpaint_erode_or_dilate,
        show_progress=False, queue=False
    )


    # Enhance Event Handlers and Helpers

    enhance_tab.select(
        fn=lambda: setattr(
            common, 'current_tab_name', 'enhance'),
        outputs=None,
        queue=False, show_progress=False,
        _js=down_js
    ).then(
        toggle_image_tab,
        inputs=[style_selections],
        outputs=layout_image_tab,
        show_progress=False, queue=False)

    def enhance_checkbox_change(arg_enhance_chk):
        config.default_enhance_checkbox = arg_enhance_chk
        return gr.update(
            config.default_enhance_checkbox)

    enhance_checkbox.change(
        fn = enhance_checkbox_change,
        inputs = enhance_checkbox,
        outputs = enhance_checkbox,
        show_progress=False, queue=False)

    enhance_input_image.upload(
        lambda: gr.update(value=True),
        outputs=enhance_checkbox,
        queue=False, show_progress=False
    ).then(
        trigger_auto_describe,
        inputs=[describe_methods, enhance_input_image,
            prompt, describe_apply_styles],
        outputs=[prompt, style_selections], queue=True
    ).then(
        fn=style_sorter.sort_styles,
        inputs=style_selections,
        outputs=style_selections,
        queue=False, show_progress=False
    ).then(
        fn=lambda x: setattr(common,
            'enhance_image_buffer', x),
        inputs=enhance_input_image,
        outputs=None
    ).then(
        lambda: None,
        _js='()=>{refresh_style_localization();}')

    def enhance_uov_method_change(arg_enhance_uov):
        config.default_enhance_uov_method = arg_enhance_uov
        return gr.update(value=
            config.default_enhance_uov_method)

    enhance_uov_method.change(
        fn = enhance_uov_method_change,
        inputs = enhance_uov_method,
        outputs = enhance_uov_method,
        show_progress=False, queue=False)

    def update_enhance_uov_processing_order(order):
        config.default_enhance_uov_processing_order = order
        # Make the prompt type selection visible
        # only when order is 'After'
        is_visible = (order == flags.enhancement_uov_after)
        return (gr.update(visible=is_visible),
                gr.update(value=
                config.default_enhance_uov_processing_order))

    enhance_uov_processing_order.change(
        fn=update_enhance_uov_processing_order,
        inputs=enhance_uov_processing_order,
        outputs=[enhance_uov_prompt_type,
            enhance_uov_processing_order],
        queue=False, show_progress=False)

    def update_enhance_uov_prompt_type(prompt_type):
        config.default_enhance_uov_prompt_type = prompt_type
        return gr.update(value=
            config.default_enhance_uov_prompt_type)

    enhance_uov_prompt_type.change(
        fn=update_enhance_uov_prompt_type,
        inputs=enhance_uov_prompt_type,
        outputs=enhance_uov_prompt_type,
        queue=False, show_progress=False
    )

    enhance_inpaint_mode.change(
        UIU.enhance_inpaint_mode_change,
        inputs=[enhance_inpaint_mode,
            inpaint_engine_state],
        outputs=[enhance_inpaint_disable_initial_latent,
            enhance_inpaint_engine,
            enhance_inpaint_strength,
            enhance_inpaint_respective_field],
        show_progress=False, queue=False)

    enhance_mask_model.change(
        lambda x: [gr.update(visible=x == 'u2net_cloth_seg')] +
                [gr.update(visible=x == 'sam')] * 2 +
                [gr.Dataset.update(visible=x == 'sam',
                    samples=config.example_enhance_detection_prompts)],
        inputs=enhance_mask_model,
        outputs=[enhance_mask_cloth_category,
            enhance_mask_dino_prompt_text,
            sam_options,
            example_enhance_mask_dino_prompt_text],
        queue=False, show_progress=False)

    example_inpaint_mask_dino_prompt_text.click(
        lambda x: x[0],
        inputs=example_inpaint_mask_dino_prompt_text,
        outputs=inpaint_mask_dino_prompt_text,
        show_progress=False, queue=False)


    # FreeU Handlers & Helpers

    def freeu_preset_change(arg_freeu_preset):
        # Get settings, fallback to default if key isn't found
        settings = flags.FREEU_DATA.get(arg_freeu_preset, flags.FREEU_DATA[flags.DEFAULT_FREEU_KEY])

        # Sync with common
        common.freeu_settings[1:5] = settings
        common.freeu_preset_name = arg_freeu_preset
        # Reset modification status since
        # we just matched the preset
        common.freeu_modified = False

        return (
            gr.update(value=settings[0]),
            gr.update(value=settings[1]),
            gr.update(value=settings[2]),
            gr.update(value=settings[3]),
            gr.update(interactive=False)
        )

    # When the dropdown changes, update sliders
    # and make the reset button non-interactive
    freeu_preset.change(
        fn=freeu_preset_change,
        inputs=freeu_preset,
        outputs=[freeu_b1, freeu_b2,
                 freeu_s1, freeu_s2,
                 freeu_restore_btn]
    )

    def freeu_enabled_change(enabled):
        common.freeu_settings[0] = enabled
        return

    freeu_enabled.change(
        fn=freeu_enabled_change,
        inputs=freeu_enabled
    )

    def freeu_restore_action(current_preset):
        # Rerun the preset change logic with the
        # currently selected dropdown value
        return freeu_preset_change(current_preset)

    # restore the FreeU default preset values
    freeu_restore_btn.click(
        fn=freeu_restore_action,
        inputs=freeu_preset,
        outputs=[freeu_b1, freeu_b2,
                 freeu_s1, freeu_s2,
                 freeu_restore_btn]
    )

    def update_and_check_freeu(preset, b1, b2, s1, s2):
        # 1. Sync current slider values with common settings
        current_values = [b1, b2, s1, s2]
        common.freeu_settings[1:5] = current_values

        # 2. Retrieve target preset values
        preset_values = flags.FREEU_DATA.get(preset, flags.FREEU_DATA[flags.DEFAULT_FREEU_KEY])

        # 3. Compare values
        # (using a float tolerance check of 0.001)
        modified = any(abs(cur - target) > 0.001 for cur, target in zip(current_values, preset_values))

        # 4. Set the common flag and
        # return the update state of the button
        common.freeu_modified = modified
        return gr.update(interactive=modified)

    # Bind all sliders to the unified function
    for slider in [freeu_b1, freeu_b2, freeu_s1, freeu_s2]:
        slider.change(
            fn=update_and_check_freeu,
            inputs=[freeu_preset,
                    freeu_b1, freeu_b2,
                    freeu_s1, freeu_s2],
            outputs=freeu_restore_btn,
            show_progress="none"
        )


    # Image Editor Event Handlers and Helpers

    def scrub_int(val, default=0):
        """
        Extracts an integer from a Gradio update dict or raw value.
        """
        if isinstance(val, dict):
            # Gradio 3.x leaks {'value': X, '__type__': 'generic_update'}
            return int(val.get('value', default))
        try:
            return int(val)
        except (TypeError, ValueError):
            return default


    all_inputs_for_update = [
        input_image_display,
        brighten_slider,
        contrast_slider,
        saturation_slider,
        hue_slider,
        sharpness_slider,
        autocontrast_chk,
        edge_chk,
        equalize_chk,
        grayscale_chk,
        rotate_slider,
        left_slider,
        right_slider,
        upper_slider,
        lower_slider,
        width_slider,
        height_slider,
        mirror_chk,
        flip_vertical_chk,
        box_blur_slider,
        gaussian_blur_slider,
        edge_more_chk,
        posterize_slider,
        solarize_slider,
        background_chk,
        erase_chk,
        transparency_slider,
        output_transparency_state
    ]


    def on_ui_update_trigger(
        # passed in from the input gr.Image value
        input_image_data: _Image.Image,
        brightness_int: int,
        contrast_int: int,
        saturation_int: int,
        hue_int: int,
        sharpness_int: int,
        autocontrast_bool: bool,
        edge_bool: bool,
        equalize_bool: bool,
        grayscale_bool: bool,
        rotate_int: int,
        left_int: int,
        right_int: int,
        upper_int: int,
        lower_int: int,
        width_int: int,
        height_int: int,
        mirror_bool: bool,
        flip_vertical_bool: bool,
        box_blur_int: int,
        gaussian_blur_int: int,
        edge_more_bool: bool,
        posterize_int: int,
        solarize_int: int,
        background_chk: bool,
        erase_chk: bool,
        trans_percent: int,
        output_transparency_data,
        update_all=False):
        """
        Function triggered by any
        UI change that calls the
        edit module's core logic.
        """
        working_image_data = input_image_data

        is_transparency_active = any(
            [background_chk, erase_chk, trans_percent > 0])
        if is_transparency_active and output_transparency_data is not None:
            # We use the transparency data as our source
            # instead of the standard input:
            working_image_data = output_transparency_data

        # Initialize a list of 6
        # "Do Nothing" updates
        # results[0]: display,
        # [1]: state, [2]: width,
        # [3]: height, [4]: right,
        # [5]: lower
        results = [gr.update() for _ in range(6)]

        # Determine what to do with
        # the five transparency controls
        if is_transparency_active:
            # The "Transparency Section" behaviour:
            # leave the transparency values alone
            trans_updates = [gr.update() for _ in range(3)]
        else:
            # The standard behaviour:
            # reset transparency to defaults
            trans_defaults = edit.get_transparency_defaults()
            trans_updates = [gr.update(value=val) for val in trans_defaults]

        if input_image_data is None:
            # We need to return exactly 9 items:
            return (
                gr.update(value=None), # display
                None,                  # state
                gr.update(),           # width
                gr.update(),           # height
                gr.update(),           # right
                gr.update(),           # lower
                gr.update(),           # trans 1
                gr.update(),           # trans 2
                gr.update()            # trans 3
            )

        # --- THE GATEKEEPER BLOCK ---
        # Scrub all transformation values
        # before they reach apply_enhancements
        rotate_int = scrub_int(rotate_int, 0)
        left_int   = scrub_int(left_int, 0)
        right_int  = scrub_int(right_int, 0)
        upper_int  = scrub_int(upper_int, 0)
        lower_int  = scrub_int(lower_int, 0)
        width_int  = scrub_int(width_int, 0)
        height_int = scrub_int(height_int, 0)
        # -----------------------------

        final_image, synced_width, synced_height = edit.apply_enhancements(
            working_image_data,
            brightness_int,
            contrast_int,
            saturation_int,
            hue_int,
            sharpness_int,
            autocontrast_bool,
            edge_bool,
            equalize_bool,
            grayscale_bool,
            rotate_int,
            left_int,
            right_int,
            upper_int,
            lower_int,
            width_int,
            height_int,
            mirror_bool,
            flip_vertical_bool,
            box_blur_int,
            gaussian_blur_int,
            edge_more_bool,
            posterize_int,
            solarize_int
        )
        results[0] = gr.update(value=final_image)
        results[1] = final_image

        if update_all:
            # --- Handle Slider Jumps ---
            # only send a VALUE update if the
            # synced value is different from
            # what was provided. This prevents
            # overwriting the user's current drag operation.
            width_update = gr.update(value=synced_width) if synced_width != width_int else gr.update()
            height_update = gr.update(value=synced_height) if synced_height != height_int else gr.update()

            # --- Handle Crop Maxima ---
            original_w, original_h = input_image_data.size
            current_w, current_h = final_image.size
            # ensure that new maxima do not auto-crop:
            if current_w < original_w:
                current_w = original_w
            if current_w < right_int:
                right_int = current_w
            if current_h < original_h:
                current_h = original_h
            if current_h < lower_int:
                lower_int = current_h
            # update the maximum values for the crop sliders
            right_max_update = gr.update(maximum=current_w, value=right_int)
            lower_max_update = gr.update(maximum=current_h, value=lower_int)

            results[2] = width_update
            results[3] = height_update
            results[4] = right_max_update
            results[5] = lower_max_update

        # Return everything together (Total 9 items)
        return tuple(results) + tuple(trans_updates)


    def on_ui_update_trigger_update_all(*args):
        # Force update_all=True to ensure sliders
        # crop maxima and dimensions remain synced.
        return on_ui_update_trigger(*args, update_all=True)


    transparency_controls = [
        background_chk,
        erase_chk,
        transparency_slider
    ]


    all_reset_outputs = [
        brighten_slider,
        contrast_slider,
        hue_slider,
        saturation_slider,
        sharpness_slider,
        autocontrast_chk,
        edge_chk,
        equalize_chk,
        grayscale_chk,
        percent_resize_slider,
        rotate_slider,
        left_slider,
        right_slider,
        upper_slider,
        lower_slider,
        width_slider,
        height_slider,
        mirror_chk,
        flip_vertical_chk,
        flip_AR_chk,
        box_blur_slider,
        gaussian_blur_slider,
        edge_more_chk,
        posterize_slider,
        solarize_slider
    ]

    update_outputs_list = [
        output_image_display,
        output_image_state,
        # this component will receive the
        # 'gr.update(value=final_width)':
        width_slider,
        # this component will receive the
        # 'gr.update(value=final_height)':
        height_slider,
        right_slider,
        lower_slider
    ]


    # 1. Image Uploaded: Update displays, then reset all settings to default values.
    input_image_display.upload(
        edit.on_upload_trigger,
        inputs=[input_image_display],
        outputs=[original_image_state, output_image_display,
            output_image_state, output_transparency_state]
    ).then(
        fn=edit.reset_to_defaults,
        inputs=[input_image_display],
        outputs=[*all_reset_outputs,
                 *transparency_controls]
    )


    # These checkboxes use the .change() handler
    instant_components = [
        autocontrast_chk,
        edge_chk,
        equalize_chk,
        grayscale_chk,
        mirror_chk,
        flip_vertical_chk,
    ]

    # These sliders use the .release() handler
    # rotate & crop controls make
    # direct calls to on_ui_update_trigger
    # resize is independently controlled
    # transparency is handled separately
    delayed_components = [
        brighten_slider,
        contrast_slider,
        hue_slider,
        saturation_slider,
        sharpness_slider,
        width_slider,
        height_slider,
        box_blur_slider,
        gaussian_blur_slider,
        posterize_slider,
        solarize_slider
    ]

    def create_ui_handler(comp, event_type="change"):
        handler = comp.release if event_type == "release" else comp.change
        handler(
            fn=edit.get_transparency_defaults,
            outputs=transparency_controls
        ).then(
            # Use the explicit update wrapper:
            fn=on_ui_update_trigger_update_all,
            inputs=all_inputs_for_update,
            outputs=[*update_outputs_list, *transparency_controls]
        )

    # 2. Any slider/checkbox changes:
    # Recalculate the image using the external edit routine.
    # This iterates over most interactive components
    for comp in instant_components:
        create_ui_handler(comp, event_type="change")
    for comp in delayed_components:
        create_ui_handler(comp, event_type="release")


    # --- Transformations Section ---

    percent_resize_slider.release(
        fn=edit.percent_resize_logic,
        inputs=[input_image_display,
            percent_resize_slider,
            right_slider, lower_slider],
        outputs=[width_slider,
                height_slider,
                right_slider,
                lower_slider,
                *transparency_controls]
    )

    def change_aspect_ratio(width, height, right, lower):
        width  = scrub_int(width)
        height = scrub_int(height)
        right  = scrub_int(right)
        lower  = scrub_int(lower)

        width, height = height, width
        right, lower = lower, right
        return (gr.update(value=width),
                gr.update(value=height),
                gr.update(value=right),
                gr.update(value=lower)
    )
    rotate_slider.release(
        fn=change_aspect_ratio,
        inputs=[width_slider, height_slider,
            right_slider, lower_slider],
        outputs=[width_slider, height_slider,
            right_slider, lower_slider],
        show_progress=False, queue=False
    ).then(
        fn=on_ui_update_trigger,
        # reruns the entire stack using
        # the current slider values:
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
        show_progress=False, queue=False
    )

    def update_width(left, right):
        left_val = scrub_int(left, 0)
        right_val = scrub_int(right, 0)
        width = right_val - left_val
        return gr.update(value=width)

    left_slider.release(
        fn=update_width,
        inputs=[left_slider, right_slider],
        outputs=crop_width,
        show_progress=False, queue=False
    ).then(
        fn=on_ui_update_trigger,
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
        show_progress=False, queue=False
    )

    right_slider.release(
        fn=update_width,
        inputs=[left_slider, right_slider],
        outputs=crop_width,
        show_progress=False, queue=False
    ).then(
        fn=on_ui_update_trigger,
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
        show_progress=False, queue=False
    )

    def update_height(upper, lower):
        upper_val = scrub_int(upper, 0)
        lower_val = scrub_int(lower, 0)
        height = lower_val - upper_val
        return gr.update(value=height
    )

    upper_slider.release(
        fn=update_height,
        inputs=[upper_slider, lower_slider],
        outputs=crop_height,
        show_progress=False, queue=False
    ).then(
        fn=on_ui_update_trigger,
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
        show_progress=False, queue=False
    )

    lower_slider.release(
        fn=update_height,
        inputs=[upper_slider, lower_slider],
        outputs=crop_height,
        show_progress=False, queue=False
    ).then(
        on_ui_update_trigger,
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
        show_progress=False, queue=False
    )


    def flip_aspect_ratio(
        width, height, right, lower):
        width  = scrub_int(width)
        height = scrub_int(height)
        right  = scrub_int(right)
        lower  = scrub_int(lower)

        width, height = height, width
        right, lower = lower, right
        return (gr.update(value=width),
                gr.update(value=height),
                gr.update(value=right),
                gr.update(value=lower)
    )

    flip_AR_chk.change(
        fn=flip_aspect_ratio,
        inputs=[width_slider, height_slider,
            right_slider, lower_slider],
        outputs=[width_slider,
                height_slider,
                right_slider,
                lower_slider],
        show_progress=False, queue=False
    ).then(
        fn=on_ui_update_trigger,
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
        show_progress=False, queue=False
    )


    all_transform_outputs = [
        percent_resize_slider,
        rotate_slider,
        left_slider,
        right_slider,
        upper_slider,
        lower_slider,
        width_slider,
        height_slider,
        mirror_chk,
        flip_vertical_chk,
        flip_AR_chk
    ]

    reset_transforms_btn.click(
        fn=edit.reset_transforms,
        inputs=input_image_display,
        outputs=[*all_transform_outputs,
                 *transparency_controls]
    ).then(
        fn=on_ui_update_trigger,
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
        show_progress=False, queue=False
    )

    # --- Transparency & Composition Section ---

    background_chk.input(
        edit.remove_background_logic,
            inputs = [input_image_display,
                      background_chk,
                      bg_model_dropdown,
                      alpha_mat_chk],
            outputs = [output_transparency_state,
                       background_chk]
    ).then(
        # run the usual edits
        # but do not reset transparency
        fn=on_ui_update_trigger_update_all,
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
        show_progress=True, queue=False
    )

    def bg_model_dropdown_change(arg_bg_model):
        return gr.update(value=arg_bg_model)

    bg_model_dropdown.change(
        fn=bg_model_dropdown_change,
        inputs=bg_model_dropdown,
        outputs=bg_model_dropdown,
        show_progress=False, queue=False)

    def alpha_mat_chk_change(arg_alpha_mat):
        return gr.update(value=arg_alpha_mat)

    alpha_mat_chk.change(
        fn=alpha_mat_chk_change,
        inputs=alpha_mat_chk,
        outputs=alpha_mat_chk,
        show_progress=False, queue=False)

    erase_chk.input(
        edit.erase_logic,
            inputs = [input_image_display, erase_chk],
            outputs = [output_transparency_state, erase_chk]
    ).then(
        # run the usual edits
        # but do not reset transparency
        fn=on_ui_update_trigger_update_all,
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
        show_progress=False, queue=False
    )

    remove_transparency_btn.click(
        fn=edit.remove_transparency_logic,
        inputs = [input_image_display,
            composite_image_display],
        outputs = [input_image_display,
                   output_image_display,
                   output_image_state,
                   output_transparency_state,
                   background_chk, erase_chk,
                   transparency_slider,
                   composite_image_display]
    ).then(
        fn=on_ui_update_trigger_update_all,
        # reruns the entire stack using the current slider values:
        inputs=all_inputs_for_update,
        outputs=update_outputs_list,
        show_progress=False, queue=False
    )


    transparency_slider.release(
        fn=edit.transparency_logic,
        inputs = [input_image_display,
                  transparency_slider],
        outputs = [output_transparency_state,
                   transparency_slider]
    ).then(
        fn=edit.display_transparency_percentage,
        inputs = transparency_slider
    ).then(
        fn=on_ui_update_trigger_update_all,
        # reruns the entire stack using the current slider values:
        inputs=all_inputs_for_update,
        outputs=update_outputs_list,
        show_progress=False, queue=False)


    apply_transparency_btn.click(
        edit.copy_to_source,
        inputs=output_transparency_state,
        outputs=input_image_display
    ).then(
        edit.call_upload_trigger,
        inputs=[input_image_display],
        outputs=[output_image_state, output_image_display,
            output_image_state, output_transparency_state]
    ).then(
        fn=on_ui_update_trigger_update_all,
        # reruns the entire stack using the current slider values:
        inputs=all_inputs_for_update,
        outputs=update_outputs_list,
        show_progress=False, queue=False
    )


    # --- Overlay Events ---

    # state variable holds the original base image
    original_base_image_state = gr.State(value=None)

    def on_base_image_upload_trigger(uploaded_image_data, output_image_overlay_data, meta=''):
        """
        Triggered when a new base image is uploaded.
        It calculates centring and updates UI components dynamically.
        """
        if uploaded_image_data is None or output_image_overlay_data is None:
            return None, gr.update(), gr.update(), gr.update(), None

        # load the metadata
        print()
        if meta == 'copy_to_base':
            interpret('[Editor] Copied the output image to the base image')
            common.base_meta = common.input_meta
            if common.input_meta:
                interpret('Using the output image metadata')
            else:
                interpret('Could not find metadata in the output image')
        elif meta == 'reload_overlay' and \
            common.base_meta:
            interpret('Using base image metadata to save in the composite image')
        elif uploaded_image_data.info:
            common.base_meta = uploaded_image_data.info
            interpret('Loaded base image metadata to save in the composite image')
        else:
            common.base_meta = common.input_meta
            interpret('Could not find metadata in the base image')
            if common.input_meta:
                interpret('Will use the overlay metadata instead')

        # Store the original base image in state
        original_base_image_state.value = uploaded_image_data.convert('RGBA')

        # Get centre-based bounds
        # start_x/y will be 0, max_x/y will be the half-width/height allowance
        # now returns the 75% base dimension limits
        start_x, start_y, max_x, max_y = edit.calculate_centred_position_and_bounds(
            original_base_image_state.value,
            output_image_overlay_data
        )

        # generate the initial composite image
        # at the centre position (rotation 0)
        composite_image = edit.update_composite_image(
            start_x, start_y, 0,
            original_base_image_state.value,
            output_image_overlay_data
        )

        # return values for UI updates:
        return (
            # composite_image (gr.Image) value:
            composite_image,
            # horizontal_slider update:
            gr.update(minimum=-max_x, maximum=max_x, value=start_x),
            # vertical_slider update:
            gr.update(minimum=-max_y, maximum=max_y, value=start_y),
            # rotate_overlay_slider update:
            gr.update(value=0),
            # base_image_display, holder value:
            original_base_image_state.value
        )

    # when the user uploads a base image,
    # run the setup logic
    base_image_display.upload(
        fn=on_base_image_upload_trigger,
        inputs=[base_image_display, output_image_state],
        outputs=[composite_image_display, horizontal_slider, vertical_slider, rotate_overlay_slider,
        original_base_image_state]
    )

    # when an overlay slider moves,
    # recalculate the composite image.
    # Pass the current slider values and the
    # original images stored in state/holders
    slider_inputs = [
        horizontal_slider,
        vertical_slider,
        rotate_overlay_slider,
        # the original base image from state:
        original_base_image_state,
        # the original overlay image from state:
        output_image_state,
        # the containment option:
        contain_chk
    ]

    horizontal_slider.release(
        fn=edit.update_composite_image, inputs=slider_inputs, outputs=composite_image_display
    )
    vertical_slider.release(
        fn=edit.update_composite_image, inputs=slider_inputs, outputs=composite_image_display
    )

    def call_base_upload_trigger_for_reload(
        base_image_display,
        output_image_state):
        # this wrapper explicitly calls the trigger with meta='reload_overlay'
        return on_base_image_upload_trigger(
            base_image_display, output_image_state,
            meta='reload_overlay')

    reload_overlay_btn.click(
        fn=call_base_upload_trigger_for_reload,
        inputs=[base_image_display,
            output_image_state],
        outputs=[composite_image_display, horizontal_slider, vertical_slider, rotate_overlay_slider,
        original_base_image_state]
    )
    rotate_overlay_slider.release(
        fn=edit.update_composite_image, inputs=slider_inputs, outputs=composite_image_display
    )
    contain_chk.change(
        fn=edit.update_composite_image,
        inputs=slider_inputs,
        outputs=composite_image_display
    )
    save_composite_btn.click(
        fn=edit.on_save_composite_click,
        inputs=[composite_image_display,
            save_format],
        # directs the saved file path
        # to the download component:
        outputs=[download_file])

    # --- Editor Input/Output Section ---

    reset_image.click(
        fn=edit.reset_to_defaults,
        inputs=(input_image_display),
        outputs=[*all_reset_outputs,
                 *transparency_controls]
    ).then(
        # rerun the main processing function with the new default inputs:
        on_ui_update_trigger,
        inputs=all_inputs_for_update,
        outputs=[*update_outputs_list,
                 *transparency_controls],
    )

    save_format.change(fn=None,
        inputs = save_format,
        outputs = save_format,
        queue=False, show_progress=False)

    save_image.click(
        fn=edit.on_save_output_click,
        inputs=[output_image_state, save_format],
        # Direct the saved file path to
        # the download component:
        outputs=[download_file]
    ).then(
        # Immediately synchronize and index
        # the catalog so the new image shows up
        fn=edit.refresh_catalog_after_save,
        inputs=[state_topbar],
        outputs=[gallery_index, gallery_index_stat, state_topbar],
        queue=False, show_progress=False
    )

    restore_original.click(
        edit.copy_to_source,
        inputs=original_image_state,
        outputs=input_image_display
    ).then(
        edit.call_upload_trigger,
        inputs=[input_image_display],
        outputs=[original_image_state, output_image_display,
            output_image_state, output_transparency_state]
    ).then(
        fn=edit.reset_to_defaults,
        inputs=[input_image_display],
        outputs=[*all_reset_outputs,
            *transparency_controls]
    )

    copy_to_source.click(
        edit.copy_to_source,
        inputs=output_image_display,
        outputs=input_image_display
    ).then(
        edit.call_upload_trigger,
        inputs=[input_image_display],
        outputs=[output_image_state, output_image_display,
            output_image_state, output_transparency_state]
    ).then(
        fn=edit.reset_to_defaults,
        inputs=[input_image_display],
        outputs=[*all_reset_outputs,
            *transparency_controls]
    )

    def call_base_upload_trigger_with_meta(
        uploaded_image_data, output_image_overlay_data,
        meta='copy_to_base'):
        # This wrapper explicitly calls the trigger with meta='copy_to_base'
        return on_base_image_upload_trigger(
            uploaded_image_data, output_image_overlay_data,)

    copy_to_base.click(
        edit.copy_to_base,
        inputs=output_image_display,
        outputs=base_image_display
    ).then(
        fn=call_base_upload_trigger_with_meta,
        inputs=[base_image_display,
            output_image_state],
        outputs=[composite_image_display,
        horizontal_slider, vertical_slider,
        rotate_overlay_slider,
        original_base_image_state])

    edit_save_metadata_chk.change(
        fn=edit.save_metadata_logic,
        inputs=edit_save_metadata_chk,
        outputs=edit_save_metadata_chk)


    # IC-Light Event Handlers

    edit_tab.select(
        fn=lambda: setattr(
            common, 'features_tab_name', 'edit'),
        outputs=None,
        queue=False, show_progress=False,
        _js=down_js)

    layer_tab.select(
        fn=lambda: setattr(
            common, 'features_tab_name', 'layer'),
        outputs=None,
        queue=False, show_progress=False,
        _js=down_js
    ).then(
        toggle_image_tab,
        inputs=[style_selections],
        outputs=layout_image_tab,
        queue=False, show_progress=False)

    def iclight_source_radio_change(arg_source):
        common.iclight_source_radio = arg_source
        return gr.update(value=common.iclight_source_radio)

    iclight_source_radio.change(
        fn=iclight_source_radio_change,
        inputs=iclight_source_radio,
        outputs=iclight_source_radio,
        queue=False, show_progress=False)

    example_quick_prompts.click(
        lambda x, y: f"{y.strip().rstrip(',')}, {x[0]}, ".lstrip(", "),
        inputs=[example_quick_prompts, prompt],
        outputs=prompt,
        show_progress=False, queue=False)

    example_quick_subjects.click(
        # x is the subject, y is the current prompt
        lambda x, y: f"{y.strip().rstrip(',')}, {x[0]}, ".lstrip(", "),
        inputs=[example_quick_subjects, prompt],
        outputs=prompt,
        show_progress=False, queue=False)

    layer_input_image.upload(
        fn=lambda x: setattr(common,
            'layer_image_buffer', x),
        inputs=layer_input_image,
        outputs=None)

    layer_input_image.clear(
        fn=lambda: setattr(common,
            'layer_image_buffer', None))


    # Wildcard Event Handlers and Helpers

    wildcards_list.click(wildcards.add_wildcards_and_array_to_prompt,
        inputs=[wildcards_list, prompt, state_topbar],
        outputs=[prompt, wildcard_tag_name_selection,
            words_in_wildcard], show_progress=False, queue=False)

    wildcard_tag_name_selection.click(wildcards.add_word_to_prompt,
        inputs=[wildcards_list, wildcard_tag_name_selection, prompt],
        outputs=prompt, show_progress=False, queue=False)

    def set_read_wildcards_in_order(bool_read_wildcards_in_order):
        common.read_wildcards_in_order = bool_read_wildcards_in_order
        return gr.update(value=common.read_wildcards_in_order)

    read_wildcards_in_order.change(
        set_read_wildcards_in_order,
        inputs=read_wildcards_in_order,
        outputs=read_wildcards_in_order,
        show_progress=False, queue=False)


    def set_negative_prompt(arg_negative_prompt):
        config.default_prompt_negative = arg_negative_prompt
        return gr.update(value=config.default_prompt_negative)

    negative_prompt.change(
        set_negative_prompt,
        inputs=negative_prompt,
        outputs=negative_prompt,
        show_progress=False, queue=False)


    def set_image_quantity(arg_image_quantity):
        config.default_image_quantity = arg_image_quantity
        return gr.update(value=config.default_image_quantity)

    image_quantity.change(
        set_image_quantity,
        inputs=image_quantity,
        outputs=image_quantity,
        show_progress=False, queue=False)

    batch_generate_button.click(
        fn=None,
        inputs = [batch_count, generate_image_grid],
        _js="(batch_count, generate_image_grid) => generateBatch(batch_count, generate_image_grid)",
        queue=False, show_progress=False)

    # hidden button, triggered by Javascript
    # script.init_batchCounter()
    batch_counter_button.click(
        UIU.init_batch_counter,
        queue=False, show_progress=False)

    def set_batch_count(arg_batch_count):
        common.batch_count = arg_batch_count
        return gr.update(value=common.batch_count)

    batch_count.release(
        set_batch_count,
        inputs=batch_count,
        outputs=batch_count,
        show_progress=False, queue=False)

    def generate_image_grid_change(generate_grid):
        config.default_generate_image_grid = generate_grid
        return gr.update(value=config.default_generate_image_grid)

    generate_image_grid.change(
        generate_image_grid_change,
        inputs=generate_image_grid,
        outputs=[generate_image_grid],
        queue=False, show_progress=False)


    # Models Tab Event Handlers & Helpers

    def set_base_model(arg_base_model):
        config.default_base_model_name = arg_base_model
        return gr.update(value=config.default_base_model_name)

    base_model.change(
        fn=set_base_model,
        inputs=base_model,
        outputs=base_model,
        show_progress=False, queue=False)

    def set_refiner_slider(arg_refiner_slider):
        config.default_refiner_switch = arg_refiner_slider
        return gr.update(value=config.default_refiner_switch)

    refiner_slider.change(
        set_refiner_slider,
        inputs=refiner_slider,
        outputs=refiner_slider,
        show_progress=False, queue=False)

    def set_refiner_model(arg_refiner_model):
        config.default_refiner=arg_refiner_model
        if config.default_refiner == 'None':
            is_visible = False
        else:
            is_visible = True
        return (gr.update(value=config.default_refiner),
                gr.update(visible = is_visible),
                gr.update(value=config.default_refiner_switch))

    refiner_model.change(set_refiner_model,
        inputs=refiner_model,
        outputs=[refiner_model,
            refiner_slider, refiner_slider],
        show_progress=False, queue=False)


    def refresh_files_clicked(state_params):
        print()
        interpret_info('Refreshing all files...')
        US.create_user_structure(args.args.user_dir)
        US.create_model_structure(
            config.paths_checkpoints,
            config.paths_loras)

        substyle_choices = US.list_files_by_patterns(
            './substyles', patterns=['*.txt'],
            names_only=True)
        config.v2_substyle = 'Default'

        wildcards.get_wildcards_samples()

        engine = state_params.get('engine', 'Fooocus')
        task_method = state_params.get('task_method', None)
        config.available_presets = PR.get_preset_list()
        model_filenames, lora_filenames, vae_filenames = config.update_files(engine, task_method)

        results = [gr.update(
            choices=substyle_choices, value='Default')]
        results += [gr.Dataset.update(samples=wildcards.get_wildcards_samples())]
        results += [gr.update(choices=model_filenames)]
        results += [gr.update(choices=['None'] + model_filenames)]
        results += [gr.update(choices=[flags.default_vae] + vae_filenames)]
        if not args.args.disable_preset_selection:
            results += [gr.update(choices=PR.get_all_presetnames())]
        for i in range(config.default_max_lora_number):
            results += [gr.update(interactive=True),
                        gr.update(choices=['None'] + lora_filenames), gr.update()]
        if config.audio_notification:
            control_notification(config.audio_notification)
        interpret_info('Refresh complete!')
        print()
        return results

    refresh_files_output = [v2_substyle, wildcards_list, base_model, refiner_model, vae_name]
    if not args.args.disable_preset_selection:
        refresh_files_output += [preset_selection]

    refresh_files.click(refresh_files_clicked,
        [state_topbar],
        refresh_files_output + lora_ctrls,
        queue=True, show_progress=False)


    # Styles Event Handlers and Helpers

    style_search_bar.change(style_sorter.search_styles,
        inputs=[style_selections, style_search_bar],
        outputs=style_selections,
        queue=False,
        show_progress=False).then(
        lambda: None, _js='()=>{refresh_style_localization();}')

    gradio_receiver_style_selections.input(
        fn= style_sorter.sort_styles,
        inputs=style_selections,
        outputs=style_selections,
        queue=False,
        show_progress=False
    ).then(
        lambda: None, _js='()=>{refresh_style_localization();}')

    def update_substyle_visibility(selected_styles):
        is_v2_active = 'Fooocus V2' in selected_styles
        return gr.update(visible=is_v2_active)

    style_selections.change(
        fn=update_substyle_visibility,
        inputs=style_selections,
        outputs=v2_substyle,
        queue=False,
        show_progress=False
    )

    def v2_substyle_change(arg_substyle):
        config.v2_substyle = arg_substyle
        return gr.update(value=config.v2_substyle)

    v2_substyle.change(
        fn=v2_substyle_change,
        inputs=v2_substyle,
        outputs=v2_substyle,
        queue=False, show_progress=False)


    # Advanced Tab Event Handlers and Helpers

    def set_guidance_scale(arg_guidance_scale):
        config.default_cfg_scale = arg_guidance_scale
        return gr.update(value=config.default_cfg_scale)

    guidance_scale.change(
        set_guidance_scale,
        inputs=guidance_scale,
        outputs=guidance_scale,
        show_progress=False, queue=False)

    def set_sharpness(arg_sharpness):
        config.default_sample_sharpness = arg_sharpness
        return gr.update(value=config.default_sample_sharpness)

    sharpness.change(
        set_sharpness,
        inputs=sharpness,
        outputs=sharpness,
        show_progress=False, queue=False)


    # Image Control Event Handlers & Helpers

    recover_images_button.click(recover_images, None, None)

    def output_format_change(arg_format):
        config.default_output_format = arg_format
        return gr.update(value=config.default_output_format)

    output_format.change(
        fn=output_format_change,
        inputs=[output_format],
        outputs=[output_format],
        queue=False, show_progress=False)

    def save_metadata(arg_save):
        config.default_save_metadata_to_images = arg_save
        return (gr.update(value=config.default_save_metadata_to_images),
                gr.update(visible=config.default_save_metadata_to_images))

    save_metadata_to_images.change(
        fn=save_metadata,
        inputs=[save_metadata_to_images],
        outputs=[save_metadata_to_images,
            metadata_scheme],
        queue=False, show_progress=False)

    def save_scheme(save_scheme):
        config.default_metadata_scheme = save_scheme
        return gr.update(value=config.default_metadata_scheme)

    metadata_scheme.change(
        fn=save_scheme,
        inputs=[metadata_scheme],
        outputs=[metadata_scheme],
        queue=False, show_progress=False)

    def disable_image_log_change(disable_log):
        config.disable_image_log = disable_log
        return gr.update(visible=not disable_log)

    disable_image_log_checkbox.change(
        fn=disable_image_log_change,
        inputs=disable_image_log_checkbox,
        outputs=newest_images_first_checkbox,
        queue=False, show_progress=False)

    def newest_images_first_change(newest_images_first):
        config.show_newest_images_first = newest_images_first
        return gr.update(value=config.show_newest_images_first)

    newest_images_first_checkbox.change(
        fn=newest_images_first_change,
        inputs=newest_images_first_checkbox,
        outputs=newest_images_first_checkbox,
        queue=False, show_progress=False)

    def disable_preview_change(arg_preview):
        common.disable_preview = arg_preview
        return gr.update(value=common.disable_preview)

    disable_preview.change(
        fn=disable_preview_change,
        inputs=disable_preview,
        outputs=disable_preview,
        queue=False, show_progress=False)

    def set_nsfw_change(arg_black_out):
        common.black_out_nsfw = arg_black_out
        return (gr.update(value=common.black_out_nsfw),
                gr.update(value=common.black_out_nsfw,
                interactive=not common.black_out_nsfw))

    black_out_nsfw.change(
        fn=set_nsfw_change,
        inputs=black_out_nsfw,
        outputs=[black_out_nsfw, disable_preview],
        queue=False, show_progress=False)

    def set_final_enhanced_image_only(arg_final_only):
        config.default_save_only_final_enhanced_image = arg_final_only
        return gr.update(
            value = config.default_save_only_final_enhanced_image)

    save_only_final_enhanced_image.change(
        fn=set_final_enhanced_image_only,
        inputs=save_only_final_enhanced_image,
        outputs=save_only_final_enhanced_image,
        queue=False, show_progress=False)


    # Catalogue Control Event Handlers & Helpers

    def catalog_enable(arg_catalog_enable):
        config.default_image_catalog_checkbox = arg_catalog_enable
        return (
            gr.update(value=config.default_image_catalog_checkbox),
            *[gr.update(visible=config.default_image_catalog_checkbox) for _ in range(4)],
            gr.update(visible=not config.default_image_catalog_checkbox),
            *[gr.update(interactive=config.default_image_catalog_checkbox) for _ in range(4)]
        )

    catalog_enable_checkbox.change(
        fn=catalog_enable,
        inputs=catalog_enable_checkbox,
        outputs=[catalog_enable_checkbox,
            catalogue_accordion,
            history_gallery,
            image_toolbox,
            image_tools_checkbox,
            welcome_window,
            quantity_pages,
            images_per_page,
            backfill_prompt],
        queue=False, show_progress=False)


    def change_quantity_pages(arg_quantity_pages):
        config.default_image_catalog_max_number=arg_quantity_pages
        return gr.update(value=config.default_image_catalog_max_number)

    quantity_pages.release(
        fn=change_quantity_pages,
        inputs=quantity_pages,
        outputs=quantity_pages,
        queue=False, show_progress=False
        ).then(
            fn=gallery_util.get_gallery_label,
            inputs=state_topbar,
            outputs=[gallery_index,
                gallery_index_stat, history_gallery],
            queue=False, show_progress=False
        ).then(
            fn=None,
            inputs=[gallery_index_stat],
            queue=False, show_progress=False,
            _js='(x)=>{window.refresh_finished_images_catalog_label(x);}')

    def change_images_per_page(arg_per_page):
        config.default_image_catalog_max_per_page=arg_per_page
        return gr.update(value=config.default_image_catalog_max_per_page)

    images_per_page.release(
        fn=change_images_per_page,
        inputs=images_per_page,
        outputs=images_per_page,
        queue=False, show_progress=False
        ).then(
            fn=gallery_util.get_gallery_label,
            inputs=state_topbar,
            outputs=[gallery_index,
                gallery_index_stat, history_gallery],
            queue=False, show_progress=False
        ).then(
            fn=None,
            inputs=[gallery_index_stat],
            queue=False, show_progress=False,
            _js='(x)=>{window.refresh_finished_images_catalog_label(x);}')

    image_tools_checkbox.change(lambda x,y: gr.update(visible=x)\
        if "gallery_state" in y and y["gallery_state"] == 'finished_index'\
        else gr.update(visible=False),
        inputs=[image_tools_checkbox, state_topbar],\
        outputs=image_toolbox,
        queue=False, show_progress=False)


    # Expert Mode Event Handlers and Helpers

    def dev_mode_checked(r):
        return gr.update(visible=r)

    dev_mode.change(dev_mode_checked, inputs=[dev_mode], outputs=[dev_tools],
        queue=False, show_progress=False)

    def set_sampler_selector(arg_sampler_name):
        config.default_sampler = arg_sampler_name
        return gr.update(value=config.default_sampler)

    sampler_selector.change(
        fn=set_sampler_selector,
        inputs=sampler_selector,
        outputs=sampler_selector,
        show_progress=False, queue=False)

    def set_scheduler_selector(arg_scheduler_name):
        config.default_scheduler = arg_scheduler_name
        return gr.update(value=config.default_scheduler)

    scheduler_selector.change(
        fn=set_scheduler_selector,
        inputs=scheduler_selector,
        outputs=scheduler_selector,
        show_progress=False, queue=False)

    def set_vae_name(arg_vae_name):
        config.default_vae = arg_vae_name
        return gr.update(value=config.default_vae)

    vae_name.change(
        fn=set_vae_name,
        inputs=vae_name,
        outputs=vae_name,
        show_progress=False, queue=False)

    def set_clip_skip(arg_clip_skip):
        config.default_clip_skip = arg_clip_skip
        return gr.update(value=config.default_clip_skip)

    clip_skip.change(
        fn=set_clip_skip,
        inputs=clip_skip,
        outputs=clip_skip,
        show_progress=False, queue=False)

    def set_adaptive_cfg(arg_adaptive_cfg):
        config.default_cfg_tsnr = arg_adaptive_cfg
        return gr.update(value=config.default_cfg_tsnr)

    adaptive_cfg.change(
        fn=set_adaptive_cfg,
        inputs=adaptive_cfg,
        outputs=adaptive_cfg,
        show_progress=False, queue=False)

    def refiner_swap_method_change(arg_swap_method):
        common.refiner_swap_method = arg_swap_method
        return gr.update(value=common.refiner_swap_method)

    refiner_swap_method.change(
        fn=refiner_swap_method_change,
        inputs=refiner_swap_method,
        outputs=refiner_swap_method,
        show_progress=False, queue=False)

    def refiner_overwrite_switch_change(arg_switch):
        config.default_overwrite_switch = arg_switch
        return gr.update(
            value=config.default_overwrite_switch)

    overwrite_switch.change(
        fn=refiner_overwrite_switch_change,
        inputs=overwrite_switch,
        outputs=overwrite_switch,
        show_progress=False, queue=False)

    def set_adm_scaler_positive(arg_adm_positive):
        common.adm_scaler_positive = arg_adm_positive
        return gr.update(value=common.adm_scaler_positive)

    adm_scaler_positive.release(
        fn=set_adm_scaler_positive,
        inputs=adm_scaler_positive,
        outputs=adm_scaler_positive,
        show_progress=False, queue=False)

    def set_adm_scaler_negative(arg_adm_negative):
        common.adm_scaler_negative = arg_adm_negative
        return gr.update(value=common.adm_scaler_negative)

    adm_scaler_negative.release(
        fn=set_adm_scaler_negative,
        inputs=adm_scaler_negative,
        outputs=adm_scaler_negative,
        show_progress=False, queue=False)

    def set_adm_scaler_end(arg_adm_end):
        common.adm_scaler_end = arg_adm_end
        return gr.update(value=common.adm_scaler_end)

    adm_scaler_end.release(
        fn=set_adm_scaler_end,
        inputs=adm_scaler_end,
        outputs=adm_scaler_end,
        show_progress=False, queue=False)


    # Debugging Tools Handlers & Helpers

    def debugging_cn_preprocessor_change(arg_debugging_cn):
        common.debugging_cn_preprocessor = arg_debugging_cn
        return gr.update(
            value=common.debugging_cn_preprocessor)

    debugging_cn_preprocessor.change(
        fn=debugging_cn_preprocessor_change,
        inputs=debugging_cn_preprocessor,
        outputs=debugging_cn_preprocessor,
        show_progress=False, queue=False
    )

    def skipping_cn_preprocessor_change(arg_skipping_cn):
        common.skipping_cn_preprocessor = arg_skipping_cn
        return gr.update(
            value=common.skipping_cn_preprocessor)

    skipping_cn_preprocessor.change(
        fn=skipping_cn_preprocessor_change,
        inputs=skipping_cn_preprocessor,
        outputs=skipping_cn_preprocessor,
        show_progress=False, queue=False
    )

    def debugging_inpaint_preprocessor_change(arg_preprocessor):
        common.debugging_inpaint_preprocessor = arg_preprocessor
        return gr.update(value=common.debugging_inpaint_preprocessor)

    debugging_inpaint_preprocessor.change(
        fn=debugging_inpaint_preprocessor_change,
        inputs=debugging_inpaint_preprocessor,
        outputs=debugging_inpaint_preprocessor,
        show_progress=False, queue=False)

    def debugging_dino_change(arg_dino):
        common.debugging_dino = arg_dino
        return gr.update(
            value=common.debugging_dino)

    debugging_dino.change(
        fn=debugging_dino_change,
        inputs=debugging_dino,
        outputs=debugging_dino,
        show_progress=False, queue=False)

    def debugging_enhance_masks_checkbox_change(
        arg_debug_enhance_masks):
        common.debugging_enhance_masks = arg_debug_enhance_masks
        return gr.update(
            value=common.debugging_enhance_masks)

    debugging_enhance_masks_checkbox.change(
        fn=debugging_enhance_masks_checkbox_change,
        inputs=debugging_enhance_masks_checkbox,
        outputs=debugging_enhance_masks_checkbox,
        show_progress=False, queue=False)

    def debug_substyles_checkbox_change(
        arg_debug_substyles):
        common.debug_substyles = arg_debug_substyles
        return gr.update(
            value=common.debug_substyles)

    debug_substyles_checkbox.change(
        fn=debug_substyles_checkbox_change,
        inputs=debug_substyles_checkbox,
        outputs=debug_substyles_checkbox,
        show_progress=False, queue=False)


    # Remove Torch Components Handlers

    # 1. Trigger the Deletion Warning (OK / Cancel dialog)
    remove_torch_btn.click(
        fn=UIU.show_remove_torch_confirm,
        inputs=None,
        outputs=[remove_torch_modal_box,
                 remove_torch_modal_msg,
                 remove_torch_proceed_btn,
                 remove_torch_cancel_btn,
                 perf_modal_box],
        queue=False, show_progress=False
    )

    # 2. Action Cancel (Close Box without doing anything)
    remove_torch_cancel_btn.click(
        fn=UIU.close_remove_torch_modal,
        inputs=None,
        outputs=remove_torch_modal_box,
        queue=False, show_progress=False
    )

    # 3. Action Confirmation (Execute Wipe,
    # then show final OK instructions)
    remove_torch_proceed_btn.click(
        fn=UIU.execute_remove_torch_components,
        inputs=None,
        outputs=[remove_torch_modal_msg,
                 remove_torch_proceed_btn,
                 remove_torch_cancel_btn,
                 perf_modal_box,
                 perform_btn],
        queue=False, show_progress=False
    )


    # Extras Event Handlers and Helpers

    preset_save_button.click(
        toolbox.toggle_note_box_preset,
        inputs=model_check + [state_topbar],
        outputs=[
            toolbox_note_info,
            toolbox_note_input_name,
            toolbox_note_preset_button,
            toolbox_note_cancel_button,
            toolbox_note_box,
            state_topbar,
            toolbox_note_input_name
            ],
            show_progress=False)

    toolbox_note_preset_button.click(
        toolbox.save_preset,
        inputs=[toolbox_note_input_name, params_backend] + reset_preset_func + load_data_outputs,
        outputs=[toolbox_note_input_name,
            toolbox_note_preset_button,
            toolbox_note_box, state_topbar] \
            + nav_bars, show_progress=False
        ).then(
            PR.save_preset,
            inputs=state_topbar,
            outputs=[system_params,
                preset_selection,
                preset_selection],
            queue=False, show_progress=False
        ).then(
            fn=lambda x: None,
            inputs=system_params,
            _js=UIS.refresh_topbar_status_js)

    def save_res_checkbox_change(arg_save_res):
        common.save_resolution = arg_save_res
        return gr.update(value=common.save_resolution)

    save_res_checkbox.change(
        fn=save_res_checkbox_change,
        inputs=save_res_checkbox,
        outputs=save_res_checkbox,
        show_progress=False, queue=False)

    def overwrite_prompts_checkbox_change(arg_overwrite):
        common.overwrite_prompts = arg_overwrite
        return gr.update(value=common.overwrite_prompts)

    overwrite_prompts_checkbox.change(
        fn=overwrite_prompts_checkbox_change,
        inputs=overwrite_prompts_checkbox,
        outputs=overwrite_prompts_checkbox,
        show_progress=False, queue=False)


    preset_favorite_button.click(
            PR.preset_favorite_modify1,
            outputs=[preset_selection],
            queue=False, show_progress=False
        ).then(
            PR.preset_favorite_modify2,
            outputs=[preset_selection, category_selection],
            queue=False, show_progress=False)

    restore_favorites_button.click(
            PR.restore_favorites,
            outputs=[preset_selection, category_selection,
                clear_favorites_button],
            queue=False, show_progress=False
        ).then(
            fn=lambda: interpret_info('Restored the default favorites'),
            outputs=None)

    clear_favorites_button.click(
            PR.clear_favorites,
            outputs=[preset_selection, category_selection,
                clear_favorites_button],
            queue=False, show_progress=False
        ).then(
            fn=lambda: interpret_info('Cleared all favorites except the default'),
            outputs=None)

    def notification_control(enable_notification):
        config.audio_notification = enable_notification
        control_notification(enable_notification)
        if enable_notification:
            audio_mp3 = 'notification.mp3'
        else:
            audio_mp3 = None
        return gr.update(value=enable_notification), \
            gr.update(value=audio_mp3)

    audio_notification_checkbox.change(notification_control,
        inputs=audio_notification_checkbox,
        outputs=[audio_notification_checkbox, audio_output],
        queue=False, show_progress=False)

    comfyd_active_checkbox.change(lambda x: comfyd.active(x), inputs=comfyd_active_checkbox,\
        queue=False, show_progress=False)

    def translator_control(enable_translator):
        config.default_prompt_translator_enable = enable_translator
        common.prompt_translator = enable_translator
        return gr.update(visible=config.default_prompt_translator_enable)

    def toggle_logo(welcome_logo):
        source_path = Path(US.masters_dir / 'master_control_images' / 'FooocusPlus_logo.png')
        logo_path = Path(config.user_dir / 'welcome_images' / 'FooocusPlus_logo.png')
        if welcome_logo:
            US.copy_file(source_path, logo_path, overwrite = True)
        else:
            US.delete_file(logo_path)

        new_welcome_path = get_welcome_image()
        if not new_welcome_path or new_welcome_path == '':
            return (gr.update(value=check_active_logo()),
                    gr.update(value=None))

        abs_path = str(Path(new_welcome_path).resolve())
        return (
            gr.update(value=check_active_logo()),
            gr.update(value=abs_path)
    )

    welcome_logo_checkbox.change(
        fn=toggle_logo,
        inputs=welcome_logo_checkbox,
        outputs=[welcome_logo_checkbox, welcome_window],
        queue=False, show_progress=False
    )

    prompt_translator_checkbox.change(
        fn=translator_control,
        inputs=prompt_translator_checkbox, outputs=translator_button,
        queue=False, show_progress=False
    )


    reset_layout_params = nav_bars + reset_preset_layout + reset_preset_func + load_data_outputs
    UIS.len_layout_params = len(reset_layout_params)
    UIS.gen_btn_offset = len(reset_layout_params) - reset_layout_params.index(generate_button)
    reset_preset_inputs = [prompt, negative_prompt, state_topbar, state_is_generating, inpaint_mode, comfyd_active_checkbox]

    def inpaint_engine_state_change(inpaint_engine_version, *args):
        if inpaint_engine_version == 'empty' or inpaint_engine_version == None or not inpaint_engine_version:
            inpaint_engine_version = config.default_inpaint_engine_version
            if inpaint_engine_version == None or not inpaint_engine_version:
                inpaint_engine_version = 'v2.6'
        result = []
        for inpaint_mode in args:
            if inpaint_mode != modules.flags.inpaint_option_detail:
                result.append(gr.update(value=inpaint_engine_version))
            else:
                result.append(gr.update())
        return result


    for i in range(config.preset_bar_length):
        bar_buttons[i].click(PR.bar_button_change, inputs=[bar_buttons[i],\
            state_topbar], outputs=[state_topbar, category_selection, preset_selection]) \
           .then(UIS.reset_layout_params, inputs=reset_preset_inputs, outputs=reset_layout_params, show_progress=False) \
           .then(fn=lambda x: x, inputs=state_topbar, outputs=system_params, show_progress=False) \
           .then(fn=lambda x: {}, inputs=system_params, outputs=system_params, _js=UIS.refresh_topbar_status_js) \
           .then(lambda: None, _js='()=>{refresh_style_localization();}') \
           .then(inpaint_engine_state_change, inputs=[inpaint_engine_state] + enhance_inpaint_mode_ctrls,\
               outputs=enhance_inpaint_engine_ctrls, queue=False, show_progress=False)

        category_selection.change(PR.set_category_selection, inputs=category_selection,\
            outputs=[category_selection, preset_selection, preset_info],
            show_progress=False, queue=False)

        preset_selection.change(PR.set_preset_selection,
            inputs=[preset_selection, state_topbar],
            outputs=[preset_selection,
                state_topbar, preset_info,
                aspect_ratios_selection,
                category_selection,
                prompt, negative_prompt,
                v2_substyle, image_quantity,
                sampler_selector, scheduler_selector,
                preset_favorite_button,
                preset_favorite_button],
            show_progress=False, queue=False) \
            .then(UIS.reset_layout_params, inputs=reset_preset_inputs,
                outputs=reset_layout_params, show_progress=False) \
            .then(fn=lambda x: x, inputs=state_topbar, outputs=system_params, show_progress=False) \
            .then(fn=lambda x: {}, inputs=system_params, outputs=system_params, _js=UIS.refresh_topbar_status_js) \
            .then(lambda: None, _js='()=>{refresh_style_localization();}') \
            .then(inpaint_engine_state_change, inputs=[inpaint_engine_state] + enhance_inpaint_mode_ctrls,
            outputs=enhance_inpaint_engine_ctrls, queue=False, show_progress=False)


    # stop ".then chain" early
    # should_stop_flag = gr.State(value=False)
    generate_button.click(
        fn=lambda: gr.update(interactive=False),
        outputs=[generate_button]
    ).then(
        lambda: None,
        inputs=None,
        outputs=None,
        queue=False, show_progress=False,
        _js='()=>{window.close_finished_images_catalog();}'
    ).then(
        fn=UIS.manage_image_buffers,
        inputs=[inpaint_input_image, inpaint_mask_image],
        outputs=None,
        queue=False
    ).then(
        UIS.process_before_generation,
        inputs=[state_topbar, params_backend] + ehps,
        outputs=[aspect_ratios_select, stop_button,
        skip_button, generate_button,
        history_gallery,
        state_is_generating, catalogue_accordion,
        image_toolbox, toolbox_info_box] +
        protections + [params_backend],
        show_progress=False
    ).then(
        fn=refresh_seed,
        inputs=[seed_random, image_seed],
        outputs=image_seed
    ).then(
        fn=get_task,
        inputs=ctrls,
        outputs=currentTask
    ).then(
        fn=enhanced_parameters.set_all_enhanced_parameters,
        inputs=ehps
    ).then(
        fn=UIU.generate_clicked,
        inputs=currentTask,
        outputs=[progress_html,
            preview_window,
            progress_gallery,
            history_gallery,
            welcome_window]
    ).then(
        UIS.process_after_generation,
        inputs=state_topbar,
        outputs=[
            welcome_window,
            preview_window,
            progress_gallery,
            history_gallery,
            generate_button,
            stop_button,
            skip_button,
            state_is_generating,
            gallery_index,
            catalogue_accordion
        ] + protections,
        show_progress=False
    ).then(
        fn=update_history_link,
        outputs=history_link
    ).then(
        fn=gallery_util.get_gallery_label,
        inputs=state_topbar,
        outputs=[gallery_index,
            gallery_index_stat,
            history_gallery],
        queue=False, show_progress=False
    ).then(
        lambda x: None,
        inputs=gallery_index_stat,
        queue=False, show_progress=False,
        _js='(x)=>{refresh_finished_images_catalog_label(x);}'
    ).then(
        fn=lambda: None,
        _js='playNotification'
    ).then(
        fn=lambda: None,
        _js='refresh_grid_delayed')


    def stop_clicked(currentTask):
        currentTask.last_stop = 'stop'
        if (currentTask.processing):
            comfyd.interrupt()
            model_management.interrupt_current_processing()
        return currentTask

    # cancelGenerateForever() also cancels Batch Generate
    stop_button.click(
        stop_clicked,
        inputs=currentTask,
        outputs=currentTask,
        queue=False,
        show_progress=False,
        _js='cancelGenerateForever')

    def skip_clicked(currentTask):
        currentTask.last_stop = 'skip'
        if (currentTask.processing):
            comfyd.interrupt()
            model_management.interrupt_current_processing()
        return currentTask

    skip_button.click(
        skip_clicked,
        inputs=currentTask,
        outputs=currentTask,
        queue=False,
        show_progress=False)


    reset_button.click(
        lambda: [worker.AsyncTask(args=[]), False,
        gr.update(visible=True, interactive=True)] +
        [gr.update(visible=False)] * 6 +
        [gr.update(visible=True, value=[])],
        outputs=[currentTask, state_is_generating,
            generate_button, reset_button,
            stop_button, skip_button,
            progress_html, preview_window,
            progress_gallery, history_gallery],
            queue=False)


    common.GRADIO_ROOT.load(
        fn=lambda x: x,
            inputs=system_params,
            outputs=state_topbar,
            _js=UIS.get_system_params_js,
            queue=False, show_progress=False
    ).then(
        UIS.init_nav_bars,
        inputs=state_topbar,
        outputs=nav_bars + [welcome_window,
            background_mode, gallery_index,
            catalogue_accordion,
            inpaint_advanced_masking_checkbox,
            preset_instruction,
            gallery_index_stat],
            show_progress=False
    ).then(
        fn=UIU.security_check,
        inputs=None,
        outputs = None,
        show_progress=False
    ).then(
        fn=lambda x: x,
        inputs=state_topbar,
        outputs=system_params,
        show_progress=False
    ).then(
        fn=lambda x: {},
        inputs=system_params,
        outputs=system_params,
        _js=UIS.refresh_topbar_status_js
    ).then(
        UIS.sync_message,
        inputs=state_topbar,
        outputs=[state_topbar]
    ).then(
        lambda x: x,
        inputs=aspect_ratios_selections[0],
        outputs=aspect_ratios_selection,
        queue=False, show_progress=False
    ).then(
        lambda x: None,
        inputs=aspect_ratios_selections[0],
        queue=False, show_progress=False,
        _js='(x)=>{refresh_aspect_ratios_label(x);}'
    ).then(
        fn=gallery_util.get_gallery_label,
        inputs=state_topbar,
        outputs=[gallery_index,
            gallery_index_stat,
            history_gallery],
        queue=False, show_progress=False
    ).then(
        # Using a lambda instead of None ensures Gradio 3
        # treats this as a standard reactive step:
        fn=lambda x: x,
        inputs=[gallery_index_stat],
        outputs=[],
        queue=False, show_progress=False,
        _js='(x)=>{refresh_finished_images_catalog_label(x);}'
    ).then(
        fn=lambda: None, _js='refresh_grid_delayed'
    )


def dump_default_english_config():
    from modules.localization import dump_english_config
    dump_english_config(grh.all_components)

#dump_default_english_config()
import logging
import httpx
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)

import logging
import httpx
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)
hydit_logger = logging.getLogger("hydit")
hydit_logger.setLevel(logging.WARNING)

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


if not args.args.disable_comfyd and comfyd_active_checkbox:
    comfyd.active(True)

common.GRADIO_ROOT.launch(
    inbrowser=args.args.in_browser,
    server_name=args.args.listen,
    server_port=args.args.port,
    share=False, quiet=True,
    allowed_paths=[config.path_outputs], # allows log viewing
    blocked_paths=[constants.AUTH_FILENAME]
)
