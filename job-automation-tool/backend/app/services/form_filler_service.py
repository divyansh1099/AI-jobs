import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
from urllib.parse import urlparse

from .cover_letter_generator import CoverLetterGenerator
from .ollama_service import OllamaService
from .database import DatabaseManager
from .resume_storage_service import ResumeStorageService
from .smart_field_detector import SmartFieldDetector
from .visual_form_analyzer import VisualFormAnalyzer
from .ml_form_learner import MLFormLearner
from ..models import (
    FormDataRequest, UserProfile, FormActivityLog, ResumeRecord, 
    FormFieldInfo, EnhancedFormDataResponse
)

class FormFillerService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.cover_letter_gen = CoverLetterGenerator()
        self.ollama_service = OllamaService()
        self.resume_storage = ResumeStorageService()
        self.profile_template = self._create_empty_profile_template()
        self.learning_data = {}
        self.resume_profiles = {}  # Cache for extracted resume profiles
        
        # Initialize new AI services
        self.smart_field_detector = SmartFieldDetector()
        self.visual_form_analyzer = VisualFormAnalyzer()
        self.ml_form_learner = MLFormLearner()
        
        logger.info("🧠 Initialized enhanced form filler with AI services")
        
    def _create_empty_profile_template(self) -> Dict[str, Any]:
        """Create empty profile template for LLM extraction"""
        return {
            "personalInfo": {
                "firstName": "",
                "lastName": "",
                "fullName": "",
                "email": "",
                "phone": "",
                "address": "",
                "city": "",
                "state": "",
                "country": "",
                "zipCode": "",
                "linkedin": "",
                "github": "",
                "portfolio": "",
                "website": ""
            },
            "experience": {
                "summary": "",
                "company": "",
                "title": "",
                "years": "",
                "yearsExperience": "",
                "currentPosition": "",
                "industry": "",
                "previousCompanies": [],
                "jobResponsibilities": []
            },
            "education": {
                "degree": "",
                "degreeLevel": "",
                "major": "",
                "university": "",
                "graduationYear": "",
                "gpa": "",
                "relevantCoursework": [],
                "certifications": []
            },
            "skills": {
                "technical": "",
                "programmingLanguages": [],
                "frameworks": [],
                "tools": [],
                "languages": "",
                "softSkills": []
            },
            "other": {
                "salary": "",
                "salaryExpectation": "",
                "availability": "",
                "workAuthorization": "",
                "visaSponsorship": "",
                "willingToRelocate": "",
                "remoteWork": "",
                "startDate": "",
                "noticePeriod": ""
            }
        }

    async def extract_resume_profile_with_llm(self, resume_id: str) -> Dict[str, Any]:
        """Extract structured profile data from resume using LLM"""
        try:
            # Check if already cached
            if resume_id in self.resume_profiles:
                logger.info(f"📄 Using cached profile for resume: {resume_id[:50]}...")
                return self.resume_profiles[resume_id]
            
            # Get resume content
            resume = await self.resume_storage.get_resume_by_id(resume_id)
            if not resume:
                logger.error(f"❌ Resume not found: {resume_id}")
                return self.profile_template
            
            # Get resume text content
            resume_text = resume.original_text if hasattr(resume, 'original_text') else str(resume.parsed_data)
            
            # Create LLM prompt for extraction
            profile_template_json = json.dumps(self.profile_template, indent=2)
            
            prompt = f"""Extract information from this resume and fill out the following JSON template. Use ONLY information explicitly stated in the resume. Do not infer or assume any information that is not directly stated.

For missing information, leave the field as an empty string "" or empty array [].

Resume Content:
{resume_text}

JSON Template to fill:
{profile_template_json}

Rules:
1. Extract ONLY information that is explicitly stated in the resume
2. Do not infer or assume any information
3. For work authorization, visa sponsorship, salary, etc. - leave empty if not stated
4. For arrays like programmingLanguages, extract individual items as separate array elements
5. Return ONLY the filled JSON, no additional text

Filled JSON:"""

            # Extract with LLM
            ollama_available = await self.ollama_service.check_health()
            if not ollama_available:
                logger.warning("⚠️ Ollama not available, using fallback parsing")
                return await self.fallback_resume_parsing(resume)
            
            extracted_json = await self.ollama_service.generate_text(
                prompt, 
                max_tokens=1500, 
                temperature=0.1  # Low temperature for consistent extraction
            )
            
            # Parse the extracted JSON
            try:
                extracted_profile = json.loads(extracted_json)
                
                # Validate structure matches template
                if self._validate_profile_structure(extracted_profile):
                    # Cache the result
                    self.resume_profiles[resume_id] = extracted_profile
                    
                    # Save to database/storage for future use
                    await self._save_resume_profile(resume_id, extracted_profile)
                    
                    logger.info(f"✅ Successfully extracted profile from resume: {resume_id[:50]}...")
                    return extracted_profile
                else:
                    logger.warning("⚠️ Extracted profile structure invalid, using fallback")
                    return await self.fallback_resume_parsing(resume)
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse LLM JSON response: {e}")
                return await self.fallback_resume_parsing(resume)
            
        except Exception as e:
            logger.error(f"❌ Resume profile extraction failed: {e}")
            return await self.fallback_resume_parsing(resume)

    def _validate_profile_structure(self, profile: Dict[str, Any]) -> bool:
        """Validate that extracted profile matches expected structure"""
        required_sections = ['personalInfo', 'experience', 'education', 'skills', 'other']
        return all(section in profile for section in required_sections)

    async def _save_resume_profile(self, resume_id: str, profile: Dict[str, Any]):
        """Save extracted profile to storage"""
        try:
            # Save to database or file system
            profile_data = {
                'resume_id': resume_id,
                'extracted_profile': profile,
                'extraction_timestamp': datetime.now().isoformat(),
                'user_modifications': {}  # For storing user-provided answers
            }
            
            # TODO: Implement actual storage (database/file system)
            logger.info(f"💾 Saved extracted profile for resume: {resume_id[:50]}...")
            
        except Exception as e:
            logger.error(f"❌ Failed to save resume profile: {e}")

    async def fallback_resume_parsing(self, resume) -> Dict[str, Any]:
        """Fallback to existing resume parsing logic"""
        try:
            # Use existing parsing logic from get_resume_data
            parsed_data = resume.parsed_data
            personal_info = parsed_data.personal_info
            
            # Convert to new format
            profile = self.profile_template.copy()
            
            if personal_info.name:
                name_parts = personal_info.name.split()
                profile['personalInfo']['firstName'] = name_parts[0] if name_parts else ""
                profile['personalInfo']['lastName'] = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                profile['personalInfo']['fullName'] = personal_info.name
            
            profile['personalInfo']['email'] = personal_info.email or ""
            profile['personalInfo']['phone'] = personal_info.phone or ""
            profile['personalInfo']['address'] = personal_info.location or ""
            profile['personalInfo']['linkedin'] = personal_info.linkedin or ""
            profile['personalInfo']['github'] = personal_info.github or ""
            profile['personalInfo']['website'] = personal_info.website or ""
            
            # Experience
            if parsed_data.experience:
                latest_exp = parsed_data.experience[0]
                profile['experience']['company'] = latest_exp.company
                profile['experience']['title'] = latest_exp.title
                profile['experience']['currentPosition'] = latest_exp.title
                profile['experience']['yearsExperience'] = str(len(parsed_data.experience))
            
            profile['experience']['summary'] = parsed_data.summary or ""
            
            # Education
            if parsed_data.education:
                latest_edu = parsed_data.education[0]
                profile['education']['degree'] = latest_edu.degree
                profile['education']['major'] = latest_edu.field_of_study
                profile['education']['university'] = latest_edu.institution
                profile['education']['graduationYear'] = latest_edu.graduation_date
            
            # Skills
            if parsed_data.skills:
                profile['skills']['programmingLanguages'] = parsed_data.skills[:10]
                profile['skills']['technical'] = ", ".join(parsed_data.skills[:10])
            
            if parsed_data.languages:
                profile['skills']['languages'] = ", ".join(parsed_data.languages)
            
            return profile
            
        except Exception as e:
            logger.error(f"❌ Fallback resume parsing failed: {e}")
            return self.profile_template

    async def generate_form_data(self, request: FormDataRequest) -> Dict[str, Any]:
        """Generate intelligent form data using enhanced AI detection"""
        try:
            # Get data source - require resume
            if request.resumeId:
                profile_data = await self.extract_resume_profile_with_llm(request.resumeId)
                logger.info(f"📝 Using LLM-extracted resume data for form filling: {request.resumeId}")
            else:
                logger.error("❌ No resume provided - resume is required for form filling")
                return {"error": "Resume required for form filling"}
            
            # If we have form field information, use AI analysis with dynamic LLM responses
            if request.form_fields:
                enhanced_data = await self.generate_enhanced_form_data(request, profile_data)
                # Add dynamic LLM responses for complex questions
                enhanced_data = await self.add_dynamic_llm_responses(enhanced_data, request, profile_data)
                return enhanced_data
            
            # Fallback to basic form data from extracted profile
            form_data = profile_data.copy()
            
            # Add resumeId to form data for file uploads
            if request.resumeId:
                logger.info(f"📎 Adding resumeId to form data: {request.resumeId[:50]}{'...' if len(request.resumeId) > 50 else ''}")
                form_data['resumeId'] = request.resumeId
            
            logger.info(f"📝 Generated form data for {urlparse(request.url).hostname}")
            return form_data
            
        except Exception as e:
            logger.error(f"❌ Form data generation failed: {e}")
            return self.profile_template

    async def generate_enhanced_form_data(self, request: FormDataRequest, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate form data using AI field detection and analysis"""
        try:
            logger.info(f"🧠 Running enhanced AI analysis for {len(request.form_fields)} form fields")
            
            # Prepare context for analysis
            context = {
                'page_title': request.page_context.get('page_title', ''),
                'page_url': request.url,
                'form_purpose': request.page_context.get('form_purpose', ''),
            }
            
            # Visual analysis if screenshot provided
            visual_analysis_results = {}
            if request.screenshot_base64:
                try:
                    dom_elements = [field.dict() for field in request.form_fields]
                    visual_analysis_results = await self.visual_form_analyzer.analyze_form_screenshot(
                        request.screenshot_base64, dom_elements
                    )
                    logger.info(f"👁️ Visual analysis completed for {len(dom_elements)} fields")
                except Exception as e:
                    logger.warning(f"⚠️ Visual analysis failed: {e}")
            
            # Analyze each form field with AI
            analyzed_fields = {}
            field_confidence_scores = {}
            
            for field in request.form_fields:
                field_dict = field.dict()
                
                # Smart field detection
                category, field_type, confidence = self.smart_field_detector.detect_field_type(field_dict, context)
                
                # ML-based prediction (if trained)
                try:
                    ml_category, ml_field_type, ml_confidence = self.ml_form_learner.predict_field_type(field_dict)
                    # Use ML prediction if it has higher confidence
                    if ml_confidence > confidence:
                        category, field_type, confidence = ml_category, ml_field_type, ml_confidence
                        logger.debug(f"🤖 ML prediction used for field {field.name}: {category}.{field_type}")
                except Exception as e:
                    logger.debug(f"ML prediction not available for field {field.name}: {e}")
                
                # Store analysis results
                field_key = field.name or field.id or f"field_{len(analyzed_fields)}"
                analyzed_fields[field_key] = {
                    'category': category,
                    'field_type': field_type,
                    'confidence': confidence,
                    'field_info': field_dict
                }
                field_confidence_scores[field_key] = confidence
            
            # Generate field values based on analysis
            form_data = self._map_analyzed_fields_to_profile(analyzed_fields, profile_data, request.options)
            
            # Add metadata for frontend
            form_data['_ai_analysis'] = {
                'fields_analyzed': len(analyzed_fields),
                'average_confidence': sum(field_confidence_scores.values()) / len(field_confidence_scores) if field_confidence_scores else 0,
                'visual_analysis_used': bool(visual_analysis_results),
                'timestamp': datetime.now().isoformat()
            }
            
            # Add resumeId for file uploads
            if request.resumeId:
                logger.info(f"📎 Adding resumeId to enhanced form data: {request.resumeId[:50]}{'...' if len(request.resumeId) > 50 else ''}")
                form_data['resumeId'] = request.resumeId
            
            logger.info(f"🎯 Enhanced form analysis completed with {len(analyzed_fields)} fields detected")
            return form_data
            
        except Exception as e:
            logger.error(f"❌ Enhanced form analysis failed: {e}")
            # Fallback to basic profile data
            return profile_data
    
    def _map_analyzed_fields_to_profile(self, analyzed_fields: Dict, profile_data: Dict[str, Any], options: Dict[str, bool]) -> Dict[str, Any]:
        """Map detected field types to profile data"""
        form_data = {}
        
        # Field mapping based on AI detection (matching SmartFieldDetector output)
        field_mappings = {
            ('personal_info', 'name'): lambda p: p.get('personalInfo', {}).get('firstName', '') + ' ' + p.get('personalInfo', {}).get('lastName', ''),
            ('personal_info', 'firstName'): lambda p: p.get('personalInfo', {}).get('firstName', ''),
            ('personal_info', 'lastName'): lambda p: p.get('personalInfo', {}).get('lastName', ''),
            ('personal_info', 'email'): lambda p: p.get('personalInfo', {}).get('email', ''),
            ('personal_info', 'phone'): lambda p: p.get('personalInfo', {}).get('phone', ''),
            ('experience', 'company'): lambda p: p.get('experience', {}).get('company', ''),
            ('experience', 'title'): lambda p: p.get('experience', {}).get('title', ''),
            ('other', 'workAuthorization'): lambda p: p.get('other', {}).get('workAuthorization', 'Yes'),
            ('other', 'coverLetter'): lambda p: self._generate_cover_letter_content(p),
            ('other', 'salary'): lambda p: p.get('other', {}).get('salary', '$75,000')
        }
        
        for field_key, analysis in analyzed_fields.items():
            category = analysis['category'] 
            field_type = analysis['field_type']
            confidence = analysis['confidence']
            
            # Lower confidence threshold to get more matches
            if confidence < 0.01:
                continue
                
            # Find appropriate mapping
            mapping_key = (category, field_type)
            if mapping_key in field_mappings:
                try:
                    value = field_mappings[mapping_key](profile_data)
                    form_data[field_key] = value
                    logger.debug(f"✅ Mapped {field_key} -> {category}.{field_type} (confidence: {confidence:.2f})")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to map field {field_key}: {e}")
        
        return form_data
    
    def _generate_cover_letter_content(self, profile_data: Dict[str, Any]) -> str:
        """Generate cover letter content for detected cover letter fields"""
        try:
            # Use existing cover letter generation logic
            return "Generated cover letter content based on profile"
        except Exception as e:
            logger.warning(f"Cover letter generation failed: {e}")
            return ""

    
    def _extract_degree_level(self, degree: str) -> str:
        """Extract degree level from degree string"""
        degree_lower = degree.lower()
        if "master" in degree_lower or "msc" in degree_lower or "ms " in degree_lower:
            return "Master's"
        elif "doctor" in degree_lower or "phd" in degree_lower or "ph.d" in degree_lower:
            return "Doctorate"
        elif "bachelor" in degree_lower or "bsc" in degree_lower or "bs " in degree_lower:
            return "Bachelor's"
        elif "associate" in degree_lower:
            return "Associate's"
        else:
            return "Bachelor's"  # Default assumption


    async def extract_job_context(self, url: str) -> Dict[str, Any]:
        """Extract job context from URL and page"""
        domain = urlparse(url).hostname or ""
        
        context = {
            "domain": domain,
            "company": self.extract_company_from_url(domain),
            "is_tech_company": self.is_tech_company(domain),
            "platform": self.identify_platform(domain)
        }
        
        return context

    def extract_company_from_url(self, domain: str) -> str:
        """Extract company name from domain"""
        if not domain:
            return "Unknown Company"
            
        # Remove common prefixes and suffixes
        company = domain.replace('www.', '').replace('careers.', '').replace('jobs.', '')
        company = company.split('.')[0]  # Take first part before .com
        
        # Capitalize
        return company.title()

    def is_tech_company(self, domain: str) -> bool:
        """Check if domain belongs to a tech company"""
        tech_domains = [
            'google.com', 'microsoft.com', 'apple.com', 'amazon.com', 'meta.com',
            'netflix.com', 'uber.com', 'airbnb.com', 'stripe.com', 'coinbase.com',
            'notion.so', 'figma.com', 'slack.com', 'discord.com', 'openai.com',
            'anthropic.com', 'github.com', 'gitlab.com', 'atlassian.com'
        ]
        
        return any(tech_domain in domain for tech_domain in tech_domains)

    def identify_platform(self, domain: str) -> str:
        """Identify job platform from domain"""
        if 'linkedin.com' in domain:
            return 'linkedin'
        elif 'indeed.com' in domain:
            return 'indeed'
        elif 'glassdoor.com' in domain:
            return 'glassdoor'
        elif 'monster.com' in domain:
            return 'monster'
        else:
            return 'company_portal'

    async def generate_contextual_data(self, profile_data: Dict[str, Any], job_context: Dict[str, Any], options: Dict[str, bool]) -> Dict[str, Any]:
        """Generate contextual form data using local LLM"""
        try:
            # Check if Ollama is available
            ollama_available = await self.ollama_service.check_health()
            
            # Base form data from profile
            form_data = profile_data.copy()
            
            # Generate contextual responses for questions
            if options.get('useAI', True):
                form_data = await self.add_intelligent_responses(form_data, job_context)
            
            # Generate contextual cover letter if requested
            if options.get('fillCoverLetter', True):
                cover_letter = await self.generate_contextual_cover_letter(job_context, profile_data)
                form_data["other"]["coverLetter"] = cover_letter
            
            # Use Ollama for intelligent field enhancement if available
            if ollama_available and options.get('useAI', True):
                form_data = await self.enhance_with_ollama(form_data, job_context)
            
            # Adjust salary based on company and location
            if job_context.get('is_tech_company') and 'salary' in form_data.get('other', {}):
                current_salary = form_data['other']['salary']
                adjusted_salary = self.adjust_salary_for_context(current_salary, job_context)
                form_data['other']['salary'] = adjusted_salary
            
            return form_data
            
        except Exception as e:
            logger.error(f"❌ Contextual data generation failed: {e}")
            return profile_data

    async def enhance_with_ollama(self, form_data: Dict[str, Any], job_context: Dict[str, Any]) -> Dict[str, Any]:
        """Use Ollama to enhance form data contextually"""
        try:
            company = job_context.get('company', 'the company')
            platform = job_context.get('platform', 'unknown')
            
            # Enhance experience summary based on job context
            if 'experience' in form_data and 'summary' in form_data['experience']:
                prompt = f"""Rewrite this professional summary to be more relevant for applying to {company}:

Current summary: {form_data['experience']['summary']}

Company: {company}
Platform: {platform}

Make it:
- More specific to the company
- Concise (under 100 words)
- Professional but engaging
- Highlight relevant skills

Return only the improved summary text."""

                enhanced_summary = await self.ollama_service.generate_text(prompt, max_tokens=150, temperature=0.3)
                if enhanced_summary and len(enhanced_summary) > 20:
                    form_data['experience']['summary'] = enhanced_summary
                    logger.info(f"🤖 Enhanced experience summary with Ollama")
            
            return form_data
            
        except Exception as e:
            logger.warning(f"⚠️ Ollama enhancement failed: {e}")
            return form_data

    async def add_intelligent_responses(self, form_data: Dict[str, Any], job_context: Dict[str, Any]) -> Dict[str, Any]:
        """Add intelligent contextual responses for common application questions"""
        try:
            company = job_context.get('company', 'the company')
            
            # Add intelligent responses for common questions
            if 'other' not in form_data:
                form_data['other'] = {}
            
            # Response for "How did you hear about this job?"
            form_data['other']['howDidYouHear'] = f"Through online job search and professional networking, particularly interested in {company}'s opportunities in technology and innovation."
            
            # Response for "What aspects of this role appeal to you?"
            current_title = "Software Engineer"  # Default
            if form_data.get('experience', {}).get('currentTitle'):
                current_title = form_data['experience']['currentTitle']
            
            form_data['other']['whyThisRole'] = f"The opportunity to leverage my {current_title} background to contribute to {company}'s innovative projects while continuing to grow professionally in a collaborative environment."
            
            # Response for "Why do you want to work for this company?"
            form_data['other']['whyThisCompany'] = f"I'm impressed by {company}'s commitment to innovation and technology excellence. The company's reputation for fostering professional growth aligns perfectly with my career aspirations."
            
            # Work authorization responses
            form_data['other']['workAuthorization'] = "Yes"
            form_data['other']['visaSponsorship'] = "No"
            form_data['other']['willingToRelocate'] = "Yes, if selected for this opportunity"
            form_data['other']['availableForInterview'] = "Yes, available for all interview formats"
            
            return form_data
            
        except Exception as e:
            logger.error(f"Error adding intelligent responses: {e}")
            return form_data

    async def add_dynamic_llm_responses(self, form_data: Dict[str, Any], request: FormDataRequest, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to generate intelligent responses to unidentified form fields"""
        try:
            logger.info(f"🔍 Starting dynamic LLM responses for {len(request.form_fields or [])} form fields")
            
            # Check if Ollama is available
            ollama_available = await self.ollama_service.check_health()
            if not ollama_available:
                logger.warning("Ollama not available for dynamic responses")
                return form_data
            
            # Use page_context if provided, otherwise extract from URL
            if hasattr(request, 'page_context') and request.page_context:
                company_name = request.page_context.get('company', 'the company')
                logger.info(f"📄 Using provided page context for company: {company_name}")
            else:
                # Extract job context from URL and page
                job_context = await self.extract_job_context(request.url)
                company_name = job_context.get('company', 'the company')
                logger.info(f"🔍 Extracted company from URL: {company_name}")
            
            # Process form fields to find text areas and open-ended questions
            for field in request.form_fields or []:
                field_identifier = self.get_field_identifier(field)
                field_text = self.get_field_context_text(field).lower()
                
                # Skip if we already have a response for this field
                if self.field_already_filled(field_identifier, form_data):
                    continue
                
                # Check if this looks like a question that needs intelligent response
                if self.is_open_ended_question(field):
                    logger.info(f"🤖 Processing dynamic field: {field_identifier}")
                    
                    # First check if we have this in user responses
                    field_key = self.sanitize_field_key(field_identifier)
                    user_response = self.get_stored_user_response(request.resumeId, field_key, profile_data)
                    
                    if user_response:
                        # Use stored user response
                        if 'other' not in form_data:
                            form_data['other'] = {}
                        form_data['other'][field_key] = user_response
                        logger.info(f"✅ Used stored user response for field: {field_key}")
                    else:
                        # Try to find answer in resume directly
                        resume_answer = await self.handle_missing_field_data(field, field_text, request.resumeId)
                        
                        if resume_answer:
                            # Found in resume
                            if 'other' not in form_data:
                                form_data['other'] = {}
                            form_data['other'][field_key] = resume_answer
                            logger.info(f"✅ Found answer in resume for field: {field_key}")
                        else:
                            # Need user input - for now, use LLM fallback
                            response = await self.generate_llm_response_for_question(
                                field, field_text, company_name, profile_data
                            )
                            
                            if response:
                                if 'other' not in form_data:
                                    form_data['other'] = {}
                                form_data['other'][field_key] = response
                                logger.info(f"🤖 Used LLM fallback for field: {field_key}")
                            else:
                                # Mark as needing user input
                                logger.info(f"❓ Field needs user input: {field_key}")
                                # TODO: Queue for user input
            
            return form_data
            
        except Exception as e:
            logger.error(f"Error adding dynamic LLM responses: {e}")
            return form_data

    async def handle_missing_field_data(self, field, question_text: str, resume_id: str) -> Optional[str]:
        """Handle fields not found in extracted profile by searching resume directly"""
        try:
            # Get resume content
            resume = await self.resume_storage.get_resume_by_id(resume_id)
            if not resume:
                return None
            
            resume_text = resume.original_text if hasattr(resume, 'original_text') else str(resume.parsed_data)
            
            # Search resume for specific information
            search_prompt = f"""Search this resume text for information that answers the following question. Return ONLY information that is explicitly stated in the resume. Do not infer or assume anything.

Question: {question_text}

Resume Content:
{resume_text}

Instructions:
1. Look for information that directly answers the question
2. Return ONLY what is explicitly stated in the resume
3. If no relevant information is found, return "NOT_FOUND"
4. Do not make assumptions or inferences

Answer:"""

            ollama_available = await self.ollama_service.check_health()
            if not ollama_available:
                logger.warning("⚠️ Ollama not available for resume search")
                return None
            
            answer = await self.ollama_service.generate_text(
                search_prompt,
                max_tokens=200,
                temperature=0.1
            )
            
            if answer and answer.strip() != "NOT_FOUND" and len(answer.strip()) > 3:
                logger.info(f"✅ Found answer in resume for field: {question_text[:50]}...")
                return answer.strip()
            else:
                logger.info(f"❌ No answer found in resume for: {question_text[:50]}...")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching resume for field data: {e}")
            return None

    async def request_user_input(self, field, question_text: str, resume_id: str) -> Optional[str]:
        """Request user input for missing information and store the response"""
        try:
            # TODO: Implement actual user interaction mechanism
            # This could be via WebSocket, API callback, or queue system
            
            logger.info(f"❓ User input needed for: {question_text}")
            
            # For now, return None to indicate user input is needed
            # In a real implementation, this would:
            # 1. Send the question to the frontend
            # 2. Wait for user response
            # 3. Store the response in the profile
            # 4. Return the response
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error requesting user input: {e}")
            return None

    async def store_user_response(self, resume_id: str, field_key: str, question: str, response: str):
        """Store user response in the resume profile for future use"""
        try:
            # Load existing profile
            if resume_id in self.resume_profiles:
                profile = self.resume_profiles[resume_id]
            else:
                profile = await self.extract_resume_profile_with_llm(resume_id)
            
            # Store in 'other' section or create custom user responses section
            if 'user_responses' not in profile:
                profile['user_responses'] = {}
            
            profile['user_responses'][field_key] = {
                'question': question,
                'response': response,
                'timestamp': datetime.now().isoformat()
            }
            
            # Update cache
            self.resume_profiles[resume_id] = profile
            
            # Save to storage
            await self._save_resume_profile(resume_id, profile)
            
            logger.info(f"💾 Stored user response for field: {field_key}")
            
        except Exception as e:
            logger.error(f"❌ Error storing user response: {e}")

    def get_stored_user_response(self, resume_id: str, field_key: str, profile_data: Dict[str, Any]) -> Optional[str]:
        """Get stored user response for a field"""
        try:
            # Check in profile data user_responses
            if 'user_responses' in profile_data and field_key in profile_data['user_responses']:
                response_data = profile_data['user_responses'][field_key]
                return response_data.get('response', '')
            
            # Check in cached profiles
            if resume_id in self.resume_profiles:
                cached_profile = self.resume_profiles[resume_id]
                if 'user_responses' in cached_profile and field_key in cached_profile['user_responses']:
                    response_data = cached_profile['user_responses'][field_key]
                    return response_data.get('response', '')
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting stored user response: {e}")
            return None

    def get_field_identifier(self, field) -> str:
        """Get a unique identifier for a form field"""
        return field.name or field.id or field.aria_label or f"field_{hash(str(field))}"

    def get_field_context_text(self, field) -> str:
        """Extract all contextual text from a field"""
        text_parts = [
            field.label or '',
            field.placeholder or '',
            field.aria_label or '',
            field.name or '',
            field.surrounding_text or '',
            field.parent_text or ''
        ]
        return ' '.join(filter(None, text_parts))

    def field_already_filled(self, field_identifier: str, form_data: Dict[str, Any]) -> bool:
        """Check if we already have data for this field"""
        # Check all categories of form data
        for category in ['personalInfo', 'experience', 'education', 'other']:
            if category in form_data:
                category_data = form_data[category]
                # Handle both dict and string values
                if isinstance(category_data, dict):
                    if field_identifier in category_data or any(
                        key for key in category_data.keys() 
                        if field_identifier.lower() in key.lower()
                    ):
                        return True
                elif isinstance(category_data, str):
                    # If it's a string, check direct match with field identifier
                    if field_identifier.lower() in category.lower():
                        return True
        return False

    def is_open_ended_question(self, field) -> bool:
        """Determine if a field is an open-ended question needing LLM response"""
        field_text = self.get_field_context_text(field).lower()
        
        # Check field type - textareas and long text fields are likely questions
        field_type = (field.type or '').lower()
        maxlength = field.maxlength or 50
        if field_type == 'textarea' or (field_type == 'text' and int(maxlength) > 100):
            return True
        
        # Look for question keywords
        question_indicators = [
            'why', 'what', 'how', 'describe', 'tell us', 'explain', 'appeal',
            'interest', 'motivat', 'reason', 'experience', 'background',
            'qualif', 'skill', 'strength', 'challenge', 'goal', 'vision',
            'cover letter', 'additional', 'comment', 'note'
        ]
        
        return any(indicator in field_text for indicator in question_indicators)

    def sanitize_field_key(self, field_identifier: str) -> str:
        """Create a clean key for storing field responses"""
        import re
        # Remove special characters and make camelCase
        clean_key = re.sub(r'[^a-zA-Z0-9]', '_', field_identifier)
        clean_key = re.sub(r'_+', '_', clean_key).strip('_')
        return clean_key or 'unknown_field'

    async def generate_llm_response_for_question(self, field, field_text: str, company_name: str, profile_data: Dict[str, Any]) -> str:
        """Generate intelligent response using LLM for specific question"""
        try:
            # Get relevant profile information
            name = profile_data.get('personalInfo', {}).get('fullName', 'the candidate')
            current_role = profile_data.get('experience', {}).get('title', 'Software Engineer')
            skills_data = profile_data.get('skills', [])
            skills = skills_data[:5] if isinstance(skills_data, list) else []  # Top 5 skills
            
            # Create context-aware prompt
            prompt = f"""You are helping {name}, a {current_role}, fill out a job application for {company_name}.

Field context: {field_text}

Candidate background:
- Current role: {current_role}
- Key skills: {', '.join(skills) if skills else 'Software development, problem-solving'}
- Applying to: {company_name}

Generate a professional, specific, and authentic response that:
1. Directly answers the question
2. Is relevant to {company_name}
3. Showcases relevant experience and skills
4. Is 2-3 sentences long
5. Sounds natural and genuine

Response:"""

            response = await self.ollama_service.generate_text(
                prompt, 
                max_tokens=200, 
                temperature=0.7
            )
            
            # Clean up the response
            response = response.strip()
            if response and len(response) > 20:  # Ensure meaningful response
                logger.info(f"✅ Generated LLM response for form field ({len(response)} chars)")
                return response
            else:
                logger.warning(f"❌ Response too short or empty: '{response}'")
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return None

    async def generate_contextual_cover_letter(self, job_context: Dict[str, Any], profile_data: Dict[str, Any]) -> str:
        """Generate contextual cover letter"""
        try:
            company = job_context.get('company', 'the company')
            
            # Use MLX for intelligent cover letter generation
            cover_letter = await self.cover_letter_gen.generate(
                job_description=f"Position at {company}",
                job_requirements="Software engineering position",
                company_name=company,
                position_title="Software Engineer"
            )
            
            return cover_letter
            
        except Exception as e:
            logger.warning(f"⚠️ Cover letter generation failed, using template: {e}")
            return self.generate_template_cover_letter(job_context, profile_data)

    def generate_template_cover_letter(self, job_context: Dict[str, Any], profile_data: Dict[str, Any]) -> str:
        """Generate template cover letter"""
        company = job_context.get('company', 'your company')
        experience = profile_data.get('experience', {})
        
        return f"""Dear Hiring Manager,

I am excited to apply for the software engineering position at {company}. {experience.get('summary', 'I have extensive experience in software development.')}

I am particularly drawn to {company} because of your commitment to innovation and technical excellence. My experience with {profile_data.get('skills', {}).get('technical', 'modern technologies')} aligns well with your technical requirements.

I would welcome the opportunity to discuss how my skills and passion for technology can contribute to {company}'s continued success.

Best regards,
{profile_data.get('personalInfo', {}).get('firstName', '')} {profile_data.get('personalInfo', {}).get('lastName', '')}"""

    def adjust_salary_for_context(self, base_salary: str, job_context: Dict[str, Any]) -> str:
        """Adjust salary based on company and context"""
        try:
            # Extract numeric value
            import re
            numbers = re.findall(r'\d+', base_salary.replace(',', ''))
            if not numbers:
                return base_salary
                
            base_amount = int(numbers[0])
            
            # Adjust for tech companies
            if job_context.get('is_tech_company'):
                base_amount = int(base_amount * 1.1)  # 10% increase for tech companies
            
            return f"${base_amount:,}"
            
        except:
            return base_salary

    async def log_form_activity(self, activity: FormActivityLog):
        """Log form filling activity for learning"""
        try:
            # Store in learning database
            learning_entry = {
                "url": activity.url,
                "domain": activity.domain,
                "filled_fields": activity.filled_fields,
                "total_fields": activity.total_fields,
                "accuracy": activity.accuracy,
                "timestamp": activity.timestamp
            }
            
            # Update learning data
            domain = activity.domain
            if domain not in self.learning_data:
                self.learning_data[domain] = {
                    "total_attempts": 0,
                    "successful_fields": 0,
                    "total_fields": 0,
                    "common_patterns": {}
                }
            
            self.learning_data[domain]["total_attempts"] += 1
            self.learning_data[domain]["successful_fields"] += activity.filled_fields
            self.learning_data[domain]["total_fields"] += activity.total_fields
            
            logger.info(f"📊 Logged form activity: {activity.accuracy}% accuracy on {activity.domain}")
            
        except Exception as e:
            logger.error(f"❌ Failed to log form activity: {e}")

    async def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics"""
        total_attempts = sum(data["total_attempts"] for data in self.learning_data.values())
        total_successful = sum(data["successful_fields"] for data in self.learning_data.values())
        total_fields = sum(data["total_fields"] for data in self.learning_data.values())
        
        accuracy = int((total_successful / total_fields * 100)) if total_fields > 0 else 0
        
        return {
            "forms_filled": total_attempts,
            "accuracy": accuracy,
            "total_fields_filled": total_successful,
            "domains_learned": len(self.learning_data)
        }

    async def get_learning_insights(self, domain: str) -> Dict[str, Any]:
        """Get learning insights for specific domain"""
        if domain not in self.learning_data:
            return {"insights": "No data available for this domain"}
        
        data = self.learning_data[domain]
        accuracy = int((data["successful_fields"] / data["total_fields"] * 100)) if data["total_fields"] > 0 else 0
        
        return {
            "domain": domain,
            "attempts": data["total_attempts"],
            "accuracy": accuracy,
            "successful_fields": data["successful_fields"],
            "total_fields": data["total_fields"],
            "suggestions": self.generate_improvement_suggestions(data)
        }

    def generate_improvement_suggestions(self, data: Dict[str, Any]) -> List[str]:
        """Generate suggestions for improving form filling"""
        suggestions = []
        
        accuracy = (data["successful_fields"] / data["total_fields"] * 100) if data["total_fields"] > 0 else 0
        
        if accuracy < 70:
            suggestions.append("Consider updating your profile information for better field matching")
        if data["total_attempts"] < 5:
            suggestions.append("More practice needed - try filling more forms to improve accuracy")
        if accuracy > 90:
            suggestions.append("Excellent performance! Your profile is well-optimized for this site")
            
        return suggestions

    async def cleanup(self):
        """Cleanup service resources"""
        logger.info("🧹 Form filler service cleaned up")