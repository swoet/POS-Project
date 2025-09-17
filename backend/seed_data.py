#!/usr/bin/env python3
"""
Seed data script for POS system
Populates the database with sample data for testing and development
"""

import os
from sqlmodel import Session, create_engine
from main import User, Category, Product, Sale
from passlib.context import CryptContext
from datetime import datetime, timedelta
import random

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pos_user:pos_password@localhost/pos_db")
engine = create_engine(DATABASE_URL, echo=False)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def create_sample_users(session: Session):
    """Create sample users"""
    users_data = [
        {
            "username": "admin",
            "email": "admin@possystem.com",
            "password": "admin123",
            "role": "admin"
        },
        {
            "username": "manager",
            "email": "manager@possystem.com",
            "password": "manager123",
            "role": "manager"
        },
        {
            "username": "cashier1",
            "email": "cashier1@possystem.com",
            "password": "cashier123",
            "role": "cashier"
        },
        {
            "username": "cashier2",
            "email": "cashier2@possystem.com",
            "password": "cashier123",
            "role": "cashier"
        }
    ]

    for user_data in users_data:
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            hashed_password=hash_password(user_data["password"]),
            role=user_data["role"]
        )
        session.add(user)
        print(f"Created user: {user.username}")

    session.commit()

def create_sample_categories(session: Session):
    """Create sample categories"""
    categories_data = [
        {"name": "Beverages", "description": "Drinks and beverages"},
        {"name": "Food", "description": "Food items and snacks"},
        {"name": "Electronics", "description": "Electronic devices and accessories"},
        {"name": "Clothing", "description": "Clothing and apparel"},
        {"name": "Books", "description": "Books and publications"},
        {"name": "Household", "description": "Household items and supplies"},
        {"name": "Personal Care", "description": "Personal care and hygiene products"},
        {"name": "Sports", "description": "Sports equipment and accessories"}
    ]

    categories = []
    for cat_data in categories_data:
        category = Category(**cat_data)
        session.add(category)
        categories.append(category)
        print(f"Created category: {category.name}")

    session.commit()
    return categories

def create_sample_products(session: Session, categories):
    """Create sample products"""
    products_data = [
        # Beverages
        {"name": "Coffee", "barcode": "10000001", "price": 3.50, "cost": 1.50, "stock_quantity": 100, "min_stock": 10, "description": "Hot brewed coffee"},
        {"name": "Green Tea", "barcode": "10000002", "price": 2.50, "cost": 1.00, "stock_quantity": 80, "min_stock": 8, "description": "Organic green tea"},
        {"name": "Cola", "barcode": "10000003", "price": 2.00, "cost": 0.80, "stock_quantity": 150, "min_stock": 15, "description": "Classic cola drink"},
        {"name": "Orange Juice", "barcode": "10000004", "price": 4.00, "cost": 2.00, "stock_quantity": 60, "min_stock": 6, "description": "Fresh orange juice"},

        # Food
        {"name": "Sandwich", "barcode": "20000001", "price": 8.50, "cost": 4.00, "stock_quantity": 50, "min_stock": 5, "description": "Turkey and cheese sandwich"},
        {"name": "Chocolate Bar", "barcode": "20000002", "price": 2.50, "cost": 1.20, "stock_quantity": 200, "min_stock": 20, "description": "Milk chocolate bar"},
        {"name": "Potato Chips", "barcode": "20000003", "price": 3.00, "cost": 1.50, "stock_quantity": 120, "min_stock": 12, "description": "Salted potato chips"},
        {"name": "Apple", "barcode": "20000004", "price": 1.50, "cost": 0.60, "stock_quantity": 300, "min_stock": 30, "description": "Fresh red apple"},

        # Electronics
        {"name": "USB Cable", "barcode": "30000001", "price": 12.99, "cost": 6.00, "stock_quantity": 75, "min_stock": 7, "description": "USB-C to USB-A cable"},
        {"name": "Wireless Mouse", "barcode": "30000002", "price": 25.99, "cost": 12.00, "stock_quantity": 40, "min_stock": 4, "description": "Bluetooth wireless mouse"},
        {"name": "Phone Case", "barcode": "30000003", "price": 19.99, "cost": 8.00, "stock_quantity": 90, "min_stock": 9, "description": "Protective phone case"},
        {"name": "Headphones", "barcode": "30000004", "price": 49.99, "cost": 22.00, "stock_quantity": 25, "min_stock": 2, "description": "Wireless headphones"},

        # Clothing
        {"name": "T-Shirt", "barcode": "40000001", "price": 15.99, "cost": 7.00, "stock_quantity": 100, "min_stock": 10, "description": "Cotton t-shirt"},
        {"name": "Jeans", "barcode": "40000002", "price": 59.99, "cost": 25.00, "stock_quantity": 30, "min_stock": 3, "description": "Blue denim jeans"},
        {"name": "Cap", "barcode": "40000003", "price": 12.99, "cost": 5.00, "stock_quantity": 60, "min_stock": 6, "description": "Baseball cap"},
        {"name": "Socks", "barcode": "40000004", "price": 8.99, "cost": 3.00, "stock_quantity": 150, "min_stock": 15, "description": "Cotton socks pack"},

        # Books
        {"name": "Python Programming", "barcode": "50000001", "price": 49.99, "cost": 25.00, "stock_quantity": 20, "min_stock": 2, "description": "Learn Python programming"},
        {"name": "Web Development", "barcode": "50000002", "price": 39.99, "cost": 20.00, "stock_quantity": 15, "min_stock": 1, "description": "Modern web development guide"},
        {"name": "Data Science", "barcode": "50000003", "price": 54.99, "cost": 28.00, "stock_quantity": 12, "min_stock": 1, "description": "Introduction to data science"},
        {"name": "Business Management", "barcode": "50000004", "price": 34.99, "cost": 18.00, "stock_quantity": 25, "min_stock": 2, "description": "Business management principles"}
    ]

    for i, product_data in enumerate(products_data):
        category = categories[i % len(categories)]
        product = Product(
            **product_data,
            category_id=category.id
        )
        session.add(product)
        print(f"Created product: {product.name} in {category.name}")

    session.commit()

