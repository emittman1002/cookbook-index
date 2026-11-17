from pathlib import Path

# __init__.py is inside cookbook_index, which is inside cookbook-index
TOP_DIR = Path(__file__).resolve().parent.parent

SOURCE_DIR = TOP_DIR / "cookbook_index"
IMAGE_DIR = TOP_DIR / "images"
WORK_DIR = TOP_DIR / "work"
OUTPUT_DIR = TOP_DIR / "output"

ROOT_DIR = TOP_DIR
ROOT_WORK_DIR = WORK_DIR
ROOT_OUTPUT_DIR = OUTPUT_DIR
ROOT_IMAGE_DIR = IMAGE_DIR
SOURCE_DIR = TOP_DIR / "cookbook_index"
IMAGE_DIR = TOP_DIR / "images"
WORK_DIR = TOP_DIR / "work"
OUTPUT_DIR = TOP_DIR / "output"

from cookbook_index.scan_images import MODEL_NAMES