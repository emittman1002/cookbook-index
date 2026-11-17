#!/usr/bin/env bash
clear

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"

SOURCE_DIR="${PROJECT_DIR}/cookbook_index"
OUTPUT_DIR="${PROJECT_DIR}/output"
WORK_DIR="${PROJECT_DIR}/work"
ACTIVATE_LINK="${PROJECT_DIR}/activate"

echo "=== Parsing Arguments ==="

# Separate image files from other arguments
image_files=()
other_args=()

for arg in "$@"; do
    # Image file pattern: p<page>-<column>.jpeg or .jpg
    if [[ "$arg" =~ ^p[0-9]+-[0-9]+\.(jpe?g)$ ]]; then
        image_files+=("$arg")
        echo "  [Image] $arg"
    else
        other_args+=("$arg")
        echo "  [Other] $arg"
    fi
done

NUM_IMAGES=${#image_files[@]}

# ------------------------------------------------------------------------------
# Initialize folders (if work/output exist from a previous run with images)
# ------------------------------------------------------------------------------

echo ""
echo "=== Reinitializing folders ==="
if [ -d "$WORK_DIR" ]; then
    rm -rf "${WORK_DIR:?}"
fi
mkdir -p "$WORK_DIR"
echo "Created ${WORK_DIR}"

if [ -d "$OUTPUT_DIR" ]; then
    rm -rf "${OUTPUT_DIR:?}"
fi
mkdir -p "$OUTPUT_DIR"
echo "Created ${OUTPUT_DIR}"

# ------------------------------------------------------------------------------
# Enable venv
# ------------------------------------------------------------------------------

echo ""
echo "=== Activating venv ==="
source "${ACTIVATE_LINK}"

# ------------------------------------------------------------------------------
# Reformat manually-created result CSV file (always, with no args)
# ------------------------------------------------------------------------------

echo ""
echo "=== Reformatting Old CSV File ==="
python "${SOURCE_DIR}/convert_manual_csv.py"

# ------------------------------------------------------------------------------
# Process image files
# ------------------------------------------------------------------------------

echo ""
echo "=== Processing Image Files ==="
if [ "$NUM_IMAGES" -gt 0 ]; then
    python "${SOURCE_DIR}/scan_images.py" "${image_files[@]}"
else
    python "${SOURCE_DIR}/scan_images.py"
fi

# ------------------------------------------------------------------------------
# Generate index (always, forward other args to generate_index.py if present)
# ------------------------------------------------------------------------------

echo ""
echo "=== Generating Index ==="
if [ ${#other_args[@]} -gt 0 ]; then
    python "${SOURCE_DIR}/generate_index.py" "${other_args[@]}"
else
    python "${SOURCE_DIR}/generate_index.py"
fi

# ------------------------------------------------------------------------------
# Validate results (always, with no args)
# ------------------------------------------------------------------------------

echo ""
echo "=== Validating ==="
python "${SOURCE_DIR}/validate_csv.py"

# ------------------------------------------------------------------------------
# Deactivate venv
# ------------------------------------------------------------------------------

echo ""
echo "=== Deactivating venv ==="
deactivate

echo ""
echo "=== All steps complete ==="
