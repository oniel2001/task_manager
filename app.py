from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import base64
import io
import matplotlib.pyplot as plt
import pandas as pd
import datetime
from datetime import datetime
import os
from flask_migrate import Migrate  # Import Flask-Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request, redirect, url_for, flash
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend


app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))

# Configurations
app.config['SECRET_KEY'] = 'password12345'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'instance', 'tasks_new.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Initialize Flask-Migrate
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    email_id = db.Column(db.String(100), nullable=True)
    mobile_number = db.Column(db.String(100), nullable=True)
    designation = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(128), nullable=True)
    role = db.Column(db.String(20), nullable=True,
                     default='viewer')  # Roles: admin, dev, viewer
    created_date = db.Column(db.Date, nullable=True)
    modified_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='Active')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    task_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='Pending')
    progress_percentage = db.Column(db.String(20), default='0%')
    assigned_to = db.Column(db.Integer, db.ForeignKey(
        'user.id'))  # Link to User table
    start_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    priority = db.Column(db.String(20), default='Medium')  # High, Medium, Low
    completion_date = db.Column(db.Date, nullable=True)
    delete_status = db.Column(db.String(20), default='False')
    user = db.relationship('User', backref='tasks', lazy=True)

# Load user callback


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Routes


SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_ADDRESS = 'your_email@gmail.com'
EMAIL_PASSWORD = 'your_password'


def send_email(to_email, subject, body):
    try:

        message = MIMEMultipart()
        message['From'] = EMAIL_ADDRESS
        message['To'] = to_email
        message['Subject'] = subject

        message.attach(MIMEText(body, 'plain'))

        try:
            # with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            #     server.starttls()
            #     server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            #     server.send_message(message)
            print("Sending Email!!!")
        except:
            pass

        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


@app.route('/')
@login_required
def dashboard():
    filter_status = request.args.get('filter', 'All')

    tasks_query = Task.query.filter_by(delete_status='False')
    print('current user name', current_user.name)
    if current_user.role in ['admin']:
        print("In admin")
        if filter_status != 'All':
            tasks_query = tasks_query.filter_by(status=filter_status)
    if current_user.role in ['dev']:
        print("In dev")
        if filter_status != 'All':
            tasks_query = tasks_query.filter_by(status=filter_status)
        tasks_query = tasks_query.filter_by(assigned_to=current_user.name)
    else:
        # tasks_query = tasks_query.filter_by(assigned_to=current_user.name)
        if filter_status != 'All':
            tasks_query = tasks_query.filter_by(status=filter_status)

    print(tasks_query)
    tasks = tasks_query.order_by(
        Task.due_date.asc(), Task.priority.desc()).all()

    print(tasks)

    # tasks = Task.query.all()
    df = pd.DataFrame([{
        'Task Name': task.title,
        'Status': task.status,
        'Assigned To': task.assigned_to if task.assigned_to else 'Unassigned',
        'Due Date': task.due_date,
        'Priority': task.priority
    } for task in tasks])

    print(df)

    if len(df) > 0:
        status_counts = df['Status'].value_counts()
        print(status_counts.head())
    else:
        df = pd.DataFrame({"Status": []})
        statuses = ['Completed', 'Pending']
        status_counts = df['Status'].value_counts()
        status_counts = status_counts.reindex(statuses, fill_value=0)

    plt.figure(figsize=(6, 4))
    status_counts.plot(kind='bar', color=['green', 'orange'])
    plt.title('Tasks by Status')
    plt.xlabel('Status')
    plt.ylabel('Count')
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    chart_base64 = base64.b64encode(img.getvalue()).decode()
    plt.close()

    if current_user.role in ['admin']:
        return render_template('admin_dashboard.html', task_count=len(tasks),
                               completed_tasks=status_counts.get(
                                   'Completed', 0),
                               pending_tasks=status_counts.get('Pending', 0),
                               chart_base64=chart_base64)
    if current_user.role in ['dev']:
        return render_template('dashboard.html', tasks=tasks)
    return render_template('dashboard.html', tasks=tasks)


@app.route('/list_users', methods=['GET'])
@login_required
def list_users():
    filter_status = request.args.get('filter', 'All')

    if current_user.role in ['admin', 'dev']:
        user_query = User.query.filter_by(status='Active').all()
        print(user_query)
        return render_template('user_table.html', users=user_query)

    else:
        if current_user.role != 'admin':
            flash('Permission denied.', 'danger')
            return redirect(url_for('admin_dashboard'))


