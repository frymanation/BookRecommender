import csv
import datetime
import json
import os
import pickle
import urllib.request as urllib2
from datetime import *
from json import JSONEncoder
from urllib.parse import quote
from flask.cli import load_dotenv

import pandas as pd
# import xmltodict
import xmltodict as xmltodict
# from dotenv import load_dotenv
#############################################################################################################
from flask import Flask, request, redirect, url_for, render_template, flash
#############################################################################################################
# Added as Test
#############################################################################################################
from flask import jsonify, session, json
from flask_cors import CORS
from flask_login import login_user, LoginManager, current_user, UserMixin, login_required, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from forms import LoginForm, SignUpForm, BookIDSearchForm
from te import get_recommendations

load_dotenv()
data_path = '/Users/jon/Code_Repo/BookRecommender/'

app = Flask(__name__)
# model = pickle.load(open('my_df.pickle','rb'))
# print(model)
## Load the data
with open(data_path + "save_books.pkl", 'rb') as infile:
    books = pickle.load(infile)

## Load the Model

#################################################################
# Creating global variables
#################################################################


#################################################################
# Creating Database
#################################################################
CORS(app)
ENV = 'prod'

LOCAL_DB_URL = os.getenv("sqlite://///Users/jon/Code_Repo/BookRecommender/new_db.db")
REMOTE_DB_URL = os.getenv("REMOTE_DB_URL")
SECRET_KEY = os.getenv("D3tR01Tl10n$")

# Setting database configs
if ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite://///Users/jon/Code_Repo/BookRecommender/new_db.db"
else:
    app.debug = False

    app.config['SECRET_KEY'] = "D3tR01Tl10n$"
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite://///Users/jon/Code_Repo/BookRecommender/new_db.db"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

app.secret_key = 'D3tR01Tl10n$'
login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = 'login'


#################################################################
# Data Loading Functions
#################################################################
def load_books():
    """ Loads in the books and titles from the pickled dataframe """
    global books, titles
    if books is None or titles is None:
        titles = []
        books = pd.read_csv('/Users/jon/Code_Repo/BookRecommender/static/data/books.csv')
        for index, row in books.iterrows():
            titles.append(row['title'])
        titles.sort()
        print('books loaded')


def load_title_mappers():
    """ Loads in the title mappers using books.csv """
    global bookid_to_title, title_to_bookid
    if bookid_to_title is None or title_to_bookid is None:
        bookid_to_title = {}
        title_to_bookid = {}
        filename = '/Users/jon/Code_Repo/BookRecommender/static/data/books.csv'
        with open(filename, "r", encoding='utf8') as f:
            reader = csv.reader(f, delimiter=",")
            for i, line in enumerate(reader):
                bookid = line[0]
                title = line[10].strip()
                bookid_to_title[bookid] = title
                title_to_bookid[title] = bookid
        print('books mapper loaded')


def load_id_mapper():
    """ Loads in the id mapper using books.csv.
    This maps goodreads book ids to our ids.
    """
    global mapper_id
    if mapper_id is None:
        mapper_id = {}
        filename = '/Users/jon/Code_Repo/BookRecommender/static/data/books.csv'
        with open(filename, "r", encoding='utf8') as f:
            reader = csv.reader(f, delimiter=",")
            for i, line in enumerate(reader):
                mapper_id[line[1]] = line[0]
        print('mapper_id loaded')


def load_data():
    global titles
    load_title_mappers()
    load_id_mapper()
    load_books()
    # load_top_recs_each_book()
    return render_template('book_list.html', titles=titles)


#################################################################
# Recommender Function
#################################################################


#################################################################
# Creating custom functions for id assignment and user id lookup
#################################################################
# Creation of id used by Ratings table to allow auto assignment of the col_id variable
def customid():
    idquery = db.session.query(Ratings).order_by(Ratings.col_id.desc()).first()
    last_id = int(idquery.col_id)
    next_id = int(last_id) + 1
    return next_id


# lookup used by Ratings Table to use associated user name to ascertain the associated user id
def user_id(userid):
    if db.session.query(Ratings).filter(Ratings.userid == User.id).count() == 0:
        idquery = db.session.query(Ratings).order_by(Ratings.userid.desc()).first()
        last_id = int(idquery.userid)
        next_id = int(last_id) + 1
        return next_id
    else:
        idquery = db.session.query(Ratings).filter(Ratings.userid == User.id).first()
        idquery_old = idquery.userid
        return idquery_old


