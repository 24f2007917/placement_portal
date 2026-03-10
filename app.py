from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database helper functions
def get_db():
    conn = sqlite3.connect('placement_portal.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with schema and admin user"""
    conn = sqlite3.connect('placement_portal.db')
    cursor = conn.cursor()
    
    # Users table (for all roles)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'company', 'student')),
            is_approved INTEGER DEFAULT 0,
            is_blacklisted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            roll_number TEXT UNIQUE NOT NULL,
            department TEXT NOT NULL,
            cgpa REAL,
            phone TEXT,
            resume_path TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Companies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            industry TEXT,
            website TEXT,
            contact_person TEXT,
            phone TEXT,
            address TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Placement Drives table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS placement_drives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            job_title TEXT NOT NULL,
            description TEXT,
            eligibility_criteria TEXT,
            min_cgpa REAL,
            salary_package TEXT,
            deadline DATE NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'closed')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    ''')
    
    # Applications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            drive_id INTEGER NOT NULL,
            application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'applied' CHECK(status IN ('applied', 'shortlisted', 'selected', 'rejected')),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (drive_id) REFERENCES placement_drives(id) ON DELETE CASCADE,
            UNIQUE(student_id, drive_id)
        )
    ''')
    
    # Create default admin user
    admin_password = generate_password_hash('admin123')
    cursor.execute('''
        INSERT OR IGNORE INTO users (email, password, role, is_approved)
        VALUES (?, ?, 'admin', 1)
    ''', ('admin@placement.com', admin_password))
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

# Session-based authentication helpers
def get_current_user():
    """Get current user from session"""
    if 'user_id' not in session:
        return None
    
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return user

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Role-based access decorators
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('login'))
            
            current_user = get_current_user()
            if not current_user or current_user['role'] != role:
                flash('Access denied. Insufficient permissions.', 'danger')
                return redirect(url_for('login'))
            if current_user['is_blacklisted']:
                flash('Your account has been blacklisted.', 'danger')
                session.clear()
                return redirect(url_for('login'))
            if role != 'admin' and not current_user['is_approved']:
                flash('Your account is pending approval.', 'warning')
                session.clear()
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            if user['is_blacklisted']:
                flash('Your account has been blacklisted.', 'danger')
                return redirect(url_for('login'))
            
            if user['role'] != 'admin' and not user['is_approved']:
                flash('Your account is pending admin approval.', 'warning')
                return redirect(url_for('login'))
            
            # Set session
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['role'] = user['role']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    if role not in ['student', 'company']:
        flash('Invalid registration type.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', role=role)
        
        conn = get_db()
        existing_user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if existing_user:
            flash('Email already registered.', 'danger')
            conn.close()
            return render_template('register.html', role=role)
        
        hashed_password = generate_password_hash(password)
        
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (email, password, role, is_approved) VALUES (?, ?, ?, 0)',
                         (email, hashed_password, role))
            user_id = cursor.lastrowid
            
            if role == 'student':
                name = request.form.get('name')
                roll_number = request.form.get('roll_number')
                department = request.form.get('department')
                cgpa = request.form.get('cgpa')
                phone = request.form.get('phone')
                
                cursor.execute('''
                    INSERT INTO students (user_id, name, roll_number, department, cgpa, phone)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, name, roll_number, department, cgpa, phone))
            
            elif role == 'company':
                company_name = request.form.get('company_name')
                industry = request.form.get('industry')
                website = request.form.get('website')
                contact_person = request.form.get('contact_person')
                phone = request.form.get('phone')
                address = request.form.get('address')
                
                cursor.execute('''
                    INSERT INTO companies (user_id, company_name, industry, website, contact_person, phone, address)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, company_name, industry, website, contact_person, phone, address))
            
            conn.commit()
            flash('Registration successful! Please wait for admin approval.', 'success')
            return redirect(url_for('login'))
        
        except sqlite3.IntegrityError as e:
            flash('Registration failed. Roll number or email already exists.', 'danger')
        finally:
            conn.close()
    
    return render_template('register.html', role=role)

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    current_user = get_current_user()
    if current_user['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user['role'] == 'company':
        return redirect(url_for('company_dashboard'))
    elif current_user['role'] == 'student':
        return redirect(url_for('student_dashboard'))

# ADMIN ROUTES
@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    conn = get_db()
    
    total_students = conn.execute('SELECT COUNT(*) as count FROM students').fetchone()['count']
    total_companies = conn.execute('SELECT COUNT(*) as count FROM companies').fetchone()['count']
    total_drives = conn.execute('SELECT COUNT(*) as count FROM placement_drives').fetchone()['count']
    total_applications = conn.execute('SELECT COUNT(*) as count FROM applications').fetchone()['count']
    
    pending_companies = conn.execute('''
        SELECT COUNT(*) as count FROM users WHERE role = 'company' AND is_approved = 0
    ''').fetchone()['count']
    
    pending_drives = conn.execute('''
        SELECT COUNT(*) as count FROM placement_drives WHERE status = 'pending'
    ''').fetchone()['count']
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                         total_students=total_students,
                         total_companies=total_companies,
                         total_drives=total_drives,
                         total_applications=total_applications,
                         pending_companies=pending_companies,
                         pending_drives=pending_drives)

