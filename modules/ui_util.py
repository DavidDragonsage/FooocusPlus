import os
import gradio as gr
import sys
import time
import common

from pathlib import Path

import ldm_patched.modules.model_management as model_management
import modules.async_worker as worker
import modules.config as config
import modules.flags as flags
import modules.html

from args_manager import args
from enhanced.translator import interpret, interpret_info, interpret_warn
from launch_support import delete_torch_dependencies, \
    get_nvidia_driver_compatibility, get_torch_base_path
from modules.flags import inpaint_option_detail, inpaint_option_modify
from modules.util import cleanup_temp_files, save_image_grid


batch_counter = 0
last_batch_size = 1
last_execution_time = 0.0


def init_batch_counter():
    global batch_counter
    batch_counter = 1
    print()
    interpret('[UI Util] Beginning the first batch...')
    return


def update_batch_counter():
    # local_batch_counter ensures that old value is printed after increment
    # interpret() is not reliable here because of UI overload
    global batch_counter
    if batch_counter > 0:
        interpret('Finished batch number:', f'{batch_counter}/{common.batch_count}')
        if batch_counter < common.batch_count:
            batch_counter += 1
        else:
            batch_counter = 0
            if common.batch_count > 1:
                interpret_info('[UI Util] All batches are complete')
    return


def sort_enhance_images(images, task):
    if not task.should_enhance or len(images) <= task.images_to_enhance_count:
        return images

    sorted_images = []
    walk_index = task.images_to_enhance_count

    for index, enhanced_img in enumerate(images[:task.images_to_enhance_count]):
        sorted_images.append(enhanced_img)
        if index not in task.enhance_stats:
            continue
        target_index = walk_index + task.enhance_stats[index]
        if walk_index < len(images) and target_index <= len(images):
            sorted_images += images[walk_index:target_index]
        walk_index += task.enhance_stats[index]

    return sorted_images


def generate_clicked(task: worker.AsyncTask):
    with model_management.interrupt_processing_mutex:
        model_management.interrupt_processing = False

    if len(task.args) == 0:
        return

    execution_start_time = time.perf_counter()
    finished = False

    status_msg = interpret('Waiting for task to start...', '', True)
    yield (  # progress_html
        gr.update(visible=True,
            value=modules.html.make_progress_html(
                1, status_msg)),              # progress_html
        gr.update(visible=True, value=None),  # preview_window
        gr.update(visible=False, value=None), # progress_gallery
        gr.update(visible=False),             # history_gallery
        gr.update())                          # welcome_window

    cleanup_temp_files()
    if batch_counter > 0:
        interpret_info('Starting batch generate', f'{batch_counter}/{common.batch_count}...')

    worker.async_tasks.append(task)

    while not finished:
        time.sleep(0.01)
        if len(task.yields) > 0:
            flag, product = task.yields.pop(0)
            if flag == 'preview':

                # help bad internet connection by skipping duplicated preview
                if len(task.yields) > 0:  # if we have the next item
                    if task.yields[0][0] == 'preview':   # if the next item is also a preview
                        # print('Skipped one preview for better internet connection.')
                        continue

                percentage, title, image = product
                yield (gr.update(visible=True,
                    value=modules.html.make_progress_html(percentage, title)),
                    gr.update(visible=True, value=image) if image is not None else gr.update(),
                    gr.update(),
                    gr.update(visible=False),
                    gr.update(visible=False))

            if flag == 'results':
                yield (gr.update(visible=True), # progress_html
                    gr.update(visible=True),    # preview_window
                    gr.update(visible=False),   # progress_gallery
                    gr.update(visible=False),   # history_gallery
                    gr.update(visible=False))   # welcome_window

            if flag == 'finish':
                product = sort_enhance_images(product, task)

                global last_batch_size
                if isinstance(product, list):
                    last_batch_size = len(product)
                else:
                    last_batch_size = 1

                yield (gr.update(visible=False), # progress_html
                    gr.update(visible=False),    # preview_window
                    gr.update(visible=True,
                        value=product),          # progress_gallery
                    gr.update(visible=False),    # history_gallery
                    gr.update(visible=False))    # welcome_window
                update_batch_counter()
                finished = True

    execution_time = time.perf_counter() - execution_start_time
    interpret('[UI Util] Total time in seconds:', f'{execution_time:.2f}')

    global last_execution_time
    last_execution_time = execution_time

    if config.default_generate_image_grid:
        # only make UI announcement if several grids are being created:
        if common.batch_count > 1:
            save_image_grid(UI=True)
        else:
            save_image_grid(UI=False)
    return


