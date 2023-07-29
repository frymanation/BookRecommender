import ast
import csv
import pandas as pd

import sys

from app import books

maxInt = sys.maxsize
decrement = True

while decrement:
    # decrease the maxInt value by factor 10
    # as long as the OverflowError occurs.

    decrement = False
    try:
        csv.field_size_limit(maxInt)
    except OverflowError:
        maxInt = int(maxInt / 10)
        decrement = True


def clean(s):
    s = s.lower().strip()
    s = s.replace('&', 'and')
    s = ''.join([i for i in s if (i.isalpha() or i.isspace())])
    s = ' '.join(s.split())
    return s


def book_id_to_name():

    mapper = {}
    mapper_original = {}
    for book in books:
        book_id = book[0]

        original_title = clean(book[9])

        title = clean(book[10])

        if book_id != 'book_id':
            mapper_original[original_title] = book_id
            mapper[title] = book_id

    print("Number of books: %s" % len(books))