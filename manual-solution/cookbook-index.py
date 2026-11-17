import csv
import argparse
from collections import namedtuple
import re
from typing import Type

from yattag import Doc, indent

TODO = 'TODO'

PRESERVE_START = '<<'
PRESERVE_END = '>>'
LEFT_PAREN = '('
RIGHT_PAREN = ')'
DASH_TOKEN = '&dash;'
APOSTROPHE_TOKEN = '&apostrophe;'
SPACE_TOKEN = '&space;'

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
Entry = None


class Indexer:
    def __init__(self, input_file, output_file=None, as_html=False):
        self.input_file = input_file  # Store the input file path

        if output_file is None:
            pos1 = input_file.rfind('/')
            if pos1 >= 0:
                self.output_file = f'{input_file[:pos1]}/'
                pos1 += 1
            else:
                self.output_file = ''
                pos1 = 0
            pos2 = input_file.rfind('.', pos1)
            if pos2 >= 0:
                self.output_file += f'{input_file[pos1:pos2]}'
            else:
                self.output_file = input_file[pos1:]
        else:
            self.output_file = output_file

        # Add safeguard to prevent overwriting the input file
        # Check if any potential output file would overwrite the input file
        if self.output_file + '.html' == self.input_file or self.output_file + '.csv' == self.input_file:
            # Append "_output" to the output filename
            self.output_file += '_output'
            print(f"Warning: Output would overwrite input file. Changed output filename to {self.output_file}.*")

        self.preservations = self.create_preservations()
        self.entries = self.read_input(input_file)
        self.index = {}
        self.as_html = as_html

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
        global Entry
        entries = []
        with open(input_file, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',', quotechar='"', skipinitialspace=True)
            for fields in reader:
                if len(fields) > 0 and not fields[0].startswith('['):
                    if Entry is None:
                        Entry: Type[tuple] = namedtuple('Entry', [fields[0].strip(), fields[1].strip()])
                    else:
                        entries.append(Entry([fields[0], fields[1]]))
        return entries

    def create_index(self):
        for entry in self.entries:
            info = self.preprocess(entry.Recipe)
            recipe_name = info['name']
            # Add index by recipe name
            self.index[recipe_name] = entry.Page
            # Add index by ingredients
            for k in info['keys']:
                if k in KEY_SUBSTITUTIONS:
                    keys = KEY_SUBSTITUTIONS[k]
                else:
                    keys = [k]
                for key in keys:
                    if key in self.index:
                        set_ = self.index[key]
                    else:
                        set_ = set()
                        self.index[key] = set_
                    set_.add(recipe_name)

    def preprocess(self, recipe):
        """
        Normalize the recipe name and create keys for indexing
        """
        names = self.recipe_names(recipe)
        keys = []
        for k in names[1].split(' '):
            k = k.replace(LEFT_PAREN, '').replace(RIGHT_PAREN, '')
            if k not in IGNORED:
                k = self.restore(k)
                if k in KEY_SUBSTITUTIONS:
                    for sub in KEY_SUBSTITUTIONS[k]:
                        keys.append(sub)
                else:
                    keys.append(k)
        return {
            'name': names[0],
            'keys': keys
        }

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

    def write_csv_index(self):
        with open(f'{self.output_file}.csv', "w", newline='') as csvfile:
            writer = csv.writer(csvfile,
                                delimiter='\t',
                                quotechar='"')
            # Add a header row
            writer.writerow(['Index of 1000 Best-Ever Recipes', '', len(self.entries)])
            writer.writerow(['Recipe', 'Indent', 'Page'])

            # Output the index entries in sorted order
            all_keys = self.index.keys()
            for k in sorted(self.index, key=lambda s: s.capitalize()):
                v = self.index[k]
                if isinstance(v, set):
                    # Don't output the set if it contains
                    # information that's already in the index
                    skip = len(v) == 1
                    if skip:
                        item = list(v)[0]
                        skip = item in all_keys
                    if not skip:
                        # Retrieve page number from index
                        row = [k, '', '']
                        writer.writerow(row)
                        for r in sorted(v):
                            row = ['', r, self.index[r]]
                            writer.writerow(row)
                else:
                    if int(v) > 0:
                        row = [k, '', v]
                        writer.writerow(row)
                    else:
                        raise ValueError(f'Unexpected value {v} in index')

    def write_html_index(self, chars_per_line=65, lines_per_page=50, start_page=1):  # Increased default from 40 to 50
        doc, tag, text, line = Doc().ttl()

        # Create a list of all rows before rendering
        all_rows = []

        # Output the index entries in sorted order
        all_keys = self.index.keys()

        for k in sorted(self.index, key=lambda s: s.capitalize()):
            v = self.index[k]
            rows = []

            if isinstance(v, set):
                # Ingredient
                # Don't output the ingredient if the only recipe is the ingredient itself
                skip = len(v) == 1
                if skip:
                    item = list(v)[0]
                    skip = item in all_keys
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
                    for r in sorted(v):
                        # Estimate lines based on typography principles - increased chars per line to 45
                        estimated_lines = self.estimate_text_height(r, chars_per_line)
                        rows.append({
                            'type': 'indented_recipe',
                            'name': r,
                            'page': self.index[r],
                            'indent': True,
                            'line_estimate': estimated_lines
                        })
            else:
                # Recipe
                if int(v) > 0:
                    # Estimate lines based on typography principles - increased chars per line to 45
                    estimated_lines = self.estimate_text_height(k, chars_per_line)
                    rows.append({
                        'type': 'recipe',
                        'name': k,
                        'page': v,
                        'indent': False,
                        'line_estimate': estimated_lines
                    })
                else:
                    raise ValueError(f'Unexpected value {v} in index')

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
                            font-size: 9pt;  /* Reduced from 10pt */
                            line-height: 1.1;  /* Reduced from 1.2 */
                            margin: 20px;
                            padding: 0;
                        }
                        .ingredient {
                            color: blue;
                            font-weight: bold;
                            font-size: 9pt;  /* Explicitly set size */
                        }
                        .page-break {
                            page-break-after: always;
                            clear: both;
                        }
                        .column-container {
                            display: flex;
                            justify-content: space-between;
                            width: 100%;
                        }
                        .left-column, .right-column {
                            width: 47%;
                        }
                        table {
                            width: 100%;
                            border-collapse: collapse;
                            table-layout: fixed;
                        }
                        td {
                            vertical-align: top;
                            padding: 0px 2px;  /* Reduced vertical padding from 1px to 0px */
                            overflow-wrap: break-word;
                            line-height: 1.1;  /* Explicitly set line height */
                        }
                        .header-container {
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            margin-bottom: 5px;  /* Reduced from 10px */
                        }
                        .title {
                            font-size: 10pt;  /* Reduced from 14pt */
                            font-weight: bold;
                            margin: 10px 5px 5px 0px;  /* Reduced bottom margin */
                        }
                        .page-number {
                            font-size: 10pt;  /* Reduced from 14pt */
                            font-weight: bold;
                        }
                        .recipe-name {
                            overflow-wrap: break-word;
                            word-wrap: break-word;
                            hyphens: auto;
                            font-size: 9pt;  /* Explicitly set size */
                        }
                    ''')
            with tag('body'):
                # Process all rows, page by page
                current_page = start_page
                row_index = 0
                total_rows = len(all_rows)

                while row_index < total_rows:
                    # Start a new page
                    with tag('div', klass='page-container'):
                        # Header with title and page number
                        with tag('div', klass='header-container'):
                            with tag('h3', klass='title'):
                                text('Index of 1000 Best-Ever Recipes')
                            with tag('span', klass='page-number'):
                                text(f'{current_page}')

                        # Container for the two columns
                        with tag('div', klass='column-container'):
                            # Left column
                            with tag('div', klass='left-column'):
                                with tag('table', border="0"):
                                    # Left column column widths
                                    with tag('colgroup'):
                                        doc.stag('col', style='width:5%')  # Indentation column
                                        doc.stag('col', style='width:85%')  # Recipe/ingredient name
                                        doc.stag('col', style='width:10%')  # Page number

                                    # Fill the left column up to lines_per_page
                                    left_lines_used = 0
                                    left_entries_added = 0

                                    while (row_index + left_entries_added < total_rows and
                                           left_lines_used + all_rows[row_index + left_entries_added][
                                               'line_estimate'] <= lines_per_page):

                                        current_entry = all_rows[row_index + left_entries_added]
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

                                        left_lines_used += current_entry['line_estimate']
                                        left_entries_added += 1

                            # Right column - independent of left column
                            with tag('div', klass='right-column'):
                                with tag('table', border="0"):
                                    # Right column column widths
                                    with tag('colgroup'):
                                        doc.stag('col', style='width:5%')  # Indentation column
                                        doc.stag('col', style='width:85%')  # Recipe/ingredient name
                                        doc.stag('col', style='width:10%')  # Page number

                                    # Fill the right column up to lines_per_page
                                    right_start_idx = row_index + left_entries_added
                                    right_lines_used = 0
                                    right_entries_added = 0

                                    while (right_start_idx + right_entries_added < total_rows and
                                           right_lines_used + all_rows[right_start_idx + right_entries_added][
                                               'line_estimate'] <= lines_per_page):

                                        current_entry = all_rows[right_start_idx + right_entries_added]
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

                                        right_lines_used += current_entry['line_estimate']
                                        right_entries_added += 1

                        # Add page break unless it's the last page
                        if row_index + left_entries_added + right_entries_added < total_rows:
                            doc.stag('div', klass='page-break')

                    # Update row index and page counter
                    row_index += left_entries_added + right_entries_added
                    current_page += 1

        with open(f'{self.output_file}.html', 'w') as f:
            f.write(indent(doc.getvalue()))

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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a cookbook index')
    parser.add_argument('input_file', nargs='?', default='index.csv',
                        help='Input CSV file (default: input.csv)')
    parser.add_argument('--output-file', '-o', help='Output file name without extension')
    parser.add_argument('--html', action='store_true', help='Generate HTML output')
    parser.add_argument('--csv', action='store_true', help='Generate CSV output')
    parser.add_argument('--start-page', '-s', type=int, default=1,
                        help='Starting page number (default: 1)')
    parser.add_argument('--lines-per-page', '-l', type=int, default=56,
                        help='Number of lines per page (default: 56)')
    parser.add_argument('--chars-per-line', '-c', type=int, default=65,
                        help='Number of characters per line (default: 65)')

    args = parser.parse_args()

    idx = Indexer(args.input_file, args.output_file, as_html=args.html or not args.csv)
    idx.create_index()

    if args.csv or not args.html:
        idx.write_csv_index()

    if args.html or not args.csv:
        idx.write_html_index(lines_per_page=args.lines_per_page, start_page=args.start_page)
