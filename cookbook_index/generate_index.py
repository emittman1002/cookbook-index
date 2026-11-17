import csv
import argparse
from collections import namedtuple
from pathlib import Path
import re
from typing import NamedTuple
from yattag import Doc, indent

from cookbook_index import OUTPUT_DIR

OUT = Path(OUTPUT_DIR)

TODO = 'TODO'

PRESERVE_START = '<<'
PRESERVE_END = '>>'
LEFT_PAREN = '('
RIGHT_PAREN = ')'
DASH_TOKEN = '&dash;'
APOSTROPHE_TOKEN = '&apostrophe;'
SPACE_TOKEN = '&space;'

# Input format produced by scan_files.py (OUTPUT_DIR/recipe-names.csv):
#   RecipeName|RecipePage|IndexPage
DEFAULT_INPUT_NAME = 'recipe-names.csv'
INPUT_DELIMITER = '|'
INPUT_NAME_FIELD = 'RecipeName'
INPUT_PAGE_FIELD = 'RecipePage'

Entry = namedtuple('Entry', ['Recipe', 'Page'])


class RecipeInfo(NamedTuple):
    name: str
    keys: list[str]


IGNORED = [
    'a',
    'and',
    'baby',
    'bake',
    'baked',
    'ball',
    'balls',
    'basic',
    'black',
    'blue',
    'brazil',
    'breasts',
    'broad',
    'bun',
    'buttered',
    'butterfly',
    'buttery',
    'choc',
    'coated',
    'comforting',
    'con',
    'creamy',
    'crisp',
    'crispy',
    'crustless',
    'curly',
    'dark',
    'deep',
    'dressed-up',
    'dried',
    'dry',
    'eastern',
    'family',
    'filling',
    'food',
    'for',
    'fresh',
    'fried',
    'gingery',
    'golden',
    'grandmothers',
    'green',
    'head',
    'hearty',
    'herb',
    'herbs',
    'hot',
    'in',
    'leg',
    'light',
    'lions',
    'many',
    'ma po',
    'meat',
    'minced',
    'middle',
    'mini',
    'mix',
    'mixed',
    'north',
    'of',
    'on',
    'oven',
    'pan',
    'paste',
    'peking',
    'people',
    'plain',
    'poached',
    'poly',
    'pot',
    'puff',
    'puy',
    'racks',
    'raised',
    'red',
    'rich',
    'roasted',
    'roly',
    'roman',
    'saucing',
    'seasoned',
    'self',
    'semi',
    'shanghai',
    'snake',
    'spice',
    'spiced',
    'spices',
    'sticks',
    'stir',
    'strips',
    'style',
    'summer',
    'three',
    'toasted/',
    'topped',
    'verde',
    'very',
    'warm',
    'water',
    'white',
    'whole',
    'wild',
    'with',
]

PRESERVED = [
    'angel hair',
    'baba ganouj',
    'bloody mary',
    'bok choy',
    'chiang mai',
    'chili con carne',
    'chow mein',
    'cocino madrileno',
    'cock-a-leekie',
    'coq au vin',
    'cordon bleu',
    'five spice',
    'goat cheese',
    'goats cheese',
    'goats milk',
    'hot chocolate',
    'ice cream',
    'lemon grass',
    'middle eastern',
    'ma po',
    'nasi goreng',
    'olive oil',
    'one pot',
    'osso buco',
    'pasta e fagioli',
    'peanut butter',
    'pine nut',
    'pine nuts',
    'poppy seed',
    'pot pie',
    'pot pies',
    'salsa verde',
    'san choy bau',
    'snow peas',
    'sour cream',
    'sri lankan',
    'stir fried',
    'stir fry',
    'sun dried',
    'sweet potato',
    'thousand island',
    'tom yum',
]

