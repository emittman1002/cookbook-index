"""
Cookbook index OCR using vision models via Ollama.

Input files are two-column crops (recipe names + page numbers) named
    p<indexpage>-<columnpair>.jpeg      e.g. p1006-1.jpeg, p1006-2.jpeg, p1006-3.jpeg

For each file the model only transcribes *physical lines*. All the logic that
joins wrapped recipe names, attaches page numbers and validates entries lives
in plain Python (assemble_entries / validate_entry), because small vision
models are unreliable at layout reasoning but reasonably good at reading lines.

Outputs (same formats as before):
    recipe-names.csv                  pipe-delimited: RecipeName|RecipePage|IndexPage
    rejected-recipe-names.md                       entries that failed validation
    p<page>_intermediate.json         per-page results, keyed by recipe name
Extra (new):
    recipe-names.<model>.csv          one CSV per model, for comparing models
    p<page>_lines.json                raw model lines + issues, for debugging
Optional input:
    overrides.txt                     one-off corrections, see the "OVERRIDES" section below
"""
import csv
import json
import os
import re
import subprocess
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sys import argv
from urllib.error import URLError
from urllib.request import urlopen

from PIL import Image, ImageOps
from ollama import Client

from cookbook_index import OUTPUT_DIR, WORK_DIR, IMAGE_DIR

OUT = Path(OUTPUT_DIR)
WORK = Path(WORK_DIR)
IMAGES = Path(IMAGE_DIR)

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------
MODEL_NAMES = [
    'minicpm-v4.5:latest',
#    'hf.co/Qwen/Qwen3-VL-8B-Instruct-GGUF:Q8_0',
]
# recipe-names.csv is built from this model; every model also gets its own CSV.
PRIMARY_MODEL = MODEL_NAMES[0]

OLLAMA_PORT = 11435
OLLAMA_HOST = f"http://localhost:{OLLAMA_PORT}"

OLLAMA_OPTIONS = {
    'num_ctx': 16384,
    'num_predict': 4096,      # guard against runaway generation loops
    'temperature': 0,         # transcription, not creativity
    'seed': 1,
    'repeat_penalty': 1.0,    # default 1.1 penalises the many repeated "Lamb"/"Spicy" starts
}

OUTPUT_CSV = OUT / "recipe-names.csv"
REJECTED_MD = OUT / "rejected-recipe-names.md"
OVERRIDES_FILE = Path(__file__).with_name("overrides.txt")   # optional; skipped if missing

# Preprocessing (used for the retry attempt)
CUTOFF_THRESHOLD = (15, 95)
MIN_WIDTH = 1600              # upscale narrower images to this width

# Validation
MAX_RECIPE_PAGE = 1000        # book is "1000 Best-Ever Recipes"
MIN_RECIPE_PAGE = 1
NAME_PATTERN = re.compile(r"^[A-Z]")   # every real entry starts with a capital letter
EXPECTED_FILES_PER_PAGE = 3   # warn when a page has a different number of column files; None to disable

FILE_RE = re.compile(r"^p(\d+)-(\d+)\.jpe?g$", re.IGNORECASE)

# Status values
VALID = "Valid"
UNRESOLVED = "Unresolved"     # name with no page number
BAD_PAGE = "BadPage"          # page missing or outside MIN/MAX_RECIPE_PAGE
BAD_NAME = "BadName"          # name does not look like a recipe start (digit/lowercase first char)

# ------------------------------------------------------------------------------
# PROMPT / SCHEMA
# ------------------------------------------------------------------------------
PROMPT = """This image is a crop of two adjacent columns from a printed cookbook index: a column of recipe names with a column of page numbers to its right.

Transcribe it ONE PRINTED LINE AT A TIME, from top to bottom. For every printed line output:
- "text": the recipe-name text on that line, exactly as printed (no page number in it)
- "indented": true if the line starts visibly further right than the lines around it (the continuation of a wrapped recipe name), otherwise false
- "page": the page number printed at the right end of that line as digits, or "" if the line has no page number

Rules:
- A long recipe name wraps onto an indented second line. The page number usually sits next to that LAST line. Do not merge lines yourself.
- Each page number is printed exactly once. Give it to ONE line only (the last line of a wrapped name) and leave "page" empty on the other lines of that name. Never copy the same page number onto two lines.
- The photo may be slightly skewed, so a number can sit a little above or below its text. Give it to the nearest line.
- Do not skip lines, do not invent lines, and do not correct spelling.
- Ignore any book-title header and any stand-alone page number at the very bottom of the page.
"""

LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "indented": {"type": "boolean"},
                    "page": {"type": "string"},
                },
                "required": ["text", "indented", "page"],
            },
        }
    },
    "required": ["lines"],
}


# ------------------------------------------------------------------------------
# IMAGE HANDLING
# ------------------------------------------------------------------------------
def preprocess_image(image_path: Path, destination: Path = WORK) -> tuple[Path, Path]:
    """Returns (working_copy, adjusted) paths.

    working_copy: orientation-corrected grayscale copy of the original.
    adjusted:     autocontrast (+ upscale if narrow) version, used as a retry.
    """
    destination.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as im:
        gray = ImageOps.exif_transpose(im).convert("L")
        work_path = destination / f"{image_path.stem}.jpg"
        gray.save(work_path)

        adjusted = ImageOps.autocontrast(gray, cutoff=CUTOFF_THRESHOLD)
        if adjusted.width < MIN_WIDTH:
            scale = MIN_WIDTH / adjusted.width
            adjusted = adjusted.resize((MIN_WIDTH, round(adjusted.height * scale)), Image.Resampling.LANCZOS)
        adjusted_path = destination / f"adjusted_{image_path.stem}.jpg"
        adjusted.save(adjusted_path)
    return work_path, adjusted_path


# ------------------------------------------------------------------------------
# MODEL CALL
# ------------------------------------------------------------------------------
def read_lines(client: Client, image_path: Path, model_name: str) -> list[dict]:
    """Asks the model for the printed lines in one column-pair image."""
    response = client.generate(
        model=model_name,
        prompt=PROMPT,
        images=[str(image_path)],
        format=LINE_SCHEMA,
        options=OLLAMA_OPTIONS,
    )
    data = json.loads(response['response'])
    lines = data.get("lines", []) if isinstance(data, dict) else []
    return [ln for ln in lines if isinstance(ln, dict)]


# ------------------------------------------------------------------------------
# REASSEMBLY + VALIDATION (pure Python, no model involved)
# ------------------------------------------------------------------------------
def parse_page(value) -> int | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def clean_name(name: str) -> str:
    """Normalizes recipe name: removes commas and periods, converts special

    accented/marked characters to English counterparts, preserves dashes,
    and standardizes whitespace.
    """
    if not name:
        return ""
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_str = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    ascii_str = ascii_str.replace('ø', 'o').replace('Ø', 'O')
    # Remove commas and periods, but explicitly preserve dashes (-)
    cleaned = re.sub(r"[,.]", "", ascii_str)
    return re.sub(r"\s+", " ", cleaned).strip()


def assemble_entries(lines: list[dict]) -> tuple[list[tuple[str, int | None]], list[str]]:
    """Joins physical lines into (name, page) entries.

    A page number CLOSES an entry, so a continuation line can never become its
    own entry and the number never has to line up with the first line of the
    name.

    Models sometimes repeat the page number on both lines of a wrapped name (or
    put it only on the first line). In that case the second line arrives after
    the entry has already been closed, so it is merged back into that entry
    instead of becoming an entry of its own (see "orphan continuation" below).
    """
    entries: list[tuple[str, int | None]] = []
    issues: list[str] = []
    pending: list[str] = []

    for ln in lines:
        text = re.sub(r"\s+", " ", str(ln.get("text", ""))).strip()
        page = parse_page(ln.get("page"))
        indented = bool(ln.get("indented", False))

        if not text and page is None:
            continue

        # Orphan continuation: nothing is pending, but this line clearly continues the
        # entry that was just closed. Signals: it starts with a lowercase letter/digit
        # (real entries start with a capital), or it is indented and repeats the page
        # number of the previous entry.
        if text and not pending and entries:
            prev_name, prev_page = entries[-1]
            starts_like_continuation = not NAME_PATTERN.match(text)
            repeats_page = indented and page is not None and page == prev_page
            if starts_like_continuation or repeats_page:
                if page is not None and prev_page is not None and page != prev_page:
                    issues.append(f"continuation '{text}' has page {page} but '{prev_name}' has page {prev_page}")
                entries[-1] = (f"{prev_name} {text}", page if page is not None else prev_page)
                continue

        if page is not None:
            # A page number closes the current entry (including any pending lines)
            if text:
                pending.append(text)
            if pending:
                name = " ".join(pending)
                entries.append((name, page))
                pending = []
            else:
                issues.append(f"page number {page} with no recipe text")
        else:
            if text:
                # Robustly identify continuation lines even if the model misses indentation:
                # 1. Explicitly marked indented by the model, OR
                # 2. Starts with a lowercase letter (e.g., "with", "and", "in").
                is_continuation = indented or (pending and not NAME_PATTERN.match(text))

                if pending and not is_continuation:
                    name = " ".join(pending)
                    entries.append((name, None))
                    issues.append(f"no page number found for '{name}'")
                    pending = []

                pending.append(text)

    if pending:
        name = " ".join(pending)
        entries.append((name, None))
        issues.append(f"trailing text without page number: '{name}'")
    return entries, issues


