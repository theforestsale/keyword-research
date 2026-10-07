import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, abort
from openai import OpenAI
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from models import db, Search, Keyword, Folder
from services.ai_researcher import (
    research_keywords,
    expand_keywords,
    classify_intent,
    cluster_content,
    ppc_forecast,
    AIResearchError,
)
import json

VALID_INTENTS = {"informational", "commercial", "transactional", "navigational"}

research_bp = Blueprint("research", __name__)


def get_search_or_404(search_id):
    search = db.session.get(Search, search_id)
    if search is None:
        abort(404)
    return search


def get_ai_client():
    return OpenAI(
        api_key=Config.AI_API_KEY,
        base_url=Config.AI_BASE_URL or None,
        timeout=Config.REQUEST_TIMEOUT,
    )


@research_bp.route("/research", methods=["POST"])
def do_research():
    seed = request.form.get("seed", "").strip()
    intent = request.form.get("intent", "all").strip()
    count = int(request.form.get("count", "10"))

    if not Config.AI_API_KEY:
        if Config.AI_PROVIDER == "groq":
            flash("GROQ_API_KEY not configured. Get a free key at console.groq.com and add it to your .env file.", "error")
        else:
            flash("OPENAI_API_KEY not configured. Add it to your .env file.", "error")
        return redirect(url_for("main.index"))

    if not seed:
        flash("Please enter a seed keyword.", "error")
        return redirect(url_for("main.index"))

    if len(seed) > Config.MAX_SEED_LENGTH:
        flash(f"Seed keyword must be {Config.MAX_SEED_LENGTH} characters or less.", "error")
        return redirect(url_for("main.index"))

    if intent not in VALID_INTENTS and intent != "all":
        intent = "all"

    count = max(1, min(count, Config.MAX_KEYWORDS))

    client = get_ai_client()

    try:
        results = research_keywords(client, Config.AI_MODEL, seed, count, intent)
    except AIResearchError as e:
        flash(str(e), "error")
        return redirect(url_for("main.index"))

    try:
        search = Search(
            seed_keyword=seed,
            options_json=json.dumps({"intent": intent, "count": count}),
        )
        db.session.add(search)
        db.session.flush()

        for r in results:
            db.session.add(Keyword(
                search_id=search.id,
                keyword=r["keyword"],
                volume_est=r["volume_est"],
                difficulty_est=r["difficulty_est"],
                intent=r["intent"],
                cpc_est=r["cpc_est"],
            ))

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Failed to save results. Please try again.", "error")
        return redirect(url_for("main.index"))

    return redirect(url_for("research.view_results", search_id=search.id))


@research_bp.route("/results/<int:search_id>")
def view_results(search_id):
    search = get_search_or_404(search_id)
    keywords = search.keywords
    folders = Folder.query.order_by(Folder.name.asc()).all()
    return render_template(
        "results.html",
        search=search,
        keywords=keywords,
        intents=VALID_INTENTS,
        folders=folders,
    )


@research_bp.route("/results/<int:search_id>/export")
def export_results(search_id):
    search = get_search_or_404(search_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Keyword", "Volume (est)", "Difficulty", "Intent", "CPC (USD)"])

    for kw in search.keywords:
        difficulty_label = f"{kw.difficulty_est}/100"
        writer.writerow([
            kw.keyword,
            kw.volume_est,
            difficulty_label,
            kw.intent,
            f"{kw.cpc_est:.2f}",
        ])

    output.seek(0)
    filename = f"keywords_{search.id}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@research_bp.route("/api/search/<int:search_id>")
def api_search(search_id):
    search = get_search_or_404(search_id)
    return jsonify({
        "id": search.id,
        "query": search.seed_keyword,
        "keywords": [
            {
                "keyword": kw.keyword,
                "volume_est": kw.volume_est,
                "difficulty_est": kw.difficulty_est,
                "intent": kw.intent,
                "cpc_est": kw.cpc_est,
            }
            for kw in search.keywords
        ],
    })


# ---------- Advanced AI tools ----------

def _require_key():
    if not Config.AI_API_KEY:
        flash("AI key not configured. Add GROQ_API_KEY (or OPENAI_API_KEY) to your .env file.", "error")
        return False
    return True


@research_bp.route("/tools")
def tools_page():
    if not _require_key():
        return redirect(url_for("main.index"))
    return render_template("tools.html")


@research_bp.route("/tools/expand", methods=["POST"])
def tools_expand():
    seed = request.form.get("seed", "").strip()
    count = max(1, min(int(request.form.get("count", "10")), Config.MAX_KEYWORDS))

    if not _require_key():
        return redirect(url_for("main.index"))
    if not seed:
        flash("Enter a seed keyword to expand.", "error")
        return redirect(url_for("research.tools_page"))

    try:
        terms = expand_keywords(get_ai_client(), Config.AI_MODEL, seed, count)
    except AIResearchError as e:
        flash(str(e), "error")
        return redirect(url_for("research.tools_page"))

    return render_template("tools_results.html", tool="expand", title=f"Expansions for \"{seed}\"",
                           seed=seed, terms=terms)


@research_bp.route("/tools/intent", methods=["POST"])
def tools_intent():
    keywords = [k.strip() for k in request.form.get("keywords", "").splitlines() if k.strip()]
    if not _require_key():
        return redirect(url_for("main.index"))
    if not keywords:
        flash("Paste at least one keyword.", "error")
        return redirect(url_for("research.tools_page"))
    keywords = keywords[:Config.MAX_KEYWORDS]

    try:
        mapping = classify_intent(get_ai_client(), Config.AI_MODEL, keywords)
    except AIResearchError as e:
        flash(str(e), "error")
        return redirect(url_for("research.tools_page"))

    rows = [{"keyword": k, "intent": mapping.get(k, "unknown")} for k in keywords]
    return render_template("tools_results.html", tool="intent", title="Intent Classification",
                           seed=None, intent_rows=rows)


@research_bp.route("/tools/cluster", methods=["POST"])
def tools_cluster():
    keywords = [k.strip() for k in request.form.get("keywords", "").splitlines() if k.strip()]
    topic = request.form.get("topic", "").strip()
    if not _require_key():
        return redirect(url_for("main.index"))
    if not keywords:
        flash("Paste at least one keyword.", "error")
        return redirect(url_for("research.tools_page"))
    keywords = keywords[:Config.MAX_KEYWORDS]
    if not topic:
        topic = keywords[0]

    try:
        clusters = cluster_content(get_ai_client(), Config.AI_MODEL, keywords, topic)
    except AIResearchError as e:
        flash(str(e), "error")
        return redirect(url_for("research.tools_page"))

    return render_template("tools_results.html", tool="cluster", title=f"Content Clusters for \"{topic}\"",
                           seed=None, clusters=clusters)


@research_bp.route("/tools/ppc", methods=["POST"])
def tools_ppc():
    keywords = [k.strip() for k in request.form.get("keywords", "").splitlines() if k.strip()]
    if not _require_key():
        return redirect(url_for("main.index"))
    if not keywords:
        flash("Paste at least one keyword.", "error")
        return redirect(url_for("research.tools_page"))
    keywords = keywords[:Config.MAX_KEYWORDS]

    try:
        estimates = ppc_forecast(get_ai_client(), Config.AI_MODEL, keywords)
    except AIResearchError as e:
        flash(str(e), "error")
        return redirect(url_for("research.tools_page"))

    return render_template("tools_results.html", tool="ppc", title="PPC & Budget Forecast",
                           seed=None, estimates=estimates)

