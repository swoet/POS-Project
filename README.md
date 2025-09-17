# POS System - Complete Point of Sale Solution

A modern, secure, and fully-featured Point of Sale (POS) system designed for retail businesses. Features offline-first operation, comprehensive inventory management, and responsive web-based administration.

## 🚀 Features

### Desktop POS Application
- ✅ Offline-first operation with automatic sync
- ✅ Product catalog with search and barcode scanning
- ✅ Cart management with tax/discount support
- ✅ Multiple payment methods
- ✅ Thermal receipt printing
- ✅ Touchscreen-optimized interface
- ✅ Light/dark mode support

### Backend API
- ✅ FastAPI with PostgreSQL database
- ✅ JWT authentication with role-based access
- ✅ CRUD operations for products, users, sales
- ✅ Inventory management and tracking
- ✅ Audit logging and security features
- ✅ 2FA support for admin users
- ✅ Rate limiting and security headers

### Admin Web Interface
- ✅ React + TailwindCSS + shadcn/ui
- ✅ Real-time dashboard with charts
- ✅ User and product management
- ✅ Sales reporting and analytics
- ✅ Inventory monitoring
- ✅ WebSocket real-time updates

### DevOps & Deployment
- ✅ Docker containerization
- ✅ Nginx reverse proxy with SSL
- ✅ GitHub Actions CI/CD pipeline
- ✅ Automated testing and linting
- ✅ Production-ready deployment

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Desktop POS   │    │   Admin Web     │    │     Backend     │
│   (Electron +   │    │   (React)       │    │   (FastAPI)     │
│    React)       │    │                 │    │                 │
│                 │    │                 │    │                 │
│ - Offline sync  │◄──►│ - Dashboard     │◄──►│ - REST API      │
│ - Barcode scan  │    │ - Management    │    │ - JWT Auth      │
│ - Receipt print │    │ - Reports       │    │ - PostgreSQL    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Nginx Proxy   │
                    │   (SSL/TLS)     │
                    └─────────────────┘
```

## 📋 Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for development)
- Python 3.11+ (for development)
- PostgreSQL (handled by Docker)

## 🚀 Quick Start

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pos-system
   ```

2. **Start the system**
   ```bash
   docker-compose up -d
   ```

3. **Access the applications**
   - Admin Web: http://localhost
   - Backend API: http://localhost/api/
   - API Documentation: http://localhost/api/docs

4. **Setup admin user**
   ```bash
   curl -X POST http://localhost/api/setup_admin \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "email": "admin@example.com", "password": "admin123", "role": "admin"}'
   ```

### Manual Development Setup

#### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database URL

# Run database migrations
alembic upgrade head

# Start the backend
uvicorn main:app --reload
```

#### Admin Frontend Setup
```bash
cd admin_frontend
npm install
npm start
```

#### Desktop POS Setup
```bash
cd pos_desktop_electron
npm install
npm run dev  # For development
npm run build && npm start  # For production
```

## 🔧 Configuration

### Environment Variables

Create `.env` files in the respective directories:

#### Backend (.env)
```env
DATABASE_URL=postgresql://user:password@localhost/pos_db
SECRET_KEY=your-super-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
OTP_SECRET=your-otp-secret
```

#### Admin Frontend (.env)
```env
REACT_APP_API_URL=http://localhost:8000
```

### Database Setup

The system uses PostgreSQL. With Docker Compose, it's automatically set up. For manual setup:

```sql
CREATE DATABASE pos_db;
CREATE USER pos_user WITH PASSWORD 'pos_password';
GRANT ALL PRIVILEGES ON DATABASE pos_db TO pos_user;
```

## 📖 API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest --cov=. --cov-report=html
```

### Frontend Tests
```bash
cd admin_frontend
npm test
```

### Desktop Tests
```bash
cd pos_desktop_electron
npm test
```

## 🚀 Deployment

### Production Deployment

1. **Build and deploy with Docker**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **SSL Configuration**
   - Place SSL certificates in `nginx/ssl/`
   - Update `nginx/nginx.conf` with certificate paths
   - Uncomment HTTPS server block in nginx.conf

3. **Environment Configuration**
   - Update production environment variables
   - Configure database connection strings
   - Set up proper secrets management

### Manual Deployment

1. **Backend**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Admin Frontend**
   ```bash
   cd admin_frontend
   npm run build
   # Serve build/ directory with nginx or Apache
   ```

3. **Desktop POS**
   ```bash
   cd pos_desktop_electron
   npm run build
   # Package with electron-builder for distribution
   ```

## 🔒 Security

### Authentication
- JWT tokens with refresh mechanism
- Role-based access control (RBAC)
- Two-factor authentication for admins
- Secure password hashing with Argon2

### API Security
- Rate limiting on all endpoints
- CORS configuration
- HTTPS enforcement in production
- Input validation and sanitization

### Database Security
- Parameterized queries
- Database user with minimal privileges
- Encrypted sensitive data
- Regular security updates

## 📊 Monitoring

### Health Checks
- Backend: `GET /health`
- Database connectivity checks
- Service dependency monitoring

### Logging
- Structured logging with levels
- Audit logs for all user actions
- Error tracking and alerting
- Performance monitoring

## 🛠️ Development

### Code Quality
- ESLint for JavaScript/React
- Black for Python formatting
- Pre-commit hooks for quality checks
- Automated testing in CI/CD

### Git Workflow
```bash
# Feature development
git checkout -b feature/new-feature
# Make changes
git commit -m "Add new feature"
git push origin feature/new-feature
# Create pull request
```

### Database Migrations
```bash
cd backend
alembic revision --autogenerate -m "Add new table"
alembic upgrade head
```

## 📚 User Manuals

### Cashier Manual
See `docs/cashier-manual.md` for POS operation instructions.

### Admin Manual
See `docs/admin-manual.md` for system administration guide.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Check the documentation in `docs/`
- Review the API documentation at `/docs`

## 📈 Roadmap

- [ ] Mobile POS app
- [ ] Customer loyalty program
- [ ] Advanced analytics and forecasting
- [ ] Multi-location support
- [ ] Integration with accounting software
- [ ] Advanced reporting with custom dashboards

---

**Built with ❤️ using FastAPI, React, Electron, and PostgreSQL**