# function to increment the gr_id by 1 for each new enter in gr_books table
def idcounter():
    iding = db.session.query(GrBook).order_by(GrBook.gr_id.desc()).first()
    last_id = int(iding.gr_id)
    next_id = int(last_id) + 1
    return next_id


def parse_xml(request_xml):
    content_dict = xmltodict.parse(request_xml)
    return jsonify(content_dict)


class CustomJSONEncoder(JSONEncoder):

    def default(o):
        if type(o) == datetime.timedelta:
            return str(o)
        elif type(o) == datetime.datetime:
            return o.isoformat()
        else:
            return super().default(o)


# app.json_encoder = CustomJSONEncoder


#################################
# Model Creation
#################################
# Function to get identity of current user
@login_manager.user_loader
def get_user(ident):
    return User.query.get(int(ident))


# Creating User model:
# During signup, User will submit username, first name, last name, email address, and create a password.
# Building user model
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200))
    first_name = db.Column(db.String(200))
    last_name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    password = db.Column(db.String(200))

    def __init__(self, username, password, first_name, last_name, email):
        self.username = username
        self.password = password
        self.first_name = first_name
        self.last_name = last_name
        self.email = email

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


# Creating Ratings model:
# The model will consist of col_id, a rating set by the logged in user, and will associate with:
# userid from users table
# book id,from books table
class Ratings(db.Model):
    __tablename__ = 'ratings'
    col_id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.Integer)
    rating = db.Column(db.Integer)
    book_id = db.Column(db.Integer)

    def __init__(self, col_id, userid, rating, book_id):
        self.col_id = col_id
        self.userid = userid
        self.rating = rating
        self.book_id = book_id


# Creation of  New Recommendations Model:
# The model will allow reading suggestions to be provided to library members based on reading history
class NewRecs(db.Model):
    __tablename__ = 'new_recs'
    id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.Integer)
    book_id = db.Column(db.Integer)
    prediction = db.Column(db.Float)

    def __init__(self, userid, book_id, prediction):
        self.userid = userid
        self.book_id = book_id
        self.prediction = prediction


# Creation of a lookup between book_id and gr_book_id
class GrBook(db.Model):
    __tablename__ = 'gr_books'
    gr_id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer)

    def __init__(self, gr_id, book_id):
        self.gr_id = gr_id
        self.book_id = book_id


# Creation of Book model
# The model will consist of an assortment of values cateloging the books available for GCOPL members
class Book(db.Model):
    __tablename__ = 'books'
    book_id = db.Column(db.Integer, primary_key=True)
    goodreads_book_id = db.Column(db.Integer)
    best_book_id = db.Column(db.Integer)
    work_id = db.Column(db.Integer)
    books_count = db.Column(db.Integer)
    isbn = db.Column(db.Integer)
    isbn13 = db.Column(db.Integer)
    authors = db.Column(db.String)
    original_publication_year = db.Column(db.Integer)
    original_title = db.Column(db.String)
    title = db.Column(db.String)
    language_code = db.Column(db.String)
    average_rating = db.Column(db.Float)
    ratings_count = db.Column(db.String)
    work_ratings_count = db.Column(db.Integer)
    work_text_reviews_count = db.Column(db.Integer)
    ratings_1 = db.Column(db.Integer)
    ratings_2 = db.Column(db.Integer)
    ratings_3 = db.Column(db.Integer)
    ratings_4 = db.Column(db.Integer)
    ratings_5 = db.Column(db.Integer)
    image_url = db.Column(db.String)
    small_image_url = db.Column(db.String)

    # review = db.relationship('Review', backref='book', lazy='dynamic')
    # user = db.relationship('User', secondary=association_table, back_populates='book_reviewed')

    def __init__(self, book_id, goodreads_book_id, best_book_id, work_id, books_count, isbn, isbn13, authors,
                 original_publication_year,
                 original_title, title, language_code, average_rating, ratings_count, work_ratings_count,
                 work_text_reviews_count, ratings_1, ratings_2, ratings_3, ratings_4, ratings_5, image_url,
                 small_image_url):
        """"""
        self.book_id = book_id
        self.goodreads_book_id = goodreads_book_id
        self.best_book_id = best_book_id
        self.work_id = work_id
        self.books_count = books_count
        self.isbn = isbn
        self.isbn13 = isbn13
        self.authors = authors
        self.original_publication_year = original_publication_year
        self.original_title = original_title
        self.title = title
        self.language_code = language_code
        self.average_rating = average_rating
        self.ratings_count = ratings_count
        self.work_ratings_count = work_ratings_count
        self.work_text_reviews_count = work_text_reviews_count
        self.ratings_1 = ratings_1
        self.ratings_2 = ratings_2
        self.ratings_3 = ratings_3
        self.ratings_4 = ratings_4
        self.ratings_5 = ratings_5
        self.image_url = image_url
        self.small_image_url = small_image_url


