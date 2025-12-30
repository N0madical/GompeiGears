from flask import send_file, url_for

from config import Config
from app import create_app, db
import sqlalchemy as sqla
import sqlalchemy.orm as sqlo
from identity.flask import Auth

app = create_app(Config)

@app.shell_context_processor
def make_shell_context():
    return {'sqla': sqla, 'sqlo': sqlo, 'db': db}


@app.before_request
def initDB(*args, **kwargs):
    if app._got_first_request:
        db.create_all()


def define_ms(app, host):
    app.ms_login = Auth(
        app,
        authority=app.config["AUTHORITY"],
        client_id=app.config["CLIENT_ID"],
        client_credential=app.config["CLIENT_SECRET"],
        redirect_uri="https://" + host + ":8000/auth/login"
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)