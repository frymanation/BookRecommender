import csv
import html
import re

import requests
from xml.etree import ElementTree
import os
import sys
import random
import math
import numpy as np
import pandas as pd
import scipy
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import linear_kernel, cosine_similarity
from sklearn.decomposition import TruncatedSVD
from collections import defaultdict
import surprise

# Custom libraries


from xml_to_dict import dict_from_xml_file
from global_vars import bad_features

not_found_error_message = "That username doesn't seem to exist on Goodreads, I'm sorry"
private_error_message = "This user account is private, I'm sorry"
no_ratings_error_message = "You don't have any ratings on the books we have access to, I'm sorry"


def get_id_from_username(username, api_key):
    response = requests.get('https://www.goodreads.com/user/show/?key=' + api_key + '&username=' + username + '&format=xml')
    tree = ElementTree.fromstring(response.content)
    try:
        user_id = tree.find('user').find('id').text
        return user_id
    except:
        # raise ValueError('Invalid Goodreads username, not id returned')
        return None


def get_user_vector(user_input, mapper):
    """ Gets the user ratings vector of a user
    Args:
        user_input::str
            username of the user
        mapper::dict
            maps the goodreads book id to our ids
    Returns:
        user_vector::np.array
            an array of 10000 ratings for the given user
        error_message::str
            an error message string, if there is an error
    """
    try:
        sparse_q = scipy.sparse.load_npz('static/data/cached_users/user_' + user_input + '.npz')
        q = sparse_q.toarray()
        q = np.array(q[0].tolist())
        print('found user_vector...')
        return q, None
    except:
        q = np.zeros((10000), dtype = np.float)
        api_key = secret.API_KEY
        if not user_input.isdigit():
            user_id = get_id_from_username(user_input, api_key)
        else:
            user_id = user_input

        if user_id is None:
            return None, not_found_error_message

        page = 1
        total_valid_reviews = 0
        while True:
            response = requests.get('https://www.goodreads.com/review/list/?v=2&id=' + user_id + '&shelf=read&format=xml&key=' + api_key + '&per_page=200&page=' + str(page))
            tree = ElementTree.fromstring(response.content)
            reviews = tree.find('reviews')
            if reviews is None:
                return None, private_error_message
            for review in reviews:
                goodreads_book_id = str(review.find('book').find('id').text)
                if goodreads_book_id in mapper:
                    book_id = int(mapper[goodreads_book_id])
                    rating = int(review.find('rating').text)
                    q[book_id - 1] = float(rating)
                    total_valid_reviews += 1
            page += 1

            print(len(reviews))
            if len(reviews) < 1:
                break

        print("total valid reviews: %s" % (total_valid_reviews))
        if total_valid_reviews < 1:
            return None, no_ratings_error_message

        # TODO: turn off if using partial fit
        # q = feature_scaling(q)

        # Disable this until we find a 'smart' caching solution
        # print('saving user_vector...')
        # scipy.sparse.save_npz('static/data/cached_users/user_'+user_input+'.npz', scipy.sparse.csr_matrix(q))

        return q, None


def feature_scaling(q):
    """ Scales the user features using the mean and the
    standard deviation.
    """
    if q.dtype != np.float:
        q = q.astype(np.float)
    nonzero = np.nonzero(q)
    nonzero_ratings = q[nonzero]
    mean = np.mean(nonzero_ratings)
    std = np.std(nonzero_ratings)
    print('Mean: %s' % (mean))
    print('S.D: %s' % (std))
    q[nonzero] = (1.0 + q[nonzero] - mean) / std
    return q


def chunker(top_books):
    # chunk into groups of 3 to display better in web app
    chunks = []
    current_chunk = []
    for i in range(len(top_books)):
        if len(current_chunk) < 3:
            current_chunk.append(top_books[i])
        else:
            chunks.append(current_chunk)
            current_chunk = [top_books[i]]

    chunks.append(current_chunk)
    return chunks


def clean_string(s):
    # often times a book will be missing a feature so we have to return if None
    if not s:
        return s

    # clean html
    TAG_RE = re.compile(r'<[^>]+>')
    s = html.unescape(s)
    s = TAG_RE.sub('', s)
    s = s.lower()
    return s


def get_mapper(filename):
    mapper = {}
    with open(filename, "r", encoding='utf8') as f:
        reader = csv.reader(f, delimiter=",")
        for i, line in enumerate(reader):
            mapper[line[1]] = line[0]
    return mapper


def get_tags(book_tags, tags):
    tag_defs = {}
    with open(tags, "r", encoding='utf8') as f:
        reader = csv.reader(f, delimiter=",")
        for i, line in enumerate(reader):
            tag_defs[line[0]] = line[1]

    books = {}
    with open(book_tags, "r", encoding='utf8') as f:
        reader = csv.reader(f, delimiter=",")
        for i, line in enumerate(reader):
            goodreads_book_id = line[1]
            tag_id = line[2]
            count = line[3]
            if goodreads_book_id not in books:
                books[goodreads_book_id] = {}

            tag_name = tag_defs[tag_id]
            if tag_name not in bad_features:
                books[goodreads_book_id][tag_name] = count
    return books