class Book_Tags(db.Model):
    __tablename__ = 'book_tags'
    goodreads_book_id = db.Column(db.Integer, primary_key=True)
    tag_id = db.Column(db.Integer, primary_key=True)
    count = db.Column(db.Integer)

    def __init__(self, goodreads_book_id, tag_id, count):
        self.goodreads_book_id = goodreads_book_id
        self.tag_id = tag_id
        self.count = count


class Tags(db.Model):
    __tablename__ = 'tags'
    tag_id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String)

    def __init__(self, tag_id, tag_name):
        self.tag_id = tag_id
        self.tag_name = tag_name


class To_read(db.Model):
    __tablename__ = 'to_read'
    user_id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, primary_key=True)

    def __init__(self, user_id, book_id):
        self.user_id = user_id
        self.book_id = book_id


#################################
# Data Preprocessing
#################################

################################
# Building routes for the site #
################################


# Route that directs to main home page for GCOPL
@app.route('/')
@app.route('/index')
def index():
    return render_template("index.html")


# Registration page for new library members
@app.route('/signup', methods=['POST', 'GET'])
def signup():
    form = SignUpForm(meta={'csrf': False})

    if form.validate_on_submit():
        # Password security
        hashed_password = generate_password_hash(form.password.data, method="sha256")

        # Check if user already exists in the database
        user_already_exists = User.query.filter_by(username=form.username.data).first()
        if user_already_exists:
            flash("You already have an account with that email address!")
            return render_template('login.html', form=form)

        # Create a new user, then go to Login page
        else:
            new_user = User(username=form.username.data, first_name=form.first_name.data, last_name=form.last_name.data,
                            email=form.email.data, password=hashed_password, )
            db.session.add(new_user)
            db.session.commit()
            session['username'] = new_user.username
            session['user_id'] = user_id(session.get('username'))
            session['first_name'] = new_user.first_name
            session['last_name'] = new_user.last_name
            session['email'] = new_user.email
            return redirect(url_for('get_profile'))
    return render_template('signup.html', form=form, title='signup')


# Routes to login page for existing library members
# sign-in page
# Route for member login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('get_profile'))
    # Initialize form
    form = LoginForm()
    if form.validate_on_submit():
        # login_user(user)
        # next = flask.request.args.get('next')
        # Check to see if email exists in the database
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('get_profile'))
    return render_template('login.html', title='Sign In', form=form)


# Signout page
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect('login')


# Routes to the currently authenticated library members main profile interface
# Profile interface includes:
# Previous book ratings
# Book recommendations based on previous reading history. Requires 10+ ratings to provide recommendation
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def get_profile():
    if request.method == 'GET':
        userid = int(current_user.id)
        username = str(current_user.username)
        ratings = db.session.query(Ratings).filter(Ratings.userid == userid).all()

        ratings_list = []
        for i in ratings:
            gr_bookid = db.session.query(GrBook).filter(GrBook.book_id == i.book_id).first().book_id
            ratings_list.append([gr_bookid, i.rating])

        bk = []
        for i in ratings_list:
            response_string = 'https://www.goodreads.com/book/show?id=' + str(i[0]) + '&key=Ev590L5ibeayXEVKycXbAw'
            xml = urllib2.urlopen(response_string)
            data = xml.read()
            xml.close()
            data = xmltodict.parse(data)
            gr_data = json.dumps(data)
            goodreads_fnl = json.loads(gr_data)
            gr = goodreads_fnl['GoodreadsResponse']['book']
            bk.append(dict(id=gr['id'], title=gr['title'], authors=gr['authors'], image_url=gr['image_url'], average_rating=i[1]))

        book = dict(work=bk)
        return render_template('profile.html', books=book)
    else:
        return 'Error in login process...'


