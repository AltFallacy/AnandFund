import csv
from io import StringIO
from flask import Blueprint, render_template, redirect, url_for, request, flash, Response
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Project, Expense, Donation
from functools import wraps

main_bp = Blueprint('main', __name__)

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash('You do not have permission to access that page.', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@main_bp.route('/')
def index():
    # Landing page for everyone
    return render_template('index.html')

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

@main_bp.route('/admin/add_user', methods=['POST'])
@login_required
@role_required('Admin')
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'Donor')
    
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash('Username already exists.', 'error')
    else:
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('User created successfully.', 'success')
        
    return redirect(url_for('main.dashboard'))

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'Admin':
        projects = Project.query.all()
        # Admin overview totals
        total_budget = sum(p.allocated_budget for p in projects)
        total_expenses = sum(e.amount for e in Expense.query.all())
        total_donations = sum(d.amount for d in Donation.query.all())
        
        return render_template('admin/dashboard.html', 
                               projects=projects, 
                               total_budget=total_budget, 
                               total_expenses=total_expenses, 
                               total_donations=total_donations)
                               
    elif current_user.role == 'Staff':
        projects = Project.query.all()
        return render_template('staff/dashboard.html', projects=projects)
        
    else:
        # Donor dashboard
        projects = Project.query.all()
        donations = Donation.query.filter_by(user_id=current_user.id).all()
        return render_template('donor/dashboard.html', projects=projects, donations=donations)

# Admin: Manage Projects
@main_bp.route('/admin/projects', methods=['POST'])
@login_required
@role_required('Admin')
def add_project():
    name = request.form.get('name')
    description = request.form.get('description')
    budget = float(request.form.get('budget', 0))
    
    new_project = Project(name=name, description=description, allocated_budget=budget)
    db.session.add(new_project)
    db.session.commit()
    flash('Project added successfully.', 'success')
    return redirect(url_for('main.dashboard'))

# Staff: Manage Expenses
@main_bp.route('/staff/expenses', methods=['GET', 'POST'])
@login_required
@role_required('Staff')
def manage_expenses():
    if request.method == 'POST':
        title = request.form.get('title')
        amount = float(request.form.get('amount', 0))
        project_id = int(request.form.get('project_id'))
        
        new_expense = Expense(title=title, amount=amount, project_id=project_id, user_id=current_user.id)
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense added successfully.', 'success')
        return redirect(url_for('main.manage_expenses'))
        
    expenses = Expense.query.all()
    projects = Project.query.all()
    return render_template('staff/expenses.html', expenses=expenses, projects=projects)

@main_bp.route('/staff/expense/delete/<int:expense_id>')
@login_required
@role_required('Staff')
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted.', 'success')
    return redirect(url_for('main.manage_expenses'))

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
        flash('Thank you for your donation!', 'success')
        return redirect(url_for('main.index'))
        
    projects = Project.query.all()
    return render_template('donor/donate.html', projects=projects)

# Reports: Export CSV
@main_bp.route('/admin/reports/csv')
@login_required
@role_required('Admin')
def export_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Type', 'Date', 'Amount', 'Project', 'Entity'])
    
    expenses = Expense.query.all()
    for e in expenses:
        cw.writerow(['Expense', e.date.date(), e.amount, e.project.name, e.title])
        
    donations = Donation.query.all()
    for d in donations:
        cw.writerow(['Donation', d.date.date(), d.amount, d.project.name, d.donor_name])
        
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=financial_report.csv"}
    )
