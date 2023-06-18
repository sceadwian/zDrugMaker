import os
import glob
import html.parser
import csv

class HTMLTableParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_tr = False
        self.in_td = False
        self.data = []
        self.row = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
        elif self.in_table and tag == 'tr':
            self.in_tr = True
        elif self.in_tr and tag == 'td':
            self.in_td = True

    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
        elif self.in_table and tag == 'tr':
            self.in_tr = False
            self.data.append(self.row)
            self.row = []
        elif self.in_tr and tag == 'td':
            self.in_td = False

    def handle_data(self, data):
        if self.in_td:
            self.row.append(data.strip())

# Get a list of all HTML files in the current directory
html_files = glob.glob('*.html')

# For each HTML file, parse the first table and write it to a CSV file
for html_file in html_files:
    # Read the HTML file
    with open(html_file, 'r') as f:
        html_content = f.read()

    # Parse the first table from the HTML content
    parser = HTMLTableParser()
    parser.feed(html_content)

    # Create a CSV file name based on the HTML file name
    csv_file = os.path.splitext(html_file)[0] + '.csv'

    # Write the table to the CSV file
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(parser.data)
