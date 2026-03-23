from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
import os
import io
import base64
import datetime
import json
import uuid
from PIL import Image
import numpy as np
import pandas as pd
from functools import wraps
import cv2
import difflib

# Import utilities
from utils.ocr import read_plate_text_from_image
from utils.yolo_detect import detect_plate_bbox
from utils.wallet import WalletManager

# Flask setup
BASE_DIR = os.getcwd()
app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)
app.secret_key = os.environ.get('SECRET_KEY', 'fueliq-secret-key-change-in-production-2024')

# Initialize wallet manager - using the main dataset
WALLET_DATASET = "datasets/valid_prepaid_wallet_dataset.csv"
wallet = WalletManager(WALLET_DATASET)

# Utility to normalise identifiers coming from OCR/user input
def clean_identifier(value):
    """Return upper-cased alphanumeric string without spaces/hyphens."""
    if value is None:
        return ""
    return ''.join(ch for ch in str(value).upper() if ch.isalnum())


def find_wallet_by_plate_fuzzy(plate_text, cutoff=0.7):
    """Try to find a wallet record by fuzzy-matching plate_text against known plates.
    Returns tuple (record, score) or (None, 0.0).
    """
    if not plate_text:
        return None, 0.0

    target = clean_identifier(plate_text)
    try:
        if not hasattr(wallet, 'df') or wallet.df is None:
            return None, 0.0

        candidates = wallet.df['number_plate_id'].astype(str).fillna('').tolist()
        # Normalize candidates
        norm_candidates = [clean_identifier(c) for c in candidates]

        # Use difflib to find close matches
        matches = difflib.get_close_matches(target, norm_candidates, n=3, cutoff=cutoff)
        if matches:
            best = matches[0]
            # find original row
            idx = norm_candidates.index(best)
            row = wallet.df.iloc[idx].to_dict()
            # compute ratio
            score = difflib.SequenceMatcher(None, target, best).ratio()
            # ensure numeric balance
            row['balance'] = float(row.get('balance', 0) or 0)
            return row, float(score)
        else:
            # Try substring matching (OCR may give partial plate)
            for i, cand in enumerate(norm_candidates):
                if target and (target in cand or cand in target):
                    row = wallet.df.iloc[i].to_dict()
                    row['balance'] = float(row.get('balance', 0) or 0)
                    return row, 0.5
    except Exception as e:
        print(f"Error in fuzzy wallet lookup: {e}")

    return None, 0.0

# Dummy admin credentials (in production, use database)
ADMIN_CREDENTIALS = {
    "admin": "admin123",
    "staff": "staff123"
}

# Fuel prices (configurable in settings)
FUEL_PRICES = {
    "Petrol": 100.0,
    "Diesel": 90.0,
    "CNG": 60.0
}

# Store transactions and bills (in production, use database)
TRANSACTIONS_FILE = "datasets/transactions.csv"
BILLS_FILE = "datasets/bills.csv"

# Initialize transaction and bill storage
def init_storage():
    """Initialize CSV files for transactions and bills if they don't exist"""
    try:
        # Create datasets directory if it doesn't exist
        os.makedirs('datasets', exist_ok=True)
        
        if not os.path.exists(TRANSACTIONS_FILE):
            pd.DataFrame(columns=[
                'transaction_id', 'bill_id', 'wallet_id', 'number_plate_id', 
                'type', 'amount', 'liters', 'fuel_type', 'rate', 
                'balance_before', 'balance_after', 'timestamp'
            ]).to_csv(TRANSACTIONS_FILE, index=False, encoding='utf-8')
            print(f"Created transactions file: {TRANSACTIONS_FILE}")
        
        if not os.path.exists(BILLS_FILE):
            pd.DataFrame(columns=[
                'bill_id', 'wallet_id', 'number_plate_id', 'fuel_type', 
                'liters', 'rate', 'total_amount', 'balance_before', 
                'balance_after', 'timestamp', 'email_sent', 'email_status'
            ]).to_csv(BILLS_FILE, index=False, encoding='utf-8')
            print(f"Created bills file: {BILLS_FILE}")
    except Exception as e:
        print(f"Error initializing storage: {e}")

init_storage()

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Session expired. Please log in again."}), 401
            return redirect(url_for('login'))
        if not session.get('is_admin', False):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Admin access required."}), 403
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def user_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('is_admin', False):
            flash('Access denied. User access only.', 'error')
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    """Inject current user info into templates"""
    user = None
    if 'user_id' in session:
        user = {
            'id': session.get('user_id'),
            'name': session.get('user_name', 'User'),
            'is_admin': session.get('is_admin', False),
            'wallet_id': session.get('wallet_id')
        }
    return {'current_user': user, 'fuel_prices': FUEL_PRICES}

# ============================================
# AUTHENTICATION ROUTES
# ============================================

