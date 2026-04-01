import sys
import os
sys.path.append(os.getcwd())

from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.utils.security import hash_password

def seed_users():
    # Ensure tables exist
    print("Creating tables in MySQL...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        users_to_create = [
            {
                "username": "admin",
                "email": "admin@examinal.com",
                "password": "admin123",
                "full_name": "System Administrator",
                "role": "admin"
            },
            {
                "username": "instructor1",
                "email": "instructor1@examinal.com",
                "password": "instructor123",
                "full_name": "Exam Instructor",
                "role": "instructor"
            }
        ]

        for u in users_to_create:
            existing = db.query(User).filter(User.username == u["username"]).first()
            if not existing:
                user = User(
                    username=u["username"],
                    email=u["email"],
                    hashed_password=hash_password(u["password"]),
                    full_name=u["full_name"],
                    role=u["role"],
                    is_active=True
                )
                db.add(user)
                print(f"Created user: {u['username']} (Password: {u['password']})")
            else:
                print(f"User {u['username']} already exists.")
        
        db.commit()
    except Exception as e:
        print(f"Error seeding users: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_users()
