from faker import Faker
import random
from app import app
from config import db
from models import User, Animal, CartItem, Order, OrderItem

fake = Faker()

with app.app_context():
    db.create_all()
    print("🌱 Seeding database...")

    # Delete existing data in FK-safe order
    OrderItem.query.delete()
    Order.query.delete()
    CartItem.query.delete()
    Animal.query.delete()
    User.query.delete()
    db.session.commit()

    # Seed Users
    users = []
    roles = ['farmer', 'buyer']
    for _ in range(15):
        role = random.choice(roles)
        user = User(
            username=fake.user_name(),
            email=fake.unique.email(),
            role=role
        )
        user.password_hash = "password123"
        db.session.add(user)
        users.append(user)
    db.session.commit()

    # Seed Animals (only for farmers)
    farmers = [u for u in users if u.role == 'farmer']
    animals = []
    for _ in range(15):
        animal = Animal(
            name=fake.first_name(),
            type=random.choice(['cow', 'goat', 'chicken', 'sheep']),
            breed=fake.word(),
            price=random.randint(1000, 50000),
            image=fake.image_url(),
            farmer_id=random.choice(farmers).id
        )
        db.session.add(animal)
        animals.append(animal)
    db.session.commit()

    # Seed Cart Items (only for buyers)
    buyers = [u for u in users if u.role == 'buyer']
    for _ in range(15):
        cart_item = CartItem(
            user_id=random.choice(buyers).id,
            animal_id=random.choice(animals).id,
            quantity=random.randint(1, 5)
        )
        db.session.add(cart_item)
    db.session.commit()

    # Seed Orders and Order Items (buyers only)
    for _ in range(15):
        buyer = random.choice(buyers)
        order = Order(
            user_id=buyer.id,
            status=random.choice(["pending", "shipped", "delivered"])
        )
        db.session.add(order)
        db.session.flush()  # Get order.id before creating items

        total_price = 0
        for _ in range(random.randint(1, 3)):
            animal = random.choice(animals)
            quantity = random.randint(1, 3)
            total_price += animal.price * quantity

            order_item = OrderItem(
                order_id=order.id,
                animal_id=animal.id,
                quantity=quantity
            )
            db.session.add(order_item)

        order.total_price = total_price
    db.session.commit()

    print("✅ Done seeding!")
