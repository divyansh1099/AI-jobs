from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobPlatform(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    COMPANY_PORTAL = "company_portal"

class JobCreate(BaseModel):
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    platform: JobPlatform = Field(..., description="Job platform")
    url: str = Field(..., description="Job posting URL")
    description: Optional[str] = Field(None, description="Job description")
    requirements: Optional[str] = Field(None, description="Job requirements")
    location: Optional[str] = Field(None, description="Job location")
    salary_range: Optional[str] = Field(None, description="Salary range")

class JobResponse(BaseModel):
    id: str
    title: str
    company: str
    platform: str
    url: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    status: JobStatus
    created_at: datetime
    applied_at: Optional[datetime] = None
    cover_letter: Optional[str] = None
    application_result: Optional[Dict[str, Any]] = None

class AutomationStatus(BaseModel):
    running: bool
    stats: Dict[str, int]
    queue: List[JobResponse]

class UserResponseRequest(BaseModel):
    resume_id: str = Field(..., description="Resume ID")
    field_key: str = Field(..., description="Field identifier")
    question: str = Field(..., description="The question asked")
    response: str = Field(..., description="User's response")

class MissingFieldInfo(BaseModel):
    field_key: str = Field(..., description="Field identifier")
    question: str = Field(..., description="The question that needs answering")
    field_type: Optional[str] = Field(None, description="Type of field")
    required: bool = Field(False, description="Whether this field is required")

class ScrapingRequest(BaseModel):
    search_terms: List[str] = Field(default=["software engineer", "data engineer"])
    locations: List[str] = Field(default=["Remote", "San Francisco"])
    max_jobs_per_search: int = Field(default=10, ge=1, le=50)

class ApplicationStats(BaseModel):
    total: int = 0
    successful: int = 0
    failed: int = 0
    pending: int = 0
    processing: int = 0

class CoverLetterRequest(BaseModel):
    job_id: str
    job_description: str
    job_requirements: str
    company_name: str
    position_title: str

class CoverLetterResponse(BaseModel):
    job_id: str
    cover_letter: str
    generated_at: datetime

class FormFieldInfo(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    placeholder: Optional[str] = None
    label: Optional[str] = None
    classes: Optional[str] = None
    aria_label: Optional[str] = None
    title: Optional[str] = None
    surrounding_text: Optional[str] = None
    parent_text: Optional[str] = None
    sibling_text: Optional[str] = None
    pattern: Optional[str] = None
    required: Optional[bool] = False
    maxlength: Optional[str] = None
    value: Optional[str] = None

class FormAnalysisRequest(BaseModel):
    url: str
    page_title: Optional[str] = None
    form_fields: List[FormFieldInfo] = []
    screenshot_base64: Optional[str] = None
    form_purpose: Optional[str] = None

class FormDataRequest(BaseModel):
    profile: Optional[str] = "default"  # Keep for backward compatibility
    resumeId: Optional[str] = None  # New resume-based approach
    options: Dict[str, bool] = {}
    url: str
    timestamp: Optional[str] = None
    form_fields: Optional[List[FormFieldInfo]] = []  # Enhanced with field information
    page_context: Optional[Dict[str, str]] = {}  # Page title, form purpose, etc.
    screenshot_base64: Optional[str] = None  # For visual analysis

class EnhancedFormDataResponse(BaseModel):
    form_data: Dict[str, Any]
    field_analysis: List[Dict[str, Any]] = []
    confidence_scores: Dict[str, float] = {}
    suggestions: List[str] = []

class UserProfile(BaseModel):
    id: str
    name: str
    personal_info: Dict[str, str]
    experience: List[Dict[str, str]]
    education: List[Dict[str, str]]
    skills: List[str]
    preferences: Dict[str, Any]

class FormActivityLog(BaseModel):
    url: str
    domain: str
    filled_fields: int
    total_fields: int
    accuracy: int
    timestamp: str

# Resume-related models
class PersonalInfo(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None

class WorkExperience(BaseModel):
    company: str
    title: str
    duration: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None

class Education(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    graduation_date: Optional[str] = None
    gpa: Optional[str] = None
    location: Optional[str] = None

class Certification(BaseModel):
    name: str
    issuing_organization: str
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None

class ParsedResumeData(BaseModel):
    personal_info: PersonalInfo
    summary: Optional[str] = None
    experience: List[WorkExperience] = []
    education: List[Education] = []
    skills: List[str] = []
    certifications: List[Certification] = []
    projects: List[Dict[str, str]] = []
    languages: List[str] = []
    awards: List[str] = []

class ResumeUploadRequest(BaseModel):
    filename: str
    content_type: str

class ResumeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_filename: str
    upload_date: datetime = Field(default_factory=datetime.now)
    parsed_data: ParsedResumeData
    is_active: bool = False
    file_size: int
    content_type: str

class ResumeResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    upload_date: datetime
    is_active: bool
    file_size: int
    content_type: str
    parsed_summary: Optional[str] = None

class ResumeListResponse(BaseModel):
    resumes: List[ResumeResponse]
    active_resume_id: Optional[str] = None

class SetActiveResumeRequest(BaseModel):
    resume_id: str

# === Job Application Tracking Models ===

class JobApplication(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resume_id: str
    
    # Job details
    job_title: str
    company: str
    job_url: str
    job_description: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    
    # Application details  
    ats_platform: Optional[str] = None  # workday, greenhouse, etc.
    application_status: str = "applied"  # applied, interview, rejected, offer
    application_date: datetime = Field(default_factory=datetime.now)
    
    # Tracking metrics
    form_fields_detected: int = 0
    form_fields_filled: int = 0
    filling_accuracy: float = 0.0
    time_spent_seconds: int = 0
    
    # AI-generated content
    customized_resume_data: Optional[Dict[str, Any]] = None
    cover_letter: Optional[str] = None
    
    # Follow-up
    last_follow_up: Optional[datetime] = None
    notes: Optional[str] = None

class JobApplicationResponse(BaseModel):
    id: str
    job_title: str
    company: str
    job_url: str
    location: Optional[str] = None
    application_status: str
    application_date: datetime
    ats_platform: Optional[str] = None
    filling_accuracy: float
    time_spent_seconds: int

class ApplicationStatsResponse(BaseModel):
    total_applications: int
    applications_this_week: int
    average_accuracy: float
    time_saved_hours: float
    success_rate: float
    top_companies: List[Dict[str, Any]]
    applications_by_status: Dict[str, int]
    ats_platforms: Dict[str, int]

class ApplicationTrackingRequest(BaseModel):
    job_title: str
    company: str
    job_url: str
    job_description: Optional[str] = None
    location: Optional[str] = None
    ats_platform: Optional[str] = None
    form_fields_detected: int = 0
    form_fields_filled: int = 0
    time_spent_seconds: int = 0