# ------------------------------------------------------------------------------
# OVERRIDES (one-off / pattern-based corrections applied after cleaning)
# ------------------------------------------------------------------------------
# File format (pipe-delimited, '#' starts a comment line, header row optional):
#
#   TargetIndexPage|TargetRecipeName|CorrectedRecipeName|TargetRecipePage|CorrectedRecipePage
#   1003|Chicken Provencal|Chicken Provencale|*|
#   *|(.*) Provencal|\1 Provencale|*|
#   1006|Lamb Tagine|*|83|88
#   1007|Foo Bar Baz|Foo~Bar Baz|51|38~51
#
# - Target fields are regular expressions that must match the WHOLE value
#   (re.fullmatch, case-sensitive; use (?i) for case-insensitive). '*' or an
#   empty field matches anything.
# - TargetRecipeName is matched against the name AFTER clean_name() (no commas/periods).
# - TargetRecipePage is matched against the page as digits ('' if no page was found).
# - CorrectedRecipeName may use \1, \2 ... for groups captured in TargetRecipeName.
#   Leave it empty (or '*') to keep the name unchanged.
# - CorrectedRecipePage must be an integer; leave empty (or '*') to keep the page.
# - SPLITTING: separate several names with '~' in CorrectedRecipeName to turn one
#   scanned entry into several (e.g. two entries the model merged into one). If
#   CorrectedRecipePage is given it must then contain the same number of '~'-separated
#   pages; if it is empty, every resulting entry keeps the original page.
# - A regex containing '|' must be wrapped in double quotes: "(Foo|Bar) Soup"
# - Rules are applied in file order; later rules see the output of earlier ones
#   (including each part of a split).
SPLIT_CHAR = "~"


@dataclass
class Override:
    line_no: int
    index_page: re.Pattern | None
    recipe_name: re.Pattern | None
    corrected_names: list[str]      # empty = keep name; more than one = split into several entries
    recipe_page: re.Pattern | None
    corrected_pages: list[int]      # empty = keep page; otherwise one per resulting entry
    hits: int = 0


OVERRIDES: list[Override] = []


def _compile_target(field: str, line_no: int) -> re.Pattern | None:
    field = field.strip()
    if field in ("", "*"):
        return None
    try:
        return re.compile(field)
    except re.error as e:
        raise ValueError(f"{OVERRIDES_FILE.name} line {line_no}: invalid regex '{field}': {e}")


