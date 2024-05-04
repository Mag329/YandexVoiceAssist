import sqlalchemy as db
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


base = declarative_base()
engine = create_engine("sqlite:///bot.db")
Session = sessionmaker(bind=engine)


class User(base):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    tokens = db.Column(db.Integer, default=0)
    symbols = db.Column(db.Integer, default=0)
    blocks = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default="test")


class History(base):
    __tablename__ = "history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    history = db.Column(db.String, default="None")
    last_type = db.Column(db.String)
    status = db.Column(db.String(50), default="active")


class Stats(base):
    __tablename__ = "stats"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    type = db.Column(db.String)
