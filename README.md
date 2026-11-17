# Cookbook Index Generator

A Python project for automating the extraction and generation of an enhanced cookbook index from printed pages using OCR (Optical Character Recognition) with vision AI models running locally.

## Overview

**The 1000 Best Recipes** from Bay Books is an excellent cookbook.  I believe it's out of print, but you can still find copies of it for sale.  The recipes are all triple-tested, and I have never found one that isn't delicious, but unfortunately the book is only indexed by the names of the recipes-- not by ingredients.  If you have some ingredient on hand and want to find out what you could make with it, you're out of luck;  even though there are actually only 988 recipes you still a lot of tedious searching to do. 

I decided to apply AI and OCR to parse ingredients from the recipe names and use them to enhance the index.  The first version was created in about a week using various models online, mostly Claude and ChatGPT.  The OCR was nowhere near perfect and a fair amount of manual fixup were required to get all of the recipes and page numbers.  As a learning experience I really wanted to be able to do something with local models and Ollama, and I wanted to create an automated process that would basically get it right.  This project represents that effort.  The manual work was valuable for validation and I was actually encouraged that the automated, simpler model actually found some errors in the original solution-- it gave me additional confidence that things were really working.


This tool extracts recipe names and page numbers from printed cookbook index pages by:

1. **OCR with Vision AI**: Scans cropped images of cookbook index pages using Ollama's vision models to identify recipe names and their corresponding page numbers
2. **Post-processing & Assembly**: Reassembles fragmented results into complete entries and validates the data
3. **Index Generation**: Creates formatted indexes in multiple output formats (CSV, HTML, PDF)


## Features

- 🤖 **Vision AI OCR**: Uses local Ollama vision models to transcribe printed text without internet connection
- 🔧 **Multi-format Output**: Generate indexes in CSV, HTML, and PDF formats
- ✅ **Entry Validation**: Cross-reference scanned results against manual reference data
- 📊 **Comprehensive Reporting**: Detailed discrepancy reports comparing multiple OCR model outputs
- 🐍 **Python-based**: Fully implemented in Python with clear separation of concerns

## Project Structure

```
cookbook-index/
├── cookbook_index/           # Core Python packages
│   ├── __init__.py           # Package configuration and path constants
│   ├── generate_index.py     # Index generation from CSV data
│   ├── scan_images.py        # OCR scanning of index page images
│   ├── convert_manual_csv.py # CSV format converter for validation
│   ├── validate_csv.py       # Validation report generator
│   ├── overrides.txt         # Pattern-based corrections (optional)
│   └── system_prompt.txt     # System prompt for vision model
├── images/                   # Source cookbook index page images
│   ├── original/             # Original full pages
│   └── p<page>-<column>.jpeg # Cropped two-column segments
├── output/                   # Generated outputs
│   ├── recipe-names.csv      # Extracted recipes (CSV format)
│   ├── recipe-names.html     # Index in HTML format
│   ├── recipe-names.pdf      # Scanned/PDF index
│   └── csv-validation-report.md  # Validation report
├── work/                     # Temporary processing files
│   └── p<page>_intermediate.json  # Intermediate OCR results
├── generate.sh               # Main execution script
├── manual-solution/          # Manual reference data (for validation)
│   └── input.csv             # Ground truth format
├── requirements.txt          # Python dependencies
└── README.md                  # This file
```

## Requirements

- **Python 3.x**
  - Development was completed with version 3.14.10
