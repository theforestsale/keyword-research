from flask import Blueprint, render_template
from models import Search, Folder

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    recent = Search.query.order_by(Search.created_at.desc()).limit(10).all()
    folders = Folder.query.order_by(Folder.name.asc()).all()
    return render_template("index.html", recent_searches=recent, folders=folders)


@main_bp.route("/api/health")
def health():
    from flask import jsonify
    return jsonify({"status": "ok"})
