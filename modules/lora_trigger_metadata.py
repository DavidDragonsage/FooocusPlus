import os
import hashlib
import requests
import json
import time
from datetime import datetime
from pathlib import Path

# LoRA Trigger and Thumbnail retriever by Taffy Carl
# thumbnails are not used in this integrated version

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
    folder_path = r"C:\Users\AI\models\loras"
    output_folder = r"C:\Users\AI\lora_triggers"

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Generate output file names with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_json = os.path.join(output_folder, f"lora_info_{timestamp}.json")
    output_txt = os.path.join(output_folder, f"lora_info_{timestamp}.txt")

    # Scan for LoRA files and retrieve info
    lora_data = scan_lora_files(folder_path)

    if not lora_data:
        print("No LoRA models found or no valid data retrieved.")
        return

    # Save to JSON
    save_to_json(lora_data, output_json)
    print(f"Data saved to {output_json}")

    # Save to TXT
    save_to_txt(lora_data, output_txt)
    print(f"Data saved to {output_txt}")

if __name__ == "__main__":
    main()
