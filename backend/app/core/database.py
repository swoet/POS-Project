"""
Enhanced database configuration with connection pooling and optimization
"""
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy import event, text
import structlog
from contextlib import contextmanager
from typing import Generator

from .config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Create engine with connection pooling and optimization
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,   # Recycle connections every hour
    echo=settings.debug,  # Log SQL queries in debug mode
    future=True,
    connect_args={
        "options": "-c timezone=utc",
        "application_name": settings.app_name,
    }
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set database pragmas and optimizations"""
    if "postgresql" in settings.database_url:
        with dbapi_connection.cursor() as cursor:
            # Set connection-level optimizations
            cursor.execute("SET statement_timeout = '30s'")
            cursor.execute("SET lock_timeout = '10s'")
            cursor.execute("SET idle_in_transaction_session_timeout = '60s'")


def create_db_and_tables():
    """Create database tables with indexes"""
    SQLModel.metadata.create_all(engine)
    
    # Create additional indexes for performance
    with engine.connect() as conn:
        try:
            # Product indexes
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_barcode 
                ON product(barcode) WHERE barcode IS NOT NULL
            """))
            
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_name_search 
                ON product USING gin(to_tsvector('english', name))
            """))
            
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_category 
                ON product(category_id) WHERE category_id IS NOT NULL
            """))
            
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_stock 
                ON product(stock_quantity) WHERE stock_quantity <= min_stock
            """))
            
            # Sale indexes
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sale_timestamp 
                ON sale(timestamp DESC)
            """))
            
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sale_user_timestamp 
                ON sale(user_id, timestamp DESC)
            """))
            
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sale_total 
                ON sale(total) WHERE total > 0
            """))
            
            # User indexes
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_email 
                ON "user"(email)
            """))
            
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_role 
                ON "user"(role) WHERE is_active = true
            """))
            
            # Inventory log indexes
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_log_product_timestamp 
                ON inventorylog(product_id, timestamp DESC)
            """))
            
            # Audit log indexes
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_user_timestamp 
                ON auditlog(user_id, timestamp DESC) WHERE user_id IS NOT NULL
            """))
            
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_resource 
                ON auditlog(resource, resource_id) WHERE resource_id IS NOT NULL
            """))
            
            conn.commit()
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.warning("Some indexes may already exist", error=str(e))
            conn.rollback()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Get database session with proper error handling"""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Database session error", error=str(e))
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session"""
    with get_db_session() as session:
        yield session


class DatabaseManager:
    """Database management utilities"""
    
    @staticmethod
    def check_connection() -> bool:
        """Check database connection health"""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error("Database connection check failed", error=str(e))
            return False
    
    @staticmethod
    def get_connection_info() -> dict:
        """Get database connection information"""
        pool = engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
        }
    
    @staticmethod
    def optimize_database():
        """Run database optimization commands"""
        try:
            with engine.connect() as conn:
                # Update table statistics
                conn.execute(text("ANALYZE"))
                
                # Vacuum if needed (PostgreSQL)
                if "postgresql" in settings.database_url:
                    conn.execute(text("VACUUM ANALYZE"))
                
                logger.info("Database optimization completed")
        except Exception as e:
            logger.error("Database optimization failed", error=str(e))


# Global database manager instance
db_manager = DatabaseManager()


async def init_db() -> bool:
    """Initialize database resources and verify connectivity."""
    return db_manager.check_connection()


async def close_db() -> None:
    """Dispose database connections during application shutdown."""
    engine.dispose()
