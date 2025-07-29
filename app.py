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
         "http://localhost:5173",
         "https://farmart-frontend-6fhz.onrender.com"
     ],
     supports_credentials=True)


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///farm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'super-secret-key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


db.init_app(app)
migrate = Migrate(app, db)
api = Api(app)
jwt = JWTManager(app)


def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        if user.role != 'admin':
            return jsonify({
                'error': 'Admins only',
                'user_role': user.role,
                'expected_role': 'admin'
            }), 403
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def home():
    return "these routes are working !"

# Auth Routes
@app.route('/register', methods=['POST'])
def register():
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
        return jsonify({'error': str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user and user.authenticate(data['password']):
        access_token = create_access_token(identity=user.id)
        return jsonify({
            'user': user.to_dict(),
            'access_token': access_token
        }), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return jsonify(user.to_dict()), 200


# Animal Routes
@app.route('/animals', methods=['GET'])
def get_animals():
    animals = Animal.query.all()
    return jsonify([a.to_dict() for a in animals]), 200

@app.route('/animals/<int:animal_id>', methods=['GET'])
def get_animal(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    return jsonify(animal.to_dict()), 200

@app.route('/animals', methods=['POST'])
@jwt_required()
def create_animal():
    user_id = get_jwt_identity()
    data = request.get_json()
    try:
        animal = Animal(
            name=data['name'],
            type=data['type'],
            breed=data['breed'],
            price=data['price'],
            image=data.get('image', ''),
            farmer_id=user_id
        )
        db.session.add(animal)
        db.session.commit()
        return jsonify(animal.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/animals/<int:animal_id>', methods=['PATCH'])
@jwt_required()
def update_animal(animal_id):
    user_id = get_jwt_identity()
    animal = Animal.query.get_or_404(animal_id)
    if animal.farmer_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    for key in data:
        setattr(animal, key, data[key])
    db.session.commit()
    return jsonify(animal.to_dict()), 200

@app.route('/animals/<int:animal_id>', methods=['DELETE'])
@jwt_required()
def delete_animal(animal_id):
    user_id = get_jwt_identity()
    animal = Animal.query.get_or_404(animal_id)
    if animal.farmer_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(animal)
    db.session.commit()
    return jsonify({'message': 'Animal deleted'}), 200

# Cart Routes
@app.route('/cart', methods=['GET'])
@jwt_required()
def get_cart():
    user_id = get_jwt_identity()
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    return jsonify([item.to_dict() for item in cart_items]), 200

@app.route('/cart', methods=['POST'])
@jwt_required()
def add_to_cart():
    user_id = get_jwt_identity()
    data = request.get_json()
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
    user_id = get_jwt_identity()
    item = CartItem.query.get_or_404(item_id)
    if item.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Removed from cart'}), 200

@app.route('/checkout', methods=['POST'])
@jwt_required()
def checkout():
    user_id = get_jwt_identity()
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400

    total = sum(item.animal.price * item.quantity for item in cart_items)
    order = Order(user_id=user_id, total_price=total)
    db.session.add(order)
    db.session.flush()

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

@app.route('/orders', methods=['GET'])
@jwt_required()
def get_orders():
    user_id = get_jwt_identity()
    orders = Order.query.filter_by(user_id=user_id).all()
    return jsonify([o.to_dict() for o in orders]), 200

@app.route('/orders/<int:order_id>/status', methods=['PATCH'])
@jwt_required()
def update_order_status(order_id):
    user_id = get_jwt_identity()
    order = Order.query.get_or_404(order_id)
    user = User.query.get(user_id)

    if user.role != 'farmer':
        return jsonify({'error': 'Only farmers can confirm/reject orders'}), 403

    data = request.get_json()
    order.status = data['status']
    db.session.commit()
    return jsonify(order.to_dict()), 200

@app.route('/admin/orders', methods=['GET'])
@admin_required
def get_all_orders():
    orders = Order.query.all()
    return jsonify([o.to_dict() for o in orders]), 200

@app.route('/admin/users', methods=['GET'])
@admin_required
def get_all_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users]), 200

@app.route('/admin/animals', methods=['GET'])
@admin_required
def get_all_animals_admin():
    animals = Animal.query.all()
    return jsonify([a.to_dict() for a in animals]), 200

if __name__ == '__main__':
    app.run(port=5555, debug=True)

# change password
# handle update profile
# handle delete profile