import asyncio
import random
from typing import List, Dict, Any
from datetime import datetime
from uuid import uuid4
from loguru import logger

from .database import DatabaseManager
from .job_queue import JobQueueManager

class JobScraperService:
    def __init__(self, db_manager: DatabaseManager, queue_manager: JobQueueManager):
        self.db = db_manager
        self.queue = queue_manager
        self.realistic_companies = [
            "Google", "Meta", "Apple", "Microsoft", "Amazon", "Netflix", "Uber", "Airbnb",
            "Stripe", "Shopify", "Slack", "Discord", "GitHub", "GitLab", "Figma", "Notion",
            "Coinbase", "Square", "PayPal", "Tesla", "SpaceX", "OpenAI", "Anthropic"
        ]
        
        self.job_templates = {
            "software_engineer": [
                "Software Engineer",
                "Senior Software Engineer", 
                "Full Stack Developer",
                "Frontend Developer",
                "Backend Developer"
            ],
            "data": [
                "Data Engineer",
                "Data Scientist", 
                "Machine Learning Engineer",
                "Data Analyst",
                "Analytics Engineer"
            ],
            "devops": [
                "DevOps Engineer",
                "Site Reliability Engineer",
                "Platform Engineer",
                "Infrastructure Engineer",
                "Cloud Engineer"
            ]
        }

    async def scrape_jobs(self, search_terms: List[str] = None, 
                         locations: List[str] = None) -> List[Dict[str, Any]]:
        """Scrape jobs from platforms (currently simulated with realistic data)"""
        
        if not search_terms:
            search_terms = ["software engineer", "data engineer"]
        if not locations:
            locations = ["Remote", "San Francisco"]
            
        logger.info(f"🔍 Scraping jobs for terms: {search_terms}, locations: {locations}")
        
        all_jobs = []
        
        for term in search_terms:
            for location in locations:
                # Simulate scraping delay
                await asyncio.sleep(random.uniform(1, 3))
                
                jobs = await self._scrape_platform_jobs(term, location)
                all_jobs.extend(jobs)
        
        # Remove duplicates and add to queue
        unique_jobs = self._deduplicate_jobs(all_jobs)
        added_count = 0
        
        for job in unique_jobs:
            try:
                job_id = await self.queue.add_job(job)
                await self.db.add_job(job_id, job)
                added_count += 1
                logger.info(f"🎯 Scraped job added: {job['title']} at {job['company']}")
            except Exception as e:
                logger.error(f"❌ Failed to add scraped job: {e}")
        
        logger.info(f"✅ Scraping completed: {added_count} jobs added")
        return unique_jobs

    async def _scrape_platform_jobs(self, search_term: str, location: str) -> List[Dict[str, Any]]:
        """Simulate scraping from a platform"""
        jobs = []
        platforms = ["linkedin", "indeed"]
        
        # Generate 2-5 realistic jobs per search
        num_jobs = random.randint(2, 5)
        
        for i in range(num_jobs):
            platform = random.choice(platforms)
            company = random.choice(self.realistic_companies)
            
            # Select job title based on search term
            if "data" in search_term.lower():
                job_category = "data"
            elif "devops" in search_term.lower() or "infrastructure" in search_term.lower():
                job_category = "devops"
            else:
                job_category = "software_engineer"
            
            title = random.choice(self.job_templates[job_category])
            
            job = {
                "title": title,
                "company": company,
                "platform": platform,
                "location": location,
                "url": f"https://{platform}.com/jobs/{uuid4().hex[:8]}",
                "description": self._generate_job_description(title, company),
                "requirements": self._generate_job_requirements(job_category),
                "salary_range": self._generate_salary_range(title),
                "search_term": search_term
            }
            
            jobs.append(job)
        
        logger.info(f"🔍 Found {len(jobs)} jobs for '{search_term}' in {location}")
        return jobs

    def _generate_job_description(self, title: str, company: str) -> str:
        """Generate realistic job description"""
        descriptions = {
            "Software Engineer": f"Join {company}'s engineering team to build scalable applications and services that impact millions of users.",
            "Senior Software Engineer": f"Lead technical initiatives at {company} and mentor junior developers while building cutting-edge solutions.",
            "Data Engineer": f"Design and maintain robust data pipelines at {company} to support analytics and machine learning initiatives.",
            "Data Scientist": f"Apply advanced analytics and machine learning to solve complex business problems at {company}.",
            "DevOps Engineer": f"Scale {company}'s infrastructure and deployment processes to support rapid growth and innovation.",
            "Full Stack Developer": f"Build end-to-end web applications at {company} using modern technologies and best practices."
        }
        
        return descriptions.get(title, f"Exciting opportunity to work at {company} as a {title}.")

    def _generate_job_requirements(self, category: str) -> str:
        """Generate realistic job requirements"""
        requirements = {
            "software_engineer": [
                "JavaScript, React, Node.js, 2+ years experience",
                "Python, Django, PostgreSQL, 3+ years experience", 
                "Java, Spring Boot, Microservices, 2+ years experience",
                "TypeScript, Next.js, GraphQL, 2+ years experience"
            ],
            "data": [
                "Python, SQL, Pandas, 2+ years experience",
                "Python, TensorFlow, Statistics, PhD preferred",
                "Spark, Airflow, AWS, 3+ years experience",
                "R, Python, Machine Learning, Statistics background"
            ],
            "devops": [
                "AWS, Kubernetes, Docker, 3+ years experience",
                "Terraform, CI/CD, Linux, 2+ years experience", 
                "GCP, Python, Monitoring, 3+ years experience",
                "Azure, PowerShell, Automation, 2+ years experience"
            ]
        }
        
        return random.choice(requirements.get(category, requirements["software_engineer"]))

    def _generate_salary_range(self, title: str) -> str:
        """Generate realistic salary range"""
        salary_ranges = {
            "Software Engineer": "$90,000 - $140,000",
            "Senior Software Engineer": "$130,000 - $200,000",
            "Data Engineer": "$100,000 - $160,000", 
            "Data Scientist": "$110,000 - $180,000",
            "DevOps Engineer": "$95,000 - $150,000",
            "Full Stack Developer": "$85,000 - $135,000"
        }
        
        return salary_ranges.get(title, "$80,000 - $120,000")

    def _deduplicate_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate jobs based on title and company"""
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            key = f"{job['title'].lower()}-{job['company'].lower()}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        return unique_jobs

    async def cleanup(self):
        """Cleanup scraper resources"""
        logger.info("🧹 Job scraper cleaned up")