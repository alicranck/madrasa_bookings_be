from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine

# Initialization
application = Flask(__name__, template_folder="../templates", static_folder="../static")
application.config.from_object(Config)
DB_URI = application.config['SQLALCHEMY_DATABASE_URI']
engine = create_engine(DB_URI)

from app import routes
