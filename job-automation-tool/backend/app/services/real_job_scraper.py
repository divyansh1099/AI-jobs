import asyncio
import random
from typing import List, Dict, Any
from datetime import datetime
from uuid import uuid4
from playwright.async_api import async_playwright, Browser
from bs4 import BeautifulSoup
from loguru import logger

from .database import DatabaseManager
from .job_queue import JobQueueManager

class RealJobScraperService:
    def __init__(self, db_manager: DatabaseManager, queue_manager: JobQueueManager):
        self.db = db_manager
        self.queue = queue_manager
        self.playwright = None
        self.browser = None

    async def initialize(self):
        """Initialize browser for scraping"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            logger.info("✅ Job scraper browser initialized")
        except Exception as e:
            logger.error(f"❌ Scraper browser init failed: {e}")
            raise

    async def scrape_jobs(self, search_terms: List[str], locations: List[str]) -> List[Dict[str, Any]]:
        """Scrape real jobs from LinkedIn and Indeed"""
        all_jobs = []
        
        for term in search_terms:
            for location in locations:
                try:
                    # Scrape LinkedIn
                    linkedin_jobs = await self._scrape_linkedin(term, location)
                    all_jobs.extend(linkedin_jobs)
                    
                    # Add delay between platforms
                    await asyncio.sleep(random.uniform(2, 5))
                    
                    # Scrape Indeed  
                    indeed_jobs = await self._scrape_indeed(term, location)
                    all_jobs.extend(indeed_jobs)
                    
                except Exception as e:
                    logger.error(f"❌ Scraping failed for {term} in {location}: {e}")
        
        # Process and store jobs
        unique_jobs = self._deduplicate_jobs(all_jobs)
        await self._save_scraped_jobs(unique_jobs)
        
        logger.info(f"✅ Scraping completed: {len(unique_jobs)} unique jobs found")
        return unique_jobs

    async def _scrape_linkedin(self, search_term: str, location: str) -> List[Dict[str, Any]]:
        """Scrape jobs from LinkedIn"""
        context = await self.browser.new_context()
        page = await context.new_page()
        jobs = []
        
        try:
            # LinkedIn jobs search URL
            search_url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={search_term.replace(' ', '%20')}"
                f"&location={location.replace(' ', '%20')}"
                f"&f_TPR=r86400"  # Last 24 hours
            )
            
            await page.goto(search_url)
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(random.uniform(2, 4))
            
            # Get job cards
            job_cards = await page.locator('.job-search-card').all()
            
            for i, card in enumerate(job_cards[:10]):  # Limit to 10 jobs
                try:
                    title_elem = card.locator('.base-search-card__title a')
                    company_elem = card.locator('.base-search-card__subtitle a')
                    location_elem = card.locator('.job-search-card__location')
                    
                    title = await title_elem.text_content() if await title_elem.count() > 0 else None
                    company = await company_elem.text_content() if await company_elem.count() > 0 else None
                    job_location = await location_elem.text_content() if await location_elem.count() > 0 else location
                    url = await title_elem.get_attribute('href') if await title_elem.count() > 0 else None
                    
                    if title and company and url:
                        # Get job details and company URL
                        description, requirements, company_url = await self._get_linkedin_job_details(page, url)
                        
                        job = {
                            "title": title.strip(),
                            "company": company.strip(),
                            "platform": "linkedin",
                            "location": job_location.strip() if job_location else location,
                            "url": company_url or (url if url.startswith('http') else f"https://www.linkedin.com{url}"),
                            "linkedin_url": url if url.startswith('http') else f"https://www.linkedin.com{url}",
                            "description": description,
                            "requirements": requirements,
                            "search_term": search_term
                        }
                        
                        jobs.append(job)
                        logger.info(f"🔍 LinkedIn job found: {title} at {company}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Failed to parse LinkedIn job card {i}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ LinkedIn scraping failed: {e}")
        finally:
            await context.close()
        
        return jobs

    async def _get_linkedin_job_details(self, page, job_url: str) -> tuple:
        """Get detailed job description and company URL from LinkedIn"""
        try:
            # Open job in new tab to avoid navigation issues
            new_page = await page.context.new_page()
            await new_page.goto(job_url)
            await new_page.wait_for_load_state('networkidle')
            
            # Extract job description
            description_elem = new_page.locator('.show-more-less-html__markup')
            description = await description_elem.text_content() if await description_elem.count() > 0 else ""
            
            # Extract requirements (usually in description)
            requirements = self._extract_requirements_from_description(description)
            
            # Look for "Apply on company website" or external application links
            company_url = None
            apply_links = new_page.locator('a[href*="apply"], a[href*="careers"], a[href*="jobs"]')
            
            for i in range(await apply_links.count()):
                link = apply_links.nth(i)
                href = await link.get_attribute('href')
                text = await link.text_content()
                
                if href and text and any(keyword in text.lower() for keyword in ['apply on', 'company website', 'external', 'careers']):
                    if not href.startswith('http'):
                        href = f"https://www.linkedin.com{href}"
                    if 'linkedin.com' not in href:
                        company_url = href
                        break
            
            await new_page.close()
            
            return description[:500], requirements, company_url
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to get LinkedIn job details: {e}")
            return "", "", None

    async def _scrape_indeed(self, search_term: str, location: str) -> List[Dict[str, Any]]:
        """Scrape jobs from Indeed"""
        context = await self.browser.new_context()
        page = await context.new_page()
        jobs = []
        
        try:
            # Indeed jobs search URL
            search_url = (
                f"https://www.indeed.com/jobs"
                f"?q={search_term.replace(' ', '+')}"
                f"&l={location.replace(' ', '+')}"
                f"&fromage=1"  # Last 24 hours
            )
            
            await page.goto(search_url)
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(random.uniform(2, 4))
            
            # Get job cards
            job_cards = await page.locator('[data-jk]').all()
            
            for i, card in enumerate(job_cards[:10]):  # Limit to 10 jobs
                try:
                    title_elem = card.locator('h2 a span[title]')
                    company_elem = card.locator('[data-testid="company-name"]')
                    location_elem = card.locator('[data-testid="job-location"]')
                    link_elem = card.locator('h2 a')
                    
                    title = await title_elem.get_attribute('title') if await title_elem.count() > 0 else None
                    company = await company_elem.text_content() if await company_elem.count() > 0 else None
                    job_location = await location_elem.text_content() if await location_elem.count() > 0 else location
                    href = await link_elem.get_attribute('href') if await link_elem.count() > 0 else None
                    
                    if title and company and href:
                        # Get company application URL from Indeed job page
                        company_url = await self._get_indeed_company_url(page, href)
                        
                        job = {
                            "title": title.strip(),
                            "company": company.strip(),
                            "platform": "indeed",
                            "location": job_location.strip() if job_location else location,
                            "url": company_url or (href if href.startswith('http') else f"https://www.indeed.com{href}"),
                            "indeed_url": href if href.startswith('http') else f"https://www.indeed.com{href}",
                            "description": f"Opportunity to work as {title} at {company}",
                            "requirements": self._generate_generic_requirements(title),
                            "search_term": search_term
                        }
                        
                        jobs.append(job)
                        logger.info(f"🔍 Indeed job found: {title} at {company}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Failed to parse Indeed job card {i}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Indeed scraping failed: {e}")
        finally:
            await context.close()
        
        return jobs

    def _extract_requirements_from_description(self, description: str) -> str:
        """Extract requirements from job description"""
        tech_keywords = [
            "Python", "JavaScript", "React", "Node.js", "SQL", "AWS", "Docker", 
            "Kubernetes", "Java", "C++", "Go", "Rust", "TypeScript", "Vue", "Angular"
        ]
        
        found_techs = []
        desc_lower = description.lower()
        
        for tech in tech_keywords:
            if tech.lower() in desc_lower:
                found_techs.append(tech)
        
        if found_techs:
            return f"{', '.join(found_techs[:5])}, 2+ years experience"
        else:
            return "Strong technical background, 2+ years experience"

    def _generate_generic_requirements(self, title: str) -> str:
        """Generate requirements based on job title"""
        title_lower = title.lower()
        
        if "data" in title_lower:
            return "Python, SQL, Pandas, 2+ years experience"
        elif "frontend" in title_lower or "react" in title_lower:
            return "JavaScript, React, HTML/CSS, 2+ years experience"
        elif "backend" in title_lower:
            return "Python/Java, APIs, Databases, 2+ years experience"
        elif "devops" in title_lower:
            return "AWS, Docker, CI/CD, 2+ years experience"
        else:
            return "Programming experience, 2+ years in relevant technologies"

    def _deduplicate_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate jobs"""
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            key = f"{job['title'].lower()}-{job['company'].lower()}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        return unique_jobs

    async def _get_indeed_company_url(self, page, job_href: str) -> Optional[str]:
        """Extract company application URL from Indeed job page"""
        try:
            job_url = job_href if job_href.startswith('http') else f"https://www.indeed.com{job_href}"
            new_page = await page.context.new_page()
            await new_page.goto(job_url)
            await new_page.wait_for_load_state('networkidle')
            
            # Look for external apply links
            external_links = new_page.locator('a[href]:has-text("Apply on"), a[href]:has-text("Company website"), a[href*="apply"]:not([href*="indeed.com"])')
            
            for i in range(await external_links.count()):
                link = external_links.nth(i)
                href = await link.get_attribute('href')
                
                if href and 'indeed.com' not in href and any(domain in href for domain in ['.com', '.org', '.net']):
                    await new_page.close()
                    return href
            
            await new_page.close()
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to get Indeed company URL: {e}")
            return None

    async def _save_scraped_jobs(self, jobs: List[Dict[str, Any]]):
        """Save scraped jobs to database and queue"""
        for job in jobs:
            try:
                job_id = await self.queue.add_job(job)
                await self.db.add_job(job_id, job)
                logger.info(f"💾 Saved job: {job['title']} at {job['company']}")
            except Exception as e:
                logger.error(f"❌ Failed to save job: {e}")

    async def cleanup(self):
        """Cleanup scraper resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("🧹 Real job scraper cleaned up")