@app.route("/")
def index():
    """Home page - redirects based on auth status"""
    if 'user_id' in session:
        if session.get('is_admin', False):
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page for both admin and users"""
    if request.method == "POST":
        login_type = request.form.get('login_type')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if login_type == 'admin':
            # Admin login
            if username in ADMIN_CREDENTIALS and ADMIN_CREDENTIALS[username] == password:
                session['user_id'] = username
                session['user_name'] = username.capitalize()
                session['is_admin'] = True
                flash('Login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials', 'error')
        else:
            # User login by Wallet ID
            wallet_id = clean_identifier(username)
            record = wallet.find_by_wallet_id(wallet_id)
            if record:
                session['user_id'] = wallet_id
                session['user_name'] = str(record.get('number_plate_id', wallet_id))
                session['is_admin'] = False
                session['wallet_id'] = str(record.get('wallet_id', wallet_id))
                session['number_plate'] = str(record.get('number_plate_id', ''))
                flash('Login successful!', 'success')
                return redirect(url_for('user_dashboard'))
            else:
                flash(f'Wallet ID "{wallet_id}" not found. Please check your Wallet ID.', 'error')
    
    return render_template("auth/login.html")

@app.route("/logout")
def logout():
    """Logout and clear session"""
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

# ============================================
# ADMIN ROUTES
# ============================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    """Admin dashboard with statistics and transaction insights"""
    # Calculate statistics
    stats = {
        "total_wallets": 0,
        "total_balance": 0.0,
        "total_fuel_sales": 0.0,
        "total_transactions": 0,
        "today_transactions": 0,
        "today_sales": 0.0,
        "weekly_sales": 0.0,
        "weekly_transactions": 0,
        "daily_data": [],
        "weekly_data": []
    }
    
    try:
        if hasattr(wallet, 'df') and isinstance(wallet.df, pd.DataFrame):
            df = wallet.df
            stats['total_wallets'] = int(df.shape[0])
            if 'balance' in df.columns:
                stats['total_balance'] = float(pd.to_numeric(df['balance'], errors='coerce').fillna(0.0).sum())
        
        # Load transactions
        if os.path.exists(TRANSACTIONS_FILE):
            tdf = pd.read_csv(TRANSACTIONS_FILE, encoding='utf-8')
            stats['total_transactions'] = len(tdf)
            
            if 'amount' in tdf.columns:
                stats['total_fuel_sales'] = float(pd.to_numeric(tdf['amount'], errors='coerce').fillna(0.0).sum())
            
            # Process timestamps for daily/weekly insights
            if 'timestamp' in tdf.columns:
                tdf['date'] = pd.to_datetime(tdf['timestamp'], errors='coerce').dt.date
                tdf['datetime'] = pd.to_datetime(tdf['timestamp'], errors='coerce')
                
                # Today's transactions
                today = datetime.date.today()
                today_df = tdf[tdf['date'] == today]
                stats['today_transactions'] = len(today_df)
                if 'amount' in today_df.columns:
                    stats['today_sales'] = float(pd.to_numeric(today_df['amount'], errors='coerce').fillna(0.0).sum())
                
                # Weekly transactions (last 7 days)
                week_ago = today - datetime.timedelta(days=7)
                weekly_df = tdf[tdf['date'] >= week_ago]
                stats['weekly_transactions'] = len(weekly_df)
                if 'amount' in weekly_df.columns:
                    stats['weekly_sales'] = float(pd.to_numeric(weekly_df['amount'], errors='coerce').fillna(0.0).sum())
                
                # Daily data for last 7 days (for chart)
                daily_stats = []
                for i in range(7):
                    date = today - datetime.timedelta(days=i)
                    day_df = tdf[tdf['date'] == date]
                    day_sales = float(pd.to_numeric(day_df['amount'], errors='coerce').fillna(0.0).sum()) if 'amount' in day_df.columns else 0.0
                    day_count = len(day_df)
                    daily_stats.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'day': date.strftime('%a'),
                        'sales': day_sales,
                        'transactions': day_count
                    })
                stats['daily_data'] = list(reversed(daily_stats))
                
                # Weekly data (last 4 weeks)
                weekly_stats = []
                for i in range(4):
                    week_start = today - datetime.timedelta(days=(i+1)*7)
                    week_end = today - datetime.timedelta(days=i*7)
                    week_df = tdf[(tdf['date'] >= week_start) & (tdf['date'] < week_end)]
                    week_sales = float(pd.to_numeric(week_df['amount'], errors='coerce').fillna(0.0).sum()) if 'amount' in week_df.columns else 0.0
                    week_count = len(week_df)
                    weekly_stats.append({
                        'week': f"Week {4-i}",
                        'sales': week_sales,
                        'transactions': week_count
                    })
                stats['weekly_data'] = list(reversed(weekly_stats))
                
    except Exception as e:
        print(f"Error calculating stats: {e}")
    
    return render_template("admin/dashboard.html", stats=stats)

@app.route("/admin/detect")
@admin_required
def admin_detect():
    """Live vehicle detection page"""
    return render_template("admin/detect.html")

@app.route("/admin/upload")
@admin_required
def admin_upload():
    """Image upload and verification page"""
    return render_template("admin/upload.html")

@app.route("/admin/bill-generation")
@admin_required
def bill_generation():
    """Bill generation form - KEY FEATURE"""
    # Get vehicle info from session if available
    vehicle_info = session.get('detected_vehicle', {})
    return render_template("admin/bill_generation.html", vehicle_info=vehicle_info)

@app.route("/admin/transactions")
@admin_required
def admin_transactions():
    """View all fuel transactions"""
    transactions = []
    try:
        if os.path.exists(TRANSACTIONS_FILE):
            tdf = pd.read_csv(TRANSACTIONS_FILE, encoding='utf-8')
            # Convert to dict and handle NaN values
            transactions = tdf.fillna('').to_dict('records')
            transactions.reverse()  # Most recent first
    except Exception as e:
        print(f"Error loading transactions: {e}")
        flash(f"Error loading transactions: {str(e)}", 'error')
    
    return render_template("admin/transactions.html", transactions=transactions)

@app.route("/admin/wallets")
@admin_required
def admin_wallets():
    """Wallet management page"""
    wallets = []
    try:
        if hasattr(wallet, 'df'):
            wallets = wallet.df.to_dict('records')
    except Exception as e:
        print(f"Error loading wallets: {e}")
    
    return render_template("admin/wallets.html", wallets=wallets)

@app.route("/admin/vehicles")
@admin_required
def admin_vehicles():
    """Vehicle records page"""
    vehicles = []
    try:
        if hasattr(wallet, 'df'):
            vehicles = wallet.df.to_dict('records')
    except Exception as e:
        print(f"Error loading vehicles: {e}")
    
    return render_template("admin/vehicles.html", vehicles=vehicles)

@app.route("/admin/settings")
@admin_required
def admin_settings():
    """System settings page"""
    return render_template("admin/settings.html", fuel_prices=FUEL_PRICES)

@app.route("/admin/logs")
@admin_required
def admin_logs():
    """System logs page"""
    logs = []
    try:
        if os.path.exists(TRANSACTIONS_FILE):
            tdf = pd.read_csv(TRANSACTIONS_FILE)
            logs = tdf.to_dict('records')
            logs.reverse()
    except Exception as e:
        print(f"Error loading logs: {e}")
    
    return render_template("admin/logs.html", logs=logs)

# ============================================
# USER ROUTES
# ============================================

@app.route("/user/dashboard")
@login_required
def user_dashboard():
    """User dashboard"""
    if session.get('is_admin', False):
        return redirect(url_for('admin_dashboard'))
    
    wallet_id = session.get('wallet_id')
    user_info = None
    recent_transactions = []
    recent_bills = []
    
    try:
        if wallet_id:
            record = wallet.find_by_wallet_id(wallet_id)
            if record:
                user_info = record
            else:
                # Try to find by number_plate if wallet_id lookup fails
                number_plate = session.get('number_plate', '')
                if number_plate:
                    record = wallet.find_by_plate(number_plate)
                    if record:
                        user_info = record
                        session['wallet_id'] = str(record.get('wallet_id', ''))
        
        # Load user's transactions
        if os.path.exists(TRANSACTIONS_FILE) and wallet_id:
            tdf = pd.read_csv(TRANSACTIONS_FILE, encoding='utf-8')
            user_txns = tdf[tdf['wallet_id'].astype(str).str.upper() == str(wallet_id).upper()]
            if not user_txns.empty:
                recent_transactions = user_txns.tail(5).fillna('').to_dict('records')
                recent_transactions.reverse()
        
        # Load user's bills
        if os.path.exists(BILLS_FILE) and wallet_id:
            bdf = pd.read_csv(BILLS_FILE, encoding='utf-8')
            user_bills = bdf[bdf['wallet_id'].astype(str).str.upper() == str(wallet_id).upper()]
            if not user_bills.empty:
                recent_bills = user_bills.tail(5).fillna('').to_dict('records')
                recent_bills.reverse()
    except Exception as e:
        print(f"Error loading user data: {e}")
        flash(f"Error loading dashboard data: {str(e)}", 'error')
    
    return render_template("user/dashboard.html", user_info=user_info, 
                         recent_transactions=recent_transactions, recent_bills=recent_bills)

@app.route("/user/wallet")
@user_only
def user_wallet():
    """User wallet view"""
    wallet_id = session.get('wallet_id')
    user_info = None
    
    try:
        if wallet_id:
            record = wallet.find_by_wallet_id(wallet_id)
            if record:
                user_info = record
            else:
                # Try to find by number_plate
                number_plate = session.get('number_plate', '')
                if number_plate:
                    record = wallet.find_by_plate(number_plate)
                    if record:
                        user_info = record
                        session['wallet_id'] = str(record.get('wallet_id', ''))
    except Exception as e:
        print(f"Error loading wallet: {e}")
        flash(f"Error loading wallet: {str(e)}", 'error')
    
    if not user_info:
        flash('Wallet information not found', 'error')
    
    return render_template("user/wallet.html", user_info=user_info)

@app.route("/user/recharge")
@user_only
def user_recharge():
    """Wallet recharge page"""
    wallet_id = session.get('wallet_id')
    user_info = None
    
    try:
        if wallet_id:
            record = wallet.find_by_wallet_id(wallet_id)
            if record:
                user_info = record
    except Exception as e:
        print(f"Error loading wallet: {e}")
    
    return render_template("user/recharge.html", user_info=user_info)

@app.route("/user/transactions")
@user_only
def user_transactions():
    """User's transaction history"""
    wallet_id = session.get('wallet_id')
    transactions = []
    
    try:
        if os.path.exists(TRANSACTIONS_FILE) and wallet_id:
            tdf = pd.read_csv(TRANSACTIONS_FILE, encoding='utf-8')
            # Filter by wallet_id (case-insensitive)
            user_txns = tdf[tdf['wallet_id'].astype(str).str.upper() == str(wallet_id).upper()]
            transactions = user_txns.fillna('').to_dict('records')
            transactions.reverse()
    except Exception as e:
        print(f"Error loading transactions: {e}")
        flash(f"Error loading transactions: {str(e)}", 'error')
    
    return render_template("user/transactions.html", transactions=transactions)

