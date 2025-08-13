import os
import hashlib
import requests
import time
from datetime import datetime
from PIL import Image
from io import BytesIO

print('Loading the LoRA Trigger Finder...')
ROOT = Path(__file__).parent
sys.path.append(str(ROOT))
os.chdir(ROOT)

import modules.user_structure as US


# LoRA Trigger and Thumbnail retriever by Taffy Carl. Downloads Triggers, Thumbnails that are converted to png and mp4 files that can't be converted.
def calculate_sha256(file_path):
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_civitai_model_info(file_hash):
    """Fetch model info from Civitai API using file hash."""
    base_url = "https://civitai.com/api/v1/model-versions/by-hash/"
    url = f"{base_url}{file_hash}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for hash {file_hash}: {e}")
        return None

def download_thumbnail(url, output_path, is_video=False, size=(150, 150)):
    """Download thumbnail; resize if image, save directly if video."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        if is_video:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            img = Image.open(BytesIO(response.content))
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(output_path, "PNG", quality=85)
            return True
    except Exception as e:
        print(f"Error downloading{'/resizing' if not is_video else ''} thumbnail from {url}: {e}")
        return False

def get_thumbnail_url(model_data, thumbnail_folder, file_name):
    """Extract thumbnail URL and save image or video locally."""
    images = model_data.get("images", [])
    for image in images:
        if image.get("url"):
            url = image["url"]
            is_video = url.lower().endswith(".mp4")
            thumbnail_filename = f"{os.path.splitext(file_name)[0]}{'.mp4' if is_video else '.png'}"
            thumbnail_path = os.path.join(thumbnail_folder, thumbnail_filename)
            if download_thumbnail(url, thumbnail_path, is_video):
                return thumbnail_filename
    return "No thumbnail available"

def scan_lora_files(folder_path, thumbnail_folder, not_found_file):
    """Scan folder and subfolders for .safetensors files and retrieve LoRA info."""
    lora_data = []
    not_found_files = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".safetensors"):
                file_path = os.path.join(root, file)
                print(f"Processing {file_path}...")

                # Calculate SHA-256 hash
                file_hash = calculate_sha256(file_path)

                # Fetch model info from Civitai
                model_info = get_civitai_model_info(file_hash)

                if model_info:
                    # Extract relevant data
                    base_model = model_info.get("baseModel", "Unknown")
                    trigger_words = model_info.get("trainedWords", [])
                    thumbnail_filename = get_thumbnail_url(model_info, thumbnail_folder, file)

                    lora_data.append({
                        "file_name": file,
                        "file_path": file_path,
                        "base_model": base_model,
                        "trigger_words": trigger_words,
                        "thumbnail_filename": thumbnail_filename
                    })
                else:
                    not_found_files.append(file_path)

                # Respect Civitai API rate limit
                time.sleep(1)

    # Sort by file_name alphabetically
    lora_data.sort(key=lambda x: x["file_name"].lower())

    # Save not found files to TXT
    if not_found_files:
        with open(not_found_file, "w", encoding="utf-8") as f:
            f.write("LoRA Files Not Found in Civitai API\n")
            f.write("=" * 50 + "\n\n")
            for file_path in not_found_files:
                f.write(f"{file_path}\n")
        print(f"Not found LoRA files saved to {not_found_file}")

    return lora_data

def save_to_html(data, output_path, thumbnail_folder):
    """Save data to HTML file with 150px thumbnails or videos."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LoRA Model Information</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        h1 { color: #333; }
        img, video { max-width: 150px; height: auto; display: block; }
    </style>
</head>
<body>
    <h1><p align=center>LoRA Model Information</p></h1>
    <table>
        <tr>
            <th><p align=center>Base Model</p></th>
            <th><p align=center>LoRA Name</p></th>
            <th><p align=center>Local Path</p></th>
            <th><p align=center>Trigger Words</p></th>
            <th><p align=center>Thumbnail</p></th>
        </tr>
"""
    for item in data:
        trigger_words = ", ".join(item["trigger_words"]) if item["trigger_words"] else "None"
        if item["thumbnail_filename"] != "No thumbnail available":
            if item["thumbnail_filename"].endswith(".mp4"):
                thumbnail = f'<video controls src="{os.path.join(thumbnail_folder, item["thumbnail_filename"])}"></video>'
            else:
                thumbnail = f'<img src="{os.path.join(thumbnail_folder, item["thumbnail_filename"])}" alt="Thumbnail">'
        else:
            thumbnail = "No thumbnail"
        html_content += f"""        <tr>
            <td>{item["base_model"]}</td>
            <td>{item["file_name"]}</td>
            <td>{item["file_path"]}</td>
            <td>{trigger_words}</td>
            <td>{thumbnail}</td>
        </tr>
"""
    html_content += """    </table>
</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

def save_to_txt(data, output_path):
    """Save data to TXT file, excluding thumbnail URL."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("LoRA Model Information\n")
        f.write("=" * 50 + "\n\n")
        for item in data:
            trigger_words = ", ".join(item["trigger_words"]) if item["trigger_words"] else "None"
            f.write(f"Base Model: {item['base_model']}\n")
            f.write(f"File Name: {item['file_name']}\n")
            f.write(f"File Path: {item['file_path']}\n")
            f.write(f"Trigger Words: {trigger_words}\n")
            f.write("-" * 50 + "\n")

def main():
    # Specify the folder to scan and output folder (modify these paths as needed)
    user_dir = Path(current_dir.resolve().parent/'UserDir'))
    output_folder = Path(user_dir/"lora_trigger_data")
    thumbnail_folder = Path(user_dir/"lora_thumbnails")

    # Create output and thumbnail folders if it doesn't exist
    US.make_dir(output_folder)
    US.make_dir(thumbnail_folder)

    # Generate output file names
    output_html = Path(output_folder/"lora_triggers.html")
    output_txt = Path(output_folder/"lora_triggers.txt")
    not_found_file = Path(output_folder/"lora_not_found.txt")

    # Scan for LoRA files and retrieve info
    lora_data = scan_lora_files(folder_path, thumbnail_folder, not_found_file)

    if not lora_data:
        print("No LoRA models found or no valid data retrieved.")
        return

    # Save to HTML
    save_to_html(lora_data, output_html, thumbnail_folder)
    print(f"Data saved to {output_html}")

    # Save to TXT
    save_to_txt(lora_data, output_txt)
    print(f"Data saved to {output_txt}")

if __name__ == "__main__":
    main()
