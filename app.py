from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from monitor import is_site_up, is_ssl_valid
from extensions import db
from models import URLMonitor, User
from forms import RegistrationForm, LoginForm
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import requests
from sqlalchemy.exc import IntegrityError
import os
import pytz
from apscheduler.executors.pool import ThreadPoolExecutor
from flask_mail import Mail
from notifications import init_mail, send_status_alert
import traceback
from functools import wraps
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    filename='swarm.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger('swarm')

app = Flask(__name__, 
           instance_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance'))
app.config['SECRET_KEY'] = '009bf8e5b42000c5158acc59e2482605'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)  # Session timeout after 60 minutes
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Protect against XSS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

mail = init_mail(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            hashed_password = generate_password_hash(form.password.data)
            user = User(
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                email=form.email.data,
                phone=form.phone.data,
                city=form.city.data,
                state=form.state.data.upper(),  # Store state in uppercase
                password=hashed_password
            )
            db.session.add(user)
            db.session.commit()
            flash('Your S.W.A.R.M. account has been created! You can now log in.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('That email is already registered. Please choose a different one.', 'danger')
        except Exception as e:
            db.session.rollback()
            print(f"Error: {str(e)}")
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            logger.info(f"Successful login for user: {user.email}")
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            logger.warning(f"Failed login attempt for email: {form.email.data}")
            flash('Login unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/users')
def list_users():
    users = User.query.all()
    return '<br>'.join([f"{user.first_name} {user.last_name} - {user.email}" for user in users])

@app.route('/dashboard')
@login_required
def dashboard():
    monitors = URLMonitor.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', monitors=monitors)

@app.route('/add_url', methods=['POST'])
@login_required
def add_url():
    url = request.form.get('url')
    logger.info(f"User {current_user.email} attempting to add URL: {url}")
    
    if URLMonitor.query.filter_by(user_id=current_user.id).count() >= 10:
        logger.warning(f"User {current_user.email} exceeded URL limit")
        flash('You can only monitor up to 10 URLs.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        # Ensure URL starts with https://
        if not url.startswith('http'):
            url = 'https://' + url
        elif not url.startswith('https://'):
            url = 'https://' + url[7:]  # Remove http:// if present
            
        print(f"Formatted URL: {url}")
        
        print(f"Checking initial status for {url}")
        site_status = "Online" if is_site_up(url) else "Offline"
        ssl_status = "Valid" if is_ssl_valid(url) else "Invalid"
        print(f"Initial status - Site: {site_status}, SSL: {ssl_status}")
        
        eastern = pytz.timezone('America/New_York')
        new_monitor = URLMonitor(
            url=url, 
            site_status=site_status,
            ssl_status=ssl_status,
            last_checked=datetime.now(eastern),  # Set initial check time
            user_id=current_user.id
        )
        
        # Send alert if the site is offline when added
        if site_status == "Offline":
            print(f"New URL {url} is offline - sending alert...")
            send_status_alert(mail, 'swarm@fdm.ooo', url, "Site Status", "Offline")
        if ssl_status == "Invalid":
            print(f"New URL {url} has invalid SSL - sending alert...")
            send_status_alert(mail, 'swarm@fdm.ooo', url, "SSL Status", "Invalid")
            
        db.session.add(new_monitor)
        db.session.commit()
        flash('URL added for monitoring!', 'success')
    except Exception as e:
        print(f"Error adding URL: {str(e)}")
        print(traceback.format_exc())
        db.session.rollback()
        flash('Error adding URL. Please try again.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/static/<path:filename>')
def custom_static(filename):
    print(f"Attempting to serve: {filename}")
    return send_from_directory('static', filename)

print(f"Static folder path: {app.static_folder}")

def check_url_status():
    with app.app_context():
        logger.info("Starting URL status check")
        monitors = URLMonitor.query.all()
        for monitor in monitors:
            try:
                logger.info(f"Checking {monitor.url}")
                
                # Check both site and SSL status
                new_site_status = "Online" if is_site_up(monitor.url) else "Offline"
                new_ssl_status = "Valid" if is_ssl_valid(monitor.url) else "Invalid"
                
                print(f"S.W.A.R.M. Status - Site: {new_site_status}, SSL: {new_ssl_status}")
                
                # Send alerts for any detected issues
                if new_site_status == "Offline":
                    print(f"S.W.A.R.M. Alert: Site is offline - sending notification...")
                    send_status_alert(mail, 'swarm@fdm.ooo', monitor.url, "Site Status", "Offline")
                
                if new_ssl_status == "Invalid":
                    print(f"S.W.A.R.M. Alert: SSL is invalid - sending notification...")
                    send_status_alert(mail, 'swarm@fdm.ooo', monitor.url, "SSL Status", "Invalid")
                
                # Update database
                monitor.site_status = new_site_status
                monitor.ssl_status = new_ssl_status
                eastern = pytz.timezone('America/New_York')
                monitor.last_checked = datetime.now(eastern)
                db.session.commit()
                print(f"Updated {monitor.url}: Site: {monitor.site_status}, SSL: {monitor.ssl_status}")
            except Exception as e:
                logger.error(f"Error checking {monitor.url}: {str(e)}")
                print(traceback.format_exc())

# Initialize scheduler but don't start it yet
scheduler = BackgroundScheduler(
    timezone='America/New_York',
    executors={'default': ThreadPoolExecutor(1)},
    job_defaults={
        'coalesce': False,
        'max_instances': 1
    }
)
scheduler.add_job(
    func=check_url_status, 
    trigger="interval", 
    seconds=600,  # Changed from 300 to 600 (10 minutes)
    next_run_time=datetime.now(),
    id='url_status_checker',
    replace_existing=True
)

def init_db(app):
    with app.app_context():
        # Ensure instance folder exists
        os.makedirs(app.instance_path, exist_ok=True)
        
        # Check if database exists
        db_path = os.path.join(app.instance_path, 'site.db')
        db_exists = os.path.exists(db_path)
        
        # Only create tables if database doesn't exist
        if not db_exists:
            print("Creating new database...")
            db.create_all()
            print("Database created successfully!")
        else:
            print("Database already exists, skipping creation")

@app.route('/delete_url/<int:monitor_id>', methods=['POST'])
@login_required
def delete_url(monitor_id):
    monitor = URLMonitor.query.get_or_404(monitor_id)
    
    # Check if the URL belongs to the current user
    if monitor.user_id != current_user.id:
        flash('You do not have permission to delete this URL.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        db.session.delete(monitor)
        db.session.commit()
        flash('URL has been removed from monitoring.', 'success')
    except Exception as e:
        print(f"Error deleting URL: {str(e)}")
        db.session.rollback()
        flash('Error removing URL. Please try again.', 'danger')
    
    return redirect(url_for('dashboard'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    total_urls = URLMonitor.query.count()
    return render_template('admin_dashboard.html', 
                         users=users,
                         total_urls=total_urls)

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Initialize database without dropping
    init_db(app)
    
    # Start scheduler only once
    try:
        scheduler.start()
        print("S.W.A.R.M. Scheduler started!")
    except Exception as e:
        print(f"Error starting scheduler: {e}")
    
    # Run Flask app
    app.run(debug=True)
