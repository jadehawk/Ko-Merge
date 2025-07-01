import os
import streamlit
import secrets
import logging
import sys
import sqlite3
import uuid
import shutil
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_from_directory, abort, after_this_request, send_from_directory
)
from werkzeug.utils import secure_filename
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

# send all INFO+ logs to stdout
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# ──── CONFIG ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

UPLOAD_FOLDER    = os.path.join(DATA_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(DATA_DIR, "processed")
COUNTER_FILE     = os.path.join(DATA_DIR, "download_count.txt")
ALLOWED_EXTS    = {"sqlite3"}
CLEANUP_AGE     = timedelta(minutes=10)
WEBSUBFOLDER = os.environ.get("WEBSUB_FOLDER", None)

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

app.config["UPLOAD_FOLDER"]    = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER
app.config["MAX_CONTENT_LENGTH"]= 100 * 1024 * 1024  # 100 MB max

# 1) Check for an env‐supplied secret
secret = os.environ.get("FLASK_SECRET")

if not secret:
    # 2) No secret provided → generate a 32-byte hex string (~64 chars)
    secret = secrets.token_urlsafe(32)
    app.logger.info(
        "No FLASK_SECRET provided—using a one‐time random key. "
        "Sessions will be invalidated on each restart."
    )

app.secret_key = secret

#===========================================================================
# This section will force app to listen on SUB-FOLDER /ko-merge
#===========================================================================
# 1) Decide if we’re mounted under /ko-merge
# ─── Sub-folder mounting toggle ────────────────────────────────
USE_SUB = os.environ.get("USE_SUBFOLDER", "").lower() in ("1", "true", "yes")
if USE_SUB:
    def not_found_app(environ, start_response):
        res = Response("Not Found", status=404)
        return res(environ, start_response)

    app.wsgi_app = DispatcherMiddleware(
        not_found_app,
        {"/ko-merge": app.wsgi_app}
    )

# ─── One-time logging guard ─────────────────────────────────────
# module-level flag instead of app._has_logged_binding
_has_logged_binding = False

@app.before_request
def log_binding_once():
    global _has_logged_binding
    if not _has_logged_binding:
        host_header = request.host  # "0.0.0.0:5000" or "example.com"
        prefix = "/ko-merge" if USE_SUB else "/"
        app.logger.info(f"🚀 Flask serving on {host_header} with prefix '{prefix}'")
        _has_logged_binding = True

#===========================================================================

# ─── Ensure your data tree exists before you ever read/write it ───────────
for path in (DATA_DIR, UPLOAD_FOLDER, PROCESSED_FOLDER):
    os.makedirs(path, exist_ok=True)

# ──── PERSISTENT DOWNLOAD COUNTER ────────────────────────────────────────────
def get_download_count() -> int:
    """Read the counter from disk, return 0 if file missing or invalid."""
    try:
        with open(COUNTER_FILE, "r") as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0

def set_download_count(count: int) -> None:
    """Write the counter back to disk."""

    with open(COUNTER_FILE, "w") as f:
        f.write(str(count))



# ──── HELPERS ─────────────────────────────────────────────────────────────
def allowed_file(fname):
    return "." in fname and fname.rsplit(".", 1)[1].lower() in ALLOWED_EXTS

def cleanup_old_files():
    now = datetime.now()
    for folder in (UPLOAD_FOLDER, PROCESSED_FOLDER):
        for fn in os.listdir(folder):
            path = os.path.join(folder, fn)
            if os.path.isfile(path):
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                if now - mtime > CLEANUP_AGE:
                    os.remove(path)

@app.before_request
def _before_request():
    cleanup_old_files()
    # ensure each visitor has a session-scoped ID
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
        session["merge_groups"] = []


def validate_db(path):
    """Raise ValueError if schema isn't a KOReader stats DB."""
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    required = {"book", "page_stat_data"}
    if not required.issubset(tables):
        raise ValueError(f"Missing tables: {required - tables}")

    # quick column check
    cur.execute("PRAGMA table_info(book)")
    cols = {r[1] for r in cur.fetchall()}
    if "total_read_time" not in cols or "md5" not in cols:
        raise ValueError("`book` table missing required columns")
    con.close()


def fetch_books(path):
    """Return list of (id, title, time, md5) from the given DB."""
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("SELECT id, title, total_read_time, md5 FROM book ORDER BY id")
    rows = cur.fetchall()
    con.close()
    return rows


def merge_books(path, keep_id, merge_ids):
    """
    Merge logic exactly as in your final script:
     - copy all sessions under keep_id using MAX() on conflict
     - delete merged books
     - rebuild totals from page_stat_data
    """
    con = sqlite3.connect(path)
    cur = con.cursor()
    try:
        cur.execute("BEGIN")
        for mid in merge_ids:
            cur.execute("""
                INSERT INTO page_stat_data
                  (id_book, page, start_time, duration, total_pages)
                SELECT ?, page, start_time, duration, total_pages
                  FROM page_stat_data
                 WHERE id_book = ?
                ON CONFLICT(id_book, page, start_time) DO UPDATE SET
                  duration    = MAX(duration, excluded.duration),
                  total_pages = MAX(total_pages, excluded.total_pages)
            """, (keep_id, mid))
            cur.execute("DELETE FROM book WHERE id = ?", (mid,))

        # recompute totals
        cur.execute("""
            UPDATE book SET
              total_read_time = COALESCE((
                SELECT SUM(duration) FROM page_stat_data WHERE id_book = ?
              ), 0),
              total_read_pages = COALESCE((
                SELECT COUNT(DISTINCT page)
                  FROM page_stat_data WHERE id_book = ?
              ), 0)
            WHERE id = ?;
        """, (keep_id, keep_id, keep_id))

        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ──── ROUTES ───────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Upload handler
        f = request.files.get("dbfile")

        # 1) Guard on f and its filename
        if not f or not f.filename:
            flash("Please upload a .sqlite3 file", "danger")
            return redirect(url_for("index"))

        if not f or not allowed_file(f.filename):
            flash("Please upload a .sqlite3 file", "danger")
            return redirect(url_for("index"))

        fn = secure_filename(f.filename)
        saved = f"{session['user_id']}.sqlite3"
        dst = os.path.join(app.config["UPLOAD_FOLDER"], saved)
        f.save(dst)

        # validate it
        try:
            validate_db(dst)
        except ValueError as ve:
            os.remove(dst)
            flash(f"Invalid KOReader DB: {ve}", "danger")
            return redirect(url_for("index"))

        session["upload_db"] = saved
        session["merge_groups"] = []
        return redirect(url_for("merge"))

    return render_template("index.html")


@app.route("/merge", methods=["GET", "POST"])
def merge():
    upload_db = session.get("upload_db")
    if not upload_db:
        return redirect(url_for("index"))

    path = os.path.join(app.config["UPLOAD_FOLDER"], upload_db)
    books = fetch_books(path)

    # handle form actions
    action = request.form.get("action")
    if action == "add_group":
        keep_id   = int(request.form["keep_id"])
        merge_ids = list(map(int, request.form.getlist("merge_ids")))
        merge_ids = [m for m in merge_ids if m != keep_id]
        if not merge_ids:
            flash("Select at least one different book to merge.", "warning")
        else:
            # append and mark session dirty so it actually saves
            session["merge_groups"].append((keep_id, merge_ids))
            session.modified = True
        return redirect(url_for("merge"))
    
    if action == "remove_last":
        if session["merge_groups"]:
            session["merge_groups"].pop()
            session.modified = True    # ← ensure Flask saves it

        return redirect(url_for("merge"))

    if action == "clear_groups":
        session["merge_groups"] = []
        session.modified = True        # ← ensure Flask saves it

        return redirect(url_for("merge"))

    if action == "run_all":
        if not session["merge_groups"]:
            flash("No merge groups to run.", "warning")
            return redirect(url_for("merge"))

        # copy upload → processed
        fixed_name = f"{session['user_id']}_fixed.sqlite3"
        src  = os.path.join(app.config["UPLOAD_FOLDER"], upload_db)
        dst  = os.path.join(app.config["PROCESSED_FOLDER"], fixed_name)
        shutil.copy(src, dst)

        # apply all batches
        for keep_id, mids in session["merge_groups"]:
            merge_books(dst, keep_id, mids)

        session["fixed_db"] = fixed_name
        return redirect(url_for("result"))

    return render_template(
        "merge.html",
        books=books,
        batches=session["merge_groups"],
    )

@app.route("/result", methods=["GET"])
def result():
    fixed = session.get("fixed_db")
    if not fixed:
        return redirect(url_for("index"))

    path = os.path.join(app.config["PROCESSED_FOLDER"], fixed)
    books = fetch_books(path)
    return render_template("result.html", books=books)


@app.route("/processed/<path:filename>")
def serve_processed(filename):
    """
    Serve the merged DB and then delete it immediately.
    """
    full_path = os.path.join(app.config["PROCESSED_FOLDER"], filename)
    if not os.path.isfile(full_path):
        abort(404)

    @after_this_request
    def cleanup(response):
        # remove the merged file AFTER it’s been sent
        try:
            os.remove(full_path)
        except OSError:
            pass
        return response

    # serve the file under the original download name
    return send_from_directory(
        app.config["PROCESSED_FOLDER"],
        filename,
        as_attachment=True,
        download_name="statistics_fixed.sqlite3"
    )

@app.route("/download")
def download():
    """
    1) Verify a merged DB is in session.
    2) Bump the persistent download counter on disk.
    3) Delete only the original uploaded file.
    4) Flash a success message.
    5) Render download.html (it auto-clicks and later invokes /cleanup).
    """
    # 1) guard: need both upload_db and fixed_db in session
    fixed    = session.get("fixed_db")
    uploaded = session.get("upload_db")
    if not fixed or not uploaded:
        flash("No merged database available for download.", "warning")
        return redirect(url_for("index"))

    # 2) persistent counter bump
    count = get_download_count() + 1
    set_download_count(count)

    # 3) delete only the original upload; leave 'fixed' for serve_processed
    try:
        os.remove(os.path.join(app.config["UPLOAD_FOLDER"], uploaded))
    except OSError:
        pass

    # 4) let the user know the download is starting
    flash("Your download is starting", "success")

    # 5) build download link and render the auto-download page
    download_url = url_for("serve_processed", filename=fixed)
    return render_template("download.html", download_url=download_url)

@app.route("/cleanup")
def cleanup():
    """
    Delete any upload/processed files for this session_id,
    clear the session, flash a message, then redirect to index.
    """
    # Grab what we saved earlier
    uploaded = session.get("upload_db")
    fixed    = session.get("fixed_db")

    # Remove upload file
    if uploaded:
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], uploaded))
        except OSError:
            pass

    # Remove processed file (in case serve_processed didn't catch it)
    if fixed:
        try:
            os.remove(os.path.join(app.config["PROCESSED_FOLDER"], fixed))
        except OSError:
            pass

    session.clear()
    flash("All session files have been deleted.", "info")
    return redirect(url_for("index"))

