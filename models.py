from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class Violation(db.Model):
    __tablename__ = "violation"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_number = db.Column(db.String(20), nullable=False, index=True)
    violation_type = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    violation_date = db.Column(db.Date, nullable=False)
    fine_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="Unpaid")
    qr_code_path = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    # Random, unguessable token used in the public QR URL, so people
    # cannot browse other records by changing a numeric ID.
    public_token = db.Column(db.String(32), unique=True, nullable=False)

    def __repr__(self):
        return f"<Violation {self.id} {self.vehicle_number}>"
