import os
import sqlite3
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, jsonify, send_file, g
)
from werkzeug.security import generate_password_hash, check_password_hash
import config
from database import (
    get_db, init_db, seed_sample_data, DB_PATH, CURRENT_DB_ENGINE,
    COMPATIBILITY_RECIPIENT_CAN_RECEIVE_FROM,
    COMPATIBILITY_DONOR_CAN_GIVE_TO
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.secret_key = config.SECRET_KEY

# Ensure database is safely initialized on startup
try:
    with app.app_context():
        init_db()
        seed_sample_data()
except Exception as e:
    print(f"[STARTUP DB INIT NOTE] Deferred initialization: {e}")

# ----------------- Helper Functions & Decorators -----------------

def get_current_user():
    if 'user_id' in session:
        conn = get_db()
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = cur.fetchone()
        conn.close()
        return user
    return None

@app.context_processor
def inject_user():
    user = get_current_user()
    donor_profile = None
    if user and user['role'] == 'donor':
        conn = get_db()
        cur = conn.execute("SELECT * FROM donors WHERE user_id = ?", (user['id'],))
        donor_profile = cur.fetchone()
        conn.close()
    
    # Expose current database engine (MySQL or SQLite) to templates
    conn = get_db()
    engine = conn.engine_type
    conn.close()
    return dict(current_user=user, donor_profile=donor_profile, active_db_engine=engine)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ----------------- Public Routes -----------------

@app.route('/')
def index():
    conn = get_db()
    
    # Stats queries using column alias 'count' for MySQL/SQLite cross-compatibility
    total_donors = conn.execute("SELECT COUNT(*) as count FROM donors").fetchone()['count']
    available_donors = conn.execute("SELECT COUNT(*) as count FROM donors WHERE is_available = 1").fetchone()['count']
    total_requests = conn.execute("SELECT COUNT(*) as count FROM blood_requests").fetchone()['count']
    fulfilled_requests = conn.execute("SELECT COUNT(*) as count FROM blood_requests WHERE status = 'Fulfilled'").fetchone()['count']

    # Recent critical/urgent requests
    recent_requests = conn.execute("""
        SELECT * FROM blood_requests 
        WHERE status = 'Pending' 
        ORDER BY 
            CASE urgency_level 
                WHEN 'Critical' THEN 1 
                WHEN 'Urgent' THEN 2 
                ELSE 3 
            END, created_at DESC 
        LIMIT 4
    """).fetchall()

    # Recent registered donors
    recent_donors = conn.execute("""
        SELECT d.*, u.name, u.phone 
        FROM donors d 
        JOIN users u ON d.user_id = u.id 
        WHERE d.is_available = 1
        ORDER BY d.id DESC 
        LIMIT 4
    """).fetchall()

    conn.close()
    return render_template('index.html',
                           total_donors=total_donors,
                           available_donors=available_donors,
                           total_requests=total_requests,
                           fulfilled_requests=fulfilled_requests,
                           recent_requests=recent_requests,
                           recent_donors=recent_donors,
                           compatibility_table=COMPATIBILITY_RECIPIENT_CAN_RECEIVE_FROM)

# ----------------- Authentication Routes -----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()
        blood_group = request.form.get('blood_group', '').strip().upper()
        age = request.form.get('age', type=int)
        gender = request.form.get('gender', '').strip()
        weight_kg = request.form.get('weight_kg', type=float)
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        address = request.form.get('address', '').strip()
        last_donation_date = request.form.get('last_donation_date', '').strip() or None

        # Basic validations
        if not all([name, email, password, phone, blood_group, age, gender, city, state]):
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        if age < 18 or age > 65:
            flash('Eligible donor age is between 18 and 65 years.', 'warning')
            return redirect(url_for('register'))

        if weight_kg and weight_kg < 45.0:
            flash('Donor weight must be at least 45 kg for health and safety.', 'warning')
            return redirect(url_for('register'))

        conn = get_db()
        existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing_user:
            conn.close()
            flash('Email already registered! Please log in or use another email.', 'danger')
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)

        try:
            # 90-day cooldown logic
            is_available = 1
            if last_donation_date:
                try:
                    last_date_obj = datetime.strptime(last_donation_date, '%Y-%m-%d').date()
                    if (date.today() - last_date_obj).days < 90:
                        is_available = 0
                except ValueError:
                    pass

            cur = conn.execute("""
                INSERT INTO users (name, email, password_hash, phone, role)
                VALUES (?, ?, ?, ?, 'donor')
            """, (name, email, password_hash, phone))
            user_id = cur.lastrowid

            conn.execute("""
                INSERT INTO donors (user_id, blood_group, age, gender, weight_kg, city, state, pincode, address, last_donation_date, is_available)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, blood_group, age, gender, weight_kg, city, state, pincode, address, last_donation_date, is_available))

            conn.commit()
            conn.close()

            flash('Registration successful! You can now log in to your donor account.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.close()
            flash(f'An error occurred during registration: {str(e)}', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['role'] = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                next_page = request.args.get('next')
                return redirect(next_page or url_for('donor_profile'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('index'))

# ----------------- Donor Search Route -----------------

@app.route('/search')
def search():
    blood_group = request.args.get('blood_group', '').strip().upper()
    city = request.args.get('city', '').strip()
    state = request.args.get('state', '').strip()
    compatible_mode = request.args.get('compatible', '0') == '1'
    available_only = request.args.get('available_only', '1') == '1'

    query = """
        SELECT d.*, u.name, u.phone, u.email 
        FROM donors d
        JOIN users u ON d.user_id = u.id
        WHERE 1=1
    """
    params = []

    if available_only:
        query += " AND d.is_available = 1"

    if blood_group and blood_group in COMPATIBILITY_RECIPIENT_CAN_RECEIVE_FROM:
        if compatible_mode:
            compat_list = COMPATIBILITY_RECIPIENT_CAN_RECEIVE_FROM[blood_group]
            placeholders = ','.join(['?'] * len(compat_list))
            query += f" AND d.blood_group IN ({placeholders})"
            params.extend(compat_list)
        else:
            query += " AND d.blood_group = ?"
            params.append(blood_group)

    if city:
        query += " AND LOWER(d.city) LIKE ?"
        params.append(f"%{city.lower()}%")

    if state:
        query += " AND LOWER(d.state) LIKE ?"
        params.append(f"%{state.lower()}%")

    query += " ORDER BY d.is_available DESC, d.total_donations DESC, d.id DESC"

    conn = get_db()
    donors = conn.execute(query, params).fetchall()

    # Distinct cities and states for quick filter suggestions
    city_rows = conn.execute("SELECT DISTINCT city FROM donors ORDER BY city").fetchall()
    cities = [r['city'] for r in city_rows]

    state_rows = conn.execute("SELECT DISTINCT state FROM donors ORDER BY state").fetchall()
    states = [r['state'] for r in state_rows]

    conn.close()

    return render_template('search.html',
                           donors=donors,
                           selected_blood_group=blood_group,
                           selected_city=city,
                           selected_state=state,
                           compatible_mode=compatible_mode,
                           available_only=available_only,
                           cities=cities,
                           states=states,
                           recipient_matrix=COMPATIBILITY_RECIPIENT_CAN_RECEIVE_FROM)

# ----------------- Emergency Blood Requests -----------------

@app.route('/requests')
def view_requests():
    blood_group = request.args.get('blood_group', '').strip().upper()
    urgency = request.args.get('urgency', '').strip()
    status = request.args.get('status', 'Pending').strip()
    city = request.args.get('city', '').strip()

    query = "SELECT * FROM blood_requests WHERE 1=1"
    params = []

    if status and status != 'All':
        query += " AND status = ?"
        params.append(status)

    if blood_group:
        query += " AND blood_group = ?"
        params.append(blood_group)

    if urgency and urgency != 'All':
        query += " AND urgency_level = ?"
        params.append(urgency)

    if city:
        query += " AND LOWER(city) LIKE ?"
        params.append(f"%{city.lower()}%")

    query += """
        ORDER BY 
            CASE status WHEN 'Pending' THEN 1 ELSE 2 END,
            CASE urgency_level WHEN 'Critical' THEN 1 WHEN 'Urgent' THEN 2 ELSE 3 END,
            created_at DESC
    """

    conn = get_db()
    requests_list = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('requests.html',
                           requests=requests_list,
                           selected_blood_group=blood_group,
                           selected_urgency=urgency,
                           selected_status=status,
                           selected_city=city)

@app.route('/requests/new', methods=['GET', 'POST'])
def post_request():
    if request.method == 'POST':
        patient_name = request.form.get('patient_name', '').strip()
        blood_group = request.form.get('blood_group', '').strip().upper()
        units_needed = request.form.get('units_needed', type=int) or 1
        hospital_name = request.form.get('hospital_name', '').strip()
        hospital_address = request.form.get('hospital_address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        contact_person = request.form.get('contact_person', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        urgency_level = request.form.get('urgency_level', 'Urgent')
        reason = request.form.get('reason', '').strip()

        if not all([patient_name, blood_group, hospital_name, city, state, contact_person, contact_phone]):
            flash('Please fill in all required fields for the emergency blood request.', 'danger')
            return redirect(url_for('post_request'))

        requester_id = session.get('user_id')

        conn = get_db()
        cur = conn.execute("""
            INSERT INTO blood_requests (
                requester_id, patient_name, blood_group, units_needed,
                hospital_name, hospital_address, city, state,
                contact_person, contact_phone, urgency_level, reason, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
        """, (requester_id, patient_name, blood_group, units_needed,
              hospital_name, hospital_address, city, state,
              contact_person, contact_phone, urgency_level, reason))
        request_id = cur.lastrowid
        conn.commit()
        conn.close()

        flash('Emergency Blood Request posted successfully! Matching donors can view and respond.', 'success')
        return redirect(url_for('request_details', request_id=request_id))

    return render_template('post_request.html')

@app.route('/requests/<int:request_id>')
def request_details(request_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM blood_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        conn.close()
        flash('Request not found.', 'danger')
        return redirect(url_for('view_requests'))

    compat_blood_types = COMPATIBILITY_RECIPIENT_CAN_RECEIVE_FROM.get(req['blood_group'], [req['blood_group']])
    placeholders = ','.join(['?'] * len(compat_blood_types))

    match_query = f"""
        SELECT d.*, u.name, u.phone, u.email,
               (CASE WHEN LOWER(d.city) = LOWER(?) THEN 1 ELSE 0 END) as city_match
        FROM donors d
        JOIN users u ON d.user_id = u.id
        WHERE d.is_available = 1 AND d.blood_group IN ({placeholders})
        ORDER BY city_match DESC, d.total_donations DESC
        LIMIT 10
    """
    params = [req['city']] + compat_blood_types
    matched_donors = conn.execute(match_query, params).fetchall()

    responses = conn.execute("""
        SELECT r.*, u.name as donor_name, u.phone as donor_phone, d.blood_group, d.city
        FROM donation_responses r
        JOIN donors d ON r.donor_id = d.id
        JOIN users u ON d.user_id = u.id
        WHERE r.request_id = ?
        ORDER BY r.created_at DESC
    """, (request_id,)).fetchall()

    conn.close()
    return render_template('request_details.html',
                           req=req,
                           matched_donors=matched_donors,
                           responses=responses,
                           compatible_groups=compat_blood_types)

@app.route('/requests/<int:request_id>/volunteer', methods=['POST'])
@login_required
def volunteer_request(request_id):
    user_id = session.get('user_id')
    conn = get_db()
    donor = conn.execute("SELECT id FROM donors WHERE user_id = ?", (user_id,)).fetchone()

    if not donor:
        conn.close()
        flash('Only registered donors can volunteer for blood requests.', 'warning')
        return redirect(url_for('request_details', request_id=request_id))

    message = request.form.get('message', 'I am willing to donate blood for this patient. Please contact me.')

    existing = conn.execute("""
        SELECT id FROM donation_responses WHERE request_id = ? AND donor_id = ?
    """, (request_id, donor['id'])).fetchone()

    if existing:
        conn.close()
        flash('You have already pledged to help with this blood request!', 'info')
        return redirect(url_for('request_details', request_id=request_id))

    conn.execute("""
        INSERT INTO donation_responses (request_id, donor_id, message)
        VALUES (?, ?, ?)
    """, (request_id, donor['id'], message))
    conn.commit()
    conn.close()

    flash('Thank you for your noble gesture! Your contact details are now shared with the patient contact.', 'success')
    return redirect(url_for('request_details', request_id=request_id))

@app.route('/requests/<int:request_id>/status', methods=['POST'])
def update_request_status(request_id):
    new_status = request.form.get('status')
    if new_status not in ['Pending', 'Fulfilled', 'Cancelled']:
        flash('Invalid status.', 'danger')
        return redirect(url_for('request_details', request_id=request_id))

    conn = get_db()
    req = conn.execute("SELECT * FROM blood_requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        conn.close()
        flash('Request not found.', 'danger')
        return redirect(url_for('view_requests'))

    user_id = session.get('user_id')
    role = session.get('role')
    if role == 'admin' or (req['requester_id'] and req['requester_id'] == user_id):
        conn.execute("UPDATE blood_requests SET status = ? WHERE id = ?", (new_status, request_id))
        conn.commit()
        flash(f'Request marked as {new_status}!', 'success')
    else:
        flash('Unauthorized to update this request.', 'danger')

    conn.close()
    return redirect(url_for('request_details', request_id=request_id))

# ----------------- Donor Profile Routes -----------------

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def donor_profile():
    user_id = session['user_id']
    conn = get_db()

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        address = request.form.get('address', '').strip()
        last_donation_date = request.form.get('last_donation_date', '').strip() or None
        is_available = 1 if request.form.get('is_available') == '1' else 0

        conn.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, user_id))

        if last_donation_date:
            try:
                last_date_obj = datetime.strptime(last_donation_date, '%Y-%m-%d').date()
                days_since = (date.today() - last_date_obj).days
                if days_since < 90:
                    is_available = 0
            except ValueError:
                pass

        conn.execute("""
            UPDATE donors 
            SET city = ?, state = ?, pincode = ?, address = ?, last_donation_date = ?, is_available = ?
            WHERE user_id = ?
        """, (city, state, pincode, address, last_donation_date, is_available, user_id))
        conn.commit()
        flash('Your profile has been updated successfully!', 'success')

    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    donor = conn.execute("SELECT * FROM donors WHERE user_id = ?", (user_id,)).fetchone()

    matching_requests = []
    if donor:
        can_give_to = COMPATIBILITY_DONOR_CAN_GIVE_TO.get(donor['blood_group'], [donor['blood_group']])
        placeholders = ','.join(['?'] * len(can_give_to))
        query = f"""
            SELECT * FROM blood_requests 
            WHERE status = 'Pending' AND blood_group IN ({placeholders})
            ORDER BY 
                CASE WHEN LOWER(city) = LOWER(?) THEN 1 ELSE 2 END,
                CASE urgency_level WHEN 'Critical' THEN 1 WHEN 'Urgent' THEN 2 ELSE 3 END,
                created_at DESC
            LIMIT 5
        """
        matching_requests = conn.execute(query, can_give_to + [donor['city']]).fetchall()

    my_pledges = []
    if donor:
        my_pledges = conn.execute("""
            SELECT r.*, resp.created_at as pledged_at, resp.status as pledge_status
            FROM donation_responses resp
            JOIN blood_requests r ON resp.request_id = r.id
            WHERE resp.donor_id = ?
            ORDER BY resp.created_at DESC
        """, (donor['id'],)).fetchall()

    days_since_donation = None
    eligible_in_days = 0
    if donor and donor['last_donation_date']:
        try:
            d_date = datetime.strptime(str(donor['last_donation_date'])[:10], '%Y-%m-%d').date()
            days_since_donation = (date.today() - d_date).days
            if days_since_donation < 90:
                eligible_in_days = 90 - days_since_donation
        except ValueError:
            pass

    conn.close()
    return render_template('profile.html',
                           user=user,
                           donor=donor,
                           matching_requests=matching_requests,
                           my_pledges=my_pledges,
                           days_since_donation=days_since_donation,
                           eligible_in_days=eligible_in_days)

@app.route('/profile/toggle-availability', methods=['POST'])
@login_required
def toggle_availability():
    user_id = session['user_id']
    conn = get_db()
    donor = conn.execute("SELECT id, is_available, last_donation_date FROM donors WHERE user_id = ?", (user_id,)).fetchone()
    if donor:
        new_status = 0 if donor['is_available'] == 1 else 1
        conn.execute("UPDATE donors SET is_available = ? WHERE id = ?", (new_status, donor['id']))
        conn.commit()
        status_text = "Available to Donate" if new_status == 1 else "Unavailable"
        flash(f'Your status updated to: {status_text}', 'info')
    conn.close()
    return redirect(url_for('donor_profile'))

# ----------------- Admin Module -----------------

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()

    total_donors = conn.execute("SELECT COUNT(*) as count FROM donors").fetchone()['count']
    available_donors = conn.execute("SELECT COUNT(*) as count FROM donors WHERE is_available = 1").fetchone()['count']
    total_requests = conn.execute("SELECT COUNT(*) as count FROM blood_requests").fetchone()['count']
    pending_requests = conn.execute("SELECT COUNT(*) as count FROM blood_requests WHERE status = 'Pending'").fetchone()['count']
    fulfilled_requests = conn.execute("SELECT COUNT(*) as count FROM blood_requests WHERE status = 'Fulfilled'").fetchone()['count']

    blood_distribution = conn.execute("""
        SELECT blood_group, COUNT(*) as count 
        FROM donors 
        GROUP BY blood_group 
        ORDER BY blood_group
    """).fetchall()

    blood_labels = [row['blood_group'] for row in blood_distribution]
    blood_counts = [row['count'] for row in blood_distribution]

    recent_requests = conn.execute("""
        SELECT * FROM blood_requests ORDER BY created_at DESC LIMIT 6
    """).fetchall()

    recent_donors = conn.execute("""
        SELECT d.*, u.name, u.phone, u.email 
        FROM donors d 
        JOIN users u ON d.user_id = u.id 
        ORDER BY d.id DESC LIMIT 6
    """).fetchall()

    conn.close()
    return render_template('admin/dashboard.html',
                           total_donors=total_donors,
                           available_donors=available_donors,
                           total_requests=total_requests,
                           pending_requests=pending_requests,
                           fulfilled_requests=fulfilled_requests,
                           blood_labels=blood_labels,
                           blood_counts=blood_counts,
                           recent_requests=recent_requests,
                           recent_donors=recent_donors)

@app.route('/admin/donors')
@admin_required
def admin_donors():
    search_query = request.args.get('q', '').strip()
    blood_group = request.args.get('blood_group', '').strip().upper()

    query = """
        SELECT d.*, u.name, u.email, u.phone, u.created_at as registered_on
        FROM donors d
        JOIN users u ON d.user_id = u.id
        WHERE 1=1
    """
    params = []

    if search_query:
        query += " AND (LOWER(u.name) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(d.city) LIKE ? OR u.phone LIKE ?)"
        term = f"%{search_query.lower()}%"
        params.extend([term, term, term, term])

    if blood_group:
        query += " AND d.blood_group = ?"
        params.append(blood_group)

    query += " ORDER BY d.id DESC"

    conn = get_db()
    donors = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('admin/donors.html', donors=donors, search_query=search_query, selected_blood_group=blood_group)

@app.route('/admin/donors/<int:donor_id>/toggle-verify', methods=['POST'])
@admin_required
def admin_toggle_verify_donor(donor_id):
    conn = get_db()
    donor = conn.execute("SELECT is_verified FROM donors WHERE id = ?", (donor_id,)).fetchone()
    if donor:
        new_val = 0 if donor['is_verified'] == 1 else 1
        conn.execute("UPDATE donors SET is_verified = ? WHERE id = ?", (new_val, donor_id))
        conn.commit()
        flash('Donor verification status updated.', 'success')
    conn.close()
    return redirect(url_for('admin_donors'))

@app.route('/admin/donors/<int:donor_id>/delete', methods=['POST'])
@admin_required
def admin_delete_donor(donor_id):
    conn = get_db()
    donor = conn.execute("SELECT user_id FROM donors WHERE id = ?", (donor_id,)).fetchone()
    if donor:
        conn.execute("DELETE FROM users WHERE id = ?", (donor['user_id'],))
        conn.commit()
        flash('Donor record deleted successfully.', 'info')
    conn.close()
    return redirect(url_for('admin_donors'))

@app.route('/admin/requests')
@admin_required
def admin_requests():
    conn = get_db()
    requests_list = conn.execute("SELECT * FROM blood_requests ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template('admin/requests.html', requests=requests_list)

@app.route('/admin/requests/<int:request_id>/update-status', methods=['POST'])
@admin_required
def admin_update_request_status(request_id):
    new_status = request.form.get('status')
    conn = get_db()
    conn.execute("UPDATE blood_requests SET status = ? WHERE id = ?", (new_status, request_id))
    conn.commit()
    conn.close()
    flash(f'Request #{request_id} updated to {new_status}.', 'success')
    return redirect(url_for('admin_requests'))

@app.route('/admin/requests/<int:request_id>/delete', methods=['POST'])
@admin_required
def admin_delete_request(request_id):
    conn = get_db()
    conn.execute("DELETE FROM blood_requests WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()
    flash(f'Request #{request_id} removed.', 'info')
    return redirect(url_for('admin_requests'))

# ----------------- Database Management Module (Admin) -----------------

@app.route('/admin/database', methods=['GET', 'POST'])
@admin_required
def admin_database():
    conn = get_db()
    tables = ['users', 'donors', 'blood_requests', 'donation_responses']
    selected_table = request.args.get('table', 'donors')
    if selected_table not in tables:
        selected_table = 'donors'

    # Get column names across MySQL and SQLite
    if conn.engine_type == 'mysql':
        cols_data = conn.execute(f"DESCRIBE {selected_table}").fetchall()
        columns = [c['Field'] for c in cols_data]
    else:
        cols_data = conn.execute(f"PRAGMA table_info({selected_table})").fetchall()
        columns = [col['name'] for col in cols_data]

    # Get records from selected table
    rows = conn.execute(f"SELECT * FROM {selected_table} LIMIT 100").fetchall()

    # Custom Query Execution for Demo / Viva presentation
    query_result = None
    query_columns = None
    custom_sql = ""
    error_msg = None

    if request.method == 'POST' and 'run_query' in request.form:
        custom_sql = request.form.get('sql_query', '').strip()
        if not custom_sql.lower().startswith('select'):
            error_msg = "Security constraint: Only read-only SELECT queries are permitted in this console."
        else:
            try:
                cur = conn.execute(custom_sql)
                rows_data = cur.fetchall()
                if cur.description:
                    query_columns = [col[0] for col in cur.description]
                    query_result = rows_data
            except Exception as e:
                error_msg = str(e)

    conn.close()
    return render_template('admin/database.html',
                           tables=tables,
                           selected_table=selected_table,
                           columns=columns,
                           rows=rows,
                           custom_sql=custom_sql,
                           query_result=query_result,
                           query_columns=query_columns,
                           error_msg=error_msg)

@app.route('/admin/database/download')
@admin_required
def download_database():
    if os.path.exists(DB_PATH):
        return send_file(DB_PATH, as_attachment=True, download_name='blood_bank_backup.db')
    sql_file = os.path.join(os.path.dirname(__file__), 'database_mysql.sql')
    if os.path.exists(sql_file):
        return send_file(sql_file, as_attachment=True, download_name='blood_bank_db.sql')
    flash('Database backup file not found.', 'danger')
    return redirect(url_for('admin_database'))

@app.route('/admin/database/reset-seed', methods=['POST'])
@admin_required
def reset_and_seed_database():
    conn = get_db()
    conn.execute("DROP TABLE IF EXISTS donation_responses")
    conn.execute("DROP TABLE IF EXISTS blood_requests")
    conn.execute("DROP TABLE IF EXISTS donors")
    conn.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    conn.close()

    init_db()
    seed_sample_data()
    flash('Database has been completely reset and fresh sample data re-seeded!', 'success')
    return redirect(url_for('admin_database'))

# ----------------- Main Entrypoint -----------------

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
