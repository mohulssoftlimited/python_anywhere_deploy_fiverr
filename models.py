from datetime import datetime
from flask_login import UserMixin
from extensions import db

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    first_name = db.Column(db.String(30), nullable=False)
    last_name = db.Column(db.String(30), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(2), nullable=False)  # Using 2-letter state codes
    is_admin = db.Column(db.Boolean, default=False)
    urls = db.relationship('URLMonitor', backref='user', lazy=True)

class URLMonitor(db.Model):
    __tablename__ = 'url_monitor'
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), nullable=False)
    site_status = db.Column(db.String(20), nullable=False, default="Unknown")
    ssl_status = db.Column(db.String(20), nullable=False, default="Unknown")
    last_checked = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
