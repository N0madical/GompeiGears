from flask import Blueprint, url_for
from app import main

admin_blueprint = Blueprint('admin', __name__)

from app.admin import admin_routes