from datetime import timedelta
import os
import uuid

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd

from models import db, User

BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
CLEANED_FOLDER = os.path.join(BASE_DIR, 'cleaned')
ALLOWED_EXTENSIONS = {'csv', 'xlsx'}
MIN_PASSWORD_LENGTH = 8

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLEANED_FOLDER, exist_ok=True)

app = Flask(__name__)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif db_url.startswith('postgresql://'):
    db_url = db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
app.config['JWT_SECRET_KEY'] = os.environ.get(
    'JWT_SECRET_KEY', 'dev-only-replace-with-a-long-random-string'
)
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=8)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

jwt = JWTManager(app)
CORS(app, origins=[o.strip() for o in os.environ.get('FRONTEND_ORIGIN', '*').split(',')])
db.init_app(app)

with app.app_context():
    db.create_all()


@app.route('/')
def home():
    return {'status': 'Flask is running'}


# ---------------------------------------------------------------- AUTH

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json(silent=True) or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email or Password is missing'}), 400

    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({
            'error': f'Password must be at least {MIN_PASSWORD_LENGTH} characters long'
        }), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'Email is already registered'}), 409

    hashed_password = generate_password_hash(password)
    new_user = User(email=email, password_hash=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User added successfully'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email or Password is missing'}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'wrong email or password'}), 401

    access_token = create_access_token(identity=email)
    return jsonify(access_token=access_token), 200


@app.route('/me', methods=['GET'])
@jwt_required()
def me():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200


# ------------------------------------------------------------ CLEANING

REGION_MAP = {
    'ny': 'New York', 'new york': 'New York',
    'tx': 'Texas', 'texas': 'Texas',
    'il': 'Illinois', 'illinois': 'Illinois',
    'ca': 'California', 'california': 'California',
    'wa': 'Washington', 'washington': 'Washington',
}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_text_column(series, mapping=None):
    """Trim whitespace and standardize casing so 'ny' / 'NY' / 'New York'
    don't get treated as separate groups. Missing values stay missing."""
    cleaned = series.astype(str).str.strip()
    if mapping:
        cleaned = cleaned.str.lower().map(mapping).fillna(cleaned.str.title())
    else:
        cleaned = cleaned.str.title()
    return cleaned.where(series.notna(), None)


def build_ai_summary(df, summary):
    """Rule-based summary for now. Swap this out for a real LLM call later
    (send `summary` + a short sample of `df` to your model of choice)."""
    total_rows = len(df)
    flagged = int((df['flag'] != '').sum())
    lines = [f"This file has {total_rows} records, {flagged} flagged for missing data."]

    if summary.get('by_category'):
        top_cat = max(summary['by_category'], key=summary['by_category'].get)
        lines.append(f"'{top_cat}' is the top category by total amount.")

    if summary.get('by_region'):
        top_region = max(summary['by_region'], key=summary['by_region'].get)
        lines.append(f"'{top_region}' is the top-performing region.")

    if flagged:
        lines.append(f"Review the {flagged} flagged row(s) before trusting this data fully.")

    return ' '.join(lines)


# -------------------------------------------------------------- UPLOAD

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'Please upload your file'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(file.filename)
    # secure_filename strips non-ASCII names down to just the extension
    if not filename.lower().endswith('.' + ext):
        filename = f'upload.{ext}'

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        df = pd.read_csv(filepath) if ext == 'csv' else pd.read_excel(filepath)
    except Exception:
        return jsonify({'error': 'Could not read this file. Is it a valid spreadsheet?'}), 400

    if df.empty:
        return jsonify({'error': 'The file has no data rows'}), 400

    # A re-uploaded cleaned file already has a "flag" column. Remove it so
    # its blank cells aren't counted as missing data.
    df = df.drop(columns=['flag'], errors='ignore')

    # Real Excel dates -> plain YYYY-MM-DD text (JSON friendly)
    for col in df.select_dtypes(include=['datetime', 'datetimetz']).columns:
        df[col] = df[col].dt.strftime('%Y-%m-%d')

    # Amount must be numeric; things like "N/A" become missing and get flagged
    if 'Amount' in df.columns:
        df['Amount'] = pd.to_numeric(
            df['Amount'].astype(str).str.replace(r'[$,]', '', regex=True),
            errors='coerce',
        )

    # Collapse "NY"/"ny"/"New York" and "SOFTWARE"/"software" into one group
    if 'Region' in df.columns:
        df['Region'] = normalize_text_column(df['Region'], REGION_MAP)
    if 'Category' in df.columns:
        df['Category'] = normalize_text_column(df['Category'])

    df['flag'] = df.isnull().any(axis=1)
    df['flag'] = df['flag'].map({True: 'Missing data', False: ''})
    df.drop_duplicates(inplace=True)

    # Save the cleaned file so the user can download it
    base = os.path.splitext(filename)[0]
    download_filename = f'{base}_cleaned.{ext}'            # name the user sees
    download_id = f'{uuid.uuid4().hex}_{download_filename}'  # name on disk
    out_path = os.path.join(CLEANED_FOLDER, download_id)

    if ext == 'csv':
        df.to_csv(out_path, index=False)
    else:
        df.to_excel(out_path, index=False)

    df = df.astype(object).where(pd.notnull(df), None)
    cleaned_data = df.to_dict(orient='records')

    summary = {}
    if 'Category' in df.columns and 'Amount' in df.columns:
        summary['by_category'] = df.groupby('Category')['Amount'].sum().to_dict()
    if 'Region' in df.columns and 'Amount' in df.columns:
        summary['by_region'] = df.groupby('Region')['Amount'].sum().to_dict()

    ai_summary = build_ai_summary(df, summary)

    return jsonify({
        'data': cleaned_data,
        'summary': summary,
        'ai_summary': ai_summary,
        'download_id': download_id,
        'download_filename': download_filename,
    }), 200


# ------------------------------------------------------------ DOWNLOAD

@app.route('/download/<path:download_id>', methods=['GET'])
@jwt_required()
def download(download_id):
    nice_name = download_id.split('_', 1)[1] if '_' in download_id else download_id
    return send_from_directory(
        CLEANED_FOLDER,
        download_id,
        as_attachment=True,
        download_name=nice_name,
    )


# --------------------------------------------------------------- ADMIN

# Set this before starting Flask, e.g. in PowerShell:
#   $env:ADMIN_EMAIL = "you@example.com"
# If it isn't set, the admin route stays locked for everyone.
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')


@app.route('/admin/users', methods=['GET'])
@jwt_required()
def admin_users():
    if not ADMIN_EMAIL or get_jwt_identity() != ADMIN_EMAIL:
        return jsonify({'error': 'Forbidden'}), 403

    users = User.query.all()
    return jsonify({
        'total_users': len(users),
        'emails': [u.email for u in users],
    }), 200


if __name__ == '__main__':
    app.run(debug=True)






































