import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_sale():
    """Test creating a sale"""
    # Setup user first
    client.post("/setup_admin", json={
        "username": "cashier",
        "email": "cashier@example.com",
        "password": "cashier123",
        "role": "cashier"
    })

    # Login to get token
    login_response = client.post("/token", data={
        "username": "cashier",
        "password": "cashier123"
    })
    token = login_response.json()["access_token"]

    # Create category and product
    category_response = client.post("/categories", json={
        "name": "Beverages",
        "description": "Drinks and beverages"
    })
    category_id = category_response.json()["id"]

    product_response = client.post("/products", json={
        "name": "Coffee",
        "barcode": "777888999",
        "category_id": category_id,
        "price": 3.50,
        "cost": 1.50,
        "stock_quantity": 100,
        "min_stock": 10,
        "description": "Hot coffee"
    })
    product_id = product_response.json()["id"]

    # Create sale
    response = client.post("/sales", json={
        "items": [{
            "product_id": product_id,
            "name": "Coffee",
            "price": 3.50,
            "quantity": 2
        }],
        "subtotal": 7.00,
        "tax": 0.70,
        "discount": 0.00,
        "payment_method": "cash"
    }, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["total"] == 7.70  # subtotal + tax
    assert data["payment_method"] == "cash"

def test_get_sales():
    """Test getting sales list"""
    response = client.get("/sales")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_bulk_sync_sales():
    """Test bulk syncing sales from offline POS"""
    # Setup user
    client.post("/setup_admin", json={
        "username": "syncuser",
        "email": "sync@example.com",
        "password": "sync123",
        "role": "cashier"
    })

    login_response = client.post("/token", data={
        "username": "syncuser",
        "password": "sync123"
    })
    token = login_response.json()["access_token"]

    # Bulk sync sales
    sales_data = [{
        "timestamp": "2025-09-17T10:00:00",
        "items_json": '[{"product_id": 1, "name": "Test Item", "price": 5.00, "quantity": 1}]',
        "total": 5.00,
        "subtotal": 5.00,
        "tax": 0.00,
        "discount": 0.00
    }]

    response = client.post("/sales/bulk_sync", json=sales_data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "saved" in data
    assert "count" in data
    assert data["count"] == 1

def test_sales_summary_report():
    """Test sales summary report"""
    response = client.get("/reports/sales_summary?start_date=2025-01-01&end_date=2025-12-31")
    assert response.status_code == 200
    data = response.json()
    assert "total_sales" in data
    assert "total_items" in data
    assert "sale_count" in data
    assert isinstance(data["total_sales"], (int, float))
    assert isinstance(data["total_items"], int)
    assert isinstance(data["sale_count"], int)

def test_inventory_adjustment():
    """Test inventory adjustment"""
    # Setup admin user
    client.post("/setup_admin", json={
        "username": "manager",
        "email": "manager@example.com",
        "password": "manager123",
        "role": "manager"
    })

    login_response = client.post("/token", data={
        "username": "manager",
        "password": "manager123"
    })
    token = login_response.json()["access_token"]

    # Create product
    category_response = client.post("/categories", json={
        "name": "Stationery",
        "description": "Office supplies"
    })
    category_id = category_response.json()["id"]

    product_response = client.post("/products", json={
        "name": "Pen",
        "barcode": "000111222",
        "category_id": category_id,
        "price": 1.50,
        "cost": 0.50,
        "stock_quantity": 100,
        "min_stock": 10,
        "description": "Ballpoint pen"
    })
    product_id = product_response.json()["id"]

    # Adjust inventory
    response = client.post("/inventory/adjust", json={
        "product_id": product_id,
        "quantity": 50,
        "reason": "Stock replenishment"
    }, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert "message" in data

def test_audit_logs():
    """Test audit log access"""
    # Setup admin user
    client.post("/setup_admin", json={
        "username": "auditor",
        "email": "auditor@example.com",
        "password": "audit123",
        "role": "admin"
    })

    login_response = client.post("/token", data={
        "username": "auditor",
        "password": "audit123"
    })
    token = login_response.json()["access_token"]

    # Get audit logs
    response = client.get("/audit_logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)