@app.route('/admin/companies')
@role_required('admin')
def admin_companies():
    search = request.args.get('search', '')
    conn = get_db()
    
    if search:
        companies = conn.execute('''
            SELECT c.*, u.email, u.is_approved, u.is_blacklisted
            FROM companies c
            JOIN users u ON c.user_id = u.id
            WHERE c.company_name LIKE ? OR c.industry LIKE ?
            ORDER BY c.id DESC
        ''', (f'%{search}%', f'%{search}%')).fetchall()
    else:
        companies = conn.execute('''
            SELECT c.*, u.email, u.is_approved, u.is_blacklisted
            FROM companies c
            JOIN users u ON c.user_id = u.id
            ORDER BY c.id DESC
        ''').fetchall()
    
    conn.close()
    return render_template('admin/companies.html', companies=companies, search=search)

@app.route('/admin/company/approve/<int:user_id>')
@role_required('admin')
def approve_company(user_id):
    conn = get_db()
    conn.execute('UPDATE users SET is_approved = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('Company approved successfully!', 'success')
    return redirect(url_for('admin_companies'))

@app.route('/admin/company/reject/<int:user_id>')
@role_required('admin')
def reject_company(user_id):
    conn = get_db()
    conn.execute('UPDATE users SET is_approved = 0 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('Company registration rejected.', 'info')
    return redirect(url_for('admin_companies'))

@app.route('/admin/company/blacklist/<int:user_id>')
@role_required('admin')
def blacklist_company(user_id):
    conn = get_db()
    company = conn.execute('SELECT is_blacklisted FROM users WHERE id = ?', (user_id,)).fetchone()
    new_status = 0 if company['is_blacklisted'] else 1
    conn.execute('UPDATE users SET is_blacklisted = ? WHERE id = ?', (new_status, user_id))
    conn.commit()
    conn.close()
    
    action = 'blacklisted' if new_status else 'removed from blacklist'
    flash(f'Company {action} successfully!', 'success')
    return redirect(url_for('admin_companies'))

@app.route('/admin/company/delete/<int:company_id>', methods=['POST'])
@role_required('admin')
def delete_company(company_id):
    conn = get_db()
    user_id = conn.execute('SELECT user_id FROM companies WHERE id = ?', (company_id,)).fetchone()['user_id']
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('Company deleted successfully!', 'success')
    return redirect(url_for('admin_companies'))

@app.route('/admin/students')
@role_required('admin')
def admin_students():
    search = request.args.get('search', '')
    conn = get_db()
    
    if search:
        students = conn.execute('''
            SELECT s.*, u.email, u.is_approved, u.is_blacklisted
            FROM students s
            JOIN users u ON s.user_id = u.id
            WHERE s.name LIKE ? OR s.roll_number LIKE ? OR s.department LIKE ?
            ORDER BY s.id DESC
        ''', (f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()
    else:
        students = conn.execute('''
            SELECT s.*, u.email, u.is_approved, u.is_blacklisted
            FROM students s
            JOIN users u ON s.user_id = u.id
            ORDER BY s.id DESC
        ''').fetchall()
    
    conn.close()
    return render_template('admin/students.html', students=students, search=search)

@app.route('/admin/student/approve/<int:user_id>')
@role_required('admin')
def approve_student(user_id):
    conn = get_db()
    conn.execute('UPDATE users SET is_approved = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('Student approved successfully!', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/student/blacklist/<int:user_id>')
@role_required('admin')
def blacklist_student(user_id):
    conn = get_db()
    student = conn.execute('SELECT is_blacklisted FROM users WHERE id = ?', (user_id,)).fetchone()
    new_status = 0 if student['is_blacklisted'] else 1
    conn.execute('UPDATE users SET is_blacklisted = ? WHERE id = ?', (new_status, user_id))
    conn.commit()
    conn.close()
    
    action = 'blacklisted' if new_status else 'removed from blacklist'
    flash(f'Student {action} successfully!', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/student/delete/<int:student_id>', methods=['POST'])
@role_required('admin')
def delete_student(student_id):
    conn = get_db()
    user_id = conn.execute('SELECT user_id FROM students WHERE id = ?', (student_id,)).fetchone()['user_id']
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/drives')
@role_required('admin')
def admin_drives():
    conn = get_db()
    drives = conn.execute('''
        SELECT pd.*, c.company_name
        FROM placement_drives pd
        JOIN companies c ON pd.company_id = c.id
        ORDER BY pd.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/drives.html', drives=drives)

@app.route('/admin/drive/approve/<int:drive_id>')
@role_required('admin')
def approve_drive(drive_id):
    conn = get_db()
    conn.execute('UPDATE placement_drives SET status = "approved" WHERE id = ?', (drive_id,))
    conn.commit()
    conn.close()
    flash('Drive approved successfully!', 'success')
    return redirect(url_for('admin_drives'))

@app.route('/admin/drive/reject/<int:drive_id>')
@role_required('admin')
def reject_drive(drive_id):
    conn = get_db()
    conn.execute('UPDATE placement_drives SET status = "rejected" WHERE id = ?', (drive_id,))
    conn.commit()
    conn.close()
    flash('Drive rejected.', 'info')
    return redirect(url_for('admin_drives'))

@app.route('/admin/applications')
@role_required('admin')
def admin_applications():
    conn = get_db()
    applications = conn.execute('''
        SELECT a.*, s.name as student_name, s.roll_number, 
               pd.job_title, c.company_name
        FROM applications a
        JOIN students s ON a.student_id = s.id
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        ORDER BY a.application_date DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/applications.html', applications=applications)

# COMPANY ROUTES
@app.route('/company/dashboard')
@role_required('company')
def company_dashboard():
    conn = get_db()
    
    company = conn.execute('''
        SELECT c.* FROM companies c
        JOIN users u ON c.user_id = u.id
        WHERE u.id = ?
    ''', (session["user_id"],)).fetchone()
    
    total_drives = conn.execute('''
        SELECT COUNT(*) as count FROM placement_drives WHERE company_id = ?
    ''', (company['id'],)).fetchone()['count']
    
    approved_drives = conn.execute('''
        SELECT COUNT(*) as count FROM placement_drives 
        WHERE company_id = ? AND status = 'approved'
    ''', (company['id'],)).fetchone()['count']
    
    total_applicants = conn.execute('''
        SELECT COUNT(*) as count FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        WHERE pd.company_id = ?
    ''', (company['id'],)).fetchone()['count']
    
    conn.close()
    
    return render_template('company/dashboard.html',
                         company=company,
                         total_drives=total_drives,
                         approved_drives=approved_drives,
                         total_applicants=total_applicants)

@app.route('/company/profile', methods=['GET', 'POST'])
@role_required('company')
def company_profile():
    conn = get_db()
    
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        industry = request.form.get('industry')
        website = request.form.get('website')
        contact_person = request.form.get('contact_person')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        conn.execute('''
            UPDATE companies SET company_name = ?, industry = ?, website = ?,
            contact_person = ?, phone = ?, address = ?
            WHERE user_id = ?
        ''', (company_name, industry, website, contact_person, phone, address, session["user_id"]))
        conn.commit()
        flash('Profile updated successfully!', 'success')
    
    company = conn.execute('SELECT * FROM companies WHERE user_id = ?', (session["user_id"],)).fetchone()
    conn.close()
    
    return render_template('company/profile.html', company=company)

@app.route('/company/drives')
@role_required('company')
def company_drives():
    conn = get_db()
    company = conn.execute('SELECT id FROM companies WHERE user_id = ?', (session["user_id"],)).fetchone()
    drives = conn.execute('''
        SELECT * FROM placement_drives WHERE company_id = ? ORDER BY created_at DESC
    ''', (company['id'],)).fetchall()
    conn.close()
    
    return render_template('company/drives.html', drives=drives)

@app.route('/company/drive/create', methods=['GET', 'POST'])
@role_required('company')
def create_drive():
    if request.method == 'POST':
        conn = get_db()
        company = conn.execute('SELECT id FROM companies WHERE user_id = ?', (session["user_id"],)).fetchone()
        
        job_title = request.form.get('job_title')
        description = request.form.get('description')
        eligibility_criteria = request.form.get('eligibility_criteria')
        min_cgpa = request.form.get('min_cgpa')
        salary_package = request.form.get('salary_package')
        deadline = request.form.get('deadline')
        
        conn.execute('''
            INSERT INTO placement_drives 
            (company_id, job_title, description, eligibility_criteria, min_cgpa, salary_package, deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (company['id'], job_title, description, eligibility_criteria, min_cgpa, salary_package, deadline))
        conn.commit()
        conn.close()
        
        flash('Placement drive created! Waiting for admin approval.', 'success')
        return redirect(url_for('company_drives'))
    
    return render_template('company/create_drive.html')

@app.route('/company/drive/edit/<int:drive_id>', methods=['GET', 'POST'])
@role_required('company')
def edit_drive(drive_id):
    conn = get_db()
    company = conn.execute('SELECT id FROM companies WHERE user_id = ?', (session["user_id"],)).fetchone()
    drive = conn.execute('SELECT * FROM placement_drives WHERE id = ? AND company_id = ?', 
                        (drive_id, company['id'])).fetchone()
    
    if not drive:
        flash('Drive not found or access denied.', 'danger')
        conn.close()
        return redirect(url_for('company_drives'))
    
    if request.method == 'POST':
        job_title = request.form.get('job_title')
        description = request.form.get('description')
        eligibility_criteria = request.form.get('eligibility_criteria')
        min_cgpa = request.form.get('min_cgpa')
        salary_package = request.form.get('salary_package')
        deadline = request.form.get('deadline')
        
        conn.execute('''
            UPDATE placement_drives 
            SET job_title = ?, description = ?, eligibility_criteria = ?, 
                min_cgpa = ?, salary_package = ?, deadline = ?
            WHERE id = ?
        ''', (job_title, description, eligibility_criteria, min_cgpa, salary_package, deadline, drive_id))
        conn.commit()
        conn.close()
        
        flash('Drive updated successfully!', 'success')
        return redirect(url_for('company_drives'))
    
    conn.close()
    return render_template('company/edit_drive.html', drive=drive)

@app.route('/company/drive/close/<int:drive_id>')
@role_required('company')
def close_drive(drive_id):
    conn = get_db()
    company = conn.execute('SELECT id FROM companies WHERE user_id = ?', (session["user_id"],)).fetchone()
    conn.execute('UPDATE placement_drives SET status = "closed" WHERE id = ? AND company_id = ?', 
                (drive_id, company['id']))
    conn.commit()
    conn.close()
    flash('Drive closed successfully!', 'success')
    return redirect(url_for('company_drives'))

@app.route('/company/drive/applicants/<int:drive_id>')
@role_required('company')
def drive_applicants(drive_id):
    conn = get_db()
    company = conn.execute('SELECT id FROM companies WHERE user_id = ?', (session["user_id"],)).fetchone()
    
    drive = conn.execute('SELECT * FROM placement_drives WHERE id = ? AND company_id = ?',
                        (drive_id, company['id'])).fetchone()
    
    if not drive:
        flash('Drive not found or access denied.', 'danger')
        conn.close()
        return redirect(url_for('company_drives'))
    
    applicants = conn.execute('''
        SELECT a.*, s.name, s.roll_number, s.department, s.cgpa, s.phone, s.resume_path
        FROM applications a
        JOIN students s ON a.student_id = s.id
        WHERE a.drive_id = ?
        ORDER BY a.application_date DESC
    ''', (drive_id,)).fetchall()
    
    conn.close()
    return render_template('company/applicants.html', drive=drive, applicants=applicants)

@app.route('/company/application/update/<int:app_id>/<status>')
@role_required('company')
def update_application_status(app_id, status):
    if status not in ['shortlisted', 'selected', 'rejected']:
        flash('Invalid status.', 'danger')
        return redirect(request.referrer)
    
    conn = get_db()
    conn.execute('UPDATE applications SET status = ? WHERE id = ?', (status, app_id))
    conn.commit()
    conn.close()
    
    flash(f'Application status updated to {status}!', 'success')
    return redirect(request.referrer)

# STUDENT ROUTES
@app.route('/student/dashboard')
@role_required('student')
def student_dashboard():
    conn = get_db()
    
    student = conn.execute('SELECT * FROM students WHERE user_id = ?', (session["user_id"],)).fetchone()
    
    total_applications = conn.execute('''
        SELECT COUNT(*) as count FROM applications WHERE student_id = ?
    ''', (student['id'],)).fetchone()['count']
    
    selected_count = conn.execute('''
        SELECT COUNT(*) as count FROM applications 
        WHERE student_id = ? AND status = 'selected'
    ''', (student['id'],)).fetchone()['count']
    
    shortlisted_count = conn.execute('''
        SELECT COUNT(*) as count FROM applications 
        WHERE student_id = ? AND status = 'shortlisted'
    ''', (student['id'],)).fetchone()['count']
    
    conn.close()
    
    return render_template('student/dashboard.html',
                         student=student,
                         total_applications=total_applications,
                         selected_count=selected_count,
                         shortlisted_count=shortlisted_count)

@app.route('/student/profile', methods=['GET', 'POST'])
@role_required('student')
def student_profile():
    conn = get_db()
    
    if request.method == 'POST':
        name = request.form.get('name')
        department = request.form.get('department')
        cgpa = request.form.get('cgpa')
        phone = request.form.get('phone')
        
        # Handle resume upload
        resume_path = None
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename:
                filename = secure_filename(str(session["user_id"]) + "_" + file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                resume_path = filename
        
        if resume_path:
            conn.execute('''
                UPDATE students SET name = ?, department = ?, cgpa = ?, phone = ?, resume_path = ?
                WHERE user_id = ?
            ''', (name, department, cgpa, phone, resume_path, session["user_id"]))
        else:
            conn.execute('''
                UPDATE students SET name = ?, department = ?, cgpa = ?, phone = ?
                WHERE user_id = ?
            ''', (name, department, cgpa, phone, session["user_id"]))
        
        conn.commit()
        flash('Profile updated successfully!', 'success')
    
    student = conn.execute('SELECT * FROM students WHERE user_id = ?', (session["user_id"],)).fetchone()
    conn.close()
    
    return render_template('student/profile.html', student=student)

@app.route('/student/drives')
@role_required('student')
def student_drives():
    conn = get_db()
    student = conn.execute('SELECT * FROM students WHERE user_id = ?', (session["user_id"],)).fetchone()
    
    drives = conn.execute('''
        SELECT pd.*, c.company_name,
               CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as has_applied
        FROM placement_drives pd
        JOIN companies c ON pd.company_id = c.id
        LEFT JOIN applications a ON pd.id = a.drive_id AND a.student_id = ?
        WHERE pd.status = 'approved' AND pd.deadline >= date('now')
        ORDER BY pd.deadline ASC
    ''', (student['id'],)).fetchall()
    
    conn.close()
    return render_template('student/drives.html', drives=drives, student=student)

@app.route('/student/apply/<int:drive_id>', methods=['POST'])
@role_required('student')
def apply_drive(drive_id):
    conn = get_db()
    student = conn.execute('SELECT * FROM students WHERE user_id = ?', (session["user_id"],)).fetchone()
    
    # Check if already applied
    existing = conn.execute('''
        SELECT * FROM applications WHERE student_id = ? AND drive_id = ?
    ''', (student['id'], drive_id)).fetchone()
    
    if existing:
        flash('You have already applied for this drive.', 'warning')
        conn.close()
        return redirect(url_for('student_drives'))
    
    # Check eligibility
    drive = conn.execute('SELECT * FROM placement_drives WHERE id = ?', (drive_id,)).fetchone()
    
    if drive['min_cgpa'] and student['cgpa'] and float(student['cgpa']) < float(drive['min_cgpa']):
        flash('You do not meet the minimum CGPA requirement.', 'danger')
        conn.close()
        return redirect(url_for('student_drives'))
    
    # Create application
    conn.execute('''
        INSERT INTO applications (student_id, drive_id) VALUES (?, ?)
    ''', (student['id'], drive_id))
    conn.commit()
    conn.close()
    
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student_drives'))

@app.route('/student/applications')
@role_required('student')
def student_applications():
    conn = get_db()
    student = conn.execute('SELECT * FROM students WHERE user_id = ?', (session["user_id"],)).fetchone()
    
    applications = conn.execute('''
        SELECT a.*, pd.job_title, pd.salary_package, c.company_name
        FROM applications a
        JOIN placement_drives pd ON a.drive_id = pd.id
        JOIN companies c ON pd.company_id = c.id
        WHERE a.student_id = ?
        ORDER BY a.application_date DESC
    ''', (student['id'],)).fetchall()
    
    conn.close()
    return render_template('student/applications.html', applications=applications)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