# Routes to search Interface that allows library member to search GCOPL catalog by book title
@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == 'POST':
        search_title = request.form.get("title")
        response_string = 'http://www.goodreads.com/search/index.xml?format=xml&key=Ev590L5ibeayXEVKycXbAw&q=' + quote(
            request.form.get("title"))
        test_list = []
        print(' test of get recommendations with Book Title: ' + search_title)
        if db.session.query(Book).filter(Book.title == search_title).count() > 0:
            book_id_from_title = []
            get_recommendations(search_title)
            for title in get_recommendations(search_title):
                # title_to_bookid(title)

                print('TITLE: ', title)
                title_id = db.session.query(Book).filter(Book.title == title).first()
                print(title_id.goodreads_book_id)
                book_id_from_title.append(title_id.goodreads_book_id)
                print('book_id_from_title list print: ', book_id_from_title)

        else:
            print('No titles found matching search term to provide recommendations')
        print('TEST_LIST: ', test_list)

        xml = urllib2.urlopen(response_string)
        data = xml.read()
        xml.close()
        data = xmltodict.parse(data)
        gr_data = json.dumps(data)
        goodreads_fnl = json.loads(gr_data)
        gr = goodreads_fnl['GoodreadsResponse']['search']['results']

        if not request.form.get("title"):
            return "Please enter a book title below."

        return render_template("search_results.html", books=gr)

    else:
        username = current_user.username
        return render_template("search.html", username=username)


# Routes to book detail for a selected title by the current user
@app.route("/book_details/<book_id>")
@login_required
def book_details(book_id):
    response_string = 'https://www.goodreads.com/book/show?id=' + book_id + '&key=Ev590L5ibeayXEVKycXbAw'

    xml = urllib2.urlopen(response_string)
    data = xml.read()
    xml.close()
    data = xmltodict.parse(data)
    gr_data = json.dumps(data)
    goodreads_fnl = json.loads(gr_data)
    gr = goodreads_fnl['GoodreadsResponse']['book']

    # tag_filter = db.session.query(GrBook).filter(GrBook.book_id == book_id).first()

    return render_template('book_details.html', book=gr, title=Book.title)


# Routes to submit the new rating entered by the currently authenticated user
@app.route("/new-rating", methods=['POST'])
@login_required
def postnew():
    if request.method == 'POST':
        col_id = customid()
        userid = current_user.id
        print("Test of postnew userID: ", userid)
        rating = request.form['rating']
        book_id = request.form.get('bookid')

        print(str(db.session.query(GrBook).filter(GrBook.book_id == book_id).count()))
        if db.session.query(GrBook).filter(GrBook.book_id == book_id).count() == 0:
            gr_id = idcounter()
            grdata = GrBook(gr_id, book_id)
            db.session.add(grdata)
            db.session.commit()
        else:
            grfilter = db.session.query(GrBook).filter(GrBook.book_id == book_id).first()
            gr_id = grfilter.gr_id

        data = Ratings(col_id, userid, rating, book_id)
        db.session.add(data)
        db.session.commit()
        return render_template('success.html')


# Routes to submit the new rating entered by the currently authenticated user
@app.route('/user_ratings', methods=['GET', 'POST'])
@login_required
def user_ratings():
    userid = int(current_user.id)
    username = str(current_user.username)
    ratings = db.session.query(Ratings).filter(Ratings.userid == userid).all()
    # book_id = db.session.query(Ratings).filter(Ratings.book_id == books.goodreads_book_id).all()
    # gr_bookid = db.session.query(GrBook).filter(GrBook.book_id == i.book_id).first().book_id
    ratings_list = []
    if request.method == 'GET':
        userid = int(current_user.id)
        username = str(current_user.username)
        ratings_by_user = db.session.query(Ratings).filter(Ratings.userid == userid).all()

        book_id = db.session.query(Book).filter(Book.book_id == userid).all()

        for i in ratings_by_user:
            ratedBook = Book
            ratedBook.goodreads_book_id = i.book_id

            gr_bookid = db.session.query(GrBook).filter(GrBook.book_id == i.book_id).first().book_id
            # book_id = db.session.query(Book).filter(ratedBook.book_id == gr_bookid).first().book_id

            ratings_list.append([gr_bookid, i.rating])

            # print(ratings_list)
        rating_by_user = []
        for i in ratings_list:
            # print("print ratings list 1: ", ratings_list)
            response_string = 'https://www.goodreads.com/book/show?id=' + str(i[0]) + '&key=Ev590L5ibeayXEVKycXbAw'
            xml = urllib2.urlopen(response_string)
            data = xml.read()
            xml.close()
            data = xmltodict.parse(data)
            gr_data = json.dumps(data)
            goodreads_fnl = json.loads(gr_data)
            gr = goodreads_fnl['GoodreadsResponse']['book']
            rating_by_user.append(dict(id=gr['id'], book_title=gr['title'], image_url=gr['image_url'], rating=i[1]))
            # print("bk 2", rating_by_user)
        rate = dict(work=rating_by_user)

        return render_template('user_ratings.html', rating=rate, title=Book.title)

    if request.method == 'POST':

        for i in ratings_list:
            response_string = 'https://www.goodreads.com/book/show?id=' + str(i[0]) + '&key=Ev590L5ibeayXEVKycXbAw'
            xml = urllib2.urlopen(response_string)
            data = xml.read()
            xml.close()
            data = xmltodict.parse(data)
            gr_data = json.dumps(data)
            goodreads_fnl = json.loads(gr_data)
            gr = goodreads_fnl['GoodreadsResponse']['book']
            book_detail_book = book_details(gr)

            return render_template('book_details.html', book_detail_book)
    else:
        return render_template('user_ratings.html')