def load_overrides(path: Path) -> list[Override]:
    if not path.exists():
        return []
    overrides: list[Override] = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            row = next(csv.reader([line.rstrip("\r\n")], delimiter="|"))
            if row and row[0].strip() == "TargetIndexPage":
                continue  # header
            if len(row) != 5:
                raise ValueError(f"{path.name} line {line_no}: expected 5 pipe-delimited fields, got {len(row)}")

            corrected_name = row[2].strip()
            corrected_names: list[str] = []
            if corrected_name not in ("", "*"):
                corrected_names = [part.strip() for part in corrected_name.split(SPLIT_CHAR)]
                if any(not part for part in corrected_names):
                    raise ValueError(f"{path.name} line {line_no}: empty name in CorrectedRecipeName")

            corrected_page = row[4].strip()
            corrected_pages: list[int] = []
            if corrected_page not in ("", "*"):
                parts = [part.strip() for part in corrected_page.split(SPLIT_CHAR)]
                if not all(part.isdigit() for part in parts):
                    raise ValueError(f"{path.name} line {line_no}: CorrectedRecipePage must be an integer "
                                     f"(or integers separated by '{SPLIT_CHAR}')")
                corrected_pages = [int(part) for part in parts]

            name_pattern = _compile_target(row[1], line_no)
            if corrected_names and name_pattern is None:
                raise ValueError(f"{path.name} line {line_no}: CorrectedRecipeName requires a TargetRecipeName")
            if not corrected_names and not corrected_pages:
                raise ValueError(f"{path.name} line {line_no}: nothing to correct "
                                 f"(CorrectedRecipeName and CorrectedRecipePage are both empty)")
            if corrected_pages and len(corrected_pages) != (len(corrected_names) or 1):
                raise ValueError(f"{path.name} line {line_no}: CorrectedRecipePage has {len(corrected_pages)} "
                                 f"value(s) but the correction produces {len(corrected_names) or 1} entr(ies)")

            overrides.append(Override(
                line_no=line_no,
                index_page=_compile_target(row[0], line_no),
                recipe_name=name_pattern,
                corrected_names=corrected_names,
                recipe_page=_compile_target(row[3], line_no),
                corrected_pages=corrected_pages,
            ))
    return overrides


def _apply_one_override(ov: Override, index_page: int, name: str,
                        page: int | None) -> list[tuple[str, int | None]]:
    """Applies a single rule to a single entry; returns one or more resulting entries."""
    unchanged = [(name, page)]
    if ov.index_page and not ov.index_page.fullmatch(str(index_page)):
        return unchanged
    match = None
    if ov.recipe_name:
        match = ov.recipe_name.fullmatch(name)
        if not match:
            return unchanged
    if ov.recipe_page and not ov.recipe_page.fullmatch("" if page is None else str(page)):
        return unchanged

    names = [match.expand(n) for n in ov.corrected_names] if ov.corrected_names else [name]
    pages = ov.corrected_pages or [page] * len(names)
    result = list(zip(names, pages))
    if result == unchanged:
        return unchanged

    ov.hits += 1
    shown = ", ".join(f"'{n}' ({p})" for n, p in result)
    print(f"      [Override line {ov.line_no}] p{index_page}: '{name}' ({page}) -> {shown}")
    return result


def apply_overrides(index_page: int, name: str, page: int | None) -> list[tuple[str, int | None]]:
    """Runs every override over one entry. Usually returns one entry; a split rule returns several."""
    results: list[tuple[str, int | None]] = [(name, page)]
    for ov in OVERRIDES:
        updated: list[tuple[str, int | None]] = []
        for cur_name, cur_page in results:
            updated.extend(_apply_one_override(ov, index_page, cur_name, cur_page))
        results = updated
    return results


def validate_entry(name: str, page: int | None) -> str:
    if not name:
        return BAD_NAME
    if page is None:
        return UNRESOLVED
    if not (MIN_RECIPE_PAGE <= page <= MAX_RECIPE_PAGE):
        return BAD_PAGE
    if not NAME_PATTERN.match(name):
        return BAD_NAME
    return VALID


def sort_key(name: str) -> str:
    first = name.split()[0] if name.split() else ""
    return re.sub(r"[^a-z0-9]", "", first.lower())


def order_warnings(entries: list[dict]) -> list[str]:
    """Coarse alphabetical check on the first word of consecutive valid entries.

    Warning only: this book's sort order is not strict enough to reject on.
    """
    warnings = []
    prev = None
    for e in entries:
        if e["Status"] != VALID:
            continue
        if prev and sort_key(e["RecipeName"]) < sort_key(prev["RecipeName"]):
            warnings.append(f"out of order: '{prev['RecipeName']}' -> '{e['RecipeName']}'")
        prev = e
    return warnings