- [Ollama](https://ollama.com/) with vision-capable models
  - minicpm-v4.5 has worked the best for me 
- Docker-compatible runtime (uses Python venv)

### Dependencies

See `requirements.txt` for complete list. Key packages:

- `olama==0.6.3` - API client for Ollama vision models
- `Pillow==13.0` - Image preprocessing
- `weasyprint==70.0` - HTML to PDF conversion
- `yattag==1.16` - XML-like template engine for index generation

### Model Support

The project supports multiple Ollama vision models (defined in `scan_images.py`). Currently configured with:

- `minicpm-v4.5:latest` (default primary model)

You can add additional models to the `MODEL_NAMES` list or modify `PRIMARY_MODEL`.

## Usage

### Running the Full Pipeline

```bash
# Download and run the provided script

chmod +x generate.sh
./generate.sh

# Or directly with images as arguments:
./generate.sh p1002-1.jpg p1006-2.jpg image1.pdf
```

### Command Line Options (after converting to CSV)

```bash
# Generate all formats (default)
python cookbook_index/generate_index.py

# Generate HTML only
python cookbook_index/generate_index.py --html

# Generate PDF only  
python cookbook_index/generate_index.py --pdf

# Custom pagination settings
python cookbook_index/generate_index.py --start-page 1 --lines-per-page 54

# Full customization
python cookbook_index/generate_index.py --start-page 20 --lines-per-page 60 --chars-per-line 50
```

### Using with Ollama

Make sure Ollama is running with a vision model:

```bash
ollama pull minicpm-v4.5:latest  # or another supported vision model
ollama serve &                    # Start in background
# Then run the pipeline
./generate.sh
```
I currently run it with a context size of 32K.


## Input Format

### Index Page Images

Images should be named with pattern `p<page>-<column>.jpeg` or `.jpg`:

- `p1002-1.jpg` - Column 1 of page 1002
- `p1002-2.jpg` - Column 2 of page 1002  
- `p1003-1.jpg` - Column 1 of page 1003

Each image should contain exactly two adjacent columns: one with recipe names, one with page numbers.

### Manual Reference Data (Optional)

For validation comparison, provide a CSV file in `manual-solution/`:

```
RecipeName,Page
[Start section],
Chicken Pot Pie,756
Chicken Soup,202
# comments allowed; used for grouping by section
```

The first column is the recipe name, second is the page number. Use `[p1002]` markers to indicate index page numbers.

## Output Formats

### CSV Export (`recipe-names.csv`)

Pipe-delimited format with columns:

| RecipeName | RecipePage | IndexPage |
|------------|-------------|------------|
| Chicken Pot Pie | 756 | 1002 |
| Pasta Alfredo | 423 | 1004 |

### HTML Export (`recipe-names.html`)

A formatted, multi-column web index with:

- Bilingual titles (English/Italian)
- Two-column layout for dense listing
- Recipe names sorted alphabetically
- Direct page number references

Sample content shows recipe entry style formatting. The HTML is designed for printing to standard 8.5" x 11" paper at approximately 54 lines per page.

### PDF Export (`recipe-names.pdf`)

Print-ready PDF version of the index, generated from the HTML using WeasyPrint. Ideal for physical printouts or viewing in PDF readers.

### Validation Report (`csv-validation-report.md`)

If reference data exists, generates a detailed markdown report with:

- Summary statistics comparing scanned vs manual results
- Per-model accuracy counts
- Detailed discrepancy tables showing name/page mismatches
- HTML scrollable tables with problem detection

## Development Workflow

### Manual Processing Flow

1. **Extract Index Pages**: Create cropped images from original cookbook pages (e.g., `p1002-1.jpg`, `p1002-2.jpg`)

2. **Reformat Manual Data** (if using manual reference):
   ```bash
   python cookbook_index/convert_manual_csv.py
   ```

3. **Scan Images with OCR**:
   ```bash
   python cookbook_index/scan_images.py p1002-1.jpg p1002-2.jpg
   ```
   
   This produces:
   - `output/recipe-names.csv`
   - `work/p100x_intermediate.json` (per-page results)

4. **Generate Index**:
   ```bash
   python cookbook_index/generate_index.py
   ```
   
   Produces HTML and PDF outputs.

5. **Validate Results** (optional):
   ```bash
   python cookbook_index/validate_csv.py
   ```

6. **Apply Overrides** (for known corrections):
   Add rules to `cookbook_index/overrides.txt` for pattern-based corrections. Example:
   ```csv
   # Comment line
   1002|Chicken Provencal|Chicken Provencale|*|
   *|.* Provencal|\1 Provencale|*|
   ```

### Adding Custom Ollama Models

Edit `cookbook_index/scan_images.py`:

```python
MODEL_NAMES = [
    'minicpm-v4.5:latest',      # Keep this or add more here
    'your-custom-model:tag',     # Add new models
]
PRIMARY_MODEL = MODEL_NAMES[0]  # Set which one writes the main CSV
```

## Troubleshooting

### "Failed to start Ollama server"

- Ensure `ollama serve` is running: `ollama serve &`
- Check if port 11435 is available (or modify `OLLAMA_PORT`)
- Verify model is downloaded: `ollama pull your-model`

### Poor OCR Results

1. **Image Quality**: Ensure images are clear, properly cropped to index sections
2. **Try Different Models**: Add alternative models to `MODEL_NAMES` list
3. **Override Patterns**: Create override rules for recurring transcription errors

### Memory Errors on Large Books

The pipeline processes pages incrementally. For very large books:

```bash
python cookbook_index/generate_index.py --lines-per-page 40 --chars-per-line 35
```

Reduce lines/characters per page to decrease memory usage during rendering.

## Customization Options

### Override Rules (`overrides.txt`)

Pattern-based corrections apply automatically:

| Column | Description |
|--------|-------------|
| 1. TargetIndexPage | Regex for index page (or `*` for any) |
| 2. TargetRecipeName | Regex for recipe name (post-cleaning) |
| 3. CorrectedRecipeName | Replacement name(s); use `~` to split into multiple entries |
| 4. TargetRecipePage | Regex for page number (or `*` for any) |
| 5. CorrectedRecipePage | Replacement page(s), or `~`-separated for splits |

Example: Change misspellings and fix mis-assigned pages in one rule.

## License

MIT License - Feel free to use, modify, and distribute.

## Contributing

Issues and improvements are welcome!

---

**Note**: This project was designed to automate cookbook index generation but requires preparation of source images (cropped index page segments). The OCR quality depends on image clarity and the capabilities of the configured Ollama vision model.
