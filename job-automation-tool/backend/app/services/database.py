import asyncio
import asyncpg
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from loguru import logger
from uuid import uuid4

from ..models import JobCreate, JobResponse, JobStatus, ApplicationStats
from ..core.config import settings

class DatabaseManager:
    def __init__(self):
        self.pool = None
        
    async def initialize(self):
        """Initialize database connection pool and create tables"""
        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                host=settings.database_host,
                port=settings.database_port,
                database=settings.database_name,
                user=settings.database_user,
                password=settings.database_password,
                min_size=5,
                max_size=20
            )
            
            await self.create_tables()
            logger.info("✅ PostgreSQL database initialized successfully")
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise

    async def create_tables(self):
        """Create database tables if they don't exist"""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id VARCHAR(255) PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                company VARCHAR(255) NOT NULL,
                platform VARCHAR(100) NOT NULL,
                url TEXT NOT NULL,
                description TEXT,
                requirements TEXT,
                salary_range VARCHAR(255),
                location VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                applied_at TIMESTAMP,
                cover_letter TEXT,
                application_result JSONB
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS resumes (
                id VARCHAR(255) PRIMARY KEY,
                filename VARCHAR(500) NOT NULL,
                file_path TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT NOW(),
                parsed_data JSONB,
                extracted_profile JSONB,
                is_active BOOLEAN DEFAULT FALSE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS form_activity (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                domain VARCHAR(255) NOT NULL,
                filled_fields INTEGER DEFAULT 0,
                total_fields INTEGER DEFAULT 0,
                accuracy DECIMAL(5,2) DEFAULT 0.0,
                timestamp TIMESTAMP DEFAULT NOW(),
                resume_id VARCHAR(255),
                FOREIGN KEY (resume_id) REFERENCES resumes(id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(platform)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_resumes_active ON resumes(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_form_activity_domain ON form_activity(domain)"
        ]
        
        async with self.pool.acquire() as connection:
            for query in queries:
                await connection.execute(query)
        
        logger.info("📊 PostgreSQL tables created/verified")

    async def add_job(self, job_id: str, job_data: Dict[str, Any]) -> str:
        """Add a new job to the database"""
        try:
            query = """
            INSERT INTO jobs (id, title, company, platform, url, description, 
                            requirements, salary_range, location, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """
            
            async with self.pool.acquire() as connection:
                await connection.execute(query,
                    job_id,
                    job_data["title"],
                    job_data["company"], 
                    job_data["platform"],
                    job_data["url"],
                    job_data.get("description"),
                    job_data.get("requirements"),
                    job_data.get("salary_range"),
                    job_data.get("location"),
                    "pending"
                )
            
            logger.info(f"📝 Job added to database: {job_data['title']} at {job_data['company']}")
            return job_id
        except Exception as e:
            logger.error(f"❌ Failed to add job to database: {e}")
            raise

    async def update_job_status(self, job_id: str, status: JobStatus, 
                              result: Optional[Dict[str, Any]] = None):
        """Update job status and application result"""
        try:
            query = """
            UPDATE jobs 
            SET status = $1, applied_at = NOW(), application_result = $2
            WHERE id = $3
            """
            
            async with self.pool.acquire() as connection:
                await connection.execute(query,
                    status.value,
                    json.dumps(result) if result else None,
                    job_id
                )
            
            logger.info(f"📊 Job status updated: {job_id} → {status.value}")
        except Exception as e:
            logger.error(f"❌ Failed to update job status: {e}")
            raise

    async def get_application_stats(self) -> ApplicationStats:
        """Get application statistics"""
        try:
            query = """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing
            FROM jobs
            """
            
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(query)
                
            return ApplicationStats(
                total=row[0] or 0,
                successful=row[1] or 0,
                failed=row[2] or 0,
                pending=row[3] or 0,
                processing=row[4] or 0
            )
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return ApplicationStats()

    async def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs from database"""
        try:
            query = "SELECT * FROM jobs ORDER BY created_at DESC"
            
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(query)
                
            jobs = []
            for row in rows:
                job_dict = dict(row)
                # PostgreSQL JSONB is automatically parsed
                jobs.append(job_dict)
                
            return jobs
        except Exception as e:
            logger.error(f"❌ Failed to get jobs: {e}")
            return []

    async def get_jobs_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get jobs by status"""
        try:
            query = "SELECT * FROM jobs WHERE status = $1 ORDER BY created_at DESC"
            
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(query, status)
                
            jobs = []
            for row in rows:
                job_dict = dict(row)
                jobs.append(job_dict)
                
            return jobs
        except Exception as e:
            logger.error(f"❌ Failed to get jobs by status: {e}")
            return []

    async def delete_job(self, job_id: str):
        """Delete a job from database"""
        try:
            async with self.pool.acquire() as connection:
                await connection.execute("DELETE FROM jobs WHERE id = $1", job_id)
            logger.info(f"🗑️ Job deleted: {job_id}")
        except Exception as e:
            logger.error(f"❌ Failed to delete job: {e}")
            raise

    async def cleanup(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("🔌 Database connection pool closed")