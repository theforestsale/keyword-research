import csv
import io
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify, abort
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from models import db, Search, Keyword, Folder
from services.ai_researcher import (
    research_keywords,
    AIResearchError,
)
from routes.research import get_search_or_404, get_ai_client

manage_bp = Blueprint("manage", __name__)

BULK_MAX = 5
BULK_COUNT = 8
MAX_ROWS = 100


@manage_bp.route("/folders")
def folders_page():
    folders = Folder.query.order_by(Folder.name.asc()).all()
    return render_template("folders.html", folders=folders)


@manage_bp.route("/folders/create", methods=["POST"])
def folder_create():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Folder name is required.", "error")
        return redirect(url_for("manage.folders_page"))
    if len(name) > 100:
        flash("Folder name must be 100 characters or less.", "error")
        return redirect(url_for("manage.folders_page"))
    db.session.add(Folder(name=name))
    db.session.commit()
    flash(f'Folder "{name}" created.', "success")
    return redirect(url_for("manage.folders_page"))


@manage_bp.route("/folders/<int:folder_id>/delete", methods=["POST"])
def folder_delete(folder_id):
    folder = db.session.get(Folder, folder_id)
    if folder is None:
        abort(404)
    for s in folder.searches:
        s.folder_id = None
    db.session.delete(folder)
    db.session.commit()
    flash(f'Folder "{folder.name}" deleted (searches kept).', "success")
    return redirect(url_for("manage.folders_page"))


@manage_bp.route("/search/<int:search_id>/assign", methods=["POST"])
def search_assign_folder(search_id):
    search = get_search_or_404(search_id)
    folder_id = request.form.get("folder_id", "").strip()
    if folder_id:
        folder = db.session.get(Folder, int(folder_id))
        if folder:
            search.folder_id = folder.id
    else:
        search.folder_id = None
    db.session.commit()
    return redirect(url_for("research.view_results", search_id=search.id))


@manage_bp.route("/search/<int:search_id>/rename", methods=["POST"])
def search_rename(search_id):
    search = get_search_or_404(search_id)
    name = request.form.get("name", "").strip()
    if name:
        search.seed_keyword = name[:100]
        db.session.commit()
    return redirect(url_for("research.view_results", search_id=search.id))


@manage_bp.route("/search/<int:search_id>/delete", methods=["POST"])
def search_delete(search_id):
    search = get_search_or_404(search_id)
    name = search.seed_keyword
    db.session.delete(search)
    db.session.commit()
    flash(f'Search "{name}" deleted.', "success")
    return redirect(url_for("main.index"))


@manage_bp.route("/compare", methods=["GET", "POST"])
def compare():
    if request.method == "POST":
        ids = []
        for key in ("id1", "id2"):
            try:
                ids.append(int(request.form.get(key)))
            except (TypeError, ValueError):
                ids.append(None)
        ids = [i for i in ids if i]
        if len(ids) != 2:
            flash("Select exactly two searches to compare.", "error")
            return redirect(url_for("manage.compare"))
        return redirect(url_for("manage.compare", a=ids[0], b=ids[1]))
    searches = Search.query.order_by(Search.created_at.desc()).all()
    a = b = None
    if request.args.get("a") and request.args.get("b"):
        a = db.session.get(Search, int(request.args.get("a")))
        b = db.session.get(Search, int(request.args.get("b")))
    return render_template("compare.html", searches=searches, a=a, b=b)


@manage_bp.route("/import", methods=["GET", "POST"])
def import_keywords():
    if request.method == "POST":
        if not Config.AI_API_KEY:
            flash("AI key not configured. Add GROQ_API_KEY to your .env file.", "error")
            return redirect(url_for("manage.import_keywords"))
        file = request.files.get("file")
        if not file or not (file.filename or "").lower().endswith(".csv"):
            flash("Please upload a CSV file.", "error")
            return redirect(url_for("manage.import_keywords"))
        text = file.read().decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        seeds = []
        for row in reader:
            cell = (row[0] if row else "").strip()
            if cell and not cell.lower().startswith("keyword"):
                seeds.append(cell)
        seeds = seeds[:MAX_ROWS]
        if not seeds:
            flash("No keywords found in the CSV.", "error")
            return redirect(url_for("manage.import_keywords"))

        client = get_ai_client()
        successes, failures = [], []
        for seed in seeds[:BULK_MAX]:
            try:
                results = research_keywords(client, Config.AI_MODEL, seed, BULK_COUNT, "all")
                search = Search(seed_keyword=seed[:100], options_json="{}")
                db.session.add(search)
                db.session.flush()
                for r in results:
                    db.session.add(Keyword(
                        search_id=search.id, keyword=r["keyword"],
                        volume_est=r["volume_est"], difficulty_est=r["difficulty_est"],
                        intent=r["intent"], cpc_est=r["cpc_est"],
                    ))
                db.session.commit()
                successes.append(seed)
            except AIResearchError as e:
                db.session.rollback()
                failures.append((seed, str(e)))
            except SQLAlchemyError:
                db.session.rollback()
                failures.append((seed, "database error"))

        return render_template("import_result.html", successes=successes, failures=failures,
                               total=len(seeds), capped=len(seeds) > BULK_MAX)
    return render_template("import.html", bulk_max=BULK_MAX, max_rows=MAX_ROWS,
                           bulk_count=BULK_COUNT)
