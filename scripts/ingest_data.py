"""Simple script to ingest the WM2/data directory into Chroma via src.rag.ingest

Usage:
    python3 scripts/ingest_data.py [data_dir]
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rag import ingest


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data")
    print(f"Ingesting data from: {data_dir}")
    try:
        res = ingest(data_dir)
        print("Ingestion result:", res)
    except Exception as e:
        print("Ingestion failed:", e)


if __name__ == '__main__':
    main()