def bind_ip_slot_logic(image_comp, radio_comp, stop_slider, weight_slider, slot_idx, update_func):
    """
    The complete Image Prompt Logic Factory.
    Ensures all slot parameters are bound to the correct index without lambdas.
    """

    # 1. Image Handler
    def img_handler(x):
        # This ensures the image actually reaches config.ip_slots[slot_idx]
        update_func(slot_idx, 'image', x)

    # 2. Stop Slider Handler
    def stop_handler(x):
        update_func(slot_idx, 'stop', x)

    # 3. Weight Slider Handler
    def weight_handler(x):
        update_func(slot_idx, 'weight', x)

    # 4. Type (Radio) Handler
    def type_handler(selected_type):
        # Update the backend type
        update_func(slot_idx, 'type', selected_type)

        # Fetch and apply defaults
        params = flags.default_parameters.get(selected_type)
        if params:
            stop, weight = params
            # CRITICAL: Also update the backend for these values
            # so the config isn't waiting for a manual slider move
            update_func(slot_idx, 'stop', stop)
            update_func(slot_idx, 'weight', weight)
            return gr.update(value=stop), gr.update(value=weight)

        return gr.update(), gr.update()

    # --- Bindings ---

    image_comp.change(
        fn=img_handler,
        inputs=[image_comp],
        queue=False,
        show_progress=False
    )

    stop_slider.change(
        fn=stop_handler,
        inputs=[stop_slider],
        queue=False,
        show_progress=False
    )

    weight_slider.change(
        fn=weight_handler,
        inputs=[weight_slider],
        queue=False,
        show_progress=False
    )

    radio_comp.change(
        fn=type_handler,
        inputs=[radio_comp],
        outputs=[stop_slider, weight_slider],
        queue=False,
        show_progress=False
    )


def inpaint_mode_change(mode, inpaint_engine_version):

    if mode == inpaint_option_detail:
        common.inpaint_mode = 'Inpaint Detail'
        return [
            gr.update(visible=True),            # inpaint_additional_prompt
            gr.update(visible=False, value=[]), # outpaint_selections
            gr.Dataset.update(visible=True,     # example_inpaint_prompts
                samples=config.example_inpaint_prompts),
            False,                         # inpaint_disable_initial_latent
            'None',                             # inpaint_engine
            0.5,                                # inpaint_strength
            0.0                                 # inpaint_respective_field
        ]

    if inpaint_engine_version in ['empty', None, '']:
        inpaint_engine_version = config.default_inpaint_engine_version
        if not inpaint_engine_version:
            inpaint_engine_version = 'v2.6'

    if mode == inpaint_option_modify:
        common.inpaint_mode = 'Inpaint Modify/Replace'
        return [
            gr.update(visible=True),            # inpaint_additional_prompt
            gr.update(visible=False, value=[]), # outpaint_selections
            gr.Dataset.update(visible=False,    # example_inpaint_prompts
                samples=config.example_inpaint_prompts),
            True,                          # inpaint_disable_initial_latent
            inpaint_engine_version,             # inpaint_engine
            1.0,                                # inpaint_strength
            0.0                                 # inpaint_respective_field
        ]

    common.inpaint_mode = 'Inpaint Default: Blend'
    return [
        gr.update(visible=False, value=''),     # inpaint_additional_prompt
        gr.update(visible=True),                # outpaint_selections
        gr.Dataset.update(visible=False,        # example_inpaint_prompts
            samples=config.example_inpaint_prompts),
        False,                             # inpaint_disable_initial_latent
        inpaint_engine_version,                 # inpaint_engine
        1.0,                                    # inpaint_strength
        0.618                                   # inpaint_respective_field
    ]


