from flask import Flask, request, jsonify
from flask_migrate import Migrate
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token, get_jwt_identity
)
from flask_restful import Api
from datetime import datetime
from functools import wraps
import os
from flask_cors import CORS
from config import db
from models import User, Animal, CartItem, Order, OrderItem

app = Flask(__name__)
CORS(app,
     origins=[
         "http://localhost:3000",
         "https://farmart-frontend-6fhz.onrender.com"
     ],
     supports_credentials=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///farm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'super-secret-key'
app.secret_key = 'shhh-very-secret'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
migrate = Migrate(app, db)
api = Api(app)
jwt = JWTManager(app)

# Decorator for admin-only routes
def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or user.role != 'admin':
            return jsonify({'error': 'Admins only'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def home():
    return "these routes are working 💋"

@app.route('/register', methods=['POST'])
def signup():
    data = request.get_json()
    try:
        user = User(
            username=data['username'],
            email=data['email'],
            role=data['role']
        )
        user.password_hash = data['password']
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user and user.authenticate(data['password']):
        access_token = create_access_token(identity=user.id)
        return jsonify({"token": access_token, "user": user.to_dict()}), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict()), 200

@app.route('/animals', methods=['GET'])
def get_animals():
    animal_type = request.args.get('type')
    breed = request.args.get('breed')
    age = request.args.get('age')

    query = Animal.query
    if animal_type:
        query = query.filter_by(type=animal_type)
    if breed:
        query = query.filter_by(breed=breed)
    if age:
        query = query.filter(Animal.age == int(age))

    animals = query.all()
    return jsonify([a.to_dict() for a in animals]), 200

@app.route('/animals/<int:animal_id>', methods=['GET'])
def get_single_animal(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    return jsonify(animal.to_dict()), 200

@app.route('/animals/search', methods=['GET'])
def search_animals():
    q = request.args.get('q', '')
    animals = Animal.query.filter(
        Animal.type.ilike(f"%{q}%") | Animal.breed.ilike(f"%{q}%")
    ).all()
    return jsonify([a.to_dict() for a in animals]), 200

@app.route('/animals', methods=['POST'])
@jwt_required()
def create_animal():
    data = request.get_json()
    user_id = get_jwt_identity()
    animal = Animal(
        name=data['name'],
        type=data['type'],
        breed=data['breed'],
        price=data['price'],
        image=data.get('image'),
        farmer_id=user_id
    )
    db.session.add(animal)
    db.session.commit()
    return jsonify(animal.to_dict()), 201

@app.route('/animals/<int:id>', methods=['PATCH'])
@jwt_required()
def update_animal(id):
    data = request.get_json()
    animal = Animal.query.get_or_404(id)
    user_id = get_jwt_identity()
    if animal.farmer_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    for field in ['name', 'type', 'breed', 'price', 'image']:
        if field in data:
            setattr(animal, field, data[field])

    db.session.commit()
    return jsonify(animal.to_dict()), 200

@app.route('/animals/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_animal(id):
    animal = Animal.query.get_or_404(id)
    user_id = get_jwt_identity()
    if animal.farmer_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    db.session.delete(animal)
    db.session.commit()
    return jsonify({"message": "Animal deleted"}), 200

@app.route('/farmer/animals', methods=['GET'])
@jwt_required()
def farmer_animals():
    user_id = get_jwt_identity()
    animals = Animal.query.filter_by(farmer_id=user_id).all()
    return jsonify([a.to_dict() for a in animals]), 200

@app.route('/farmer/orders', methods=['GET'])
@jwt_required()
def farmer_orders():
    user_id = get_jwt_identity()
    orders = Order.query.join(OrderItem).join(Animal).filter(Animal.farmer_id == user_id).all()
    return jsonify([o.to_dict() for o in orders]), 200

@app.route('/orders/<int:order_id>/status', methods=['PATCH'])
@jwt_required()
def update_order_status(order_id):
    data = request.get_json()
    order = Order.query.get_or_404(order_id)
    order.status = data.get('status', order.status)
    db.session.commit()
    return jsonify(order.to_dict()), 200

@app.route('/cart', methods=['GET'])
@jwt_required()
def get_cart():
    user_id = get_jwt_identity()
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    return jsonify([item.to_dict() for item in cart_items]), 200

@app.route('/cart', methods=['POST'])
@jwt_required()
def add_to_cart():
    data = request.get_json()
    user_id = get_jwt_identity()
    item = CartItem(
        user_id=user_id,
        animal_id=data['animal_id'],
        quantity=data.get('quantity', 1)
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201

@app.route('/cart/<int:item_id>', methods=['DELETE'])
@jwt_required()
def remove_cart_item(item_id):
    item = CartItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Item removed from cart"}), 200

@app.route('/orders', methods=['GET'])
@jwt_required()
def get_orders():
    user_id = get_jwt_identity()
    orders = Order.query.filter_by(user_id=user_id).all()
    return jsonify([o.to_dict() for o in orders]), 200

@app.route('/orders', methods=['POST'])
@jwt_required()
def place_order():
    user_id = get_jwt_identity()
    cart_items = CartItem.query.filter_by(user_id=user_id).all()

    if not cart_items:
        return jsonify({"error": "Cart is empty"}), 400

    total_price = sum(item.animal.price * item.quantity for item in cart_items)
    order = Order(user_id=user_id, total_price=total_price)
    db.session.add(order)
    db.session.commit()

    for item in cart_items:
        order_item = OrderItem(
            order_id=order.id,
            animal_id=item.animal_id,
            quantity=item.quantity
        )
        db.session.add(order_item)
        db.session.delete(item)

    db.session.commit()
    return jsonify(order.to_dict()), 201


@app.route('/payment', methods=['POST'])
@jwt_required()
def process_payment():
    data = request.get_json()
    return jsonify({"message": "Payment processed", "data": data}), 200

@app.route('/users', methods=['GET'])
@admin_required
def list_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users]), 200

if __name__ == '__main__':
    app.run(port=5555, debug=True)
