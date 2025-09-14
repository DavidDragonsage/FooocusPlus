import os
from enhanced.translator import interpret
from urllib.parse import urlparse
from typing import Optional


def load_file_from_url(
        url: str,
        *,
        model_dir: str,
        progress: bool = True,
        file_name: Optional[str] = None,
) -> str:
    # this line traps LowVRAMdef when used as the default preset
    if url.find('segmind-vega.safetensors') != -1: return ''
    """Download a file from `url` into `model_dir`, using the file present if possible.
    Returns the path to the downloaded file.
    The HF_MIRROR processing at Lines 19 & 20 may be causing more harm than good
    """
    domain = os.environ.get("HF_MIRROR", "https://huggingface.co").rstrip('/')
    url = str.replace(url, "https://huggingface.co", domain, 1)
    os.makedirs(model_dir, exist_ok=True)
    if not file_name:
        parts = urlparse(url)
        file_name = os.path.basename(parts.path)
    cached_file = os.path.abspath(os.path.join(model_dir, file_name))
    if not os.path.exists(cached_file):
        interpret('Downloading:', url + ' → ' + cached_file)
        from torch.hub import download_url_to_file
        try:
                download_url_to_file(url, cached_file, progress=progress)
        except:
                interpret('Could not download', cached_file)
                interpret('It may need to be downloaded manually from', url)
                print()
    return cached_file