# ------------------------------------------------------------------------------
# PER-FILE / PER-PAGE PROCESSING
# ------------------------------------------------------------------------------
def scan_column_file(client: Client, model_name: str, original: Path, adjusted: Path,
                     index_page: int, column: int) -> tuple[list[dict], dict]:
    """Scans one file. Tries the original image first and the adjusted image

    only if the first result has problems. Keeps whichever attempt is cleaner.
    """
    best = None
    for label, path in (("original", original), ("preprocessed", adjusted)):
        try:
            print(f"      Scanning {path.name} ({label})...", end=" ")
            lines = read_lines(client, path, model_name)
            pairs, issues = assemble_entries(lines)
            entries = []
            for raw_name, raw_page in pairs:
                # An override can correct an entry or split it into several
                for name, page in apply_overrides(index_page, clean_name(raw_name), raw_page):
                    entries.append({
                        "RecipeName": name,
                        "RecipePage": page if page is not None else -1,
                        "IndexPage": index_page,
                        "Status": validate_entry(name, page),
                        "Column": column,
                        "_source_file_": str(path),
                    })
            problems = issues + [e["RecipeName"] for e in entries if e["Status"] != VALID]
            score = (len(problems), -len(entries))
            print(f"{len(entries)} entries, {len(problems)} problem(s)")
            if best is None or score < best[0]:
                best = (score, entries, {"source": str(path), "lines": lines, "issues": issues})
            if not problems and entries:
                break
        except Exception as e:  # model/JSON failure: try the next image
            print(f"[error: {e}]")
            if best is None:
                best = ((10 ** 6, 0), [], {"source": str(path), "lines": [], "issues": [str(e)]})

    return best[1], best[2]


def process_page(client: Client, index_page: int, columns: list[tuple[int, Path]]) -> dict[str, list[dict]]:
    """Scans every column file of one index page with every model and

    reassembles each model's entries into reading order (column 1, 2, 3 ...).
    """
    print(f"Processing index page {index_page} ({len(columns)} file(s))")
    prepared = {col: preprocess_image(path) for col, path in columns}

    page_results: dict[str, list[dict]] = {}
    debug: dict = {}

    for model_name in MODEL_NAMES:
        print(f"  Using model [{model_name}]")
        model_entries: list[dict] = []
        debug[model_name] = {}
        for col, path in columns:
            print(f"    Column file {path.name}")
            original, adjusted = prepared[col]
            entries, info = scan_column_file(client, model_name, original, adjusted, index_page, col)
            model_entries.extend(entries)
            debug[model_name][path.name] = info

        warnings = order_warnings(model_entries)
        for w in warnings:
            print(f"      [Warning] {w}")
        debug[model_name]["order_warnings"] = warnings
        page_results[model_name] = model_entries

    # intermediate file: recipe name -> list of per-model results (same shape as before)
    restructured: dict[str, list[dict]] = {}
    for model_name, entries in page_results.items():
        for e in entries:
            restructured.setdefault(e["RecipeName"], []).append({
                "RecipePage": e["RecipePage"],
                "IndexPage": e["IndexPage"],
                "Status": e["Status"],
                "model": model_name,
            })
    WORK.mkdir(parents=True, exist_ok=True)
    with open(WORK / f"p{index_page}_intermediate.json", "w", encoding="utf-8") as f:
        json.dump(restructured, f, indent=2, ensure_ascii=False)
    with open(WORK / f"p{index_page}_lines.json", "w", encoding="utf-8") as f:
        json.dump(debug, f, indent=2, ensure_ascii=False)
    return page_results


def group_by_page(paths: list[Path]) -> dict[int, list[tuple[int, Path]]]:
    """p1006-2.jpeg -> {1006: [(2, path)]}; columns sorted left to right."""
    groups: dict[int, list[tuple[int, Path]]] = defaultdict(list)
    for p in paths:
        m = FILE_RE.match(p.name)
        if not m:
            print(f"[Skipped] '{p.name}' does not match p<page>-<column>.jpeg")
            continue
        groups[int(m.group(1))].append((int(m.group(2)), p))
    return {page: sorted(cols) for page, cols in sorted(groups.items())}


