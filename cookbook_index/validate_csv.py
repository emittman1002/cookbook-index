import csv
import html
import json
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from cookbook_index import OUTPUT_DIR, WORK_DIR

WORK = Path(WORK_DIR)
VALIDATED_RESULTS_PATH = WORK / 'manual-input.csv'
REPORT_PATH = Path(OUTPUT_DIR) / 'csv-validation-report.md'

# A scanned name that is not an exact match but is at least this similar (difflib ratio) to an
# unmatched manual-input name on the same index page is treated as the same recipe with a wrong name.
NEAR_MATCH_RATIO = 0.8

# How each manual-input entry compares with one model's results
CORRECT = 'correct'                    # name and page both match
WRONG_PAGE = 'wrong_page'              # name matches exactly, page differs
WRONG_NAME = 'wrong_name'              # near-match name, page matches
WRONG_BOTH = 'wrong_name_and_page'     # near-match name, page differs
MISSING = 'missing'                    # nothing resembling it was scanned
EXTRA = 'extra'                        # scanned entry that matches nothing in manual-input
NOT_SCANNED = 'not_scanned'            # the model has no results for this index page

PROBLEMS = (WRONG_PAGE, WRONG_NAME, WRONG_BOTH, MISSING, EXTRA)

# Inline styles for the scrollable tables with a sticky header row
CONTAINER_STYLE = 'max-height:80vh;overflow:auto;border:1px solid #ddd;'
TABLE_STYLE = 'width:100%;border-collapse:separate;border-spacing:0;margin:0;'
TH_STYLE = (
    'position:sticky;top:0;z-index:10;background-color:#f8f9fa;color:#000;'
    'padding:8px 12px;text-align:left;border-bottom:2px solid #ccc;'
)


def parse_input_csv(filename):
    """
    Parse CSV file with 3-column format 'RecipeName|RecipePage|IndexPage'.
    Assumes header row; skips it.
    Returns list of dicts: {'recipe': str, 'page': int, 'index': int}.
    """
    entries = []
    with open(filename, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='|')
        next(reader, None)  # Skip header

        error_count = 0
        for row in reader:
            if len(row) < 3:
                print(f'Invalid row: {row}')
                error_count += 1
                continue
            try:
                page = int(row[1].strip())
                index = int(row[2].strip())
            except (ValueError, IndexError):
                page = 0
                index = 0

            entries.append({'recipe': row[0].strip(), 'page': page, 'index': index})
        if error_count > 0:
            raise Exception(f'Error parsing {filename}')
    return entries


def get_short_model_name(model_name_full):
    """Extract clean, short model name from model identifier or path."""
    parts = model_name_full.rsplit('/', 1)
    if len(parts) == 2:
        return parts[1].split(':')[0]
    return model_name_full.split(':')[0]


def load_model_results(work_dir):
    """Reads the p<page>_intermediate.json files.

    Returns (results, scanned_pages):
      results[model]       -> list of {'recipe', 'page', 'index'} for entries with Status == Valid
                              (the entries that end up in that model's CSV)
      scanned_pages[model] -> set of index pages the model produced any output for
    """
    results = defaultdict(list)
    scanned_pages = defaultdict(set)
    for path in sorted(Path(work_dir).glob('*_intermediate.json')):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        for recipe_name, runs in data.items():
            for run in runs:
                model_full = run.get('model')
                if not model_full:
                    continue
                model = get_short_model_name(model_full)
                scanned_pages[model].add(run.get('IndexPage'))
                if run.get('Status') == 'Valid':
                    results[model].append({
                        'recipe': recipe_name,
                        'page': run.get('RecipePage'),
                        'index': run.get('IndexPage'),
                    })
    return results, scanned_pages


def one_word_difference(str1: str, str2: str) -> bool:
    """Check if two strings differ by exactly one word (case-insensitive).

    "Differ by one word" means either:
      - same number of words, and exactly one word is different
        ("Chocolate cherry cake" vs "Chocolate cherry pie"), or
      - one string has exactly one extra word
        ("Chicken Provencale" vs "Chicken")
    """
    words1 = str1.lower().split()
    words2 = str2.lower().split()

    if not words1 or not words2 or words1 == words2:
        return False

    if len(words1) == len(words2):
        return sum(a != b for a, b in zip(words1, words2)) == 1

    if abs(len(words1) - len(words2)) == 1:
        shorter, longer = sorted((words1, words2), key=len)
        return any(longer[:i] + longer[i + 1:] == shorter for i in range(len(longer)))

    return False


def near_match_score(a: str, b: str) -> float:
    """0.0 if the names are not near matches, otherwise a score (higher = closer).

    Catches one-word differences plus spelling slips inside a word or a missing space
    ("Dry potato and pea curry" vs "Dry potatoand pea curry"), which one_word_difference misses.
    """
    if one_word_difference(a, b):
        return 1.0
    ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return ratio if ratio >= NEAR_MATCH_RATIO else 0.0


