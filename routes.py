import csv
import os
from io import StringIO
from flask import Blueprint, render_template, redirect, url_for, request, flash, Response, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Message
from models import db, User, Project, Expense, Donation
from functools import wraps
from datetime import datetime

main_bp = Blueprint('main', __name__)

def role_required(roles):
    if isinstance(roles, str):
        roles = [roles]
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash('You do not have permission to access that page.', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def send_email(subject, recipient, body_html):
    try:
        msg = Message(subject, recipients=[recipient])
        msg.html = body_html
        current_app.mail.send(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

@main_bp.route('/')
def index():
    # Fetch real-time totals for homepage
    total_donations = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    projects = Project.query.all()
    return render_template('index.html', total_donations=total_donations, projects=projects)

@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'Donor')
        email = request.form.get('email') # Added email field
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.', 'error')
        else:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username, password=hashed_password, role=role)
            db.session.add(new_user)
            db.session.commit()
            
            # Send Welcome Email
            if email:
                html = render_template('emails/welcome.html', username=username)
                send_email('Welcome to Anandvan', email, html)
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('main.login'))
            
    return render_template('register.html')

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Login unsuccessful. Please check your credentials.', 'error')
            
    return render_template('login.html')

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    projects = Project.query.all()
    if current_user.role == 'Admin':
        total_budget = sum(p.allocated_budget for p in projects)
        total_expenses = db.session.query(db.func.sum(Expense.amount)).scalar() or 0
        total_donations = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
        
        # Data for Chart.js
        project_names = [p.name for p in projects]
        project_budgets = [p.allocated_budget for p in projects]
        project_donations = [sum(d.amount for d in p.donations) for p in projects]
        project_expenses = [sum(e.amount for e in p.expenses) for p in projects]

        return render_template('admin/dashboard.html', 
                               projects=projects, 
                               total_budget=total_budget, 
                               total_expenses=total_expenses, 
                               total_donations=total_donations,
                               chart_data={
                                   'labels': project_names,
                                   'budgets': project_budgets,
                                   'donations': project_donations,
                                   'expenses': project_expenses
                               })
                               
    elif current_user.role == 'Staff':
        expenses = Expense.query.all()
        return render_template('staff/dashboard.html', projects=projects, expenses=expenses)
        
    else:
        # Donor dashboard
        donations = Donation.query.filter_by(user_id=current_user.id).all()
        user_total = sum(d.amount for d in donations)
        return render_template('donor/dashboard.html', projects=projects, donations=donations, user_total=user_total)

# Admin: Manage Projects
@main_bp.route('/admin/projects', methods=['POST'])
@login_required
@role_required('Admin')
def add_project():
    name = request.form.get('name')
    description = request.form.get('description')
    budget = float(request.form.get('budget', 0))
    
    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            upload_subdir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'projects')
            if not os.path.exists(upload_subdir):
                os.makedirs(upload_subdir)
            
            full_path = os.path.join(upload_subdir, filename)
            file.save(full_path)
            # Store path relative to 'static' for easy use in templates
            image_path = f"uploads/projects/{filename}"
    
    new_project = Project(name=name, description=description, allocated_budget=budget, image_path=image_path)
    db.session.add(new_project)
    db.session.commit()
    flash('Initiative added successfully.', 'success')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/admin/edit_project/<int:project_id>', methods=['POST'])
@login_required
@role_required('Admin')
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    project.name = request.form.get('name')
    project.description = request.form.get('description')
    project.allocated_budget = float(request.form.get('budget', 0))
    
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            # Delete old image if it exists
            if project.image_path:
                old_path = os.path.join(current_app.root_path, 'static', project.image_path)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception as e:
                        print(f"Error deleting old image: {e}")

            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            upload_subdir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'projects')
            if not os.path.exists(upload_subdir):
                os.makedirs(upload_subdir)
                
            full_path = os.path.join(upload_subdir, filename)
            file.save(full_path)
            project.image_path = f"uploads/projects/{filename}"
    
    db.session.commit()
    flash('Initiative updated successfully.', 'success')
    return redirect(url_for('main.dashboard'))

# Staff: Manage Expenses
@main_bp.route('/staff/expenses', methods=['GET', 'POST'])
@login_required
@role_required(['Staff', 'Admin'])
def manage_expenses():
    if request.method == 'POST':
        title = request.form.get('title')
        amount = float(request.form.get('amount', 0))
        project_id = int(request.form.get('project_id'))
        
        receipt_path = None
        if 'receipt' in request.files:
            file = request.files['receipt']
            if file and file.filename != '':
                filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                receipt_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(receipt_path)
                receipt_path = receipt_path.replace('\\', '/') # Ensure browser compatible path
        
        new_expense = Expense(title=title, amount=amount, project_id=project_id, user_id=current_user.id, receipt_path=receipt_path)
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense recorded with proof.', 'success')
        return redirect(url_for('main.manage_expenses'))
        
    expenses = Expense.query.all()
    projects = Project.query.all()
    return render_template('staff/expenses.html', expenses=expenses, projects=projects)

# Donor: Make Donation
@main_bp.route('/donate', methods=['GET', 'POST'])
def donate():
    if request.method == 'POST':
        donor_name = request.form.get('donor_name')
        email = request.form.get('email')
        amount = float(request.form.get('amount', 0))
        project_id = int(request.form.get('project_id'))
        
        user_id = current_user.id if current_user.is_authenticated else None
        
        new_donation = Donation(donor_name=donor_name, email=email, amount=amount, project_id=project_id, user_id=user_id)
        db.session.add(new_donation)
        db.session.commit()
        
        # Send Confirmation Emails
        confirm_html = render_template('emails/donation_receipt.html', name=donor_name, amount=amount, project=Project.query.get(project_id).name, datetime=datetime)
        send_email('Donation Confirmation - Anandvan', email, confirm_html)
        
        # Notify Admin
        admin_email = current_app.config['MAIL_USERNAME']
        admin_html = f"<h2>New Donation Received</h2><p><strong>Donor:</strong> {donor_name}</p><p><strong>Amount:</strong> ₹{amount}</p><p><strong>Initiative:</strong> {Project.query.get(project_id).name}</p>"
        send_email('Alert: New Donation Recorded', admin_email, admin_html)
        
        flash('Thank you for your generous donation! A receipt has been sent to your email.', 'success')
        return redirect(url_for('main.index'))
        
    projects = Project.query.all()
    return render_template('donor/donate.html', projects=projects)

# API: Real-time Data
@main_bp.route('/api/totals')
def get_totals():
    total_donations = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount)).scalar() or 0
    return jsonify({
        'total_donations': float(total_donations),
        'total_expenses': float(total_expenses),
        'balance': float(total_donations - total_expenses)
    })

@main_bp.route('/transparency')
def transparency():
    projects = Project.query.all()
    expenses = Expense.query.order_by(Expense.date.desc()).all()
    return render_template('transparency.html', projects=projects, expenses=expenses)

# Reports: Export CSV
@main_bp.route('/admin/reports/csv')
@login_required
@role_required('Admin')
def export_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Type', 'Date', 'Amount', 'Project', 'Entity', 'Receipt'])
    
    expenses = Expense.query.all()
    for e in expenses:
        cw.writerow(['Expense', e.date.date(), e.amount, e.project.name, e.title, e.receipt_path])
        
    donations = Donation.query.all()
    for d in donations:
        cw.writerow(['Donation', d.date.date(), d.amount, d.project.name, d.donor_name, 'N/A'])
        
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=financial_report.csv"}
    )
