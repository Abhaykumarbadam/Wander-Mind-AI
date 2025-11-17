from typing import List, Dict, Tuple
import os
from .utils import list_json_files, load_json_file, normalize_country_record
from loguru import logger


def load_and_flatten(data_dir: str) -> List[Dict]:
    """Load JSON files and convert to list of (text, metadata) entries.

    Each high-level key/value pair becomes a separate text chunk so we can
    embed and retrieve by concept/category.
    """
    file_paths = list_json_files(data_dir)
    entries = []
    for path in file_paths:
        try:
            raw = load_json_file(path)
            # Support two common JSON shapes:
            # 1) top-level dict with keys -> values (existing behavior)
            # 2) top-level list of records (e.g., list of POIs) -> create one entry per item
            if isinstance(raw, list):
                # Each item is typically a dict representing a POI or similar
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    rec = normalize_country_record(item, path)
                    country = rec.get('country', 'unknown')
                    # Prefer a human-friendly description if present
                    if rec.get('description'):
                        text = str(rec.get('description'))
                    else:
                        # Fallback: join key:value pairs
                        text = "\n".join([f"{k}: {v}" for k, v in rec.items() if k != 'country'])

                    meta = {
                        'country': country,
                        'category': rec.get('category', 'poi'),
                        'source_file': os.path.basename(path)
                    }
                    entries.append({'text': text, 'metadata': meta})
            elif isinstance(raw, dict):
                rec = normalize_country_record(raw, path)
                country = rec.get('country', 'unknown')
                # For every top-level key in record, make a text entry
                for key, value in rec.items():
                    if key == 'country':
                        continue
                    # Skip empty
                    if value is None or (isinstance(value, (list, dict)) and len(value) == 0):
                        continue

                    if isinstance(value, list):
                        text = "\n".join([str(x) for x in value])
                    elif isinstance(value, dict):
                        # Flatten dict to lines
                        text = "\n".join([f"{k}: {v}" for k, v in value.items()])
                    else:
                        text = str(value)

                    meta = {
                        'country': country,
                        'category': key,
                        'source_file': os.path.basename(path)
                    }
                    entries.append({'text': text, 'metadata': meta})
            else:
                logger.debug(f"Skipping unsupported JSON type in {path}: {type(raw)}")
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
    logger.info(f"Loaded {len(entries)} entries from {len(file_paths)} files")
    return entries
