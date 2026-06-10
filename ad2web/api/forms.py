# -*- coding: utf-8 -*-

import string
from flask_wtf import FlaskForm as Form
from wtforms import URLField, EmailField, TelField
from wtforms import (ValidationError, HiddenField, StringField, HiddenField,
        PasswordField, SubmitField, TextAreaField, IntegerField, RadioField,
        FileField, DecimalField, BooleanField, SelectField, FormField, FieldList)
from wtforms.validators import (DataRequired, Length, EqualTo, Email, NumberRange,
        URL, AnyOf, Optional, IPAddress)
from flask_login import current_user

from ..user import User

from ..widgets import ButtonField

class APIKeyForm(Form):
    pass