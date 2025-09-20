import asyncio
import random
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger

from ..models import JobStatus
from .database import DatabaseManager
from .job_queue import JobQueueManager
from .cover_letter_generator import CoverLetterGenerator
from .browser_automation import BrowserAutomationService

class AutomationManager:
    def __init__(self, db_manager: DatabaseManager, queue_manager: JobQueueManager):
        self.db = db_manager
        self.queue = queue_manager
        self.cover_letter_gen = CoverLetterGenerator()
        self.browser_automation = BrowserAutomationService()
        self.is_running = False
        self._automation_task = None
        self.processed_count = 0

    async def start(self):
        """Start the automation process"""
        if self.is_running:
            logger.warning("⚠️ Automation already running")
            return
            
        self.is_running = True
        logger.info("🚀 Starting job automation...")
        
        # Initialize browser automation
        try:
            await self.browser_automation.initialize()
        except Exception as e:
            logger.warning(f"⚠️ Browser automation init failed, using simulation: {e}")
        
        # Start background task
        self._automation_task = asyncio.create_task(self._automation_loop())

    async def stop(self):
        """Stop the automation process"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if self._automation_task:
            self._automation_task.cancel()
            try:
                await self._automation_task
            except asyncio.CancelledError:
                pass
                
        logger.info("⏹️ Automation stopped")

    async def _automation_loop(self):
        """Main automation processing loop"""
        try:
            while self.is_running:
                job = await self.queue.get_next_job()
                
                if job:
                    await self._process_job(job)
                else:
                    # No jobs available, wait before checking again
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            logger.info("🔄 Automation loop cancelled")
        except Exception as e:
            logger.error(f"❌ Automation loop error: {e}")

    async def _process_job(self, job: Dict[str, Any]):
        """Process a single job application"""
        job_id = job["id"]
        job_title = job["title"]
        company = job["company"]
        
        try:
            logger.info(f"🔄 Processing: {job_title} at {company}")
            
            # Update status to processing
            await self.db.update_job_status(job_id, JobStatus.PROCESSING)
            
            # Step 1: Generate cover letter
            cover_letter = await self._generate_cover_letter(job)
            
            # Step 2: Real browser automation
            application_result = await self.browser_automation.apply_to_job(job, cover_letter)
            
            # Step 3: Update final status
            final_status = JobStatus.COMPLETED if application_result["success"] else JobStatus.FAILED
            await self.db.update_job_status(job_id, final_status, application_result)
            
            self.processed_count += 1
            
            status_emoji = "✅" if application_result["success"] else "❌"
            logger.info(f"{status_emoji} {job_title} at {company}: {final_status.value}")
            
        except Exception as e:
            logger.error(f"❌ Failed to process job {job_id}: {e}")
            await self.db.update_job_status(job_id, JobStatus.FAILED, {"error": str(e)})

    async def _generate_cover_letter(self, job: Dict[str, Any]) -> str:
        """Generate cover letter for job"""
        try:
            # Simulate cover letter generation time
            await asyncio.sleep(random.uniform(1, 3))
            
            cover_letter = await self.cover_letter_gen.generate(
                job_description=job.get("description", ""),
                job_requirements=job.get("requirements", ""),
                company_name=job["company"],
                position_title=job["title"]
            )
            
            logger.info(f"📝 Cover letter generated for {job['title']}")
            return cover_letter
            
        except Exception as e:
            logger.warning(f"⚠️ Cover letter generation failed, using fallback: {e}")
            return self._generate_fallback_cover_letter(job)

    def _generate_fallback_cover_letter(self, job: Dict[str, Any]) -> str:
        """Generate a basic fallback cover letter"""
        return f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job['title']} position at {job['company']}.

With my background in software development and data analysis, I am excited about the opportunity to contribute to your team. My experience aligns well with the requirements outlined in your job posting.

I am particularly drawn to {job['company']} and would welcome the opportunity to discuss how my skills can contribute to your continued success.

Thank you for your consideration.

Best regards,
[Your Name]"""

    async def _simulate_application(self, job: Dict[str, Any], cover_letter: str) -> Dict[str, Any]:
        """Simulate job application process"""
        platform = job["platform"]
        
        # Simulate application time
        processing_time = random.uniform(2, 8)
        await asyncio.sleep(processing_time)
        
        # Simulate success/failure with realistic rates
        success_rates = {
            "linkedin": 0.75,  # 75% success rate
            "indeed": 0.65,   # 65% success rate
            "company_portal": 0.80  # 80% success rate
        }
        
        success_rate = success_rates.get(platform, 0.70)
        success = random.random() < success_rate
        
        result = {
            "success": success,
            "platform": platform,
            "processing_time": round(processing_time, 2),
            "timestamp": datetime.now().isoformat(),
            "cover_letter_length": len(cover_letter)
        }
        
        if not success:
            error_reasons = [
                "Application deadline passed",
                "Position no longer available", 
                "Technical error during submission",
                "CAPTCHA challenge failed",
                "Account verification required"
            ]
            result["error"] = random.choice(error_reasons)
        
        return result

    async def get_stats(self) -> Dict[str, Any]:
        """Get automation statistics"""
        return {
            "is_running": self.is_running,
            "processed_count": self.processed_count,
            "queue_size": len(await self.queue.get_all_jobs())
        }

    async def cleanup(self):
        """Cleanup automation resources"""
        await self.stop()
        await self.browser_automation.cleanup()
        logger.info("🧹 Automation manager cleaned up")