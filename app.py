# app.py - TallerPlus API + UI
import os
import sys
import datetime
import re
from flask import Flask, request, render_template, redirect
from flask_restx import Api, Resource, fields
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from werkzeug.security import generate_password_hash, check_password_hash
from faker import Faker
from dotenv import load_dotenv
from flask_cors import CORS
from sqlalchemy import or_

# -----------------------------
# CONFIGURACIÓN BÁSICA
# -----------------------------
load_dotenv()

app = Flask(__name__, template_folder="templates")
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "cambia_este_secreto_localmente")
app.config["RESTX_MASK_SWAGGER"] = False

db = SQLAlchemy(app)
jwt = JWTManager(app)
api = Api(app, version="1.0", title="TallerPlus API", doc="/docs")

# -----------------------------
# VALIDACIÓN DE EMAIL
# -----------------------------
def is_valid_email(email):
    if not email:
        return True  # Email es opcional
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

# -----------------------------
# MODELOS DE BASE DE DATOS
# -----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(80), unique=False)
    telefono = db.Column(db.String(50), unique=False)
    email = db.Column(db.String(150))
    direccion = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "documento": self.documento,
            "telefono": self.telefono,
            "email": self.email,
            "direccion": self.direccion,
            "created_at": self.created_at.isoformat()
        }

# -----------------------------
# MODELOS DE API (Swagger)
# -----------------------------
auth_model = api.model("Login", {
    "email": fields.String(required=True, example="admin@tallerplus.com"),
    "password": fields.String(required=True, example="Admin123")
})

client_model = api.model("Client", {
    "nombre": fields.String(required=True),
    "documento": fields.String(),
    "telefono": fields.String(),
    "email": fields.String(),
    "direccion": fields.String()
})

# -----------------------------
# NAMESPACES
# -----------------------------
ns_auth = api.namespace("auth", description="Autenticación")
ns_clients = api.namespace("clients", description="Gestión de clientes")

# -----------------------------
# ENDPOINTS DE AUTENTICACIÓN
# -----------------------------
@ns_auth.route("/login")
class Login(Resource):
    @ns_auth.expect(auth_model, validate=True)
    def post(self):
        data = api.payload
        email = data.get("email")
        password = data.get("password")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return {"message": "Credenciales inválidas"}, 401
        token = create_access_token(identity=str(user.id), expires_delta=datetime.timedelta(hours=8))
        return {"access_token": token, "user": {"id": user.id, "email": user.email}}

# -----------------------------
# ENDPOINTS DE CLIENTES
# -----------------------------
@ns_clients.route("")
class ClientList(Resource):
    @jwt_required()
    def get(self):
        search = request.args.get("search", "").strip()
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        query = Client.query
        if search:
            like = f"%{search}%"
            query = query.filter(
                or_(
                    Client.nombre.ilike(like),
                    Client.documento.ilike(like),
                    Client.telefono.ilike(like)
                )
            )
        total = query.count()
        clients = query.order_by(Client.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size, "items": [c.to_dict() for c in clients]}

    @ns_clients.expect(client_model, validate=True)
    @jwt_required()
    def post(self):
        data = api.payload
        nombre = data.get("nombre", "").strip()
        documento = data.get("documento", "").strip()
        telefono = data.get("telefono", "").strip()
        email = data.get("email", "").strip()

        # Validaciones
        if not nombre:
            return {"message": "El nombre es obligatorio"}, 400
        if not documento and not telefono:
            return {"message": "Debe ingresar al menos un documento o teléfono"}, 400
        if email and not is_valid_email(email):
            return {"message": "Correo electrónico inválido"}, 400
        if documento and Client.query.filter_by(documento=documento).first():
            return {"message": "Documento ya registrado"}, 400
        if telefono and Client.query.filter_by(telefono=telefono).first():
            return {"message": "Teléfono ya registrado"}, 400

        c = Client(
            nombre=nombre,
            documento=documento,
            telefono=telefono,
            email=email,
            direccion=data.get("direccion")
        )
        db.session.add(c)
        db.session.commit()
        return c.to_dict(), 201


@ns_clients.route("/<int:id>")
class ClientItem(Resource):
    @jwt_required()
    def get(self, id):
        c = Client.query.get_or_404(id)
        return c.to_dict()

    @ns_clients.expect(client_model, validate=True)
    @jwt_required()
    def put(self, id):
        c = Client.query.get_or_404(id)
        data = api.payload
        nombre = data.get("nombre", c.nombre).strip()
        documento = data.get("documento", c.documento).strip() if data.get("documento") is not None else c.documento
        telefono = data.get("telefono", c.telefono).strip() if data.get("telefono") is not None else c.telefono
        email = data.get("email", c.email).strip() if data.get("email") is not None else c.email

        # Validaciones
        if not nombre:
            return {"message": "El nombre es obligatorio"}, 400
        if not documento and not telefono:
            return {"message": "Debe ingresar al menos un documento o teléfono"}, 400
        if email and not is_valid_email(email):
            return {"message": "Correo electrónico inválido"}, 400
        if documento and Client.query.filter(Client.documento == documento, Client.id != id).first():
            return {"message": "Documento ya registrado"}, 400
        if telefono and Client.query.filter(Client.telefono == telefono, Client.id != id).first():
            return {"message": "Teléfono ya registrado"}, 400

        c.nombre = nombre
        c.documento = documento
        c.telefono = telefono
        c.email = email
        c.direccion = data.get("direccion", c.direccion)
        db.session.commit()
        return c.to_dict()

    @jwt_required()
    def delete(self, id):
        c = Client.query.get_or_404(id)
        db.session.delete(c)
        db.session.commit()
        return {"message": "Eliminado"}, 204

# -----------------------------
# RUTAS HTML
# -----------------------------
@app.route("/")
def index():
    return redirect("/login")

@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@app.route("/app/clients", methods=["GET"])
def clients_page():
    return render_template("clients.html")

# -----------------------------
# SEED DB
# -----------------------------
def seed_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email="admin@tallerplus.com").first():
            admin = User(
                email="admin@tallerplus.com",
                password_hash=generate_password_hash("Admin123")
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuario admin creado: admin@tallerplus.com / Admin123")
        fake = Faker("es_CO")
        if Client.query.count() == 0:
            for _ in range(20):
                c = Client(
                    nombre=fake.name(),
                    documento=fake.bothify(text="##????###"),
                    telefono=fake.phone_number(),
                    email=fake.safe_email(),
                    direccion=fake.address().replace("\n", ", ")
                )
                db.session.add(c)
            db.session.commit()
            print("✅ 20 clientes falsos añadidos.")
        print("🎉 Seed completado.")

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        seed_db()
        sys.exit(0)

    with app.app_context():
        db.create_all()
    print("🚀 Servidor ejecutándose en http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
