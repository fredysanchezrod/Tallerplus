# create_db.py
from app import db, app
from werkzeug.security import generate_password_hash
from app import User  # si tu User está en app.py; ajusta si está en otro módulo

with app.app_context():
    db.create_all()
    # Crear admin si no existe
    if not User.query.filter_by(email="admin@tallerplus.com").first():
        admin = User(email="admin@tallerplus.com", password_hash=generate_password_hash("Admin123"))
        db.session.add(admin)
        db.session.commit()
        print("Admin created")
    else:
        print("Admin ya existe")