def create_sample_sales(session: Session, users, products):
    """Create sample sales data"""
    # Get user IDs
    user_ids = [user.id for user in users]

    # Create sales for the last 30 days
    for i in range(30):
        sale_date = datetime.utcnow() - timedelta(days=i)

        # Random number of sales per day (1-5)
        num_sales = random.randint(1, 5)

        for _ in range(num_sales):
            user_id = random.choice(user_ids)

            # Random number of items per sale (1-5)
            num_items = random.randint(1, 5)
            sale_items = []
            subtotal = 0

            for _ in range(num_items):
                product = random.choice(products)
                quantity = random.randint(1, min(5, product.stock_quantity))
                item_total = product.price * quantity
                subtotal += item_total

                sale_items.append({
                    "product_id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "quantity": quantity
                })

            tax = subtotal * 0.10  # 10% tax
            discount = random.choice([0, 0, 0, subtotal * 0.05, subtotal * 0.10])  # 0%, 5%, or 10% discount
            total = subtotal + tax - discount

            sale = Sale(
                user_id=user_id,
                timestamp=sale_date,
                items_json=str(sale_items).replace("'", '"'),
                subtotal=round(subtotal, 2),
                tax=round(tax, 2),
                discount=round(discount, 2),
                total=round(total, 2),
                payment_method=random.choice(["cash", "card", "digital"])
            )
            session.add(sale)

    session.commit()
    print("Created sample sales data for the last 30 days")

def main():
    """Main seed function"""
    print("Starting database seeding...")

    with Session(engine) as session:
        print("Creating sample users...")
        create_sample_users(session)

        print("Creating sample categories...")
        categories = create_sample_categories(session)

        print("Creating sample products...")
        create_sample_products(session, categories)

        # Get users and products for sales
        users = session.query(User).all()
        products = session.query(Product).all()

        print("Creating sample sales...")
        create_sample_sales(session, users, products)

    print("Database seeding completed successfully!")
    print("\nSample login credentials:")
    print("Admin: admin / admin123")
    print("Manager: manager / manager123")
    print("Cashier: cashier1 / cashier123")

if __name__ == "__main__":
    main()