def match_page(manual_list, scanned_list):
    """Pairs manual-input entries with scanned entries for ONE model on ONE index page.

    Returns (matches, extras):
      matches: list of (manual_entry, scanned_entry_or_None, status), in manual order
      extras:  scanned entries that matched nothing
    """
    pairing = {}        # manual position -> scanned position
    exact = set()       # manual positions matched by exact name

    # 1. Exact names. If a name occurs more than once, prefer the candidate with the same page.
    for mi, m in enumerate(manual_list):
        used = set(pairing.values())
        candidates = [si for si, s in enumerate(scanned_list)
                      if si not in used and s['recipe'] == m['recipe']]
        if not candidates:
            continue
        same_page = [si for si in candidates if scanned_list[si]['page'] == m['page']]
        pairing[mi] = (same_page or candidates)[0]
        exact.add(mi)

    # 2. Near matches among what is left, best scores first
    used = set(pairing.values())
    candidates = []
    for mi, m in enumerate(manual_list):
        if mi in pairing:
            continue
        for si, s in enumerate(scanned_list):
            if si in used:
                continue
            score = near_match_score(m['recipe'], s['recipe'])
            if score:
                candidates.append((score, mi, si))
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    for _, mi, si in candidates:
        if mi in pairing or si in pairing.values():
            continue
        pairing[mi] = si

    matches = []
    for mi, m in enumerate(manual_list):
        if mi not in pairing:
            matches.append((m, None, MISSING))
            continue
        s = scanned_list[pairing[mi]]
        same_page = s['page'] == m['page']
        if mi in exact:
            status = CORRECT if same_page else WRONG_PAGE
        else:
            status = WRONG_NAME if same_page else WRONG_BOTH
        matches.append((m, s, status))

    used = set(pairing.values())
    extras = [s for si, s in enumerate(scanned_list) if si not in used]
    return matches, extras


def cell_text(cell):
    """Report text for one model's result on one row."""
    if not cell:
        return ''
    status = cell['status']
    name = html.escape(str(cell.get('name', '')))
    page = cell.get('page')
    if status == CORRECT:
        return '✓'
    if status == WRONG_PAGE:
        return f'✓ <b>page {page}</b>'
    if status == WRONG_NAME:
        return f'<b>name:</b> {name}'
    if status == WRONG_BOTH:
        return f'<b>name:</b> {name}, <b>page {page}</b>'
    if status == MISSING:
        return '<i>missing</i>'
    if status == EXTRA:
        return f'<i>extra</i> ({page})'
    if status == NOT_SCANNED:
        return '–'
    return ''


def render_html_table(rows, models):
    headers = ['Index Page', 'Recipe Name', 'Manual Input'] + models
    lines = [
        f'<div class="scrollable-table" style="{CONTAINER_STYLE}">',
        f'<table style="{TABLE_STYLE}">',
        '  <thead>',
        '    <tr>',
    ]
    for h in headers:
        lines.append(f'      <th style="{TH_STYLE}">{html.escape(h)}</th>')
    lines += ['    </tr>', '  </thead>', '  <tbody>']

    for r in rows:
        if r['manual_page'] is None:
            manual = ''
        else:
            manual = f"({r['manual_page']})" if r['manual_page'] > 0 else '(?)'
        lines.append('    <tr>')
        lines.append(f'      <td>{r["index"]}</td>')
        lines.append(f'      <td>{html.escape(r["name"])}</td>')
        lines.append(f'      <td>{manual}</td>')
        for m in models:
            lines.append(f'      <td>{cell_text(r["cells"].get(m))}</td>')
        lines.append('    </tr>')

    lines += ['  </tbody>', '</table>', '</div>']
    return '\n'.join(lines)


STYLE_BLOCK = '\n'.join([
    '<style>',
    '  .scrollable-table {',
    '    max-height: 80vh;',
    '    overflow: auto;',
    '    border: 1px solid #ddd;',
    '  }',
    '  .scrollable-table table {',
    '    width: 100%;',
    '    /* "separate" keeps sticky header borders attached while scrolling */',
    '    border-collapse: separate;',
    '    border-spacing: 0;',
    '    margin: 0;',
    '  }',
    '  .scrollable-table th, .scrollable-table td {',
    '    padding: 8px 12px;',
    '    border-right: 1px solid #ddd;',
    '    border-bottom: 1px solid #ddd;',
    '    text-align: left;',
    '  }',
    '  .scrollable-table th {',
    '    position: sticky;',
    '    top: 0;',
    '    background-color: #f8f9fa;',
    '    z-index: 10;',
    '    border-bottom: 2px solid #ccc;',
    '  }',
    '</style>',
])


