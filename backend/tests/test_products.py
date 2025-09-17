import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_category():
    """Test creating a category"""
    response = client.post("/categories", json={
        "name": "Test Category",
        "description": "A test category"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Category"
    assert data["description"] == "A test category"

def test_get_categories():
    """Test getting categories"""
    # Create a category first
    client.post("/categories", json={
        "name": "Test Category 2",
        "description": "Another test category"
    })

    response = client.get("/categories")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_create_product():
    """Test creating a product"""
    # Create category first
    category_response = client.post("/categories", json={
        "name": "Electronics",
        "description": "Electronic products"
    })
    category_id = category_response.json()["id"]

    response = client.post("/products", json={
        "name": "Test Product",
        "barcode": "123456789",
        "category_id": category_id,
        "price": 29.99,
        "cost": 15.50,
        "stock_quantity": 100,
        "min_stock": 10,
        "description": "A test product"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Product"
    assert data["price"] == 29.99
    assert data["stock_quantity"] == 100

def test_get_products():
    """Test getting products"""
    response = client.get("/products")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_search_products():
    """Test searching products"""
    # Create a product first
    category_response = client.post("/categories", json={
        "name": "Books",
        "description": "Book category"
    })
    category_id = category_response.json()["id"]

    client.post("/products", json={
        "name": "Python Programming Book",
        "barcode": "987654321",
        "category_id": category_id,
        "price": 49.99,
        "cost": 25.00,
        "stock_quantity": 50,
        "min_stock": 5,
        "description": "Learn Python programming"
    })

    # Search by name
    response = client.get("/products?search=Python")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert "Python" in data[0]["name"]

def test_update_product():
    """Test updating a product"""
    # Create product first
    category_response = client.post("/categories", json={
        "name": "Clothing",
        "description": "Clothing category"
    })
    category_id = category_response.json()["id"]

    create_response = client.post("/products", json={
        "name": "T-Shirt",
        "barcode": "111222333",
        "category_id": category_id,
        "price": 19.99,
        "cost": 8.00,
        "stock_quantity": 200,
        "min_stock": 20,
        "description": "Cotton t-shirt"
    })
    product_id = create_response.json()["id"]

    # Update product
    response = client.put(f"/products/{product_id}", json={
        "name": "Updated T-Shirt",
        "barcode": "111222333",
        "category_id": category_id,
        "price": 24.99,
        "cost": 10.00,
        "stock_quantity": 150,
        "min_stock": 15,
        "description": "Updated cotton t-shirt"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated T-Shirt"
    assert data["price"] == 24.99
    assert data["stock_quantity"] == 150

def test_delete_product():
    """Test deleting a product"""
    # Create product first
    category_response = client.post("/categories", json={
        "name": "Food",
        "description": "Food category"
    })
    category_id = category_response.json()["id"]

    create_response = client.post("/products", json={
        "name": "Apple",
        "barcode": "444555666",
        "category_id": category_id,
        "price": 1.99,
        "cost": 0.80,
        "stock_quantity": 500,
        "min_stock": 50,
        "description": "Fresh apple"
    })
    product_id = create_response.json()["id"]

    # Delete product
    response = client.delete(f"/products/{product_id}")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data

    # Verify product is deleted
    get_response = client.get(f"/products/{product_id}")
    assert get_response.status_code == 404