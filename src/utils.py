import os
import json
from typing import List
from loguru import logger


def list_json_files(data_dir: str) -> List[str]:
    files = []
    for root, _, filenames in os.walk(data_dir):
        for f in filenames:
            if f.lower().endswith('.json'):
                files.append(os.path.join(root, f))
    logger.debug(f"Found {len(files)} JSON files in {data_dir}")
    return files


def load_json_file(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def normalize_country_record(record: dict, source_file: str) -> dict:
    # Normalize structure and ensure expected keys exist. Return record with country field.
    normalized = dict(record)
    if 'country' not in normalized:
        # infer from filename if possible
        normalized['country'] = os.path.splitext(os.path.basename(source_file))[0].replace('_', ' ').title()
    return normalized
