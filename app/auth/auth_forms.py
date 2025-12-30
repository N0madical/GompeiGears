from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, IntegerField
from wtforms_alchemy.fields import PhoneNumberField
from wtforms.validators import ValidationError, DataRequired, EqualTo, Email, Length, NumberRange, Optional
import phonenumbers


class AccountForm(FlaskForm):
    preferred = StringField('Preferred Name', validators = [Optional(), Length(min=2, max=25)])
    phone = PhoneNumberField('Phone Number', validators=[Optional()])
    unsubscribe_notifications = BooleanField('Unsubscribe from Notifications', validators=[Optional()])
    submit = SubmitField('Update Account')

    # def validate_phone(form, field):
    #     if len(field.data) > 16:
    #         raise ValidationError('Invalid phone number.')
    #     elif field.data != "":
    #         print("Trying to test")
    #         try:
    #             input_number = phonenumbers.parse(field.data)
    #             if not (phonenumbers.is_valid_number(input_number)):
    #                 print("Phone number is nto valid.")
    #                 raise ValidationError('Invalid phone number.')
    #         except Exception as e:
    #             print("Bru I cant understand that", e)
    #             raise ValidationError('Invalid phone number.')