def enhance_inpaint_mode_change(mode, inpaint_engine_version):

    # inpaint_disable_initial_latent, inpaint_engine,
    # inpaint_strength, inpaint_respective_field

    if mode == inpaint_option_detail:
        return [
            False, 'None', 0.5, 0.0
        ]

    if inpaint_engine_version == 'empty' or inpaint_engine_version == None or not inpaint_engine_version:
        inpaint_engine_version = config.default_inpaint_engine_version
        if inpaint_engine_version == None or not inpaint_engine_version:
            inpaint_engine_version = 'v2.6'

    if mode == inpaint_option_modify:
        return [
            True, inpaint_engine_version, 1.0, 0.0
        ]

    return [
        False, inpaint_engine_version, 1.0, 0.618
    ]


def security_warn():
    interpret_warn('Please check the Security Report under the Extras tab!')
    print()
    return

def security_alert():
    try:
        if (args.listen == "127.0.0.1") and (args.port == 7860):
            alert = False
        else:
            alert = True
    except:
        # trap partial upgrade error for FooocusPlus 1.0.9.13
        interpret('Please restart FooocusPlus to complete the security upgrade')
        print()
        sys.exit()
    return alert

def security_check():
    if security_alert() == True:
        security_warn()
    return


def format_last_generation_time():
    """
    Formulates the last generation speed metrics from the generate_clicked()
    Returns:
        str: Localized markdown with compact, single-spaced throughput statistics.
    """
    global last_batch_size, last_execution_time

    if last_execution_time <= 0.0:
        return ''

    # Clean, global safeguard to prevent ZeroDivisionError
    if last_batch_size <= 0:
        last_batch_size = 1

    # Format total time as MM:SS (or raw seconds if under a minute)
    minutes = int(last_execution_time // 60)
    seconds = last_execution_time % 60
    if minutes > 0:
        time_str = f"{minutes}:{seconds:05.2f}"  # Zero-pads the seconds (e.g., 3:05.20)
    else:
        time_str = f"{seconds:.2f}s"

    # Calculate throughput metrics
    sec_per_img = last_execution_time / last_batch_size
    img_per_min = (last_batch_size * 60) / last_execution_time

    # Pre-translate modular labels silently
    lbl_metrics = interpret('Last Generation Metrics', silent=True)
    lbl_duration = interpret('Generation Time:', silent=True)
    lbl_throughput = interpret('Throughput:', silent=True)
    lbl_sec_img = interpret('seconds/image', silent=True)
    lbl_img_min = interpret('images/minute', silent=True)
    lbl_batch_size = interpret('Image Quantity:', silent=True)

    # Uses pure HTML to bypass the Markdown parser constraints
    # The styled div container enforces a good line-height
    stats_markdown = (
        f'<hr style="margin: 18px 0; border: 0; border-top: 1px solid;" />\n'  # Increased vertical margins to 18px
        f'<h3 style="margin: 0 0 10px 0; font-size: 1.1em; font-weight: bold;">{lbl_metrics}</h3>\n'
        f'<div style="line-height: 1.6; margin-top: 6px;">\n'  # Container enforcing clean line-height
        f'<strong>{lbl_duration}</strong> {time_str}<br />\n'
        f'<strong>{lbl_batch_size}</strong> {last_batch_size}<br />\n'
        f'<strong>{lbl_throughput}</strong> {img_per_min:.2f} {lbl_img_min}<br />\n'
        f'<div style="margin-left: 50px;">({sec_per_img:.2f} {lbl_sec_img})</div>\n'  # Horizontal centering
        f'</div>\n'
        f'<div style="height: 20px;"></div>'
    )
    return stats_markdown


def check_performance_handler():
    """
    Runs the Nvidia driver and architecture
    compatibility (arch) checks,
    determining optimal performance
    and configuring the UI popup.
    """
    # 1. Fetch the GPU's hardware architecture version via torchruntime
    from torchruntime.device_db import get_gpus
    from torchruntime.platform_detection import get_nvidia_arch
    gpu_infos = get_gpus()
    device_names = set(gpu.device_name for gpu in gpu_infos)
    arch_version = get_nvidia_arch(device_names)

    # 2. Check the raw driver compatibility status
    is_compatible, message = get_nvidia_driver_compatibility()

    # 3. Check the currently running PyTorch environment version
    import torch
    is_running_cu130 = torch.__version__.startswith('2.10.')
    is_running_cu128 = torch.__version__.startswith('2.7.')

    torch_base_path = get_torch_base_path()

    # Pre-translate modular UI labels silently to minimize console noise
    header_check = interpret('NVIDIA Performance Check', silent=True)
    status_label = interpret('Status:', silent=True)
    details_label = interpret('Details:', silent=True)

    # Grab the latest generation metrics (if any exist) to append to the bottom
    stats_msg = format_last_generation_time()

    # =============================================================================
    # PATH A: USER HAS BLACKWELL GPU (RTX 50-series, CC >= 12.0)
    # =============================================================================
    if arch_version >= 12.0:
        if is_compatible:
            if is_running_cu130:
                # Scenario A1: Blackwell running optimal CUDA 13.0
                status_val = interpret('Fully Upgraded (Optimal with CU130)', silent=True)
                already_upgraded = interpret('Your Blackwell GPU is running on the native CUDA 13.0 high-performance stack.', silent=True)

                msg = (
                    f"### **{header_check}**\n\n"
                    f"**{status_label}** {status_val}\n\n"
                    f"**{details_label}** {message}\n\n"
                    f"{already_upgraded}\n\n"
                )
                return (
                    gr.update(visible=True),                             # perf_modal_box
                    gr.update(value=msg),                                 # perf_modal_header_msg
                    gr.update(value=stats_msg, visible=bool(stats_msg)),  # perf_modal_metrics_msg (at bottom)
                    gr.update(visible=True),                             # perf_ok_btn (Show bottom OK)
                    gr.update(visible=False),                            # perf_upgrade_btn
                    gr.update(visible=False)                             # perf_cancel_btn
                )
            else:
                # Scenario A2: Blackwell running old version (Prompt Upgrade)
                status_val = interpret('Running in Compatibility Mode using CUDA 12.8', silent=True)
                gpu_support = interpret('Your Blackwell GPU supports full native CUDA 13.0 with Blackwell FP4 performance.', silent=True)
                ask_upgrade = interpret('Do you want to enable the high-performance environment upgrade?', silent=True)
                restart_warn = interpret('This will automatically download then reconfigure PyTorch and its dependencies on your next restart.', silent=True)

                msg = (
                    f"### **{header_check}**\n\n"
                    f"**{status_label}** {status_val}\n\n"
                    f"**{details_label}** {message}\n\n"
                    f"{gpu_support}\n\n"
                    f"**{ask_upgrade}**\n"
                    f"{restart_warn}\n\n"
                    f'<div style="height: 5px;"></div>'
                )
                return (
                    gr.update(visible=True),                             # perf_modal_box
                    gr.update(value=msg),                                 # perf_modal_header_msg
                    gr.update(value=stats_msg, visible=bool(stats_msg)),  # perf_modal_metrics_msg (below buttons)
                    gr.update(visible=False),                            # perf_ok_btn (Hide bottom OK)
                    gr.update(visible=True),                             # perf_upgrade_btn (Show action)
                    gr.update(visible=True)                              # perf_cancel_btn (Show cancel)
                )
        else:
            # Scenario A3: Blackwell with outdated driver (Recommend Driver Upgrade)
            status_val = interpret('Video Driver Upgrade Recommended', silent=True)
            driver_old = interpret('Your NVIDIA graphics driver is older than the required version 580.65.', silent=True)
            recommend_upgrade = interpret('Please upgrade your NVIDIA display driver to version 580.xx or newer to unlock native CUDA 13.0.', silent=True)

            msg = (
                f"### **{header_check}**\n\n"
                f"**{status_label}** {status_val}\n\n"
                f"**{details_label}** {message}\n\n"
                f"{driver_old}\n\n"
                f"{recommend_upgrade}\n\n"
            )
            return (
                gr.update(visible=True),                             # perf_modal_box
                gr.update(value=msg),                                 # perf_modal_header_msg
                gr.update(value=stats_msg, visible=bool(stats_msg)),  # perf_modal_metrics_msg
                gr.update(visible=True),                             # perf_ok_btn (Show bottom OK)
                gr.update(visible=False),                            # perf_upgrade_btn
                gr.update(visible=False)                             # perf_cancel_btn
            )

    # =============================================================================
    # PATH B: USER HAS NON-BLACKWELL GPU (RTX 20/30/40 series, CC <= 12.0)
    # =============================================================================
    else:
        if is_compatible:
            if is_running_cu130:
                # Scenario B1: Non-Blackwell GPU running experimental CUDA 13.0
                status_val = interpret('Experimental Configuration Active', silent=True)
                experimental_warn = interpret('You are currently running on the experimental CUDA 13.0 stack. Flux models may run from about 6% to 17% slower with CUDA 13 and SDXL models may operate from 3% faster to 9% slower', silent=True)
                ask_revert = interpret('Would you like to restore the CUDA 12.8 configuration?', silent=True)
                revert_warn = interpret('This will automatically download then reconfigure PyTorch and its dependencies on your next restart.', silent=True)

                msg = (
                    f"### **{header_check}**\n\n"
                    f"**{status_label}** {status_val}\n\n"
                    f"**{details_label}** {message}\n\n"
                    f"{experimental_warn}\n\n"
                    f"**{ask_revert}**\n"
                    f"{revert_warn}\n\n"
                    f'<div style="height: 5px;"></div>'
                )
                return (
                    gr.update(visible=True),                             # perf_modal_box
                    gr.update(value=msg),                                 # perf_modal_header_msg
                    gr.update(value=stats_msg, visible=bool(stats_msg)),  # perf_modal_metrics_msg (below buttons)
                    gr.update(visible=False),                            # perf_ok_btn (Hide bottom OK)
                    gr.update(visible=True),                             # perf_upgrade_btn (Show action)
                    gr.update(visible=True)                              # perf_cancel_btn (Show cancel)
                )
            else:
                # Scenario B2: Non-Blackwell running optimal CUDA 12.8 (Optimal!)
                status_val = interpret('Optimal Configuration using CUDA 12.8', silent=True)
                message = interpret('Fully Compliant Video Driver', silent=True)
                already_optimal = interpret('Your GPU is running on the stable CUDA 12.8 stack, which is the optimal high-performance configuration for your GPU architecture. Your NVIDIA display driver fully supports this system.', silent=True)

                msg = (
                    f"### **{header_check}**\n\n"
                    f"**{status_label}** {status_val}\n\n"
                    f"**{details_label}** {message}\n\n"
                    f"{already_optimal}\n\n"
                )
                return (
                    gr.update(visible=True),                             # perf_modal_box
                    gr.update(value=msg),                                 # perf_modal_header_msg
                    gr.update(value=stats_msg, visible=bool(stats_msg)),  # perf_modal_metrics_msg
                    gr.update(visible=True),                             # perf_ok_btn (Show bottom OK)
                    gr.update(visible=False),                            # perf_upgrade_btn
                    gr.update(visible=False)                             # perf_cancel_btn
                )
        else:
            # Scenario B3: Non-Blackwell with outdated driver (Recommend Driver Upgrade)
            status_val = interpret('Video Driver Upgrade Recommended', silent=True)
            driver_old = interpret('Your NVIDIA graphics driver is older than 580.65, the required version .', silent=True)
            recommend_upgrade = interpret('Please upgrade your NVIDIA display driver to version 580.xx or newer to ensure maximum performance and stability.', silent=True)

            msg = (
                f"### **{header_check}**\n\n"
                f"**{status_label}** {status_val}\n\n"
                f"**{details_label}** {message}\n\n"
                f"{driver_old}\n\n"
                f"{recommend_upgrade}\n\n"
            )
            return (
                gr.update(visible=True),                             # perf_modal_box
                gr.update(value=msg),                                 # perf_modal_header_msg
                gr.update(value=stats_msg, visible=bool(stats_msg)),  # perf_modal_metrics_msg
                gr.update(visible=True),                             # perf_ok_btn (Show bottom OK)
                gr.update(visible=False),                            # perf_upgrade_btn
                gr.update(visible=False)                             # perf_cancel_btn
            )


def execute_cuda13_upgrade():
    """
    Deletes torch_base.txt to trigger the
    environment upgrade on next launch.
    """
    torch_base_path = get_torch_base_path()

    if torch_base_path.exists():
        try:
            torch_base_path.unlink()
            header_success = interpret('Upgrade Unlocked Successfully!', silent=True)
            flag_cleared = interpret('The Torch identification file has been removed.',
                silent=False)
            restart_instruction = interpret('Please close this window and restart FooocusPlus. The launcher will automatically install PyTorch and its dependencies on startup.', silent=False)

            msg = (
                f"### **{header_success}**\n\n"
                f"{flag_cleared}\n\n"
                f"{restart_instruction}"
            )
        except Exception as e:
            header_error = interpret('Error', silent=True)
            fail_msg = interpret('Failed to remove "torch_base.txt":', silent=True)
            msg = f"### **{header_error}**\n\n{fail_msg} {e}"
    else:
        header_status = interpret('Status', silent=True)
        already_cleared = interpret('The "torch_base.txt" file has already been removed. ', restart_instruction, silent=True)
        msg = f"### **{header_status}**\n\n{already_cleared}"

    # Return exactly 6 elements to match the unified outputs array
    return (
        gr.update(visible=True),                                 # perf_modal_box (Keep visible)
        gr.update(value=msg),                                     # perf_modal_header_msg
        gr.update(visible=False),                                 # perf_modal_metrics_msg (Hide metrics on success)
        gr.update(visible=True),                                  # perf_ok_btn (Show bottom OK to close)
        gr.update(visible=False),                                 # perf_upgrade_btn
        gr.update(visible=False)                                  # perf_cancel_btn
    )


def close_performance_modal():
    """
    Hides the performance modal.
    """
    return gr.update(visible=False)


def show_remove_torch_confirm():
    """
    Triggers the confirmation dialog warning
    the user of the impending deletion.
    """
    header = interpret('Reconfigure PyTorch Components', silent=True)
    warning_text = interpret('Warning: This will uninstall PyTorch, TorchVision, TorchAudio, xFormers, and related dependencies from the Python environment.', silent=True)
    ask_proceed = interpret('Do you want to proceed?', silent=True)

    msg = (
        f"### **{header}**\n\n"
        f"**{warning_text}**\n\n"
        f"**{ask_proceed}**\n\n"
        f'<div style="height: 5px;"></div>'  # Standardized 5px spacer
    )
    return (
        gr.update(visible=True),   # remove torch_modal_box
        gr.update(value=msg),      # remove torch_modal_msg
        gr.update(visible=True),   # remove torch_proceed_btn
        gr.update(visible=True,
            value='Cancel'),       # remove torch_cancel_btn
        gr.update(visible=False)   # perf_modal_box
    )


def execute_remove_torch_components():
    """
    Deletes the torch_base.txt identification
    file so that launch.py will cleanly wipe
    and reinstall the dynamic Torch components
    on the next startup.
    """
    torch_base_path = get_torch_base_path()
    if torch_base_path.exists():
        try:
            torch_base_path.unlink()
            print()
            interpret('[UI Util] Removed the Torch identification file:',f'"torch_base.txt"')
            interpret('Please close this window and restart FooocusPlus!')
            print()
        except Exception as e:
            interpret('[UI Util] Warning: Failed to remove', f'"torch_base.txt": {e}')

    # Formulate translated success message
    header_success = interpret('Removal Scheduled',
        silent=True)
    restart_instruction = interpret('The Torch identification file has been removed. Please close this window and restart FooocusPlus. The launcher will automatically install PyTorch and its dependencies on startup.', silent=True)

    msg = (
        f"### **{header_success}**\n\n"
        f"{restart_instruction}\n\n"
        f'<div style="height: 5px;"></div>'
    )

    return (
        gr.update(value=msg),     # remove torch_modal_msg
        gr.update(visible=False), # remove torch_proceed_btn
        gr.update(visible=True,
            value='OK'), # change torch_cancel_btn to "OK"
        gr.update(visible=False), # perf_modal_box
        gr.update(visible=False), # perf_button
    )


def close_remove_torch_modal():
    """
    Hides the remove torch modal.
    """
    return gr.update(visible=False)
