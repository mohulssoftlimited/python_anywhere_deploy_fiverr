from app import app, db
from models import User

with app.app_context():
    # First show all users
    print("\nCurrent users in database:")
    users = User.query.all()
    for user in users:
        print(f"Email: {user.email}")

    # Then set admin
    print("\nSetting admin privileges...")
    user = User.query.filter_by(email='trevorhunter7392@gmail.com').first()
    if user:
        user.is_admin = True
        db.session.commit()
        print(f"Admin access granted to {user.email}")
    else:
        print("User not found. Please check email spelling")
