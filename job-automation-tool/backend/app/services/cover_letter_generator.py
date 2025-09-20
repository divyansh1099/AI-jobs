import asyncio
import aiohttp
import json
from typing import Dict, Any
from loguru import logger

class CoverLetterGenerator:
    def __init__(self):
        self.model_name = "qwen2.5:3b"  # Ollama model
        self.max_tokens = 512
        self.ollama_url = "http://localhost:11434"
        self.templates = {
            "software_engineer": {
                "intro": "I am writing to express my strong interest in the {position} role at {company}.",
                "experience": "With my experience in software development, I have developed expertise in {technologies}.",
                "motivation": "I am particularly drawn to {company} because of your innovative approach to technology.",
                "closing": "I would welcome the opportunity to discuss how my skills can contribute to your team's success."
            },
            "data_engineer": {
                "intro": "I am excited to apply for the {position} position at {company}.",
                "experience": "My experience in data engineering has equipped me with strong skills in {technologies}.",
                "motivation": "I am impressed by {company}'s commitment to data-driven solutions.",
                "closing": "I look forward to discussing how my background aligns with your team's needs."
            }
        }

    async def generate(self, job_description: str, job_requirements: str, 
                      company_name: str, position_title: str) -> str:
        """Generate cover letter using Ollama local LLM"""
        try:
            # Try Ollama first
            return await self._generate_with_ollama(
                job_description, job_requirements, company_name, position_title
            )
        except Exception as e:
            logger.warning(f"⚠️ Ollama generation failed, using template: {e}")
            return self._generate_with_template(
                job_description, job_requirements, company_name, position_title
            )

    async def _generate_with_ollama(self, job_description: str, job_requirements: str,
                                   company_name: str, position_title: str) -> str:
        """Generate cover letter using Ollama local LLM"""
        prompt = f"""Generate a professional cover letter for this job application:

Job Title: {position_title}
Company: {company_name}
Job Description: {job_description}
Requirements: {job_requirements}

Requirements:
- Keep it concise (3-4 paragraphs, under 300 words)
- Match the tone to the company culture
- Highlight relevant experience and skills
- Be specific about why you're interested in this role
- End with a clear call to action
- Do not include placeholder text like [Your Name]

Return only the cover letter text, no additional formatting or explanations."""

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": 0.7
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        cover_letter = result.get('response', '').strip()
                        logger.info(f"✅ Ollama cover letter generated ({len(cover_letter)} chars)")
                        return cover_letter
                    else:
                        raise Exception(f"Ollama API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"❌ Ollama generation failed: {e}")
            raise

    def _generate_with_template(self, job_description: str, job_requirements: str,
                              company_name: str, position_title: str) -> str:
        """Generate cover letter using templates"""
        
        # Select appropriate template
        title_lower = position_title.lower()
        if "data" in title_lower and ("engineer" in title_lower or "analyst" in title_lower):
            template = self.templates["data_engineer"]
        else:
            template = self.templates["software_engineer"]
        
        # Extract technologies from requirements
        tech_keywords = ["Python", "JavaScript", "React", "Node.js", "SQL", "AWS", "Docker", "Kubernetes"]
        mentioned_techs = [tech for tech in tech_keywords if tech.lower() in job_requirements.lower()]
        technologies = ", ".join(mentioned_techs[:3]) if mentioned_techs else "modern technologies"
        
        # Build cover letter
        cover_letter = f"""Dear Hiring Manager,

{template['intro'].format(position=position_title, company=company_name)}

{template['experience'].format(technologies=technologies)}

{template['motivation'].format(company=company_name)}

{template['closing']}

Best regards,
[Your Name]"""

        logger.info(f"📝 Template cover letter generated ({len(cover_letter)} chars)")
        return cover_letter

    async def batch_generate(self, jobs: list) -> Dict[str, str]:
        """Generate cover letters for multiple jobs"""
        results = {}
        
        for job in jobs:
            try:
                cover_letter = await self.generate(
                    job.get("description", ""),
                    job.get("requirements", ""),
                    job["company"],
                    job["title"]
                )
                results[job["id"]] = cover_letter
            except Exception as e:
                logger.error(f"❌ Failed to generate cover letter for {job['id']}: {e}")
                results[job["id"]] = self._generate_fallback_cover_letter(job)
        
        return results

    def _generate_fallback_cover_letter(self, job: Dict[str, Any]) -> str:
        """Simple fallback cover letter"""
        return f"""Dear Hiring Manager,

I am writing to express my interest in the {job['title']} position at {job['company']}.

My background in software development and problem-solving makes me a strong candidate for this role. I am excited about the opportunity to contribute to your team.

Thank you for your consideration.

Best regards,
[Your Name]"""