# ------------------------------------------------------------------------------
# OUTPUT
# ------------------------------------------------------------------------------
def write_csv(path: Path, entries: list[dict]) -> int:
    rows = [e for e in entries if e["Status"] == VALID]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["RecipeName", "RecipePage", "IndexPage"],
                                delimiter="|", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_rejected(all_results: dict[str, list[dict]]) -> None:
    rejected: dict[tuple, dict] = {}
    for model_name, entries in all_results.items():
        for e in entries:
            if e["Status"] == VALID:
                continue
            key = (e["RecipeName"], e["RecipePage"], e["IndexPage"], e["Status"])
            item = rejected.setdefault(key, {"files": [], "models": []})
            if e["_source_file_"] not in item["files"]:
                item["files"].append(e["_source_file_"])
            if model_name not in item["models"]:
                item["models"].append(model_name)

    with open(REJECTED_MD, "w", encoding="utf-8") as f:
        f.write("# Rejected Recipe Entries\n\n")
        if not rejected:
            f.write("All recipe entries had Valid status.\n")
            return
        f.write("Entries that were not included because their Status was not Valid.\n\n")
        f.write("| Recipe Name | Recipe Page | Index Page | Status | Files | Models |\n")
        f.write("|--------------|-------------|-------------|--------|--------|----------|\n")
        for (name, page, index_page, status), item in sorted(rejected.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[0][1])):
            f.write(f"| {name} | {page} | {index_page} | {status} | "
                    f"{'; '.join(item['files'])} | {', '.join(item['models'])} |\n")
    print(f"  [Done] Wrote rejected entries to {REJECTED_MD}")


def model_slug(model_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", model_name).strip("_")


# ------------------------------------------------------------------------------
# OLLAMA PROCESS MANAGEMENT
# ------------------------------------------------------------------------------
def start_ollama_process():
    env = os.environ.copy()
    env["OLLAMA_HOST"] = OLLAMA_HOST
    process = subprocess.Popen(["ollama", "serve"], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    start_time = time.time()
    timeout = 30
    while time.time() - start_time < timeout:
        try:
            with urlopen(OLLAMA_HOST, timeout=1) as response:
                if response.status == 200:
                    return process
        except (URLError, ConnectionRefusedError, OSError):
            time.sleep(0.25)
    process.terminate()
    raise RuntimeError(f"Failed to start Ollama server on port {OLLAMA_PORT} within {timeout} seconds.")


def stop_ollama_process(process: subprocess.Popen):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            print("Ollama server process killed forcefully.")


# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
def main():
    ollama_proc = None
    try:
        if len(argv) > 1:
            image_files = [Path(p) for p in argv[1:]]
        else:
            image_files = [f for f in IMAGES.glob("*.jp*g") if not f.name.startswith(".")]

        pages = group_by_page(image_files)
        if not pages:
            print(f"No files named p<page>-<column>.jpeg found in '{IMAGES}'.")
            return

        OVERRIDES[:] = load_overrides(OVERRIDES_FILE)   # fail fast on a bad overrides file
        if OVERRIDES:
            print(f"Loaded {len(OVERRIDES)} override rule(s) from {OVERRIDES_FILE.name}")

        ollama_proc = start_ollama_process()
        client = Client(host=OLLAMA_HOST)
        all_results: dict[str, list[dict]] = {m: [] for m in MODEL_NAMES}

        started = datetime.now()
        for index_page, columns in pages.items():
            if EXPECTED_FILES_PER_PAGE and len(columns) != EXPECTED_FILES_PER_PAGE:
                print(f"[Warning] Page {index_page} has {len(columns)} file(s), "
                      f"expected {EXPECTED_FILES_PER_PAGE}")
            # All column files of this page are scanned here, then reassembled
            page_results = process_page(client, index_page, columns)
            for model_name, entries in page_results.items():
                all_results[model_name].extend(entries)
                valid = sum(1 for e in entries if e["Status"] == VALID)
                print(f"  [Final] {model_name}: {valid} valid of {len(entries)} entries on page {index_page}")
        print(f"Processed {len(pages)} page(s) in {datetime.now() - started}\n")

        OUT.mkdir(parents=True, exist_ok=True)
        for model_name, entries in all_results.items():
            n = write_csv(WORK / f"recipe-names.{model_slug(model_name)}.csv", entries)
            print(f"  {model_name}: {n} valid entries")

        for ov in OVERRIDES:
            if ov.hits == 0:
                print(f"  [Warning] Override on line {ov.line_no} of {OVERRIDES_FILE.name} never changed anything "
                      f"(typo, or the OCR now gets it right?)")

        total = write_csv(OUTPUT_CSV, all_results[PRIMARY_MODEL])
        write_rejected(all_results)
        print(f"\nProcessing complete! Wrote {total} total entries to '{OUTPUT_CSV}' (model: {PRIMARY_MODEL}).")
    finally:
        if ollama_proc:
            stop_ollama_process(ollama_proc)


if __name__ == "__main__":
    main()