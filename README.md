# Smart Traffic Violation Logger

A Flask web application for traffic police to digitally record, track and
manage traffic violations. Each violation gets a unique QR code that opens a
public page showing the violation and its payment status.

## Features
- Dashboard: total, paid and unpaid violations, total fine amount
- Add / edit violation records (status defaults to "Unpaid")
- Automatic unique QR code generation (saved in `static/qr/`)
- History table with search by vehicle number, filter by status, type and date
- Violation details page with QR image
- "Mark as Paid" button
- Public QR status page (no login required)
- Delete with confirmation popup
- Session-based admin login (add / edit / delete / mark paid are protected)

## Tech Stack
Python, Flask, Flask-SQLAlchemy, SQLite, Bootstrap 5, qrcode

## Setup

```bash
# 1. (Recommended) create a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py
```

Open http://127.0.0.1:5000 in your browser.
The database (`database.db`) and `static/qr/` folder are created automatically.

## Default Admin Login
- Username: `admin`
- Password: `admin123`

Change these with environment variables before real use:

```bash
# Windows (PowerShell)
$env:ADMIN_USERNAME="police"; $env:ADMIN_PASSWORD="StrongPass!23"; $env:SECRET_KEY="long-random-string"

# macOS / Linux
export ADMIN_USERNAME=police ADMIN_PASSWORD='StrongPass!23' SECRET_KEY='long-random-string'
```

## Making QR codes scannable from a phone
QR codes contain the full public URL. By default this is `http://127.0.0.1:5000/...`,
which a phone cannot reach. Find your computer's LAN IP (e.g. 192.168.1.10) and
start the app with:

```bash
# Windows (PowerShell)
$env:BASE_URL="http://192.168.1.10:5000"; python app.py

# macOS / Linux
BASE_URL=http://192.168.1.10:5000 python app.py
```

Phone and computer must be on the same Wi-Fi. QR codes are generated when a
record is created, so set `BASE_URL` before adding records. For production,
use your real domain name.

## Project Structure
```
traffic_logger/
├── app.py            # Flask routes and QR logic
├── models.py         # SQLAlchemy model
├── requirements.txt
├── database.db       # created automatically
├── templates/        # Jinja2 + Bootstrap 5 templates
└── static/
    ├── css/style.css
    └── qr/           # generated QR images
```

## Notes
- Public QR URLs use a random token (`/status/<token>`), not the numeric ID,
  so records can't be enumerated by guessing URLs.
- If you change the model later, delete `database.db` so it is recreated.
- For production, run behind a WSGI server (e.g. gunicorn), turn off
  `debug=True`, and set a strong `SECRET_KEY`.
