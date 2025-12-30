from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField, HiddenField, BooleanField, URLField, TelField, EmailField
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.validators import  ValidationError, DataRequired, Optional, Length, Email, URL, Regexp
from app.main.models import Bike, User
import re
import datetime

from app import db
import sqlalchemy as sqla


class BikeSortForm(FlaskForm):
    today = datetime.date.today()
    first_of_month = datetime.datetime(today.year, today.month, 1, 0, 0, 0)
    date = SelectField('Date',choices = [(7, 'Past Week'),
                                         (30, 'This Month'),
                                         (91,'Past 3 Months'),
                                         (183, 'Past 6 Months'),
                                         (365, 'This Year'),
                                         (0, 'All Time')])
    # duration = SelectField('Duration',choices = [(0, 'All'), (8, 'Over 8 Hours'), (12,'Over 12 Hours')])
    duration = BooleanField('Overtime only:')
    search = StringField('Search', validators=[Length(max=100)])
    bike = QuerySelectField('Bike ID', query_factory= lambda : db.session.scalars(sqla.select(Bike).order_by(Bike.id)),
                                   get_label = lambda theBike : theBike.get_name(),
                                   allow_blank = True)
    user = QuerySelectField('User ID', query_factory= lambda : db.session.scalars(sqla.select(User).order_by(User.id)),
                                   get_label = lambda theUser : theUser.get_id(),
                                   allow_blank = True)
    submit = SubmitField('Filter')

class UserSortForm(FlaskForm):
    search = StringField('Search', validators=[Length(max=100)])
    is_admin = BooleanField('Is Admin')
    locked = BooleanField('Is Locked')
    user = QuerySelectField('User ID', query_factory= lambda : db.session.scalars(sqla.select(User).order_by(User.id)),
                                   get_label = lambda theUser : theUser.get_id(), 
                                   allow_blank = True)
    user_email = QuerySelectField('User Email', query_factory= lambda : db.session.scalars(sqla.select(User).order_by(User.email)),
                                   get_label = lambda theUser : theUser.get_email(), 
                                   allow_blank = True)
    
    submit = SubmitField('Filter')

class FleetEditForm(FlaskForm):
    user_agreement = URLField('User Agreement URL', validators=[Length(max=256), DataRequired(), URL()])
    contact_email = EmailField('Contact Email Address', validators=[Length(max=256), DataRequired(), Email()])
    contact_phone = TelField('Contact Phone Number', validators=[Length(max=10), DataRequired(), Regexp(r'[0-9]{10}', message="Invalid Phone Number")])

    submit = SubmitField('Update')

class StationEditForm(FlaskForm):
    name = StringField('Station Name', validators=[DataRequired(), Length(max=100)])
    lat1 = HiddenField('Latitude 1', validators=[DataRequired()])
    long1 = HiddenField('Longitude 1', validators=[DataRequired()])
    lat2 = HiddenField('Latitude 2', validators=[DataRequired()])
    long2 = HiddenField('Longitude 2', validators=[DataRequired()])
    lat3 = HiddenField('Latitude 3', validators=[DataRequired()])
    long3 = HiddenField('Longitude 3', validators=[DataRequired()])
    lat4 = HiddenField('Latitude 4', validators=[DataRequired()])
    long4 = HiddenField('Longitude 4', validators=[DataRequired()])

    submit = SubmitField('Update')

class StationDeleteForm(FlaskForm):
    submit = SubmitField('Delete Station')

class MessagingForm(FlaskForm):
    recipients = QuerySelectMultipleField(
        'Recipients',
        query_factory=lambda : db.session.scalars(sqla.select(User).order_by(User.email)),
        get_label=lambda user : user.email,
        widget=ListWidget(prefix_label=False), 
        option_widget=CheckboxInput()
    )
    recipients_all = BooleanField('Recipients - All Members')
    mock = BooleanField('Mock', [Optional()])
    subject = StringField('Subject', validators=[DataRequired(), Length(max=100)])
    body = TextAreaField('Body', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('Send')

class ReportSortForm(FlaskForm):
    search = StringField('Search', validators=[Length(max=100)])
    category = SelectField('Category', choices=[(0, 'All'), (1, 'Brake Issue'), (2, 'App Issue'), (3, 'Tire Issue'), (4, 'Lock Issue'), (5, 'Gear Issue'), (6, 'Frame Issue')])
    submit = SubmitField('Filter')