from flask import Flask
from config import Config
from identity.flask import Auth
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_moment import Moment

db = SQLAlchemy()

migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.account'
moment = Moment()

ms_login = None
vapid_public_key = None
vapid_private_key = None

def create_app(config_class=Config):
    global ms_login, vapid_public_key, vapid_private_key

    app = Flask(__name__)
    app.config.from_object(config_class)
    app.static_folder = config_class.STATIC_FOLDER
    app.template_folder = config_class.TEMPLATE_FOLDER_MAIN

    db.init_app(app)
    migrate.init_app(app,db)
    login.init_app(app)
    moment.init_app(app)

    ms_login = Auth(
        app,
        authority=app.config["AUTHORITY"],
        client_id=app.config["CLIENT_ID"],
        client_credential=app.config["CLIENT_SECRET"],
        redirect_uri=app.config["REDIRECT_URI"]
    )

    vapid_public_key=app.config["VAPID_PUBLIC_KEY"]
    vapid_private_key=app.config["VAPID_PRIVATE_KEY"]
    
    # blueprint registration
    from app.main import main_blueprint as main
    main.template_folder = Config.TEMPLATE_FOLDER_MAIN
    app.register_blueprint(main)

    from app.auth import auth_blueprint as auth
    auth.template_folder = Config.TEMPLATE_FOLDER_AUTH
    app.register_blueprint(auth)

    from app.admin import admin_blueprint as admin
    admin.template_folder = Config.TEMPLATE_FOLDER_ADMIN
    app.register_blueprint(admin)

    from app.errors import error_blueprint as errors
    errors.template_folder = Config.TEMPLATE_FOLDER_ERRORS
    app.register_blueprint(errors)

    return app

def get_nav_pages(is_admin=True):
    pages = [
        {'url': "main.home", 'name': 'Map', 'icon': 'bi-map'},
        {'url': "main.managerental", 'name': 'Manage Rental', 'icon': 'bi-bicycle'},
        {'url': "main.create_report", 'name': 'Reports', 'icon': 'bi-flag'},
        {'url': "main.user_help", 'name': 'Help', 'icon': 'bi-patch-question'},
        {'url': "auth.account", 'name': 'Account', 'icon': 'bi-person-circle'},
    ]

    admin_pages = [
        {'url': "admin.load_admin_rides", 'name': 'Rides', 'icon': 'bi-hammer'},
        {'url': "admin.assets", 'name': 'Assets', 'icon': 'bi-columns'},
        {'url': "admin.load_admin_users", 'name': 'Users', 'icon': 'bi-people'},
        {'url': "admin.messaging", 'name': 'Messaging', 'icon': 'bi-chat-left-text'},
        {'url': "admin.load_admin_reports", 'name': 'Reports', 'icon': 'bi-wrench'},
        {'url': "admin.fleet_settings", 'name': 'Fleet', 'icon': 'bi-substack'},
    ]

    if is_admin:
        return [pages, admin_pages]
    else:
        return [pages]