@app.route("/user/bills")
@user_only
def user_bills():
    """User's bills"""
    wallet_id = session.get('wallet_id')
    bills = []
    
    try:
        if os.path.exists(BILLS_FILE) and wallet_id:
            bdf = pd.read_csv(BILLS_FILE, encoding='utf-8')
            # Filter by wallet_id (case-insensitive)
            user_bills = bdf[bdf['wallet_id'].astype(str).str.upper() == str(wallet_id).upper()]
            bills = user_bills.fillna('').to_dict('records')
            bills.reverse()
    except Exception as e:
        print(f"Error loading bills: {e}")
        flash(f"Error loading bills: {str(e)}", 'error')
    
    return render_template("user/bills.html", bills=bills)

@app.route("/user/bill/<bill_id>")
@user_only
def user_bill_view(bill_id):
    """View individual bill (user only)"""
    wallet_id = session.get('wallet_id')
    bill = None
    
    try:
        if os.path.exists(BILLS_FILE) and wallet_id:
            bdf = pd.read_csv(BILLS_FILE, encoding='utf-8')
            # Filter by bill_id and wallet_id (case-insensitive)
            bill_row = bdf[
                (bdf['bill_id'].astype(str) == str(bill_id)) & 
                (bdf['wallet_id'].astype(str).str.upper() == str(wallet_id).upper())
            ]
            if not bill_row.empty:
                bill = bill_row.iloc[0].fillna('').to_dict()
    except Exception as e:
        print(f"Error loading bill: {e}")
    
    if not bill:
        flash('Bill not found or access denied', 'error')
        return redirect(url_for('user_bills'))
    
    return render_template("user/bill_view.html", bill=bill)



