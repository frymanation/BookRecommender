from flask_wtf import FlaskForm
from wtforms import Form, StringField, SelectField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Email, Length, DataRequired


# Search for book by title or author,
class BookSearchForm2(Form):
    choices = [('title', 'Title'),('authors', 'Author')]
    select = SelectField('Search for books:', choices=choices)
    search = StringField('')


# Select book by book id
class BookIDSelectForm(FlaskForm):
    submit = SubmitField('Submit')


# Search for book by book id
class BookIDSearchForm(FlaskForm):
    book_id = StringField('book_id', validators=[InputRequired(), Length(max=50)])
    submit = SubmitField('Submit')


# Form that allows search using book by book id, author, or title
class BookSearchForm(FlaskForm):

    choices = [('book_id', 'Book ID'),('title', 'Title'),('authors', 'Author')]
    select = SelectField('Search for a book:&nbsp;&nbsp;&nbsp;',
                         choices=[('book_id', 'By Book ID'), ('title', 'By Title'), ('authors', 'By Author')])
    search = StringField('', validators=[DataRequired()])
    submit = SubmitField('Search')


# Form for library member login
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(max=50)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4, max=80)])
    submit = SubmitField('Submit')


# Form for library member registration
class SignUpForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=1, max=40)])
    first_name = StringField('First Name', validators=[InputRequired()])
    last_name = StringField('Last Name', validators=[InputRequired()])
    email = StringField('Email Address', validators=[InputRequired(), Email(message='Invalid email')])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4, max=80)])
    submit = SubmitField('Submit')


class BookForm(FlaskForm):
    bookname=StringField('Enter Book Name...',validators=[DataRequired()])
    submit=SubmitField('Search')