import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_setup_admin():
    """Test initial admin setup"""
    response = client.post("/setup_admin", json={
        "username": "admin",
        "email": "admin@example.com",
        "password": "admin123",
        "role": "admin"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"

def test_login_success():
    """Test successful login"""
    # First setup admin
    client.post("/setup_admin", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "role": "cashier"
    })

    # Then login
    response = client.post("/token", data={
        "username": "testuser",
        "password": "testpass123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    response = client.post("/token", data={
        "username": "nonexistent",
        "password": "wrongpass"
    })
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data

def test_refresh_token():
    """Test token refresh"""
    # Setup user and get initial token
    client.post("/setup_admin", json={
        "username": "refreshuser",
        "email": "refresh@example.com",
        "password": "refresh123",
        "role": "cashier"
    })

    login_response = client.post("/token", data={
        "username": "refreshuser",
        "password": "refresh123"
    })
    refresh_token = login_response.json()["refresh_token"]

    # Refresh token
    response = client.post("/refresh_token", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token_type" in data

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"