# ============================================
# API ROUTES
# ============================================


@app.route("/api/detect", methods=["POST"])
@admin_required
def api_detect():
    """API: Detect vehicle number plate from image"""
    try:
        data = request.get_json()
        
        if not data or "image" not in data:
            return jsonify({"error": "No image received"}), 400
        
        img_b64 = data["image"]
        if not img_b64 or "," not in img_b64:
            return jsonify({"error": "Invalid image format"}), 400
        
        header, encoded = img_b64.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        np_img = np.array(img)
        
        # YOLO detection with annotation
        from utils.yolo_detect import detect_and_annotate
        annotated_img = None
        boxes = []
        
        try:
            # Convert RGB to BGR for OpenCV
            bgr_img = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR) if len(np_img.shape) == 3 else np_img
            annotated_img, boxes = detect_and_annotate(bgr_img)
            # Convert back to RGB for encoding
            if len(annotated_img.shape) == 3:
                annotated_img = cv2.cvtColor(annotated_img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print(f"YOLO detection error: {e}")
            annotated_img = np_img.copy()
            boxes = []
        
        # Crop detected plate (use first detection with highest confidence)
        crop = np_img
        if boxes and len(boxes) > 0:
            # Sort by confidence if available
            if len(boxes[0]) == 5:
                boxes = sorted(boxes, key=lambda x: x[4], reverse=True)
            
            x1, y1, x2, y2 = boxes[0][:4]
            # Ensure valid coordinates
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(np_img.shape[1], int(x2)), min(np_img.shape[0], int(y2))
            if x2 > x1 and y2 > y1:
                crop = np_img[y1:y2, x1:x2]
        
        # OCR
        plate = ""
        try:
            # Convert to BGR for OCR function
            crop_bgr = cv2.cvtColor(crop, cv2.COLOR_RGB2BGR) if len(crop.shape) == 3 else crop
            plate = clean_identifier(read_plate_text_from_image(crop_bgr))
        except Exception as e:
            print(f"OCR error: {e}")
            plate = ""

        # Fake plate check
        plate_alert = {}
        if plate:
            from utils.ocr import check_plate_authenticity
            plate_alert = check_plate_authenticity(plate)
        
        # Wallet lookup (exact, then fuzzy fallback)
        record = None
        match_score = 0.0
        match_type = 'none'
        if plate:
            record = wallet.find_by_plate(plate)
            if record:
                match_type = 'exact'
                match_score = 1.0
            else:
                # Try fuzzy lookup
                fuzzy_record, score = find_wallet_by_plate_fuzzy(plate, cutoff=0.65)
                if fuzzy_record:
                    record = fuzzy_record
                    match_score = float(score)
                    match_type = 'fuzzy' if score < 0.99 else 'exact'

        # Store in session for bill generation if found
        if record:
            session['detected_vehicle'] = {
                'number_plate_id': str(record.get('number_plate_id', '')),
                'wallet_id': str(record.get('wallet_id', '')),
                'balance': float(record.get('balance', 0)),
                'fuel_type': str(record.get('fuel_type', 'Petrol')),
                'vehicle_type': str(record.get('vehicle_type', '')),
                'owner_email': str(record.get('email', '')),
                'email': str(record.get('email', '')),
                'match_type': match_type,
                'match_score': float(match_score)
            }
        
        # Encode annotated image to base64
        annotated_b64 = ""
        try:
            annotated_pil = Image.fromarray(annotated_img)
            buffer = io.BytesIO()
            annotated_pil.save(buffer, format='JPEG')
            annotated_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            annotated_b64 = f"data:image/jpeg;base64,{annotated_b64}"
        except Exception as e:
            print(f"Error encoding annotated image: {e}")
        
        return jsonify({
            "plate_text": plate,
            "wallet": record,
            "annotated_image": annotated_b64,
            "detections": len(boxes),
            "confidence": boxes[0][4] if boxes and len(boxes[0]) == 5 else 0.0,
            "match_type": match_type,
            "match_score": float(match_score),
            "plate_alert": plate_alert
        })
    except Exception as e:
        print(f"Error in api_detect: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/generate-bill", methods=["POST"])
@admin_required
def api_generate_bill():
    """API: Generate bill - KEY FEATURE - staff only enters fuel quantity"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        # Staff enters ONLY fuel quantity
        try:
            liters = float(data.get('liters', 0))
            if liters <= 0:
                return jsonify({"error": "Fuel quantity must be greater than 0"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid fuel quantity"}), 400
        
        fuel_type = str(data.get('fuel_type', 'Petrol')).strip()
        if fuel_type not in FUEL_PRICES:
            return jsonify({"error": f"Invalid fuel type. Must be one of: {', '.join(FUEL_PRICES.keys())}"}), 400
        
        # Accept plate/wallet from request body OR session (request body takes priority)
        vehicle_info = session.get('detected_vehicle') or {}
        number_plate = clean_identifier(
            data.get('number_plate_id') or vehicle_info.get('number_plate_id', '')
        )
        wallet_id = clean_identifier(
            data.get('wallet_id') or vehicle_info.get('wallet_id', '')
        )
        
        if not number_plate and not wallet_id:
            return jsonify({"error": "Vehicle not detected. Please scan vehicle first or enter plate manually."}), 400
        
        # Get wallet record (exact, then fuzzy, then by wallet id)
        record = None
        if number_plate:
            record = wallet.find_by_plate(number_plate)
            if not record:
                fuzzy_record, score = find_wallet_by_plate_fuzzy(number_plate, cutoff=0.65)
                if fuzzy_record:
                    record = fuzzy_record
                    # sync number_plate to canonical value
                    number_plate = clean_identifier(record.get('number_plate_id', number_plate))

        if not record and wallet_id:
            record = wallet.find_by_wallet_id(wallet_id)
            # If found by wallet, sync plate for downstream logging
            if record:
                number_plate = clean_identifier(record.get('number_plate_id', number_plate))

        if not record:
            return jsonify({"error": f"Wallet not found for vehicle: {number_plate}"}), 404
        
        # Use wallet_id from record if not provided
        if not wallet_id:
            wallet_id = str(record.get('wallet_id', ''))
        
        # Auto-calculate all bill details
        rate = float(FUEL_PRICES.get(fuel_type, 100.0))
        total_amount = liters * rate
        balance_before = float(record.get('balance', 0))
        
        # Check balance
        if balance_before < total_amount:
            return jsonify({
                "error": "Insufficient balance",
                "balance": balance_before,
                "required": total_amount,
                "shortfall": total_amount - balance_before
            }), 400
        
        # Generate bill ID
        bill_id = f"BILL-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        
        # Deduct from wallet
        try:
            balance_after = wallet.debit(number_plate, total_amount)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            print(f"Error debiting wallet: {e}")
            return jsonify({"error": "Failed to process payment"}), 500
        
        # Save transaction — all values explicitly cast to JSON-safe Python types
        transaction = {
            'transaction_id': str(f"TXN-{uuid.uuid4().hex[:8].upper()}"),
            'bill_id':        str(bill_id),
            'wallet_id':      str(wallet_id),
            'number_plate_id':str(number_plate),
            'type':           'debit',
            'amount':         float(total_amount),
            'liters':         float(liters),
            'fuel_type':      str(fuel_type),
            'rate':           float(rate),
            'balance_before': float(balance_before),
            'balance_after':  float(balance_after),
            'timestamp':      datetime.datetime.now().isoformat()
        }
        
        # Save bill — all values explicitly cast to JSON-safe Python types
        bill = {
            'bill_id':        str(bill_id),
            'wallet_id':      str(wallet_id),
            'number_plate_id':str(number_plate),
            'fuel_type':      str(fuel_type),
            'liters':         float(liters),
            'rate':           float(rate),
            'total_amount':   float(total_amount),
            'balance_before': float(balance_before),
            'balance_after':  float(balance_after),
            'timestamp':      datetime.datetime.now().isoformat(),
            'email_sent':     False,
            'email_status':   'pending'
        }
        
        # Append to CSV files
        try:
            # Ensure files exist
            init_storage()
            
            # Append transaction
            if os.path.exists(TRANSACTIONS_FILE):
                tdf = pd.read_csv(TRANSACTIONS_FILE, encoding='utf-8')
            else:
                tdf = pd.DataFrame(columns=[
                    'transaction_id', 'bill_id', 'wallet_id', 'number_plate_id', 
                    'type', 'amount', 'liters', 'fuel_type', 'rate', 
                    'balance_before', 'balance_after', 'timestamp'
                ])
            tdf = pd.concat([tdf, pd.DataFrame([transaction])], ignore_index=True)
            tdf.to_csv(TRANSACTIONS_FILE, index=False, encoding='utf-8')
            
            # Append bill
            if os.path.exists(BILLS_FILE):
                bdf = pd.read_csv(BILLS_FILE, encoding='utf-8')
            else:
                bdf = pd.DataFrame(columns=[
                    'bill_id', 'wallet_id', 'number_plate_id', 'fuel_type', 
                    'liters', 'rate', 'total_amount', 'balance_before', 
                    'balance_after', 'timestamp', 'email_sent', 'email_status'
                ])
            bdf = pd.concat([bdf, pd.DataFrame([bill])], ignore_index=True)
            bdf.to_csv(BILLS_FILE, index=False, encoding='utf-8')
            
            # Send email in background thread so response is not blocked
            user_email = str(record.get('email', '') or '')
            if user_email:
                bill['email_status'] = 'sending'
                import threading
                from utils.email_sender import send_bill_email
                bill_copy = dict(bill)  # snapshot before thread starts
                def _send(b, e):
                    try:
                        send_bill_email(b, e)
                    except Exception as ex:
                        print(f"[Email thread] {ex}")
                threading.Thread(target=_send, args=(bill_copy, user_email), daemon=True).start()
            else:
                bill['email_sent'] = False
                bill['email_status'] = 'no_email'
            
        except Exception as e:
            print(f"Error saving transaction/bill: {e}")
            # Don't fail the request if CSV save fails, but log it
        
        # Clear detected vehicle from session
        session.pop('detected_vehicle', None)
        
        return jsonify({
            "status": "success",
            "bill_id": bill_id,
            "bill": bill,
            "transaction": transaction
        })
    except Exception as e:
        print(f"Error in api_generate_bill: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/recharge", methods=["POST"])
@user_only
def api_recharge():
    """API: Recharge wallet"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        try:
            amount = float(data.get('amount', 0))
            if amount <= 0:
                return jsonify({"error": "Amount must be greater than 0"}), 400
            if amount < 100:
                return jsonify({"error": "Minimum recharge amount is ₹100"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid amount"}), 400
        
        wallet_id = session.get('wallet_id')
        number_plate = session.get('number_plate', '')
        
        # If number_plate not in session, try to find by wallet_id
        if not number_plate and wallet_id:
            record = wallet.find_by_wallet_id(wallet_id)
            if record:
                number_plate = str(record.get('number_plate_id', ''))
        
        if not number_plate:
            return jsonify({"error": "Vehicle information not found"}), 404
        
        # Get balance before recharge
        record_before = wallet.find_by_plate(number_plate)
        balance_before = float(record_before.get('balance', 0)) if record_before else 0.0
        
        # Recharge wallet
        try:
            balance_after = wallet.recharge(number_plate, amount)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            print(f"Error recharging wallet: {e}")
            return jsonify({"error": "Failed to recharge wallet"}), 500
        
        # Get updated wallet_id if it was created
        record_after = wallet.find_by_plate(number_plate)
        wallet_id = str(record_after.get('wallet_id', wallet_id))
        
        # Save transaction
        transaction = {
            'transaction_id': f"TXN-{uuid.uuid4().hex[:8].upper()}",
            'bill_id': '',
            'wallet_id': wallet_id,
            'number_plate_id': number_plate,
            'type': 'credit',
            'amount': amount,
            'liters': 0,
            'fuel_type': '',
            'rate': 0,
            'balance_before': balance_before,
            'balance_after': balance_after,
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        try:
            init_storage()
            if os.path.exists(TRANSACTIONS_FILE):
                tdf = pd.read_csv(TRANSACTIONS_FILE, encoding='utf-8')
            else:
                tdf = pd.DataFrame(columns=[
                    'transaction_id', 'bill_id', 'wallet_id', 'number_plate_id', 
                    'type', 'amount', 'liters', 'fuel_type', 'rate', 
                    'balance_before', 'balance_after', 'timestamp'
                ])
            tdf = pd.concat([tdf, pd.DataFrame([transaction])], ignore_index=True)
            tdf.to_csv(TRANSACTIONS_FILE, index=False, encoding='utf-8')
        except Exception as e:
            print(f"Error saving transaction: {e}")
            # Don't fail the request if CSV save fails
        
        return jsonify({
            "status": "success",
            "new_balance": balance_after,
            "amount_recharged": amount
        })
    except Exception as e:
        print(f"Error in api_recharge: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/update-fuel-prices", methods=["POST"])
@admin_required
def api_update_fuel_prices():
    """API: Update fuel prices in settings"""
    global FUEL_PRICES
    data = request.get_json()
    
    FUEL_PRICES['Petrol'] = float(data.get('petrol', FUEL_PRICES['Petrol']))
    FUEL_PRICES['Diesel'] = float(data.get('diesel', FUEL_PRICES['Diesel']))
    FUEL_PRICES['CNG'] = float(data.get('cng', FUEL_PRICES['CNG']))
    
    return jsonify({"status": "success", "prices": FUEL_PRICES})

@app.route("/api/wallet-info/<wallet_id>")
@admin_required
def api_wallet_info(wallet_id):
    """API: Get wallet information"""
    record = wallet.find_by_wallet_id(wallet_id)
    if not record:
        return jsonify({"error": "Wallet not found"}), 404
    return jsonify(record)

@app.route("/api/lookup-plate", methods=["POST"])
@admin_required
def api_lookup_plate():
    """API: Manual plate lookup — used when auto-detection fails"""
    data = request.get_json() or {}
    plate = clean_identifier(data.get('plate', ''))
    if not plate:
        return jsonify({"error": "Plate number required"}), 400

    record = wallet.find_by_plate(plate)
    if not record:
        record, score = find_wallet_by_plate_fuzzy(plate, cutoff=0.55)
        if record:
            record['_match'] = 'fuzzy'
        else:
            return jsonify({"error": f"No wallet found for plate: {plate}"}), 404

    # Store in session
    session['detected_vehicle'] = {
        'number_plate_id': str(record.get('number_plate_id', plate)),
        'wallet_id': str(record.get('wallet_id', '')),
        'balance': float(record.get('balance', 0)),
        'fuel_type': str(record.get('fuel_type', 'Petrol')),
        'vehicle_type': str(record.get('vehicle_type', '')),
        'email': str(record.get('email', '')),
        'match_type': record.pop('_match', 'exact'),
        'match_score': 1.0
    }

    # Fake plate check
    from utils.ocr import check_plate_authenticity
    plate_alert = check_plate_authenticity(plate)

    return jsonify({"success": True, "record": session['detected_vehicle'], "plate_alert": plate_alert})

# ============================================
# UTILITY ROUTES
# ============================================

@app.route("/download-bill/<bill_id>")
@login_required
def download_bill(bill_id):
    """Download bill as PDF using reportlab"""
    wallet_id_sess = session.get('wallet_id')
    is_admin = session.get('is_admin', False)

    bill = None
    try:
        if os.path.exists(BILLS_FILE):
            bdf = pd.read_csv(BILLS_FILE)
            bill_row = bdf[bdf['bill_id'].astype(str) == str(bill_id)]
            if not is_admin and wallet_id_sess:
                bill_row = bill_row[bill_row['wallet_id'].astype(str).str.upper() == str(wallet_id_sess).upper()]
            if not bill_row.empty:
                bill = bill_row.iloc[0].fillna('').to_dict()
    except Exception as e:
        print(f"Error loading bill: {e}")

    if not bill:
        flash('Bill not found', 'error')
        return redirect(url_for('user_bills' if not is_admin else 'admin_transactions'))

    # Try PDF generation with reportlab
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                rightMargin=20*mm, leftMargin=20*mm,
                                topMargin=20*mm, bottomMargin=20*mm)

        styles = getSampleStyleSheet()
        accent = colors.HexColor('#6c63ff')
        dark   = colors.HexColor('#1c1f2e')
        muted  = colors.HexColor('#64748b')

        title_style = ParagraphStyle('title', parent=styles['Title'],
                                     textColor=colors.white, fontSize=22,
                                     spaceAfter=4, alignment=TA_CENTER)
        sub_style   = ParagraphStyle('sub', parent=styles['Normal'],
                                     textColor=colors.HexColor('#a5b4fc'),
                                     fontSize=10, alignment=TA_CENTER)
        label_style = ParagraphStyle('lbl', parent=styles['Normal'],
                                     textColor=muted, fontSize=9)
        value_style = ParagraphStyle('val', parent=styles['Normal'],
                                     textColor=dark, fontSize=10, fontName='Helvetica-Bold')
        total_style = ParagraphStyle('tot', parent=styles['Normal'],
                                     textColor=accent, fontSize=14, fontName='Helvetica-Bold',
                                     alignment=TA_RIGHT)

        ts = str(bill.get('timestamp', ''))[:19].replace('T', ' ')
        liters_val  = float(bill.get('liters', 0) or 0)
        rate_val    = float(bill.get('rate', 0) or 0)
        total_val   = float(bill.get('total_amount', 0) or 0)
        bal_before  = float(bill.get('balance_before', 0) or 0)
        bal_after   = float(bill.get('balance_after', 0) or 0)

        elements = []

        # Header banner
        header_data = [[Paragraph('<b>FuelIQ</b>', title_style)],
                       [Paragraph('Smart Fueling System — Fuel Bill', sub_style)]]
        header_table = Table(header_data, colWidths=[170*mm])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), dark),
            ('TOPPADDING',    (0,0), (-1,-1), 14),
            ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 8*mm))

        # Bill meta
        meta = [
            ['Bill ID',      str(bill.get('bill_id', '')),  'Date & Time', ts],
            ['Vehicle Plate',str(bill.get('number_plate_id', '')), 'Wallet ID', str(bill.get('wallet_id', ''))],
        ]
        meta_table = Table(meta, colWidths=[35*mm, 55*mm, 35*mm, 45*mm])
        meta_table.setStyle(TableStyle([
            ('FONTNAME',  (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME',  (2,0), (2,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0,0), (0,-1), muted),
            ('TEXTCOLOR', (2,0), (2,-1), muted),
            ('FONTSIZE',  (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 6*mm))
        elements.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#e2e8f0')))
        elements.append(Spacer(1, 6*mm))

        # Line items
        items_header = [['Description', 'Quantity', 'Rate (₹/L)', 'Amount (₹)']]
        items_data   = [[str(bill.get('fuel_type', 'Fuel')),
                         f'{liters_val:.2f} L',
                         f'₹{rate_val:.2f}',
                         f'₹{total_val:.2f}']]
        items_table = Table(items_header + items_data,
                            colWidths=[80*mm, 30*mm, 30*mm, 30*mm])
        items_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), accent),
            ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 10),
            ('ALIGN',         (1,0), (-1,-1), 'RIGHT'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
            ('GRID',          (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 4*mm))

        # Total row
        total_table = Table([['', '', 'Total Amount:', f'₹{total_val:.2f}']],
                             colWidths=[80*mm, 30*mm, 30*mm, 30*mm])
        total_table.setStyle(TableStyle([
            ('FONTNAME',  (2,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',  (2,0), (-1,0), 12),
            ('TEXTCOLOR', (3,0), (3,0), accent),
            ('ALIGN',     (2,0), (-1,0), 'RIGHT'),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(total_table)
        elements.append(Spacer(1, 6*mm))
        elements.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#e2e8f0')))
        elements.append(Spacer(1, 4*mm))

        # Balance summary
        bal_data = [
            ['Balance Before:', f'₹{bal_before:.2f}'],
            ['Amount Deducted:', f'₹{total_val:.2f}'],
            ['Balance After:',  f'₹{bal_after:.2f}'],
        ]
        bal_table = Table(bal_data, colWidths=[60*mm, 40*mm])
        bal_table.setStyle(TableStyle([
            ('FONTNAME',  (0,0), (0,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0,0), (0,-1), muted),
            ('FONTSIZE',  (0,0), (-1,-1), 9),
            ('ALIGN',     (1,0), (1,-1), 'RIGHT'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
        ]))
        elements.append(bal_table)
        elements.append(Spacer(1, 10*mm))

        # Footer
        footer_style = ParagraphStyle('footer', parent=styles['Normal'],
                                      textColor=muted, fontSize=8, alignment=TA_CENTER)
        elements.append(Paragraph('Thank you for using FuelIQ Smart Fueling System', footer_style))
        elements.append(Paragraph('This is a computer-generated bill. No signature required.', footer_style))

        doc.build(elements)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=True,
                         download_name=f'FuelIQ-Bill-{bill_id}.pdf')

    except ImportError:
        # Fallback: render printable HTML
        return render_template("admin/bill_pdf.html", bill=bill)
    except Exception as e:
        print(f"PDF generation error: {e}")
        return render_template("admin/bill_pdf.html", bill=bill)

# ============================================
# Run App
# ============================================

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
