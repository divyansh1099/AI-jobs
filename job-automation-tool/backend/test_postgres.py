#!/usr/bin/env python3
"""
Test PostgreSQL connection and database setup
"""
import asyncio
import asyncpg
from loguru import logger
from app.core.config import settings

async def test_postgres_connection():
    """Test PostgreSQL connection"""
    try:
        # Test basic connection
        logger.info("Testing PostgreSQL connection...")
        
        connection = await asyncpg.connect(
            host=settings.database_host,
            port=settings.database_port,
            database=settings.database_name,
            user=settings.database_user,
            password=settings.database_password
        )
        
        # Test basic query
        result = await connection.fetchval("SELECT version()")
        logger.info(f"✅ PostgreSQL version: {result}")
        
        await connection.close()
        logger.info("✅ Database connection test successful")
        
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False
        
    return True

async def test_database_manager():
    """Test DatabaseManager initialization"""
    try:
        from app.services.database import DatabaseManager
        
        logger.info("Testing DatabaseManager...")
        
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        # Test adding a sample job
        job_data = {
            "title": "Test Job",
            "company": "Test Company", 
            "platform": "test",
            "url": "https://test.com/job"
        }
        
        job_id = "test-job-123"
        await db_manager.add_job(job_id, job_data)
        logger.info("✅ Sample job added successfully")
        
        # Test getting jobs
        jobs = await db_manager.get_all_jobs()
        logger.info(f"✅ Retrieved {len(jobs)} jobs from database")
        
        # Clean up
        await db_manager.delete_job(job_id)
        logger.info("✅ Test job deleted")
        
        await db_manager.cleanup()
        logger.info("✅ DatabaseManager test successful")
        
    except Exception as e:
        logger.error(f"❌ DatabaseManager test failed: {e}")
        return False
        
    return True

async def main():
    """Main test function"""
    logger.info("🧪 Starting PostgreSQL database tests...")
    
    # Test 1: Basic connection
    success1 = await test_postgres_connection()
    
    # Test 2: DatabaseManager
    success2 = await test_database_manager()
    
    if success1 and success2:
        logger.info("🎉 All database tests passed!")
    else:
        logger.error("❌ Some database tests failed!")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())