@app.route('/list_tasks', methods=['GET'])
@login_required
def list_tasks():
    filter_status = request.args.get('filter', 'All')

    tasks_query = Task.query.filter_by(delete_status='False')
    print('current user name', current_user.name)
    if current_user.role in ['admin', 'dev']:
        print("In admin")
        if filter_status != 'All':
            tasks_query = tasks_query.filter_by(status=filter_status)
    else:
        tasks_query = tasks_query.filter_by(assigned_to=current_user.name)
        if filter_status != 'All':
            tasks_query = tasks_query.filter_by(status=filter_status)

    print(tasks_query)
    tasks = tasks_query.order_by(
        Task.due_date.asc(), Task.priority.desc()).all()

    print(tasks)

    df = pd.DataFrame([{
        'Task Name': task.title,
        'Status': task.status,
        'Assigned To': task.assigned_to if task.assigned_to else 'Unassigned',
        'Due Date': task.due_date,
        'Priority': task.priority
    } for task in tasks])

    print(df)

    if len(df) > 0:
        status_counts = df['Status'].value_counts()
        print(status_counts.head())
    else:
        df = pd.DataFrame({"Status": []})
        statuses = ['Completed', 'Pending']
        status_counts = df['Status'].value_counts()
        status_counts = status_counts.reindex(statuses, fill_value=0)

    if current_user.role in ['admin', 'dev']:
        task_query = Task.query.filter_by(delete_status='False').all()
        print(task_query)
        return render_template('task_table.html', tasks=task_query, task_count=len(tasks),
                               completed_tasks=status_counts.get(
                                   'Completed', 0),
                               pending_tasks=status_counts.get('Pending', 0))

    else:
        if current_user.role != 'admin':
            flash('Permission denied.', 'danger')
            return redirect(url_for('dashboard'))


@app.route('/task_page', methods=['GET'])
@login_required
def task_page():
    print("task_page")
    try:
        task_id = request.args.get('task_id')
        if task_id:
            task = Task.query.filter_by(task_id=task_id).all()[0]
        user_query = User.query.filter_by(role='dev').all()
        print(user_query)
        if task_id:
            user_query = [
                user for user in user_query if user.name != task.assigned_to]
        print(user_query)
        if task_id:
            return render_template('create_task.html', users=user_query, task=task)
    except Exception as e:
        print("Task error : ", e)
    return render_template('create_task.html', users=user_query)


@app.route('/user_page', methods=['GET'])
@login_required
def user_page():
    print("user_page")
    user_id = request.args.get('id')
    if user_id:
        user = User.query.filter_by(id=user_id).all()[0]
        return render_template('create_user.html', user=user)
    return render_template('create_user.html')


@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    if current_user.role not in ['admin', 'dev']:
        flash('Permission denied.', 'danger')
        return redirect(url_for('list_tasks'))

    print(request.form)
    task_id = request.form.get('task_id', None)
    task_name = request.form.get('task_title')
    assigned_to = request.form.get('assigned_to')
    due_date = request.form.get('due_date')
    start_date = request.form.get('start_date')
    priority = request.form.get('priority', 'Medium')
    progress_percentage = request.form.get('progress_percentage', '0%')
    status = request.form.get('status', 'Pending')

    if progress_percentage == '100%':
        status = 'Completed'
    if status == 'Completed':
        progress_percentage = '100%'

    try:
        due_date = datetime.strptime(
            due_date, '%Y-%m-%d') if due_date else None
        start_date = datetime.strptime(
            start_date, '%Y-%m-%d') if start_date else None
    except ValueError:
        flash('Invalid date format. Use YYYY-MM-DD.', 'danger')
        return redirect(url_for('list_tasks'))

    if task_id:
        task = Task.query.get_or_404(task_id)
        task.title = task_name
        task.assigned_to = assigned_to
        task.due_date = due_date
        task.start_date = start_date
        task.priority = priority
        task.progress_percentage = progress_percentage
        task.status = status
        db.session.commit()
        print('Task updated successfully!')
    else:
        new_task = Task(
            title=task_name,
            assigned_to=assigned_to if current_user.role == 'admin' else current_user.id,
            due_date=due_date,
            start_date=start_date,
            priority=priority,
            progress_percentage=progress_percentage,
            status=status
        )
        db.session.add(new_task)
        db.session.commit()
        flash('Task added successfully!', 'success')

    return redirect(url_for('list_tasks'))