def compare_and_report(validated_results_path, work_dir, report_path):
    manual = parse_input_csv(validated_results_path)
    model_results, scanned_pages = load_model_results(work_dir)
    models = sorted(model_results)

    manual_by_index = defaultdict(list)
    rows = []
    manual_rows = {}
    for e in manual:
        manual_by_index[e['index']].append(e)
        row = {'index': e['index'], 'name': e['recipe'], 'manual_page': e['page'], 'cells': {}}
        manual_rows[id(e)] = row
        rows.append(row)

    extra_rows = {}
    counts = {m: defaultdict(Counter) for m in models}    # model -> index page -> Counter(status)

    for m in models:
        scanned_by_index = defaultdict(list)
        for s in model_results[m]:
            scanned_by_index[s['index']].append(s)

        for idx in sorted(set(manual_by_index) | set(scanned_by_index)):
            manual_list = manual_by_index.get(idx, [])
            if idx not in scanned_pages[m]:
                for e in manual_list:
                    manual_rows[id(e)]['cells'][m] = {'status': NOT_SCANNED}
                continue

            matches, extras = match_page(manual_list, scanned_by_index.get(idx, []))
            for entry, scanned, status in matches:
                cell = {'status': status}
                if scanned:
                    cell.update(name=scanned['recipe'], page=scanned['page'])
                manual_rows[id(entry)]['cells'][m] = cell
                counts[m][idx][status] += 1
            for s in extras:
                key = (idx, s['recipe'].lower())
                if key not in extra_rows:
                    extra_rows[key] = {'index': idx, 'name': s['recipe'], 'manual_page': None, 'cells': {}}
                    rows.append(extra_rows[key])
                extra_rows[key]['cells'][m] = {'status': EXTRA, 'name': s['recipe'], 'page': s['page']}
                counts[m][idx][EXTRA] += 1

    rows.sort(key=lambda r: (r['index'], r['name'].lower()))
    problem_rows = [r for r in rows if any(c['status'] in PROBLEMS for c in r['cells'].values())]

    # ============ 1. SUMMARY ============
    summary = [
        '## Summary', '',
        'Every manual-input entry is counted exactly once per model: '
        '**Manual = Correct + Wrong page + Wrong name + Wrong name & page + Missing**. '
        '"Extra" counts scanned entries that match nothing in manual-input and is not part of that sum.',
        '',
        '- **Correct**: name and page both match',
        '- **Wrong page**: name matches exactly, page differs',
        '- **Wrong name**: a very similar name was scanned (page matches)',
        '- **Wrong name & page**: a very similar name was scanned and the page differs',
        '- **Missing**: nothing resembling the entry was scanned',
        '',
        'Index pages a model has no results for are left out of its table.',
        '',
    ]
    columns = [('Index Page', None), ('Manual', None), ('Correct', CORRECT), ('Wrong page', WRONG_PAGE),
               ('Wrong name', WRONG_NAME), ('Wrong name & page', WRONG_BOTH), ('Missing', MISSING),
               ('Extra', EXTRA)]
    for m in models:
        summary += [f'### {m}', '']
        summary.append('| ' + ' | '.join(c[0] for c in columns) + ' |')
        summary.append('| ' + ' | '.join(['---'] * len(columns)) + ' |')
        total = Counter()
        total_manual = 0
        for idx in sorted(counts[m]):
            c = counts[m][idx]
            manual_count = sum(c[s] for s in (CORRECT, WRONG_PAGE, WRONG_NAME, WRONG_BOTH, MISSING))
            total.update(c)
            total_manual += manual_count
            cells = [str(idx), str(manual_count)] + [str(c[s]) for _, s in columns[2:]]
            summary.append('| ' + ' | '.join(cells) + ' |')
        cells = ['Total', str(total_manual)] + [str(total[s]) for _, s in columns[2:]]
        summary.append('| ' + ' | '.join(f'**{x}**' for x in cells) + ' |')
        summary.append('')

    # ============ 2. DISCREPANCIES ============
    body = [
        f'## Discrepancies ({len(problem_rows)} rows)', '',
        'Only rows where at least one model has a problem. '
        '✓ = correct; **page N** = the page the model reported; **name:** = the name the model reported.',
        '',
        STYLE_BLOCK,
        render_html_table(problem_rows, models),
        '',
        '## All recipes', '',
        render_html_table(rows, models),
    ]

    full_report = '\n'.join(summary + body)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(full_report)

    print(f'Report written to {report_path}')


if __name__ == '__main__':
    compare_and_report(VALIDATED_RESULTS_PATH, WORK, REPORT_PATH)