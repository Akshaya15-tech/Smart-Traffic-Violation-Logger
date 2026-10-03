import os
import re
import uuid
from datetime import date, datetime
from functools import wraps

import qrcode
from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from qrcode.constants import ERROR_CORRECT_M
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from models import Violation, db

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
QR_FOLDER = os.path.join(BASE_DIR, "static", "qr")
DB_PATH = os.path.join(BASE_DIR, "database.db").replace("\\", "/")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Admin credentials (override with environment variables in real use)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get("ADMIN_PASSWORD", "admin123")
)

# Optional: set BASE_URL (e.g. http://192.168.1.10:5000) so QR codes point to
# an address that phones on your network can reach.
BASE_URL = os.environ.get("BASE_URL", "").strip()

VIOLATION_TYPES = [
    "Over Speeding",
    "Signal Jumping",
    "No Helmet",
    "No Seat Belt",
    "Wrong Parking",
    "Drunk Driving",
    "Using Mobile While Driving",
    "Driving Without License",
    "Triple Riding",
    "Wrong Way Driving",
    "Other",
]

db.init_app(app)

with app.app_context():
    os.makedirs(QR_FOLDER, exist_ok=True)
    db.create_all()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    return {
        "violation_types": VIOLATION_TYPES,
        "today": date.today().isoformat(),
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def public_url(token):
    path = url_for("public_status", token=token)
    if BASE_URL:
        return BASE_URL.rstrip("/") + path
    return url_for("public_status", token=token, _external=True)


def generate_qr(token):
    """Create a QR image for the public status URL and return its path
    relative to the static folder (e.g. 'qr/qr_<token>.png')."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(public_url(token))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    filename = f"qr_{token}.png"
    os.makedirs(QR_FOLDER, exist_ok=True)
    img.save(os.path.join(QR_FOLDER, filename))
    return f"qr/{filename}"


def parse_violation_form(form):
    """Validate form input. Returns (cleaned_data, errors)."""
    errors = []

    vehicle = form.get("vehicle_number", "").strip().upper().replace(" ", "")
    if not vehicle:
        errors.append("Vehicle number is required.")
    elif not re.fullmatch(r"[A-Z0-9-]{4,15}", vehicle):
        errors.append("Vehicle number must be 4-15 letters/digits (e.g. TN33AB1234).")

    vtype = form.get("violation_type", "").strip()
    if vtype not in VIOLATION_TYPES:
        errors.append("Please select a valid violation type.")

    location = form.get("location", "").strip()
    if not location:
        errors.append("Location is required.")

    vdate = None
    try:
        vdate = datetime.strptime(form.get("violation_date", ""), "%Y-%m-%d").date()
        if vdate > date.today():
            errors.append("Violation date cannot be in the future.")
    except ValueError:
        errors.append("Please enter a valid date.")

    fine = None
    try:
        fine = round(float(form.get("fine_amount", "")), 2)
        if fine <= 0:
            errors.append("Fine amount must be greater than zero.")
    except ValueError:
        errors.append("Please enter a valid fine amount.")

    data = {
        "vehicle_number": vehicle,
        "violation_type": vtype,
        "location": location,
        "violation_date": vdate,
        "fine_amount": fine,
    }
    return data, errors


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@app.route("/")
def dashboard():
    total = Violation.query.count()
    paid = Violation.query.filter_by(status="Paid").count()
    unpaid = Violation.query.filter_by(status="Unpaid").count()
    total_fine = db.session.query(
        func.coalesce(func.sum(Violation.fine_amount), 0)
    ).scalar()
    pending_fine = db.session.query(
        func.coalesce(func.sum(Violation.fine_amount), 0)
    ).filter(Violation.status == "Unpaid").scalar()
    recent = Violation.query.order_by(Violation.created_at.desc()).limit(5).all()

    return render_template(
        "dashboard.html",
        total=total,
        paid=paid,
        unpaid=unpaid,
        total_fine=total_fine,
        pending_fine=pending_fine,
        recent=recent,
    )


# --------------------------------------------------------------------------
# Add / Edit
# --------------------------------------------------------------------------
@app.route("/add", methods=["GET", "POST"])
@login_required
def add_violation():
    form = {}
    if request.method == "POST":
        form = request.form
        data, errors = parse_violation_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            token = uuid.uuid4().hex
            violation = Violation(
                **data,
                status="Unpaid",
                public_token=token,
                qr_code_path=generate_qr(token),
            )
            db.session.add(violation)
            db.session.commit()
            flash("Violation recorded and QR code generated.", "success")
            return redirect(url_for("details", violation_id=violation.id))

    return render_template("add_violation.html", violation=None, form=form)


@app.route("/violation/<int:violation_id>/edit", methods=["GET", "POST"])
@login_required
def edit_violation(violation_id):
    violation = db.get_or_404(Violation, violation_id)

    if request.method == "POST":
        form = request.form
        data, errors = parse_violation_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            for key, value in data.items():
                setattr(violation, key, value)
            db.session.commit()
            flash("Violation updated.", "success")
            return redirect(url_for("details", violation_id=violation.id))
    else:
        form = {
            "vehicle_number": violation.vehicle_number,
            "violation_type": violation.violation_type,
            "location": violation.location,
            "violation_date": violation.violation_date.isoformat(),
            "fine_amount": violation.fine_amount,
        }

    return render_template("add_violation.html", violation=violation, form=form)


# --------------------------------------------------------------------------
# History with search & filters
# --------------------------------------------------------------------------
@app.route("/history")
def history():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    vtype = request.args.get("violation_type", "").strip()
    date_str = request.args.get("date", "").strip()

    query = Violation.query

    if q:
        term = q.upper().replace(" ", "")
        query = query.filter(Violation.vehicle_number.ilike(f"%{term}%"))
    if status in ("Paid", "Unpaid"):
        query = query.filter(Violation.status == status)
    if vtype:
        query = query.filter(Violation.violation_type == vtype)
    if date_str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            query = query.filter(Violation.violation_date == d)
        except ValueError:
            flash("Invalid date filter ignored.", "warning")

    violations = query.order_by(
        Violation.violation_date.desc(), Violation.id.desc()
    ).all()

    return render_template(
        "history.html",
        violations=violations,
        q=q,
        status=status,
        vtype=vtype,
        date_str=date_str,
    )


# --------------------------------------------------------------------------
# Details, pay, delete
# --------------------------------------------------------------------------
@app.route("/violation/<int:violation_id>")
def details(violation_id):
    violation = db.get_or_404(Violation, violation_id)
    return render_template(
        "details.html",
        violation=violation,
        public_link=public_url(violation.public_token),
    )


@app.route("/violation/<int:violation_id>/pay", methods=["POST"])
@login_required
def mark_paid(violation_id):
    violation = db.get_or_404(Violation, violation_id)
    if violation.status == "Paid":
        flash("This violation is already marked as paid.", "info")
    else:
        violation.status = "Paid"
        db.session.commit()
        flash("Payment status updated to Paid.", "success")
    return redirect(request.referrer or url_for("details", violation_id=violation.id))


@app.route("/violation/<int:violation_id>/delete", methods=["POST"])
@login_required
def delete_violation(violation_id):
    violation = db.get_or_404(Violation, violation_id)

    if violation.qr_code_path:
        qr_file = os.path.join(BASE_DIR, "static", violation.qr_code_path)
        if os.path.exists(qr_file):
            os.remove(qr_file)

    db.session.delete(violation)
    db.session.commit()
    flash("Violation record deleted.", "success")
    return redirect(url_for("history"))


# --------------------------------------------------------------------------
# Public QR status page (no login)
# --------------------------------------------------------------------------
@app.route("/status/<token>")
def public_status(token):
    violation = Violation.query.filter_by(public_token=token).first()
    if violation is None:
        abort(404)
    return render_template("public_status.html", violation=violation)


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["admin"] = True
            session["username"] = username
            flash("Logged in successfully.", "success")

            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