# Read in book metadata and store in a dictionary
def get_books(data_path):
    metadata_directory = data_path + 'books_xml/'
    goodreads_to_bookid = get_mapper(data_path + 'books.csv')
    book_tags = get_tags(data_path + 'book_tags_with_bookid.csv', data_path + 'tags.csv')
    books = []

    for file in os.listdir(metadata_directory):
        filename = metadata_directory + '/' + os.fsdecode(file)
        raw_book = dict_from_xml_file(filename)

        book = {}
        goodreads_id = raw_book['book']['id']
        book['id'] = goodreads_to_bookid[goodreads_id]
        book['title'] = raw_book['book']['title']
        book['image_url'] = raw_book['book']['image_url']
        book['url'] = raw_book['book']['url']
        book['author'] = raw_book['book']['authors']['author']

        # if multiple authors, only use first (main) author
        if isinstance(book['author'], dict):
            book['author'] = book['author']['name']
        else:
            book['author'] = book['author'][0]['name']

        book['description'] = raw_book['book']['description']
        book['description'] = clean_string(book['description'])

        # Turn popular shelves into soup
        normalizing_value = 5


        # Turn book tags into soup
        book['tags'] = ''
        tags = book_tags[goodreads_id]
        for key, value in tags.items():
            for i in range(int(value) // normalizing_value):
                book['tags'] += ' ' + key

        books.append(book)
    return books


def get_book_dataframe(data_path):
    # check if dataframe already exists
    try:
        books = pd.read_pickle('../.tmp/books_dataframe')
        print("found books_dataframe in file...")
        return books
    except:
        # Get books as dictionary of all its features
        books = get_books(data_path)

        df = pd.DataFrame(books)
        df['id'] = df['id'].astype(int)
        df = df.sort_values(by=['id'])
        df = df.set_index('id')

        # Replace NaN with an empty string
        df['description'] = df['description'].fillna('')
        print('saving books_dataframe to file')
        df.to_pickle('../.tmp/books_dataframe')
        return df

def reduce_matrix(X, n_components=1000, n_iter=7, random_state=None):
    """ Uses SVD to reduce a matrix into its components

    Args:
        X:              the matrix to reduce
        n_components:   number of singular values to limit to
        n_iter:         the number of iterations for SVD
        random_state:   the random initial state SVD
    Returns:
        U: the row representations
        S: the singular values
        V: the column representations
    """
    svd = TruncatedSVD(n_components=n_components, n_iter=n_iter, random_state=random_state)
    reduced_matrix = svd.fit_transform(X)
    return reduced_matrix, svd.singular_values_, svd.components_


def get_sparse(ratings):
    users = list(ratings.user_id.unique())
    books = list(ratings.book_id.unique())
    data = ratings['rating'].tolist()
    row = ratings.user_id.astype('category', categories=users).cat.codes
    col = ratings.book_id.astype('category', categories=books).cat.codes
    sparse_matrix = csr_matrix((data, (row, col)), shape=(len(users), len(books)), dtype=np.dtype('u1'))
    return sparse_matrix



def get_book_features(df):
    """ Returns the sparse feature vector of books.
    The features are the tf-idf values of the book descriptions,
    popular shelves, and book tags.
    """
    # see if file exists in file
    try:
        feature_matrix = scipy.sparse.load_npz('../.tmp/feature_matrix.npz')
        print('feature_matrix exists in file...')
        return feature_matrix
    except:
        tfidf = TfidfVectorizer(stop_words='english')

        tfidf_matrix_description = tfidf.fit_transform(df['description'])
        tfidf_matrix_shelves = tfidf.fit_transform(df['popular_shelves'])
        tfidf_matrix_tags = tfidf.fit_transform(df['tags'])

        # Weight the smaller matrices bc ration to largest column matrix
        shelves_weight = tfidf_matrix_description.shape[1] / tfidf_matrix_shelves.shape[1]
        tags_weight = tfidf_matrix_description.shape[1] / tfidf_matrix_tags.shape[1]

        tfidf_matrix_shelves = tfidf_matrix_shelves.multiply(shelves_weight)
        tfidf_matrix_tags = tfidf_matrix_tags.multiply(tags_weight)

        feature_matrix = scipy.sparse.hstack([tfidf_matrix_description, tfidf_matrix_shelves, tfidf_matrix_tags])
        print('printing feature_matrix to file')
        scipy.sparse.save_npz('../.tmp/feature_matrix', feature_matrix)
        return feature_matrix


def get_book_authors(df):
    """ Returns the sparse author counts matrix """
    count_matrix_author = pd.get_dummies(df['author'])
    count_matrix_author = scipy.sparse.csr_matrix(count_matrix_author.values)
    return count_matrix_author



