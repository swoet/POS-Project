# Administrator Manual - POS System

## System Overview

As a system administrator, you are responsible for configuring, maintaining, and monitoring the Point of Sale (POS) system. This manual covers all administrative functions and best practices for system management.

## Initial Setup

### System Installation

#### Docker Deployment (Recommended)

1. **Prerequisites**
   - Docker Engine 20.10+
   - Docker Compose 2.0+
   - At least 4GB RAM
   - 20GB free disk space

2. **Deployment Steps**
   ```bash
   # Clone repository
   git clone <repository-url>
   cd pos-system

   # Start all services
   docker-compose up -d

   # Check service status
   docker-compose ps

   # View logs
   docker-compose logs -f
   ```

3. **Initial Configuration**
   ```bash
   # Setup admin user
   curl -X POST http://localhost/api/setup_admin \
     -H "Content-Type: application/json" \
     -d '{
       "username": "admin",
       "email": "admin@yourstore.com",
       "password": "SecurePass123!",
       "role": "admin"
     }'
   ```

#### Manual Installation

1. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Database Setup**
   ```sql
   CREATE DATABASE pos_db;
   CREATE USER pos_user WITH PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE pos_db TO pos_user;
   ```

3. **Environment Configuration**
   ```bash
   # Copy and edit environment files
   cp backend/.env.example backend/.env
   cp admin_frontend/.env.example admin_frontend/.env
   ```

### SSL Configuration

1. **Obtain SSL Certificate**
   ```bash
   # Using Let's Encrypt
   certbot certonly --webroot -w /var/www/html -d yourdomain.com
   ```

2. **Configure Nginx**
   ```nginx
   server {
       listen 443 ssl http2;
       server_name yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

       # SSL configuration
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:...;
       ssl_prefer_server_ciphers off;
   }
   ```

## User Management

### Creating User Accounts

1. **Access Admin Panel**
   - Navigate to http://yourdomain.com
   - Login with admin credentials

2. **Add New User**
   - Go to Users → Add User
   - Fill required information:
     - Username (unique)
     - Email address
     - Full name
     - Role (Admin/Manager/Cashier)
     - Password (temporary)

3. **User Roles and Permissions**

   **Administrator**
   - Full system access
   - User management
   - System configuration
   - Audit log access

   **Manager**
   - Product management
   - Inventory control
   - Sales reporting
   - Staff scheduling

   **Cashier**
   - POS operations
   - Sale processing
   - Basic reporting

### Password Management

1. **Password Policies**
   - Minimum 8 characters
   - Mix of uppercase/lowercase
   - At least one number
   - At least one special character

2. **Password Reset**
   ```bash
   # Generate reset token
   curl -X POST http://localhost/api/forgot_password \
     -H "Content-Type: application/json" \
     -d '{"email": "user@domain.com"}'
   ```

3. **Force Password Change**
   - Login to admin panel
   - Users → Select user → Reset Password
   - User will be prompted to change password on next login

## Product Management

### Adding Products

1. **Basic Information**
   - Product name
   - SKU/Barcode
   - Description
   - Category selection

2. **Pricing**
   - Base price
   - Cost price
   - Tax settings
   - Discount eligibility

3. **Inventory**
   - Initial stock quantity
   - Minimum stock level
   - Reorder point
   - Supplier information

### Category Management

1. **Creating Categories**
   - Go to Products → Categories
   - Click "Add Category"
   - Enter name and description

2. **Category Hierarchy**
   - Support for subcategories
   - Drag-and-drop reordering
   - Bulk category operations

### Bulk Operations

1. **CSV Import**
   ```csv
   name,sku,price,cost,stock,category
   "Coffee Beans", "CF001", 15.99, 10.50, 100, "Beverages"
   "Green Tea", "TE001", 8.99, 5.25, 50, "Beverages"
   ```

2. **Import Process**
   - Go to Products → Import
   - Upload CSV file
   - Map columns
   - Validate data
   - Confirm import

## Inventory Management

### Stock Tracking

1. **Real-time Monitoring**
   - Dashboard shows low stock alerts
   - Automatic reorder notifications
   - Stock movement history

2. **Stock Adjustments**
   - Manual count adjustments
   - Damaged goods write-offs
   - Supplier returns
   - Audit trail for all changes

### Inventory Reports

1. **Stock Levels Report**
   - Current stock by product
   - Value of inventory
   - Stock turnover rates

2. **Low Stock Alerts**
   - Automatic email notifications
   - Configurable thresholds
   - Supplier contact integration

## Sales and Reporting

### Sales Analytics

1. **Dashboard Metrics**
   - Daily/weekly/monthly sales
   - Top products
   - Revenue trends
   - Customer analytics

2. **Custom Reports**
   - Date range selection
   - Product category filtering
   - Payment method breakdown
   - Staff performance

### Export Options

1. **Report Formats**
   - PDF reports
   - CSV data export
   - Excel spreadsheets
   - Scheduled email reports

