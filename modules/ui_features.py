import sys
import subprocess
import socket
import time
import webbrowser
from pathlib import Path

import backend_base.comfyd as comfyd
import common
import modules.user_structure as US
from enhanced.translator import interpret

# Track the active developer process globally
standalone_process = None

# new features for the UI
def control_notification(enable_notification):
    if enable_notification:
        masters_path = Path('masters').resolve()
        master_audio_path = Path(masters_path/'master_audio/notification.mp3')
        US.mkdir_copy_file(master_audio_path, Path.cwd())
        user_audio_path = Path(US.user_path/'user_audio')
        US.make_dir(user_audio_path)
        random_source_file = US.random_file_copy(user_audio_path, Path.cwd(), 'notification.mp3')
        if not random_source_file:
            random_source_file = 'notification.mp3'
        interpret('[Features] Enabled audio notification using:', random_source_file)
    else:
        interpret('[Features] Disabled audio notification')
    return


def add_to_favorites(preset_file, category_selection):
    preset_file = f'{preset_file}.json'
    master_presets_path = Path('masters/master_presets')
    source_file = Path(master_presets_path/category_selection/preset_file)
    dest_dir = Path(US.user_path/f'user_presets/Favorite')
    success = US.mkdir_copy_file(source_file, dest_dir)
    if success:
        interpret('[Features] Added to favorites:', preset_file)
    else:
        interpret('[Features] Could not add to favorites:', preset_file)
    return

def remove_from_favorites(preset_file):
    source_file = Path(US.user_path/f'user_presets/Favorite/{preset_file}.json')
    dest_dir = Path(US.user_path/f'user_presets/Old Favorites')
    success = US.move_file(source_file, dest_dir)
    if success:
        interpret('[Features] Removed from favorites:', preset_file)
        interpret('and saved it to', dest_dir)
    else:
        interpret('[Features] Could not remove from favorites:', preset_file)
    return success


def launch_standalone_comfy():
    """Stops the internal daemon and spawns
    a standalone developer ComfyUI canvas."""
    global standalone_process

    # 1. Stop the internal comfyd daemon to free VRAM
    try:
        interpret('[Features] Stopping internal Comfy daemon to release VRAM...')
        comfyd.stop()
    except Exception as e:
        interpret(f'[Features] Warning: Failed to stop internal Comfy cleanly: {str(e)}')

    # 2. Use the comfyd port finder, starting at 8190 for the developer canvas
    port = comfyd.find_free_port(8190)
    # Update shared config for client API matching
    common.comfy_port = port

    # 3. Locate paths cleanly using pathlib.Path
    root_path = Path(common.ROOT)
    comfy_script = root_path.joinpath('comfy', 'main.py')
    python_exe = root_path.parent.joinpath('python_embedded', 'python.exe')

    # Fallback for Linux or non-embedded Python environments
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    # 4. Construct a universal, separate database URL to prevent SQLite locking conflicts
    gateway_db_path = root_path.joinpath('comfy', 'user', 'comfyui_gateway.db')

    # Ensure the parent directory (user/) exists before SQLite attempts file creation
    gateway_db_path.parent.mkdir(parents=True, exist_ok=True)

    # Format to posix style (e.g. sqlite:///E:/FooocusPlus-Dev/FooocusPlusAI/comfy/user/comfyui_gateway.db)
    db_url = f'sqlite:///{gateway_db_path.as_posix()}'

    # 5. Launch the standalone ComfyUI process, bound to local loopback and the unique DB URL
    interpret(f'[Features] Launching standalone developer ComfyUI on port {port}...')
    try:
        standalone_process = subprocess.Popen(
            [
                str(python_exe), str(comfy_script),
                '--port', str(port),
                '--listen', '127.0.0.1',
                '--database-url', db_url
            ],
            cwd=str(root_path.joinpath('comfy'))
        )

        # 6. Wait for the web server to start up
        # before opening the browser
        interpret('[Features] Waiting for ComfyUI web server to initialize...')
        server_ready = False
        for _ in range(30):  # Try for up to 15 seconds (30 * 0.5s)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                # connect_ex returns 0 if the port is open and listening
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    server_ready = True
                    break
            time.sleep(0.5)

        # Early return check: If the server is not ready,
        # do not open a dead tab
        if not server_ready:
            interpret(f'[Features] Warning: ComfyUI server did not respond on port {port} in time.')
            return interpret(
                f'### ❌ Launch Failed\n\n'
                f'The ComfyUI server failed to respond on port {port} within the 15-second timeout.\n\n'
                f'Please check the terminal console for any PyTorch, model loading, or Python initialization errors.'
            )

        # 7. Open browser tab only when the server
        # is verified as active and listening
        url = f'http://127.0.0.1:{port}'
        webbrowser.open_new_tab(url)
        return interpret(
            f'### 🔧 Developer Gateway Active\n\n'
            f'The standalone ComfyUI workspace is now running at **{url}**.\n\n'
            f'The internal Comfy generator is suspended to release some GPU memory (VRAM). '
            f'Use the opened browser tab to design workflows, etc.\n\n'
            f"When you are finished, click the button to release the standalsone session's resources and restore normal FooocusPlus operation.\n\n"
            f'You will need to manually close its tab.\n\n'
        )

    except Exception as e:
        return f'[Features] Failed to launch developer gateway: {str(e)}'


def stop_standalone_comfy():
    """Kills the standalone developer canvas process to prepare for FooocusPlus generation."""
    global standalone_process
    if standalone_process is not None:
        try:
            interpret('[Features] Terminating standalone ComfyUI process...')
            standalone_process.terminate()
            standalone_process.wait()
        except Exception as e:
            interpret(f'[Features] Warning: Failed to terminate standalone process cleanly: {str(e)}')
        standalone_process = None
    return 'Developer Gateway stopped. Internal generator is ready to resume.'