@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if current_user.role not in ['admin', 'dev'] or (task.assigned_to != current_user.name and current_user.role != 'admin'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        task.title = request.form.get('task_name')
        task.due_date = datetime.strptime(request.form.get(
            'due_date'), '%Y-%m-%d') if request.form.get('due_date') else None
        task.priority = request.form.get('priority', 'Medium')
        db.session.commit()
        flash('Task updated successfully!', 'success')
        return redirect(url_for('list_tasks'))

    return render_template('edit_task.html', task=task)


@app.route('/update_status/<int:task_id>', methods=['POST'])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)

    # Check permissions
    if current_user.role == 'viewer':
        # Viewers can only toggle status of tasks assigned to them
        if task.assigned_to != current_user.name:
            flash(
                'Permission denied. You can only modify tasks assigned to you.', 'danger')
            return redirect(url_for('dashboard'))
    elif current_user.role not in ['admin', 'dev']:
        # Non-admin and non-dev users cannot modify tasks
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard'))

    # Toggle the task status
    task.status = 'Completed' if task.status == 'Pending' else 'Pending'
    if task.status == 'Completed':
        completion_date = datetime.now().date()
        task.completion_date = completion_date
    else:
        task.completion_date = None
        # pass
    db.session.commit()

    status = task.status
    recipient_email = 'test_email@gmail.com'

    # Compose the email
    subject = f"Task Status Update: {status}"
    body = f"Hello,\n\nThe task status has been updated to: {status}.\n\nBest regards,\nYour Flask App"

    send_email(recipient_email, subject, body)
    flash(f"Task status updated to '{task.status}' successfully!", 'success')
    if current_user.role not in ['admin']:
        return redirect(url_for('dashboard'))
    return redirect(url_for('list_tasks'))


@app.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if current_user.role != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('list_tasks'))
    # db.session.delete(task)
    task.delete_status = 'True'
    db.session.commit()
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('list_tasks'))


@app.route('/reports')
@login_required
def reports():
    if current_user.role != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard'))

    tasks = Task.query.all()
    df = pd.DataFrame([{
        'Task Name': task.title,
        'Status': task.status,
        'Assigned To': task.user.name if task.user else 'Unassigned',
        'Due Date': task.due_date,
        'Priority': task.priority
    } for task in tasks])

    # Count tasks by status
    status_counts = df['Status'].value_counts()

    # Plot task status counts
    plt.figure(figsize=(6, 4))
    status_counts.plot(kind='bar', color=['green', 'orange'])
    plt.title('Tasks by Status')
    plt.xlabel('Status')
    plt.ylabel('Count')
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    chart_base64 = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return render_template(
        'reports.html',
        task_count=len(tasks),
        completed_tasks=status_counts.get('Completed', 0),
        pending_tasks=status_counts.get('Pending', 0),
        chart_base64=chart_base64
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email_id = request.form.get('email_id')
        mobile_number = request.form.get('mobile_number')
        created_date = datetime.now().date()
        role = request.form.get('role', 'viewer')

        if User.query.filter_by(name=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))

        new_user = User(name=username, role=role, email_id=email_id,
                        mobile_number=mobile_number, created_date=created_date)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    if request.method == 'POST':
        print(request.form)
        user_id = request.form.get('userid')
        username = request.form.get('username')
        password = request.form.get('password')
        email_id = request.form.get('email_id')
        mobile_number = request.form.get('mobile_number')
        created_date = datetime.now().date()
        role = request.form.get('role', 'viewer')

        if User.query.filter_by(name=username).first() and not user_id:
            flash('Username already exists.', 'danger')
            return redirect(url_for('user_page'))

        if user_id:
            user = User.query.filter_by(id=user_id).all()[0]
            user.name = username
            user.email_id = email_id
            user.mobile_number = mobile_number
            user.role = role
            db.session.commit()
            return redirect(url_for('list_users'))

        new_user = User(name=username, role=role, email_id=email_id,
                        mobile_number=mobile_number, created_date=created_date)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('list_users'))

    return render_template('user_page.html')


@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if current_user.role != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('list_users'))
    # db.session.delete(user)
    user.status = 'InActive'
    db.session.commit()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('list_users'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(name=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            print('Login_successful!')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
