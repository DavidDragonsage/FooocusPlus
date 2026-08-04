import os  # Strictly used only for os.environ environment variable checks
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional
from enhanced.translator import interpret, \
    interpret_info, interpret_warn


def load_file_from_url(
        url: str,
        *,
        model_dir: str,
        progress: bool = True,
        file_name: Optional[str] = None,
) -> str:
    # this line traps LowVRAMdef when used as the default preset
    if url.find('segmind-vega.safetensors') != -1:
        return ''

    """Download a file from `url` into `model_dir`, using the file present if possible.
    Returns the path to the downloaded file.
    """
    # 1. Resolve Hugging Face Mirror environment configurations
    domain = os.environ.get('HF_MIRROR', 'https://huggingface.co').rstrip('/')
    url = str.replace(url, 'https://huggingface.co', domain, 1)

    # 2. Resolve paths using pathlib.Path (No os for file operations)
    model_path_dir = Path(model_dir)
    model_path_dir.mkdir(parents=True, exist_ok=True)

    if not file_name:
        parts = urlparse(url)
        file_name = Path(parts.path).name

    cached_file = (model_path_dir / file_name).resolve()

    # 3. If the file is missing from your drive, initiate the download
    if not cached_file.exists():
        # Print the UI popup and console warnings EXACTLY ONCE here
        interpret_info('[Loader] Downloading:', url + ' → ' + str(cached_file))
        interpret('Please wait for the download to complete.')
        interpret_warn('Please wait for the download to complete. Progress can be checked in the console window.', silent=True)

        is_hf = 'huggingface.co' in url or (domain != 'https://huggingface.co' and domain in url)
        hf_download_success = False

        # --- AUTOMATED HUGGING FACE LFS/XET INTERCEPTOR ---
        if is_hf:
            try:
                from huggingface_hub import hf_hub_download

                # Parse the repo_id from the URL string, respecting custom mirror domains
                parts = url.split(domain + '/')
                if len(parts) > 1:
                    separator = '/resolve/' if '/resolve/' in parts[1] else '/blob/'
                    sub_parts = parts[1].split(separator)
                    if len(sub_parts) > 1:
                        repo_id = sub_parts[0]

                        # Execute the secure, automated download
                        hf_hub_download(
                            repo_id=repo_id,
                            filename=file_name,
                            local_dir=str(model_path_dir)
                        )
                        interpret_info('[Loader] Successfully downloaded:', file_name)
                        print()
                        hf_download_success = True
            except Exception as e:
                # If hf_hub_download fails (or is missing), print warning to console and fallback
                print(f'[Loader] Warning: hf_hub_download failed. Falling back to standard downloader: {e}')

        # --- ORIGINAL FALLBACK DOWNLOADER (Using torch.hub) ---
        # Runs only if the hf_hub download was skipped or failed
        if not hf_download_success:
            from torch.hub import download_url_to_file
            try:
                download_url_to_file(url, str(cached_file), progress=progress)
            except Exception:
                interpret_info('Could not download', str(cached_file))
                interpret_warn('It may need to be downloaded manually from', url)
                print()

    return str(cached_file)