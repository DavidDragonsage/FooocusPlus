# Extracts metadata from .safetensors files with optional Civitai API integration.
# Designed for integration into FooocusPlus (https://github.com/DavidDragonsage/FooocusPlus).
# Thanks to the Pure Fooocus AI Facebook group (https://www.facebook.com/groups/fooocus)
# for testing and feedback.
#Taffy Carl

import os
import json
import struct
import logging
import hashlib
import requests
import time
import args_manager as args
import modules.config as config
import modules.user_structure as US
from datetime import datetime
from PIL import Image
from io import BytesIO
from pathlib import Path
# from enhanced.translator import interpret


class LoraMetadataExtractor:
    def __init__(self, lora_dir, output_dir, debug=False):
        """
        Initialize the LoRA metadata extractor.

        Args:
            lora_dir (str): Directory containing .safetensors files (e.g., UserDir/models/loras).
            output_dir (str): Directory to save JSON metadata files and thumbnails.
            debug (bool): Enable debug logging to output_dir/debug_log.txt.
        """
        self.lora_dir = lora_dir
        self.output_dir = output_dir
        self.debug = debug
        self.logger = self._setup_logging()
        self.metadata_dir = os.path.join(output_dir, "metadata")
        self.thumbnail_dir = os.path.join(output_dir, "thumbnails")
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.thumbnail_dir, exist_ok=True)

    def _setup_logging(self):
        """Set up logging to file and console if debug is enabled."""
        logger = logging.getLogger("LoraMetadataExtractor")
        logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")

        # File handler
        os.makedirs(self.output_dir, exist_ok=True)
        log_file = os.path.join(self.output_dir, "debug_log.txt")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler
        if self.debug:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger

    def _calculate_sha256(self, file_path):
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash for {file_path}: {e}")
            return f"Error: {e}"

    def _extract_safetensors_metadata(self, file_path):
        """Extract metadata from a .safetensors file."""
        try:
            with open(file_path, 'rb') as f:
                header_size_data = f.read(8)
                if len(header_size_data) < 8:
                    self.logger.error(f"Invalid header size in {file_path}")
                    return None
                header_size = struct.unpack('<Q', header_size_data)[0]
                header_data = f.read(header_size)
                if len(header_data) < header_size:
                    self.logger.error(f"Incomplete header in {file_path}")
                    return None
                header_str = header_data.decode('utf-8')
                header = json.loads(header_str)
                metadata = header.pop('__metadata__', {})
                self.logger.debug(f"Extracted metadata from {file_path}: {list(metadata.keys())}")
                return metadata
        except Exception as e:
            self.logger.error(f"Error extracting metadata from {file_path}: {e}")
            return None

    def _infer_base_model(self, metadata):
        """Infer base model from metadata fields."""
        base_model_fields = ['ss_base_model_name', 'ss_sd_model_name', 'ss_network_module']
        for field in base_model_fields:
            if field in metadata:
                return metadata[field]
        return "Unknown"

    def _infer_trigger_words(self, metadata):
        """Infer trigger words from metadata fields."""
        if 'ss_tag_frequency' in metadata:
            try:
                tag_freq = json.loads(metadata['ss_tag_frequency'])
                if isinstance(tag_freq, dict):
                    return list(tag_freq.keys())
                elif isinstance(tag_freq, list):
                    return tag_freq
            except json.JSONDecodeError:
                self.logger.debug(f"Failed to parse ss_tag_frequency: {metadata['ss_tag_frequency']}")
                return [metadata['ss_tag_frequency']] if metadata['ss_tag_frequency'] else []
        if 'ss_output_name' in metadata:
            return [metadata['ss_output_name']]
        return []

    def _download_thumbnail(self, url, output_path, is_video=False):
        """Download and resize thumbnail to 150px height."""
        if os.path.exists(output_path):
            self.logger.debug(f"Thumbnail already exists: {output_path}")
            return True
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            if is_video:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                # Resize video thumbnail (create a still)
                try:
                    img = Image.open(BytesIO(response.content))
                    h_percent = 150 / float(img.size[1])
                    w_size = int(float(img.size[0]) * float(h_percent))
                    img = img.resize((w_size, 150), Image.Resampling.LANCZOS)
                    img.save(output_path.replace(".mp4", ".png"), "PNG", quality=85)
                    self.logger.debug(f"Converted video thumbnail to PNG: {output_path.replace('.mp4', '.png')}")
                except Exception as e:
                    self.logger.warning(f"Could not resize video thumbnail {output_path}: {e}")
                self.logger.debug(f"Downloaded video thumbnail: {output_path}")
                return True
            else:
                img = Image.open(BytesIO(response.content))
                h_percent = 150 / float(img.size[1])
                w_size = int(float(img.size[0]) * float(h_percent))
                img = img.resize((w_size, 150), Image.Resampling.LANCZOS)
                img.save(output_path, "PNG", quality=85)
                self.logger.debug(f"Downloaded and resized image thumbnail: {output_path}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to download thumbnail from {url}: {e}")
            return False

    def _fetch_civitai_metadata(self, file_hash, file_name):
        """Fetch metadata and thumbnail from Civitai API using SHA256 hash."""
        base_url = "https://civitai.com/api/v1/model-versions/by-hash/"
        url = f"{base_url}{file_hash}"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            self.logger.debug(f"Fetched Civitai data for hash {file_hash}: {data.get('id')}")

            # Extract relevant fields
            civitai_info = {
                "civitai_model_id": data.get("modelId"),
                "civitai_version_id": data.get("id"),
                "civitai_base_model": data.get("baseModel", "Unknown"),
                "civitai_trigger_words": data.get("trainedWords", []),
                "civitai_description": data.get("description", ""),
                "civitai_clip_skip": data.get("clipSkip", None),
                "civitai_images": []
            }

            # Download thumbnail
            thumbnail_filename = "changeme.jpg"
            images = data.get("images", [])
            if images:
                for img in images:
                    url = img.get("url")
                    if not url:
                        continue
                    is_video = url.lower().endswith(".mp4")
                    ext = ".mp4" if is_video else ".png"
                    thumbnail_filename = f"{os.path.splitext(file_name)[0]}{ext}"
                    thumbnail_path = os.path.join(self.thumbnail_dir, thumbnail_filename)
                    if self._download_thumbnail(url, thumbnail_path, is_video):
                        civitai_info["civitai_images"].append({
                            "url": url,
                            "width": img.get("width"),
                            "height": img.get("height"),
                            "hasPrompt": img.get("hasPositivePrompt", False),
                            "local_path": thumbnail_path
                        })
                        break  # Use first valid image/video
            else:
                self.logger.debug(f"No images found in Civitai data for {file_name}")

            return civitai_info, thumbnail_filename
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching Civitai metadata for {file_hash}: {e}")
            return None, "changeme.jpg"
        except Exception as e:
            self.logger.error(f"Unexpected error in Civitai fetch for {file_hash}: {e}")
            return None, "changeme.jpg"

    def _save_lora_metadata(self, item):
        """Save metadata for a single LoRA to a JSON file."""
        file_name = item["file_name"]
        json_filename = f"{os.path.splitext(file_name)[0]}.json"
        json_path = os.path.join(self.metadata_dir, json_filename)
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(item, f, indent=4)
            self.logger.debug(f"Saved metadata to {json_path}")
            return json_filename
        except Exception as e:
            self.logger.error(f"Failed to save {json_path}: {e}")
            return None

    def extract_metadata(self):
        """
        Scan lora_dir for .safetensors files and extract metadata.
        Saves each LoRA's metadata to a separate JSON file in output_dir/metadata/.
        Returns a list of dictionaries with LoRA details.
        """
        self.logger.info("Starting metadata extraction...")
        self.logger.info("Note: This script does not modify .safetensors files.")
        if not os.path.isdir(self.lora_dir):
            self.logger.error(f"Invalid LoRA directory: {self.lora_dir}")
            return []
        if not os.path.isdir(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            self.logger.info(f"Created output directory: {self.output_dir}")

        # Load existing JSON data to avoid reprocessing
        existing_data = {}
        for root, _, files in os.walk(self.metadata_dir):
            for name in files:
                if name.lower().endswith(".json"):
                    json_path = os.path.join(root, name)
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            item = json.load(f)
                            if "file_path" in item:
                                existing_data[os.path.normcase(os.path.normpath(item["file_path"]))] = item
                        self.logger.debug(f"Loaded existing metadata from {json_path}")
                    except Exception as e:
                        self.logger.error(f"Failed to load {json_path}: {e}")

        # Scan for .safetensors files
        files = []
        for root, _, fs in os.walk(self.lora_dir):
            for name in fs:
                if name.lower().endswith(".safetensors"):
                    files.append(os.path.join(root, name))
        self.logger.info(f"Found {len(files)} .safetensors files")

        metadata_list = []
        for file_path in files:
            try:
                file_name = os.path.basename(file_path)
                normalized_path = os.path.normcase(os.path.normpath(file_path))

                # Check if file is already processed
                if normalized_path in existing_data:
                    self.logger.debug(f"Using cached data for {file_path}")
                    metadata_list.append(existing_data[normalized_path])
                    continue

                # Calculate hash
                file_hash = self._calculate_sha256(file_path)

                # Extract safetensors metadata
                metadata = self._extract_safetensors_metadata(file_path) or {}

                # Infer base model and trigger words from local metadata
                base_model = self._infer_base_model(metadata)
                trigger_words = self._infer_trigger_words(metadata)

                # Fetch Civitai metadata and thumbnail
                thumbnail_filename = "changeme.jpg"
                civitai_info = None
                if isinstance(file_hash, str) and len(file_hash) == 64 and all(c in '0123456789abcdefABCDEF' for c in file_hash):
                    civitai_info, thumbnail_filename = self._fetch_civitai_metadata(file_hash, file_name)
                    if civitai_info:
                        # Override with Civitai data if available
                        base_model = civitai_info.get("civitai_base_model", base_model)
                        trigger_words = civitai_info.get("civitai_trigger_words", trigger_words)
                    time.sleep(1)  # 1-second delay to avoid overwhelming Civitai API

                # Store data
                item = {
                    "file_name": file_name,
                    "file_path": file_path,
                    "file_hash": file_hash,
                    "base_model": base_model,
                    "trigger_words": trigger_words,
                    "thumbnail_filename": thumbnail_filename,
                    "metadata": metadata,
                    "civitai_info": civitai_info
                }

                # Save to individual JSON file
                json_filename = self._save_lora_metadata(item)
                if json_filename:
                    item["metadata_filename"] = json_filename

                metadata_list.append(item)
                self.logger.info(f"Processed {file_name}")
            except Exception as e:
                self.logger.error(f"Error processing {file_path}: {e}")
                item = {
                    "file_name": file_name,
                    "file_path": file_path,
                    "file_hash": f"Error: {e}",
                    "base_model": "Unknown",
                    "trigger_words": [],
                    "thumbnail_filename": "changeme.jpg",
                    "metadata": {},
                    "civitai_info": None,
                    "metadata_filename": None
                }
                json_filename = self._save_lora_metadata(item)
                if json_filename:
                    item["metadata_filename"] = json_filename
                metadata_list.append(item)

        # Sort by file name
        metadata_list.sort(key=lambda x: x["file_name"].lower())

        return metadata_list

def main():
    """Example usage of LoraMetadataExtractor."""
    print(f'Processing LoRAs from {config.paths_loras[0]}')
    lora_dir = Path(config.paths_loras[0])
    user_dir = Path(args.args.user_dir)
    output_dir = Path(user_dir/"lora_trigger_data")

    # Create output folder if it doesn't exist
    US.make_dir(output_dir)

#    lora_dir = "UserDir/models/loras"  # FooocusPlus's model directory
#    output_dir = "UserDir/triggerwords"  # FooocusPlus's triggerword directory
    extractor = LoraMetadataExtractor(lora_dir, output_dir, debug=False)
    metadata = extractor.extract_metadata()
    print(f"Extracted metadata for {len(metadata)} LoRA models:")
    for item in metadata:
        triggers = ', '.join(item['trigger_words'])
        print(f"- {item['file_name']}: {item['base_model']}, Triggers: {triggers}")
        if item.get('civitai_info'):
            print(f"  Civitai ID: {item['civitai_info'].get('civitai_model_id')}, Name: {item['civitai_info'].get('civitai_description')[:50]}...")
            if item['civitai_info'].get('civitai_images'):
                print(f"  Thumbnail: {item['thumbnail_filename']}")
        if item.get('metadata_filename'):
            print(f"  Metadata File: {item['metadata_filename']}")

if __name__ == "__main__":
    main()