from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField, BooleanField, HiddenField, RadioField
from wtforms.widgets import CheckboxInput, ListWidget
from wtforms.validators import  ValidationError, DataRequired, Length
from wtforms_sqlalchemy.fields import QuerySelectField

from app import db
from app.main.models import Bike, Station
import sqlalchemy as sqla

class RentalForm (FlaskForm):
    lat = HiddenField('Latitude', validators=[DataRequired()])
    long = HiddenField('Longitude', validators=[DataRequired()])
    notification_endpoint = HiddenField('Notification endpoint')
    notification_p256dh_key = HiddenField('Notification p256dh key')
    notification_auth_key = HiddenField('Notification auth key')
    signed_agreements = BooleanField('By checking this box, you agree to the user agreement.')
    start = SubmitField('Start Rental')

class EndRentalForm (FlaskForm):
    rating = RadioField('Rating', choices=(('positive', 'Positive'), ('negative', 'Negative')), validators=[DataRequired()])
    lat = HiddenField('Latitude', validators=[DataRequired()])
    long = HiddenField('Longitude', validators=[DataRequired()])
    report_issue = BooleanField('I would like to report an issue with this bike')
    end = SubmitField('End Rental')

class SetLockForm (FlaskForm):
    state = HiddenField('Locked', validators=[DataRequired()])
    setlock = SubmitField('Lock/Unlock')

class CreateReportForm(FlaskForm):
    bike_id = QuerySelectField('Bike', 
                               query_factory= lambda : db.session.scalars(sqla.select(Bike).order_by(Bike.name)),
                               get_label = lambda theBike : theBike.get_name(),
                               allow_blank=False)
    category = SelectField('Category of Report', choices=[(0, 'Other'), (1, 'Brake Issue'), (2, 'App Issue'), (3, 'Tire Issue'), (4, 'Lock Issue'), (5, 'Gear Issue'), (6, 'Frame Issue')])
    description = TextAreaField(validators=[Length(min=1, max=1500)])
    submit = SubmitField('Submit Report')

