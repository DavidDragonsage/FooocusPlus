import os
import sys
import hashlib
import requests
import json
import time
from datetime import datetime
from pathlib import Path

print('Loading the LoRA Trigger Finder...')

ROOT = Path(__file__).parent
sys.path.append(str(ROOT))
os.chdir(ROOT)

import modules.user_structure as US


# LoRA Trigger and Thumbnail retriever by Taffy Carl
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

def get_thumbnail_url(model_data):
    """Extract thumbnail URL from model images, preferring the first available image."""
    images = model_data.get("images", [])
    for image in images:
        if image.get("url"):
            return image["url"]
    return "No thumbnail available"

def scan_lora_files(folder_path):
    """Scan folder and subfolders for .safetensors files and retrieve LoRA info."""
    lora_data = []

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
                    thumbnail_url = get_thumbnail_url(model_info)

                    lora_data.append({
                        "file_name": file,
                        "file_path": file_path,
                        "base_model": base_model,
                        "trigger_words": trigger_words,
                        "thumbnail_url": thumbnail_url
                    })

                # Respect Civitai API rate limit
                time.sleep(1)

    # Sort by file_name alphabetically
    lora_data.sort(key=lambda x: x["file_name"].lower())

    return lora_data

def save_to_json(data, output_path):
    """Save data to JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def save_to_html(data, output_path):
    """Save data to HTML file with 150px thumbnails."""
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
        img { max-width: 150px; height: auto; display: block; }
    </style>
</head>
<body>
    <h1>LoRA Model Information</h1>
    <table>
        <tr>
            <th>Base Model</th>
            <th>File Name</th>
            <th>File Path</th>
            <th>Trigger Words</th>
            <th>Thumbnail</th>
        </tr>
"""
    for item in data:
        trigger_words = ", ".join(item["trigger_words"]) if item["trigger_words"] else "None"
        thumbnail = f'<img src="{item["thumbnail_url"]}" alt="Thumbnail">' if item["thumbnail_url"] != "No thumbnail available" else "No thumbnail"
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
    print(f'config.paths_loras(0) {config.paths_loras(0)}')
    folder_path = Path(config.paths_loras(0))
    user_dir = Path(current_dir.resolve().parent/'UserDir'))
    output_folder = Path(user_dir/"lora_trigger_data")

    # Create output folder if it doesn't exist
    US.make_dir(output_folder)
    print(f'Main 1 {main}')

    # Generate output file names with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_json = os.path.join(output_folder, f"lora_info_{timestamp}.json")
    output_html = os.path.join(output_folder, f"lora_info_{timestamp}.html")
    output_txt = os.path.join(output_folder, f"lora_info_{timestamp}.txt")

    # Scan for LoRA files and retrieve info
    lora_data = scan_lora_files(folder_path)

    if not lora_data:
        print("No LoRA models found or no valid data retrieved.")
        return

    # Save to JSON
    save_to_json(lora_data, output_json)
    print(f"Data saved to {output_json}")

    # Save to HTML
    save_to_html(lora_data, output_html)
    print(f"Data saved to {output_html}")

    # Save to TXT
    save_to_txt(lora_data, output_txt)
    print(f"Data saved to {output_txt}")

if __name__ == "__main__":
    main()