CONTENT_SUBSTITUTIONS = {
    'chilli': 'chili',
    'currychicken': 'curry chicken',
    'dhal': 'daal',
    'familystyle': 'family style',
    'fivespice': 'five spice',
    'flavour': 'flavor',
    'flavours': 'flavors',
    'goats cheese': 'goat cheese',
    'greekstyle': 'greek style',
    'indianstyle': 'indian style',
    'italianstyle': 'italian style',
    'japanesestyle': 'japanese style',
    'lemon grass': 'lemongrass',
    'lowfat': 'low fat',
    'ma por': 'ma po',
    'middleeastern': 'middle eastern',
    'musaman': 'massaman',
    'onepot': 'one pot',
    'ovenbaked': 'oven baked',
    'panfried': 'pan fried',
    'phad thai': 'pad thai',
    'pizzatopped': 'pizza topped',
    'redcurrant': 'red currant',
    'saltandpepper': 'salt and pepper',
    'savoury': 'savory',
    'selfsaucing': 'self saucing',
    'sundried': 'sun dried',
    'stirfry': 'stir fry',
    'stirfried': 'stir fried',
    'tapenadecoated': 'tapenade coated',
    'thaispiced': 'thai spiced',
    'thaistyle': 'thai style',
    'threebean': 'three bean',
    'twicebaked': 'twice baked',
    'won ton': 'wonton',
    'yoghurt': 'yogurt',
}

KEY_SUBSTITUTIONS = {
    'almond': ['almonds', 'nuts'],
    'apple': ['apples'],
    'apricot': ['apricots'],
    'artichoke': ['artichokes'],
    'avocado': ['avocados'],
    'banana': ['bananas'],
    'barbecued': ['barbecue'],
    'bean': ['beans'],
    'berry': ['berries'],
    'blueberry': ['blueberries', 'berries'],
    'blue cheese': ['blue cheese', 'cheese'],
    'braise': ['braised'],
    'burger': ['burgers'],
    'cakes': ['cake'],
    'caper': ['capers'],
    'carrot': ['carrots'],
    'cashew': ['cashews', 'nuts'],
    'cashews': ['cashews', 'nuts'],
    'casseroles': ['casserole'],
    'chiang mai': ['chiang mai', 'thai'],
    'cheeses': ['cheese'],
    'cherry': ['cherries'],
    'chickens': ['chicken'],
    'chickpea': ['chickpeas'],
    'chilies': ['chilies', 'peppers'],
    'chip': ['chips'],
    'choc': ['chocolate'],
    'chocmint': ['chocolate', 'mint'],
    'chocnut': ['chocolate', 'nuts'],
    'chop': ['chops'],
    'cock-a-leekie': ['cock-a-leekie', 'chicken'],
    'coq au vin': ['coq au vin', 'chicken'],
    'currant': ['currants'],
    'daal': ['daal', 'lentils'],
    'egg': ['eggs'],
    'deepfried': ['deep fried'],
    'fig': ['figs'],
    'fillets': ['fillet'],
    'goats milk': ['goats milk', 'milk'],
    'goong': ['prawns'],
    'gnocchi': ['gnocchi', 'pasta'],
    'grape': ['grapes'],
    'hummus': ['hummus', 'chickpeas'],
    'leek': ['leeks'],
    'lemon': ['lemons'],
    'lentil': ['lentils'],
    'lime': ['limes'],
    'livers': ['liver'],
    'minted': ['mint'],
    'mung': ['mung beans', 'beans'],
    'mushroom': ['mushrooms'],
    'nasi goreng': ['nasi goreng', 'chicken', 'prawns'],
    'noodle': ['noodles'],
    'nut': ['nuts'],
    'nutty': ['nuts'],
    'olive': ['olives'],
    'oyster': ['oysters'],
    'passion': ['passionfruit'],
    'pea': ['peas'],
    'peanut': ['peanuts', 'nuts'],
    'pear': ['pears'],
    'pecan': ['pecans', 'nuts'],
    'penne': ['penne', 'pasta'],
    'peppercorn': ['peppercorns'],
    'peppered': ['pepper'],
    'pies': ['pie'],
    'pine nut': ['pine nuts'],
    'pittas': ['pitta'],
    'pizzas': ['pizza'],
    'plum': ['plums'],
    'pollo': ['chicken'],
    'poppy seed': ['poppy seeds'],
    'pot pies': ['pot pie'],
    'potato': ['potatoes'],
    'prawn': ['prawns'],
    'puddings': ['pudding'],
    'quiches': ['quiche'],
    'ravioli': ['ravioli', 'pasta'],
    'rocket': ['rocket', 'arugula'],
    'san choy bau': ['san choy bau', 'vietnamese', 'wraps', 'lettuce', 'pork'],
    'scallop': ['scallops'],
    'silverbeet': ['silverbeet', 'chard, swiss'],
    'shanks': ['lamb'],
    'shiitake': ['shiitake', 'mushrooms'],
    'snapper': ['snapper', 'fish', 'seafood'],
    'soba': ['soba', 'japanese'],
    'souffles': ['souffle'],
    'spaghetti': ['spaghetti', 'pasta'],
    'stack': ['stacks'],
    'stir fry': ['stir fried'],
    'strawberry': ['strawberries', 'berries'],
    'swordfish': ['swordfish', 'fish', 'seafood'],
    'tarts': ['tart'],
    'tom yum': ['tom yum', 'thai'],
    'tuna': ['tuna', 'fish', 'seafood'],
    'trout': ['trout', 'fish'],
    'terrines': ['terrine'],
    'tomato': ['tomatoes'],
    'vegetable': ['vegetables'],
    'walnut': ['walnuts', 'nuts'],
    'whitefish': ['whitefish', 'fish'],
}


