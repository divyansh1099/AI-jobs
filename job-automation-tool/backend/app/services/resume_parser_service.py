"""
Resume parsing service using Ollama LLM to extract structured data from resume text
"""

import json
import re
from typing import Optional, Dict, Any
from loguru import logger
from app.models import ParsedResumeData, PersonalInfo, WorkExperience, Education, Certification
from app.services.ollama_service import OllamaService


class ResumeParserService:
    def __init__(self):
        self.ollama_service = OllamaService()
        
    async def parse_resume_text(self, resume_text: str) -> ParsedResumeData:
        """
        Parse resume text using Ollama LLM to extract structured data
        """
        try:
            logger.info("Starting resume parsing with Ollama LLM")
            
            # Store resume text for potential fallback skills extraction
            self.last_resume_text = resume_text
            
            # Create structured prompt for resume parsing
            prompt = self._create_parsing_prompt(resume_text)
            
            # Get LLM response
            response = await self.ollama_service.generate_text(prompt)
            
            # Parse the JSON response
            parsed_data = self._parse_llm_response(response, resume_text)
            
            logger.info("Successfully parsed resume data")
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parsing resume: {e}")
            # Return basic structure with extracted personal info as fallback
            return self._create_fallback_data(resume_text)
    
    def _create_parsing_prompt(self, resume_text: str) -> str:
        """
        Create a structured prompt for the LLM to parse resume data - optimized for token limits
        """
        prompt = f"""Extract resume data as JSON. Resume text:

{resume_text}

Return JSON in this format (use null for missing fields):
{{
    "personal_info": {{
        "name": "Full Name",
        "email": "email@example.com", 
        "phone": "+1-555-0123",
        "location": "City, State",
        "linkedin": "linkedin.com/in/profile",
        "github": "github.com/username",
        "website": "website.com"
    }},
    "summary": "Brief professional summary",
    "experience": [
        {{
            "company": "Company Name",
            "title": "Job Title", 
            "duration": "Jan 2020 - Present",
            "description": "Brief achievements"
        }}
    ],
    "education": [
        {{
            "institution": "University",
            "degree": "Degree",
            "field_of_study": "Field",
            "graduation_date": "2020"
        }}
    ],
    "skills": ["skill1", "skill2", "skill3"],
    "languages": ["English"],
    "projects": [],
    "certifications": [],
    "awards": []
}}

Only JSON, no other text:"""
        return prompt
    
    def _parse_llm_response(self, response: str, resume_text: str = "") -> ParsedResumeData:
        """
        Parse the LLM JSON response into structured data models
        """
        try:
            # Clean the response to extract JSON
            json_str = self._extract_json_from_response(response)
            parsed_json = json.loads(json_str)
            
            # Create structured models
            personal_info = PersonalInfo(**parsed_json.get("personal_info", {}))
            
            # Parse work experience
            experience = []
            for exp in parsed_json.get("experience", []):
                experience.append(WorkExperience(**exp))
            
            # Parse education
            education = []
            for edu in parsed_json.get("education", []):
                education.append(Education(**edu))
            
            # Parse certifications
            certifications = []
            certs_data = parsed_json.get("certifications", [])
            if certs_data:  # Check if not None
                for cert in certs_data:
                    certifications.append(Certification(**cert))
            
            # Use fallback skills extraction if JSON skills are empty/truncated
            json_skills = parsed_json.get("skills", [])
            if not json_skills or len(json_skills) < 3:
                logger.info("JSON skills empty/limited, using fallback extraction")
                fallback_skills = self._extract_skills_from_text(resume_text)
                json_skills = fallback_skills if fallback_skills else json_skills
            
            return ParsedResumeData(
                personal_info=personal_info,
                summary=parsed_json.get("summary"),
                experience=experience,
                education=education,
                skills=json_skills,
                certifications=certifications,
                projects=parsed_json.get("projects") or [],
                languages=parsed_json.get("languages") or [],
                awards=parsed_json.get("awards") or []
            )
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            logger.error(f"Response was: {response}")
            
            # Try hybrid parsing - extract what we can from partial JSON + fallback
            return self._hybrid_parsing_fallback(response, resume_text)
    
    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON from LLM response, handling potential extra text and malformed JSON
        """
        try:
            # Try to find complete JSON block
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # Try to parse it to validate
                json.loads(json_str)
                return json_str
        except json.JSONDecodeError:
            pass
        
        # If JSON is incomplete, try to fix common issues
        try:
            # Find the start of JSON
            start_idx = response.find('{')
            if start_idx == -1:
                raise ValueError("No JSON found in response")
            
            # Extract from start to end, but handle truncation
            json_str = response[start_idx:].strip()
            
            # Try to fix common JSON issues
            json_str = self._attempt_json_repair(json_str)
            
            # Validate fixed JSON
            json.loads(json_str)
            return json_str
            
        except (json.JSONDecodeError, ValueError):
            # If all else fails, assume entire response is JSON
            return response.strip()
    
    def _attempt_json_repair(self, json_str: str) -> str:
        """
        Attempt to repair common JSON formatting issues
        """
        logger.info("Attempting JSON repair...")
        
        # Remove incomplete strings at the end
        lines = json_str.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # If line has unterminated string, truncate before it
            if ('"' in line and 
                line.count('"') % 2 != 0 and  # Odd number of quotes (unterminated)
                not line.endswith('",') and not line.endswith('"') and 
                i > len(lines) - 5):  # Only check near the end
                logger.info(f"Found unterminated string, truncating at line: {line}")
                break
                
            cleaned_lines.append(line)
        
        # Rejoin lines
        json_str = '\n'.join(cleaned_lines)
        
        # Count braces to see if we need to close arrays and objects
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        
        # Remove trailing comma if present
        json_str = json_str.rstrip().rstrip(',')
        
        # Close any open arrays first
        if open_brackets > close_brackets:
            missing_brackets = open_brackets - close_brackets
            json_str += ']' * missing_brackets
            
        # Then close any open objects
        if open_braces > close_braces:
            missing_braces = open_braces - close_braces
            json_str += '}' * missing_braces
        
        # Fix trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix missing commas between array elements
        json_str = re.sub(r'}\s*\n\s*{', '},\n    {', json_str)
        
        logger.info(f"JSON repair completed, length: {len(json_str)}")
        return json_str
    
    def _extract_skills_from_text(self, resume_text: str) -> list:
        """Extract skills from resume text using pattern matching"""
        skills = []
        
        # Try multiple patterns for skills extraction - prioritize technical skills sections
        skills_patterns = [
            # Technical skills section
            r'(?:technical\s+skills?|programming\s+languages?)[:;\s]*\n?([^:]*?)(?:\n\n|\n(?:tools?|cloud|devops|projects?|experience|education)[:;\s])',
            # Skills section
            r'(?:^|\n)skills?[:;\s]*\n?([^:]*?)(?:\n\n|\n(?:projects?|experience|education|languages?|awards?)[:;\s])',
            # Technologies section  
            r'(?:^|\n)technologies?[:;\s]*\n?([^:]*?)(?:\n\n|\n(?:projects?|experience|education|languages?)[:;\s])',
            # Programming languages specifically
            r'programming\s+languages?[:;\s]*\n?([^:]*?)(?:\n\n|\n(?:frontend|backend|tools?)[:;\s])',
            # Frontend/Backend sections
            r'(?:frontend|backend)[:;\s]*([^:]*?)(?:\n\n|\n[A-Z])',
        ]
        
        for pattern in skills_patterns:
            skills_match = re.search(pattern, resume_text, re.IGNORECASE | re.DOTALL)
            if skills_match:
                skills_text = skills_match.group(1)
                # Split by common delimiters and clean
                skill_items = re.split(r'[,•·\n]', skills_text)
                for skill in skill_items:
                    skill = skill.strip()
                    # Enhanced filtering for technical skills
                    if (skill and len(skill) <= 30 and len(skill) >= 2 and
                        not any(word in skill.lower() for word in [
                            'tools', 'cloud', 'devops', '&', 'years', 'experience', 
                            'native', 'conversational', 'fluent', 'proficient',
                            'english', 'hindi', 'spanish', 'french', 'german', 'chinese'
                        ]) and
                        not skill.startswith(('(', '[', '{', '-')) and
                        not re.match(r'^[A-Z]{2,3}\s*\d{5}', skill) and  # Not ZIP codes
                        not '@' in skill):  # Not email addresses
                        skills.append(skill)
                        
                if skills and len(skills) >= 3:  # Only accept if we found a decent number of skills
                    break
        
        # Remove duplicates and limit
        skills = list(dict.fromkeys(skills))[:15]
        
        # If still no skills found, try broader search with supervised learning
        if not skills:
            logger.info("Using supervised keyword-based skills extraction...")
            
            # Enhanced tech keywords based on actual resume patterns
            tech_keywords = [
                # Programming Languages
                'Java', 'Python', 'C/C++', 'C++', 'TypeScript', 'JavaScript', 'Golang', 'Go',
                
                # Databases
                'MySQL', 'MongoDB', 'PostgreSQL', 'Oracle', 'SQL',
                
                # Frameworks & Libraries  
                'ReactJS', 'React', 'Spring Boot', 'Spring MVC', 'Flask', 'Django', 'Express',
                
                # Protocols & Data Formats
                'SOAP', 'REST', 'JSON', 'XML',
                
                # Testing & Build Tools
                'Cucumber', 'Gherkin', 'Maven', 'Gradle', 'JUnit', 'Mockito',
                
                # Logging & Monitoring
                'Log4J', 'Splunk', 'JMX',
                
                # Cloud & DevOps
                'AWS', 'Azure', 'Docker', 'Kubernetes', 'Jenkins', 'Terraform',
                
                # Messaging & Streaming
                'Kafka', 'XMPP',
                
                # Version Control & Tools
                'Git', 'GitHub', 'Postman', 'Jira', 'Confluence',
                
                # Analytics & Visualization
                'Pandas', 'NumPy', 'Tableau', 'Power BI',
                
                # Methodologies
                'Agile', 'SDLC'
            ]
            
            # Look for skills in the text with case-insensitive matching
            for keyword in tech_keywords:
                # Check for exact matches and common variations
                patterns = [
                    rf'\\b{re.escape(keyword)}\\b',
                    rf'\\b{re.escape(keyword.lower())}\\b',
                    rf'\\b{re.escape(keyword.upper())}\\b'
                ]
                
                for pattern in patterns:
                    if re.search(pattern, resume_text, re.IGNORECASE):
                        skills.append(keyword)
                        break  # Found it, don't check other patterns for same keyword
                    
            # Remove duplicates and limit
            skills = list(dict.fromkeys(skills))[:25]
        
        return skills
    
    def _hybrid_parsing_fallback(self, partial_response: str, resume_text: str) -> ParsedResumeData:
        """
        Hybrid parsing that extracts successful parts from partial LLM response + fallback
        """
        logger.info("Using hybrid parsing fallback...")
        
        # Try to extract individual sections that might have parsed successfully
        personal_info = None
        summary = None
        experience = []
        education = []
        
        try:
            # Look for personal_info section that often gets parsed successfully
            personal_match = re.search(r'"personal_info":\s*\{([^}]*)\}', partial_response, re.DOTALL)
            if personal_match:
                personal_json = "{" + personal_match.group(1) + "}"
                # Clean up the JSON
                personal_json = re.sub(r',\s*$', '', personal_json.strip())
                try:
                    personal_data = json.loads(personal_json)
                    personal_info = PersonalInfo(**personal_data)
                    logger.info("Successfully extracted personal_info from partial response")
                except:
                    pass
            
            # Look for summary
            summary_match = re.search(r'"summary":\s*"([^"]*)"', partial_response)
            if summary_match:
                summary = summary_match.group(1)
                logger.info("Successfully extracted summary from partial response")
            
            # Look for experience array
            exp_match = re.search(r'"experience":\s*\[(.*?)\]', partial_response, re.DOTALL)
            if exp_match:
                exp_content = exp_match.group(1)
                # Find individual experience objects
                exp_objects = re.findall(r'\{([^}]*)\}', exp_content)
                for exp_obj_content in exp_objects:
                    try:
                        exp_json = "{" + exp_obj_content + "}"
                        exp_json = re.sub(r',\s*$', '', exp_json.strip())
                        exp_data = json.loads(exp_json)
                        
                        # Ensure required fields exist with defaults
                        if 'company' not in exp_data or 'title' not in exp_data or 'duration' not in exp_data:
                            continue
                        if 'description' not in exp_data:
                            exp_data['description'] = None
                        
                        experience.append(WorkExperience(**exp_data))
                    except Exception as e:
                        logger.debug(f"Failed to parse experience object: {e}")
                        continue
                if experience:
                    logger.info(f"Successfully extracted {len(experience)} experience entries from partial response")
            
            # Look for education array
            edu_match = re.search(r'"education":\s*\[(.*?)\]', partial_response, re.DOTALL)
            if edu_match:
                edu_content = edu_match.group(1)
                edu_objects = re.findall(r'\{([^}]*)\}', edu_content)
                for edu_obj_content in edu_objects:
                    try:
                        edu_json = "{" + edu_obj_content + "}"
                        edu_json = re.sub(r',\s*$', '', edu_json.strip())
                        edu_data = json.loads(edu_json)
                        education.append(Education(**edu_data))
                    except:
                        continue
                if education:
                    logger.info(f"Successfully extracted {len(education)} education entries from partial response")
                    
        except Exception as e:
            logger.error(f"Error in hybrid parsing: {e}")
        
        # Use fallback for anything we couldn't extract
        if not personal_info:
            logger.info("Using fallback for personal_info")
            fallback_data = self._create_fallback_data(resume_text)
            personal_info = fallback_data.personal_info
        
        # Try to extract skills from LLM response first, then fallback
        skills = []
        try:
            # Look for skills array in the partial response - handle truncated arrays
            skills_match = re.search(r'"skills":\s*\[([^\]]*)', partial_response, re.DOTALL)
            if skills_match:
                skills_content = skills_match.group(1)
                # Extract quoted strings
                skill_items = re.findall(r'"([^"]+)"', skills_content)
                skills = [skill.strip() for skill in skill_items if skill.strip()]
                logger.info(f"Successfully extracted {len(skills)} skills from partial LLM response: {skills[:5]}")
        except Exception as e:
            logger.debug(f"Error extracting skills from partial response: {e}")
        
        # Always supplement with fallback extraction to get comprehensive skills
        logger.info("Using fallback skills extraction to supplement LLM skills")
        fallback_skills = self._extract_skills_from_text(resume_text)
        
        # Combine LLM skills + fallback skills and deduplicate
        all_skills = skills + fallback_skills
        skills = list(dict.fromkeys(all_skills))[:25]
        logger.info(f"Final combined skills ({len(skills)}): {skills[:10]}")
        
        return ParsedResumeData(
            personal_info=personal_info,
            summary=summary,
            experience=experience,
            education=education,
            skills=skills,
            certifications=[],  # Could be enhanced to extract from partial response
            projects=[],  # Could be enhanced to extract from partial response
            languages=[],  # Could be enhanced to extract from partial response
            awards=[]  # Could be enhanced to extract from partial response
        )
    
    def _create_fallback_data(self, resume_text: str) -> ParsedResumeData:
        """
        Create fallback data structure when LLM parsing fails - enhanced extraction
        """
        logger.info("Using enhanced fallback data extraction...")
        
        # Enhanced extraction using regex patterns
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', resume_text)
        
        # Better phone number extraction
        phone_patterns = [
            r'\+?1[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            r'📱\s*([+0-9\-.\s()]+)',
            r'phone:?\s*([+0-9\-.\s()]+)',
            r'mobile:?\s*([+0-9\-.\s()]+)',
        ]
        phone_match = None
        for pattern in phone_patterns:
            phone_match = re.search(pattern, resume_text, re.IGNORECASE)
            if phone_match:
                break
        
        # Extract LinkedIn
        linkedin_patterns = [
            r'linkedin\.com/in/([a-zA-Z0-9\-_]+)',
            r'💼\s*(linkedin\.com/in/[a-zA-Z0-9\-_]+)',
            r'linkedin:?\s*(linkedin\.com/in/[a-zA-Z0-9\-_]+)',
        ]
        linkedin_match = None
        for pattern in linkedin_patterns:
            linkedin_match = re.search(pattern, resume_text, re.IGNORECASE)
            if linkedin_match:
                break
        
        # Extract GitHub
        github_patterns = [
            r'github\.com/([a-zA-Z0-9\-_]+)',
            r'👨‍💻\s*(github\.com/[a-zA-Z0-9\-_]+)',
            r'github:?\s*(github\.com/[a-zA-Z0-9\-_]+)',
        ]
        github_match = None
        for pattern in github_patterns:
            github_match = re.search(pattern, resume_text, re.IGNORECASE)
            if github_match:
                break
        
        # Extract location
        location_patterns = [
            r'📍\s*([A-Za-z\s,]+\d{5})',
            r'location:?\s*([A-Za-z\s,]+\d{5})',
            r'([A-Za-z\s]+,\s*[A-Z]{2}\s*\d{5})',
        ]
        location_match = None
        for pattern in location_patterns:
            location_match = re.search(pattern, resume_text, re.IGNORECASE)
            if location_match:
                break
        
        # Extract name (first non-empty line that looks like a name)
        lines = resume_text.strip().split('\n')
        potential_name = "Unknown"
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line and not any(char in line for char in ['@', '📧', '📱', '📍', '💼', '👨‍💻']):
                # Remove common prefixes/suffixes
                line = re.sub(r'^(mr\.?|ms\.?|dr\.?)\s*', '', line, flags=re.IGNORECASE)
                if len(line.split()) >= 2 and len(line) <= 50:  # Reasonable name length
                    potential_name = line
                    break
        
        # Extract skills using the enhanced extraction method
        skills = self._extract_skills_from_text(resume_text)
        
        personal_info = PersonalInfo(
            name=potential_name,
            email=email_match.group(0) if email_match else None,
            phone=phone_match.group(0) if phone_match else None,
            location=location_match.group(1) if location_match else None,
            linkedin=f"https://{linkedin_match.group(0)}" if linkedin_match else None,
            github=f"https://{github_match.group(0)}" if github_match else None,
            website=None  # Could add website extraction too
        )
        
        logger.info(f"Fallback extraction - Name: {personal_info.name}, Email: {personal_info.email}, Phone: {personal_info.phone}, Skills: {len(skills)}")
        
        return ParsedResumeData(
            personal_info=personal_info,
            summary=None,
            experience=[],
            education=[],
            skills=skills[:10],  # Limit to first 10 skills
            certifications=[],
            projects=[],
            languages=[],
            awards=[]
        )
    
    async def extract_resume_summary(self, parsed_data: ParsedResumeData) -> str:
        """
        Generate a concise summary of the parsed resume for display purposes
        """
        try:
            name = parsed_data.personal_info.name
            experience_count = len(parsed_data.experience)
            skills_count = len(parsed_data.skills)
            education_count = len(parsed_data.education)
            
            # Get latest job title if available
            latest_title = ""
            if parsed_data.experience:
                latest_title = f", {parsed_data.experience[0].title}"
            
            summary = f"{name}{latest_title} • {experience_count} jobs • {skills_count} skills • {education_count} degrees"
            return summary
            
        except Exception as e:
            logger.error(f"Error creating resume summary: {e}")
            return "Resume summary unavailable"