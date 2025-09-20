import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
from loguru import logger

# Use in-memory queue for now to avoid Redis compatibility issues
REDIS_AVAILABLE = False

class JobQueueManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.in_memory_queue = []
        self.use_redis = False
        
    async def initialize(self, db_manager=None):
        """Initialize job queue (Redis or in-memory fallback)"""
        if REDIS_AVAILABLE:
            try:
                self.redis = await aioredis.from_url(self.redis_url)
                await self.redis.ping()
                self.use_redis = True
                logger.info("✅ Redis job queue initialized")
            except Exception as e:
                logger.warning(f"⚠️ Redis not available: {e}")
                self.use_redis = False
        else:
            self.use_redis = False
        
        # Load pending jobs from database into queue
        if db_manager:
            await self._load_pending_jobs(db_manager)
        
        logger.info("✅ Job queue initialized")

    async def _load_pending_jobs(self, db_manager):
        """Load pending jobs from database into queue"""
        try:
            pending_jobs = await db_manager.get_jobs_by_status("pending")
            
            for job_data in pending_jobs:
                # Add to queue without creating new job ID
                if self.use_redis:
                    await self.redis.lpush("job_queue", json.dumps(job_data))
                else:
                    self.in_memory_queue.append(job_data)
            
            if pending_jobs:
                # Sort by priority
                if not self.use_redis:
                    self.in_memory_queue.sort(key=lambda x: x.get("priority", 0))
                
                logger.info(f"📥 Loaded {len(pending_jobs)} pending jobs into queue")
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to load pending jobs: {e}")

    async def add_job(self, job_data: Dict[str, Any]) -> str:
        """Add job to queue and return job ID"""
        job_id = str(uuid4())
        job_entry = {
            "id": job_id,
            **job_data,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "priority": self._calculate_priority(job_data)
        }
        
        if self.use_redis:
            await self.redis.lpush("job_queue", json.dumps(job_entry))
            logger.info(f"📥 Job added to Redis queue: {job_data['title']}")
        else:
            self.in_memory_queue.append(job_entry)
            # Sort by priority (lower number = higher priority)
            self.in_memory_queue.sort(key=lambda x: x.get("priority", 0))
            logger.info(f"📥 Job added to memory queue: {job_data['title']}")
        
        return job_id

    def _calculate_priority(self, job_data: Dict[str, Any]) -> int:
        """Calculate job priority based on keywords and salary"""
        priority = 0
        title = job_data.get("title", "").lower()
        
        # High value keywords
        high_value_keywords = ["senior", "lead", "principal", "architect", "staff"]
        medium_value_keywords = ["engineer", "developer", "analyst"]
        
        if any(keyword in title for keyword in high_value_keywords):
            priority += 10
        elif any(keyword in title for keyword in medium_value_keywords):
            priority += 5
            
        # Salary-based priority
        salary = job_data.get("salary_range", "")
        if salary and "100" in salary:  # Rough check for 100k+
            priority += 5
            
        return -priority  # Negative for higher priority first

    async def get_next_job(self) -> Optional[Dict[str, Any]]:
        """Get next job from queue"""
        if self.use_redis:
            job_data = await self.redis.brpop("job_queue", timeout=1)
            if job_data:
                return json.loads(job_data[1])
        else:
            if self.in_memory_queue:
                return self.in_memory_queue.pop(0)
        
        return None

    async def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs in queue (for display purposes)"""
        if self.use_redis:
            jobs_data = await self.redis.lrange("job_queue", 0, -1)
            return [json.loads(job) for job in jobs_data]
        else:
            return self.in_memory_queue.copy()

    async def remove_job(self, job_id: str):
        """Remove specific job from queue"""
        if self.use_redis:
            # Redis removal is more complex, skip for now
            pass
        else:
            self.in_memory_queue = [
                job for job in self.in_memory_queue 
                if job.get("id") != job_id
            ]
            logger.info(f"🗑️ Job removed from queue: {job_id}")

    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        jobs = await self.get_all_jobs()
        
        stats = {
            "total": len(jobs),
            "pending": len([j for j in jobs if j.get("status") == "pending"]),
            "processing": len([j for j in jobs if j.get("status") == "processing"]),
        }
        
        return stats

    async def clear_queue(self):
        """Clear all jobs from queue"""
        if self.use_redis:
            await self.redis.delete("job_queue")
        else:
            self.in_memory_queue.clear()
        
        logger.info("🧹 Job queue cleared")

    async def cleanup(self):
        """Cleanup resources"""
        if self.redis:
            await self.redis.close()
            logger.info("🔌 Redis connection closed")