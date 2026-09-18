from flask_wtf import FlaskForm

from wtforms import (
    HiddenField,
    SubmitField,
)


class ChooseMapForm(FlaskForm):
    xmin = HiddenField("xmin")
    ymin = HiddenField("ymin")
    xmax = HiddenField("xmax")
    ymax = HiddenField("ymax")

    submit = SubmitField("Calculer")