2. **Data Export**
   ```bash
   # Export sales data
   curl -X GET "http://localhost/api/reports/sales?start_date=2024-01-01&end_date=2024-01-31&format=csv" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

## System Configuration

### General Settings

1. **Business Information**
   - Company name
   - Address and contact details
   - Tax settings
   - Currency configuration

2. **POS Settings**
   - Receipt templates
   - Payment methods
   - Tax calculations
   - Discount policies

### Security Settings

1. **Authentication**
   - Session timeout
   - Password policies
   - Two-factor authentication
   - Login attempt limits

2. **API Security**
   - Rate limiting configuration
   - CORS settings
   - API key management

## Backup and Recovery

### Database Backup

1. **Automated Backups**
   ```bash
   # Docker backup
   docker exec pos_db pg_dump -U pos_user pos_db > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Backup Schedule**
   - Daily incremental backups
   - Weekly full backups
   - Monthly archive backups
   - Offsite storage

### System Recovery

1. **Database Restore**
   ```bash
   # Stop services
   docker-compose down

   # Restore database
   docker exec -i pos_db psql -U pos_user pos_db < backup_file.sql

   # Restart services
   docker-compose up -d
   ```

2. **File System Backup**
   - Configuration files
   - SSL certificates
   - Log files
   - User uploads

## Monitoring and Maintenance

### System Health Checks

1. **Service Monitoring**
   ```bash
   # Check all services
   docker-compose ps

   # Check specific service
   docker-compose logs backend
   ```

2. **Performance Monitoring**
   - CPU and memory usage
   - Database query performance
   - API response times
   - Error rates

### Log Management

1. **Log Locations**
   - Application logs: `/var/log/pos/`
   - Nginx logs: `/var/log/nginx/`
   - Database logs: `/var/log/postgresql/`

2. **Log Rotation**
   ```bash
   # Configure logrotate
   /var/log/pos/*.log {
       daily
       rotate 30
       compress
       missingok
       notifempty
   }
   ```

## Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check database connectivity
docker exec pos_db psql -U pos_user -d pos_db -c "SELECT 1;"

# Restart database
docker-compose restart db
```

#### Application Errors
```bash
# Check application logs
docker-compose logs backend

# Restart application
docker-compose restart backend
```

#### Performance Issues
```bash
# Check resource usage
docker stats

# Scale services if needed
docker-compose up -d --scale backend=2
```

### Emergency Procedures

1. **System Down**
   - Assess impact
   - Implement backup procedures
   - Communicate with stakeholders
   - Restore from backup

2. **Data Loss**
   - Stop all write operations
   - Assess data loss extent
   - Restore from backup
   - Verify data integrity

## Updates and Upgrades

### Software Updates

1. **Update Process**
   ```bash
   # Pull latest images
   docker-compose pull

   # Update services
   docker-compose up -d

   # Check for issues
   docker-compose logs
   ```

2. **Version Management**
   - Track version changes
   - Test updates in staging
   - Schedule maintenance windows
   - Document update procedures

### Database Migrations

1. **Migration Process**
   ```bash
   # Create migration
   docker exec backend alembic revision --autogenerate -m "Add new feature"

   # Apply migration
   docker exec backend alembic upgrade head
   ```

## Security Best Practices

### Access Control

1. **Principle of Least Privilege**
   - Grant minimum required permissions
   - Regular permission audits
   - Remove inactive accounts

2. **Network Security**
   - Firewall configuration
   - SSL/TLS encryption
   - VPN for remote access

### Data Protection

1. **Encryption**
   - Database encryption
   - File system encryption
   - Secure key management

2. **Compliance**
   - GDPR compliance
   - PCI DSS for payments
   - Regular security audits

## Support and Resources

### Documentation
- API Documentation: `/api/docs`
- User Manuals: `/docs/`
- Troubleshooting Guide: `/docs/troubleshooting.md`

### Support Contacts
- **Technical Support**: support@pos-system.com
- **Emergency Hotline**: 1-800-POS-HELP
- **Vendor Support**: vendor@pos-vendor.com

### Community Resources
- User forums
- Knowledge base
- Training materials
- Best practices guides

## Appendix

### Configuration Files

#### docker-compose.yml
```yaml
version: '3.8'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: pos_db
      POSTGRES_USER: pos_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://pos_user:${DB_PASSWORD}@db:5432/pos_db
    ports:
      - "8000:8000"
```

#### nginx.conf
```nginx
upstream backend {
    server backend:8000;
}

server {
    listen 80;
    server_name yourdomain.com;

    location /api/ {
        proxy_pass http://backend/;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### API Endpoints

#### Authentication
- `POST /token` - User login
- `POST /refresh_token` - Refresh access token
- `POST /setup_admin` - Initial admin setup

#### Users
- `GET /users` - List users
- `POST /users` - Create user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user

#### Products
- `GET /products` - List products
- `POST /products` - Create product
- `PUT /products/{id}` - Update product
- `DELETE /products/{id}` - Delete product

#### Sales
- `GET /sales` - List sales
- `POST /sales` - Create sale
- `POST /sales/bulk_sync` - Sync offline sales

### Error Codes

- **1001**: Database connection failed
- **1002**: Authentication failed
- **1003**: Authorization denied
- **1004**: Resource not found
- **1005**: Validation error
- **1006**: Rate limit exceeded
- **1007**: System overload
- **1008**: External service error

---

*This manual is maintained by the system administrators. Please report any issues or suggestions for improvement.*