# Routes to the main books table that provides an overview of all books currently in the GCOPL catalog.
# This will eventually be enahnced by allowing the user to review specific book details page for a selected title
@app.route('/books', methods=['GET', 'POST'])
def books():
    form = BookIDSearchForm(meta={'csrf': False})
    if request.method == 'POST':
        response_string = 'http://www.goodreads.com/search/index.xml?format=xml&key=Ev590L5ibeayXEVKycXbAw&q=' + quote(
            request.form.get("title"))
        print(get_recommendations(request.form.get("title")))

        xml = urllib2.urlopen(response_string)
        data = xml.read()
        xml.close()
        data = xmltodict.parse(data)
        gr_data = json.dumps(data)
        goodreads_fnl = json.loads(gr_data)
        gr = goodreads_fnl['GoodreadsResponse']['search']['results']

        if not request.form.get("title"):
            return "Please enter a book title below."
        return render_template("books.html")

    else:
        username = current_user.username
        books = Book.query
        return render_template("books.html", books=books, form=form, title=Book.title, book_id=Book.book_id)


@app.route("/recs/<title>")
@login_required
def get_recs(title):
    if request.method == 'GET':
        userid = int(current_user.id)
        username = str(current_user.username)
        recs = get_recommendations(title)
        original_title = title
        gr_book_author = db.session.query(Book).filter(Book.title == title).first().authors
        gr_book_rating = db.session.query(Book).filter(Book.title == title).first().average_rating
        print(recs)

        recs_list = []
        for title in recs:
            gr_bookid = db.session.query(Book).filter(Book.title == title).first().goodreads_book_id
            gr_book_author = db.session.query(Book).filter(Book.title == title).first().authors
            gr_book_rating = db.session.query(Book).filter(Book.title == title).first().average_rating
            # gr_authors = db.session.query(Book).filter(Book.goodreads_book_id == gr_bookid).first().authors
            print('gr_bookid:', gr_bookid)
            print('gr_book_author:', gr_book_author)
            print('gr_book_rating:', gr_book_rating)
            recs_list.append([gr_bookid, title, gr_book_author, gr_book_rating])
            print('recs_list: ', recs_list)
        bk = []
        for i in recs_list:
            response_string = 'https://www.goodreads.com/book/show?id=' + str(i[0]) + '&key=Ev590L5ibeayXEVKycXbAw'
            xml = urllib2.urlopen(response_string)
            data = xml.read()
            xml.close()
            data = xmltodict.parse(data)
            gr_data = json.dumps(data)
            goodreads_fnl = json.loads(gr_data)
            gr = goodreads_fnl['GoodreadsResponse']['book']
            gr_book_author = db.session.query(Book).filter(Book.title == title).first().authors
            gr_book_rating = db.session.query(Book).filter(Book.title == title).first().average_rating
            bk.append(dict(id=gr['id'], book_title=gr['title'], image_url=gr['image_url']))

        book = dict(work=bk)
        return render_template('recs.html', recs=book, title=original_title)
    else:
        return 'Error in loading recommendations ...'

# Route for Library Branch Location Information
@app.route('/locations')
def locations():
    return render_template('locations.html')


# Route for About page providing basic information pertaining to the library system
@app.route('/about')
def about():
    return render_template("about.html")


if __name__ == '__main__':
    app.run(debug=True)
