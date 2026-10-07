from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Folder(db.Model):
    __tablename__ = "folders"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    searches = db.relationship("Search", backref="folder", lazy="select")


class Search(db.Model):
    __tablename__ = "searches"

    id = db.Column(db.Integer, primary_key=True)
    seed_keyword = db.Column("query", db.String(100), nullable=False)
    options_json = db.Column(db.Text, nullable=False, default="{}")
    folder_id = db.Column(db.Integer, db.ForeignKey("folders.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    keywords = db.relationship("Keyword", backref="search", lazy="select",
                               cascade="all, delete-orphan", order_by="Keyword.volume_est.desc()")


class Keyword(db.Model):
    __tablename__ = "keywords"

    id = db.Column(db.Integer, primary_key=True)
    search_id = db.Column(db.Integer, db.ForeignKey("searches.id"), nullable=False)
    keyword = db.Column(db.String(200), nullable=False)
    volume_est = db.Column(db.Integer, nullable=False, default=0)
    difficulty_est = db.Column(db.Integer, nullable=False, default=0)
    intent = db.Column(db.String(20), nullable=False, default="unknown")
    cpc_est = db.Column(db.Float, nullable=False, default=0.0)
