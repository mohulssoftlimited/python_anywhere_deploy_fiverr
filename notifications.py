from flask_mail import Mail, Message
import traceback
from datetime import datetime
import pytz

def init_mail(app):
    print("Initializing S.W.A.R.M. mail system:")
    app.config['MAIL_SERVER'] = 'fdm.ooo'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'swarm@fdm.ooo'
    app.config['MAIL_PASSWORD'] = 'Liz8283957392$'
    app.config['MAIL_DEBUG'] = False
    app.config['MAIL_SUPPRESS_SEND'] = False
    
    print(f"Mail configuration complete")
    
    try:
        mail = Mail(app)
        print("S.W.A.R.M. mail system initialized successfully")
        return mail
    except Exception as e:
        print(f"Error initializing mail system: {str(e)}")
        print(traceback.format_exc())
        raise

def send_status_alert(mail, user_email, url, status_type, status):
    print(f"\nAttempting to send email alert:")
    print(f"To: {user_email}")
    print(f"About: {url}")
    print(f"Status: {status_type} - {status}")
    
    subject = f"S.W.A.R.M. Monitor Alert: {url} is {status}"
    body = f"""
    S.W.A.R.M. Monitoring Alert
    -------------------------
    
    URL: {url}
    Status Change: {status_type} is now {status}
    Time: {datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d %H:%M:%S %Z')}
    
    Action Required:
    - Please check the URL availability
    - Login to your S.W.A.R.M. dashboard for more details
    - Take necessary actions to resolve any issues
    
    --
    S.W.A.R.M. Monitoring System
    https://swarm.fdm.ooo
    """
    
    try:
        msg = Message(
            subject=subject,
            sender='swarm@fdm.ooo',
            recipients=[user_email],
            body=body
        )
        print("Message created, attempting to send...")
        mail.send(msg)
        print(f"Successfully sent alert to {user_email} for {url}")
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        print("Full error:")
        print(traceback.format_exc())
        return False
