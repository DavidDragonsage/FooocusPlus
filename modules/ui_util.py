import os
import gradio as gr
import time
import common
import ldm_patched.modules.model_management as model_management
import modules.async_worker as worker
import modules.config as config
import modules.html

from enhanced.translator import interpret, interpret_info
from modules.flags import inpaint_option_detail, inpaint_option_modify
from modules.util import cleanup_temp_files, save_image_grid


batch_counter = 0

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
    yield gr.update(visible=True, value=modules.html.make_progress_html(1, status_msg)), \
        gr.update(visible=True, value=None), \
        gr.update(visible=False, value=None), \
        gr.update(visible=False)

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
                yield gr.update(visible=True, value=modules.html.make_progress_html(percentage, title)), \
                    gr.update(visible=True, value=image) if image is not None else gr.update(), \
                    gr.update(), \
                    gr.update(visible=False)
            if flag == 'results':
                yield gr.update(visible=True), \
                    gr.update(visible=True), \
                    gr.update(visible=True, value=product), \
                    gr.update(visible=False)
            if flag == 'finish':
                product = sort_enhance_images(product, task)

                yield gr.update(visible=False), \
                    gr.update(visible=False), \
                    gr.update(visible=True, value=product), \
                    gr.update(visible=False)
                update_batch_counter()
                finished = True

                # delete Fooocus temp images, only keep gradio temp images
                if config.disable_image_log:
                    for filepath in product:
                        if isinstance(filepath, str) and os.path.exists(filepath):
                            os.remove(filepath)

    execution_time = time.perf_counter() - execution_start_time
    interpret('Total time in seconds:', f'{execution_time:.2f}')

    if config.default_generate_image_grid:
        # only make UI announcement if several grids are being created:
        if common.batch_count > 1:
            save_image_grid(True)
        else:
            save_image_grid(False)
    return


def inpaint_mode_change(mode, inpaint_engine_version):

    # inpaint_additional_prompt, outpaint_selections, example_inpaint_prompts,
    # inpaint_disable_initial_latent, inpaint_engine,
    # inpaint_strength, inpaint_respective_field

    if mode == inpaint_option_detail:
        return [
            gr.update(visible=True), gr.update(visible=False, value=[]),
            gr.Dataset.update(visible=True, samples=config.example_inpaint_prompts),
            False, 'None', 0.5, 0.0
        ]

    if inpaint_engine_version == 'empty' or inpaint_engine_version == None or not inpaint_engine_version:
            inpaint_engine_version = config.default_inpaint_engine_version
            if inpaint_engine_version == None or not inpaint_engine_version:
                inpaint_engine_version = 'v2.6'

    if mode == inpaint_option_modify:
        return [
            gr.update(visible=True), gr.update(visible=False, value=[]),
            gr.Dataset.update(visible=False, samples=config.example_inpaint_prompts),
            True, inpaint_engine_version, 1.0, 0.0
        ]

    return [
        gr.update(visible=False, value=''), gr.update(visible=True),
        gr.Dataset.update(visible=False, samples=config.example_inpaint_prompts),
        False, inpaint_engine_version, 1.0, 0.618
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