class Indexer:
    def __init__(self):
        # By default, read the file that scan_files.py wrote into OUTPUT_DIR
        self.input_file = OUT / DEFAULT_INPUT_NAME

        base = OUT / self.input_file.stem

        base.parent.mkdir(parents=True, exist_ok=True)
        self.output_file = base

        self.preservations = self.create_preservations()
        self.entries = self.read_input(self.input_file)

        # The index has two kinds of headings, kept in separate dictionaries
        # so that each one has a single, consistent value type:
        #   recipes:     recipe name -> page number (str)
        #   ingredients: ingredient  -> set of recipe names
        self.recipes: dict[str, str] = {}
        self.ingredients: dict[str, set[str]] = {}
        # (key, is_recipe) -> order in which the key was first added,
        # used to break ties when sorting
        self._order: dict[tuple[str, bool], int] = {}

    @staticmethod
    def create_preservations():
        preservations = {}
        for s in PRESERVED:
            replacement = (
                s.replace('-', DASH_TOKEN)
                .replace("'", APOSTROPHE_TOKEN)
                .replace(" ", SPACE_TOKEN)
            )
            preservations[s] = f'{PRESERVE_START}{replacement}{PRESERVE_END}'
        return preservations

    @staticmethod
    def read_input(input_file):
        """
        Read the pipe-delimited file written by scan_files.py:

            RecipeName|RecipePage|IndexPage

        Only the recipe name and recipe page are used; the index page
        (where the entry was found in the original index) is ignored.
        """
        entries = []
        with open(input_file, newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=INPUT_DELIMITER, quotechar='"')
            missing = [f for f in (INPUT_NAME_FIELD, INPUT_PAGE_FIELD)
                       if f not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(
                    f"{input_file}: missing expected column(s) {', '.join(missing)}; "
                    f"found {reader.fieldnames}")

            for line_no, row in enumerate(reader, start=2):  # line 1 is the header
                name = (row.get(INPUT_NAME_FIELD) or '').strip()
                page = (row.get(INPUT_PAGE_FIELD) or '').strip()

                # Skip blank lines and bracketed lines (as before)
                if not name or name.startswith('['):
                    continue
                if not page.isdigit() or int(page) <= 0:
                    print(f"Warning: {input_file} line {line_no}: skipping '{name}' "
                          f"with invalid page '{page}'")
                    continue

                entries.append(Entry(name, str(int(page))))
        return entries

    def _note_key(self, key, is_recipe):
        self._order.setdefault((key, is_recipe), len(self._order))

    def create_index(self):
        for entry in self.entries:
            info = self.preprocess(entry.Recipe)
            recipe_name = info.name
            # Add index by recipe name
            self.recipes[recipe_name] = entry.Page
            self._note_key(recipe_name, True)
            # Add index by ingredients
            for k in info.keys:
                if k in KEY_SUBSTITUTIONS:
                    keys = KEY_SUBSTITUTIONS[k]
                else:
                    keys = [k]
                for key in keys:
                    self.ingredients.setdefault(key, set()).add(recipe_name)
                    self._note_key(key, False)

    def sorted_index_keys(self):
        """
        All index headings (recipes and ingredients) in printed order, as
        (key, is_recipe) tuples. Sorting is on the capitalized heading;
        headings that compare equal keep the order in which they were added.
        """
        keys = [(k, True) for k in self.recipes] + [(k, False) for k in self.ingredients]
        return sorted(keys, key=lambda item: (item[0].capitalize(), self._order[item]))

    def preprocess(self, recipe) -> RecipeInfo:
        """
        Normalize the recipe name and create keys for indexing
        """
        name, indexable_name = self.recipe_names(recipe)
        keys = []
        for k in indexable_name.split(' '):
            k = k.replace(LEFT_PAREN, '').replace(RIGHT_PAREN, '')
            if k not in IGNORED:
                k = self.restore(k)
                if k in KEY_SUBSTITUTIONS:
                    for sub in KEY_SUBSTITUTIONS[k]:
                        keys.append(sub)
                else:
                    keys.append(k)
        return RecipeInfo(name, keys)

    def recipe_names(self, recipe):
        """
        Normalize the recipe name and create keys for indexing
        """
        # Some preservations retain punctuation
        recipe_name = self.preserve(
            recipe.strip()
            .lower()
        )
        # Remove punctuation
        recipe_name = (
            recipe_name.replace('-', '')
            .replace("'", "")
        )
        # Some preservations specify the normalized name
        recipe_name = self.preserve(recipe_name)
        # Use US spellings
        for k in CONTENT_SUBSTITUTIONS:
            recipe_name = recipe_name.replace(k, CONTENT_SUBSTITUTIONS[k])
        # Create a name to parse for the index
        indexable_name = recipe_name.lower()
        # Restore preserved strings
        # and capitalize
        recipe_name = (
            self.restore(recipe_name)
            .title()
            .replace(' And ', ' and ')
            .replace(' With ', ' with ')
            .replace(' In ', ' in ')
            .replace(' Of ', ' of ')
            .replace(' Con ', ' con ')
            .replace(' For ', ' for ')
            .replace(' A ', ' a ')
            .replace('-A-', '-a-')
        )
        return recipe_name, indexable_name

    def preserve(self, string):
        for s in PRESERVED:
            string = string.replace(s, self.preservations[s])
        return string

    @staticmethod
    def restore(string):
        if PRESERVE_START in string:
            pattern = re.compile(f'{PRESERVE_START}(.*?){PRESERVE_END}')
            match = pattern.search(string)
            while match:
                string = string.replace(match.group(),
                                        match.group(1).replace(DASH_TOKEN, '-')
                                        .replace(APOSTROPHE_TOKEN, "'")
                                        .replace(SPACE_TOKEN, ' ')
                                        )
                match = pattern.search(string)
        return string

    def create_html_index(self, chars_per_line=42, lines_per_page=54, start_page=1):
        doc, tag, text, line = Doc().ttl()

        # Create a list of all rows before rendering
        all_rows = []

        # Output the index entries in sorted order
        for k, is_recipe in self.sorted_index_keys():
            rows = []

            if not is_recipe:
                # Ingredient
                recipes_for_key = self.ingredients[k]
                # Don't output the ingredient if the only recipe is the ingredient itself
                skip = len(recipes_for_key) == 1
                if skip:
                    item = list(recipes_for_key)[0]
                    skip = item in self.recipes
                if not skip:
                    # Output the ingredient
                    rows.append({
                        'type': 'ingredient',
                        'name': k,
                        'page': '',
                        'indent': False,
                        'line_estimate': 1  # Ingredients are usually short, single line
                    })

                    # Output the recipes for this ingredient
                    for r in sorted(recipes_for_key):
                        estimated_lines = self.estimate_text_height(r, chars_per_line)
                        rows.append({
                            'type': 'indented_recipe',
                            'name': r,
                            'page': self.recipes[r],
                            'indent': True,
                            'line_estimate': estimated_lines
                        })
            else:
                # Recipe
                page = self.recipes[k]
                if int(page) > 0:
                    estimated_lines = self.estimate_text_height(k, chars_per_line)
                    rows.append({
                        'type': 'recipe',
                        'name': k,
                        'page': page,
                        'indent': False,
                        'line_estimate': estimated_lines
                    })
                else:
                    raise ValueError(f'Unexpected value {page} in index')

            all_rows.extend(rows)

        with tag('html'):
            with tag('head'):
                with tag('title'):
                    text('1000 Best-Ever Recipes')
                with tag('style'):
                    text('''
                        @page {
                            size: 8.5in 11in;
                            margin: 0.75in;
                        }
                        body {
                            font-family: Arial, sans-serif;
                            font-size: 9pt;
                            line-height: 1.1;
                            margin: 0;
                            padding: 0;
                        }
                        @media screen {
                            body {
                                max-width: 8.5in;
                                margin: 24px auto;
                                padding: 0 36px;
                            }
                            .page-container {
                                margin-bottom: 32px;
                                padding-bottom: 16px;
                                border-bottom: 1px solid #ddd;
                            }
                        }
                        .page-container {
                            width: 100%;
                            break-inside: avoid;
                            page-break-inside: avoid;
                        }
                        .page-container.has-break {
                            break-after: page;
                            page-break-after: always;
                        }
                        .ingredient {
                            color: blue;
                            font-weight: bold;
                            font-size: 9pt;
                        }
                        .column-container {
                            display: table;
                            width: 100%;
                            table-layout: fixed;
                        }
                        .left-column, .right-column {
                            display: table-cell;
                            width: 47%;
                            vertical-align: top;
                        }
                        .column-spacer {
                            display: table-cell;
                            width: 6%;
                        }
                        table.entries {
                            width: 100%;
                            border-collapse: collapse;
                            table-layout: fixed;
                        }
                        td {
                            vertical-align: top;
                            padding: 0px 2px;
                            overflow-wrap: break-word;
                            line-height: 1.1;
                        }
                        .header-container {
                            display: table;
                            width: 100%;
                            margin-bottom: 5px;
                        }
                        .title {
                            display: table-cell;
                            font-size: 10pt;
                            font-weight: bold;
                            margin: 0;
                            padding: 4px 0;
                            text-align: left;
                        }
                        .page-number {
                            display: table-cell;
                            font-size: 10pt;
                            font-weight: bold;
                            padding: 4px 0;
                            text-align: right;
                        }
                        .recipe-name {
                            overflow-wrap: break-word;
                            word-wrap: break-word;
                            hyphens: auto;
                            font-size: 9pt;
                        }
                    ''')
            with tag('body'):
                # Process all rows, page by page
                current_page = start_page
                row_index = 0
                total_rows = len(all_rows)

                while row_index < total_rows:
                    # Pre-calculate entries for left and right columns so we know
                    # whether a page break is needed after this page-container
                    left_lines_used = 0
                    left_entries_added = 0
                    while (row_index + left_entries_added < total_rows and
                           left_lines_used + all_rows[row_index + left_entries_added][
                               'line_estimate'] <= lines_per_page):
                        left_lines_used += all_rows[row_index + left_entries_added]['line_estimate']
                        left_entries_added += 1

                    right_start_idx = row_index + left_entries_added
                    right_lines_used = 0
                    right_entries_added = 0
                    while (right_start_idx + right_entries_added < total_rows and
                           right_lines_used + all_rows[right_start_idx + right_entries_added][
                               'line_estimate'] <= lines_per_page):
                        right_lines_used += all_rows[right_start_idx + right_entries_added]['line_estimate']
                        right_entries_added += 1

                    has_more = (row_index + left_entries_added + right_entries_added) < total_rows
                    container_class = 'page-container has-break' if has_more else 'page-container'

                    # Start a new page
                    with tag('div', klass=container_class):
                        # Header with title and page number
                        with tag('div', klass='header-container'):
                            with tag('div', klass='title'):
                                text('Index of 1000 Best-Ever Recipes')
                            with tag('div', klass='page-number'):
                                text(f'{current_page}')

                        # Container for the two columns
                        with tag('div', klass='column-container'):
                            # Left column
                            with tag('div', klass='left-column'):
                                with tag('table', klass='entries', border="0"):
                                    with tag('colgroup'):
                                        doc.stag('col', style='width:5%')  # Indentation column
                                        doc.stag('col', style='width:85%')  # Recipe/ingredient name
                                        doc.stag('col', style='width:10%')  # Page number

                                    for i in range(left_entries_added):
                                        current_entry = all_rows[row_index + i]
                                        with tag('tr'):
                                            if current_entry['type'] == 'ingredient':
                                                with tag('td', colspan="3", klass="ingredient"):
                                                    text(current_entry['name'])
                                            elif current_entry['type'] == 'indented_recipe':
                                                line('td', '')  # Empty first column for indentation
                                                with tag('td', klass="recipe-name"):
                                                    text(current_entry['name'])
                                                line('td', current_entry['page'], style="text-align:right")
                                            else:  # Regular recipe
                                                with tag('td', colspan="2"):
                                                    with tag('span', klass="recipe-name"):
                                                        text(current_entry['name'])
                                                line('td', current_entry['page'], style="text-align:right")

                            # Spacer between columns
                            with tag('div', klass='column-spacer'):
                                text('')

                            # Right column - independent of left column
                            with tag('div', klass='right-column'):
                                with tag('table', klass='entries', border="0"):
                                    with tag('colgroup'):
                                        doc.stag('col', style='width:5%')  # Indentation column
                                        doc.stag('col', style='width:85%')  # Recipe/ingredient name
                                        doc.stag('col', style='width:10%')  # Page number

                                    for i in range(right_entries_added):
                                        current_entry = all_rows[right_start_idx + i]
                                        with tag('tr'):
                                            if current_entry['type'] == 'ingredient':
                                                with tag('td', colspan="3", klass="ingredient"):
                                                    text(current_entry['name'])
                                            elif current_entry['type'] == 'indented_recipe':
                                                line('td', '')  # Empty first column for indentation
                                                with tag('td', klass="recipe-name"):
                                                    text(current_entry['name'])
                                                line('td', current_entry['page'], style="text-align:right")
                                            else:  # Regular recipe
                                                with tag('td', colspan="2"):
                                                    with tag('span', klass="recipe-name"):
                                                        text(current_entry['name'])
                                                line('td', current_entry['page'], style="text-align:right")

                    # Update row index and page counter
                    row_index += left_entries_added + right_entries_added
                    current_page += 1
        self.html_index_doc = doc

    @staticmethod
    def estimate_text_height(text, chars_per_line):
        """
        Estimate the number of lines needed for text based on typography principles.

        Args:
            text: The text to estimate
            chars_per_line: Approximate characters per line (based on column width)

        Returns:
            Estimated number of lines
        """
        # Basic calculation based on character count and column width
        if not text:
            return 1

        # Account for word breaks - can't break in the middle of words
        words = text.split()
        line_count = 1
        current_line_length = 0

        for word in words:
            # If adding this word would exceed the line length
            if current_line_length + len(word) + 1 > chars_per_line:
                line_count += 1
                current_line_length = len(word)
            else:
                if current_line_length > 0:  # Add space if not at beginning of line
                    current_line_length += 1
                current_line_length += len(word)

        # Add a small margin for exceptionally long words or special formatting
        # Using a smaller margin (0.2) since we've reduced font size and line height
        if any(len(word) > chars_per_line // 2 for word in words):
            line_count += 0.2

        return max(1, round(line_count))  # Ensure at least 1 line

    @staticmethod
    def calculate_complexity(text):
        """Calculate the complexity of an entry based on various factors."""
        # Base complexity based on length
        base_complexity = len(text) // 25 + 1

        # Add complexity for special characters that might affect rendering
        special_chars = sum(1 for c in text if not c.isalnum() and c not in [' ', '-'])
        special_complexity = special_chars // 2

        # Add complexity for very long words
        words = text.split()
        long_words = sum(1 for word in words if len(word) > 10)
        long_word_complexity = long_words * 2

        # Total complexity
        return base_complexity + special_complexity + long_word_complexity

    def write_html_index(self):
        path = f'{self.output_file}.html'
        with open(path, 'w') as f:
            f.write(indent(self.html_index_doc.getvalue()))
        print(f'Wrote {path}')

    def write_pdf_index(self):
        # Convert HTML to PDF using WeasyPrint
        html_content = indent(self.html_index_doc.getvalue())

        path = f'{self.output_file}.pdf'

        # Suppress WeasyPrint's progress output to stderr
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()

        # Create PDF from HTML
        import weasyprint
        pdf_doc = weasyprint.HTML(string=html_content).write_pdf(path)

        # Restore stdout/stderr and get them
        sys.stderr = old_stderr
        sys.stdout = old_stdout

        print(f'Wrote {path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a cookbook index')
    parser.add_argument('--all', action='store_true', default=True, help='Generate output in all formats')
    parser.add_argument('--html', action='store_true', help='Generate only HTML output')
    parser.add_argument('--pdf', action='store_true', help='Generate only PDF output')
    parser.add_argument('--start-page', '-s', type=int, default=1,
                        help='Starting page number (default: 1)')
    parser.add_argument('--lines-per-page', '-l', type=int, default=54,
                        help='Number of lines per page (default: 54)')
    parser.add_argument('--chars-per-line', '-c', type=int, default=42,
                        help='Number of characters per line (default: 42)')

    args = parser.parse_args()
    if args.html or args.pdf:
        args.all = False

    idx = Indexer()
    idx.create_index()

    # The HTML index is the basis we create other formats from,
    # so always create it even if we won't be writing it to a file
    idx.create_html_index(
        chars_per_line=args.chars_per_line,
        lines_per_page=args.lines_per_page,
        start_page=args.start_page,
    )

    # Produce output files
    if args.all or args.html:
        idx.write_html_index()
    if args.all or args.pdf:
        idx.write_pdf_index()