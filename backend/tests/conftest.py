import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
from main import app
from fastapi.testclient import TestClient

# Test database URL
TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[None] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user_data():
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "role": "cashier"
    }

@pytest.fixture
def test_product_data():
    return {
        "name": "Test Product",
        "barcode": "123456789",
        "price": 10.99,
        "cost": 7.50,
        "stock_quantity": 100,
        "min_stock": 10,
        "description": "A test product"
    }

@pytest.fixture
def test_category_data():
    return {
        "name": "Test Category",
        "description": "A test category"
    }