@app.template_filter("format_time")
def format_time_filter(seconds):
    """Convert seconds into Hh:Mm:Ss format."""
    try:
        sec = int(seconds)
    except (ValueError, TypeError):
        return "00h:00m:00s"
    td = timedelta(seconds=sec)
    total = td.days * 86400 + td.seconds
    hrs  = total // 3600
    mins = (total % 3600) // 60
    secs = total % 60
    return f"{hrs:02d}h:{mins:02d}m:{secs:02d}s"
#=========================================================================
# Stats Call
#=========================================================================
def fetch_stats(path):
    """
    Returns a list of rows with these keys:
      - book_id
      - title
      - total_read_time       (sum of all durations, de-duplicated)
      - total_events          (how many page_stat rows we counted)
      - unique_durations      (count of distinct duration values)
      - avg_duration          (avg seconds per event)
      - secs_per_page         (seconds_of_reading / distinct_pages)
      - pages_per_sec         (events per second_of_reading)
    """
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
    WITH uniq AS (
      SELECT DISTINCT id_book, page, start_time, duration
      FROM page_stat
    )
    SELECT
      b.id              AS book_id,
      b.title           AS title,
      SUM(u.duration)   AS total_read_time,
      COUNT(*)          AS total_events,
      COUNT(DISTINCT u.duration) AS unique_durations,
      AVG(u.duration)   AS avg_duration,
      -- seconds per page: total_time / distinct pages read
      ROUND(SUM(u.duration) / COUNT(DISTINCT u.page), 4)
                        AS secs_per_page,
      -- pages per second: distinct pages / total_time
      ROUND(COUNT(DISTINCT u.page) / SUM(u.duration), 4)
                        AS pages_per_sec
    FROM uniq AS u
    JOIN book AS b
      ON u.id_book = b.id
    GROUP BY b.id, b.title
    ORDER BY b.title;
    """)
    rows = cur.fetchall()
    con.close()
    return rows

@app.route("/stats")
def stats():
    upload_db = session.get("upload_db")
    if not upload_db:
        return redirect(url_for("index"))

    path = os.path.join(app.config["UPLOAD_FOLDER"], upload_db)
    stats = fetch_stats(path)    # whatever your DB filepath var is
    # format times for human friendliness
    for row in stats:
        row["total_read_time_fmt"] = format_time_filter(row["total_read_time"])
    return render_template("stats.html", stats=stats)


# ──── CONTEXT PROCESSOR ───────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    return dict(
        download_count=get_download_count(),
        branding="KOReader Statistics Database Merger"
    )

def _self_request():
    # match the host:port that your clients will use
    host   = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port   = os.environ.get("FLASK_RUN_PORT", "5025")
    prefix = "/ko-merge" if USE_SUB else "/"

    # build the URL path your before_request logic expects
    path     = prefix if prefix.endswith("/") else prefix + "/"
    base_url = f"http://{host}:{port}"

    # Fire a fake GET through the full WSGI stack
    with app.test_client() as client:
        client.get(path, base_url=base_url)

# Immediately invoke it (runs under `python app.py` or `gunicorn app:app`)
_self_request()


if __name__ == "__main__":
    #commented out 
    #host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    #port = int(os.environ.get("FLASK_RUN_PORT", 5025))
    #app.run(host=host, port=port)
