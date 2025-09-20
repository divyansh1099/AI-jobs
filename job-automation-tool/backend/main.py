from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
import uvicorn
import os
import uuid
from loguru import logger
import PyPDF2
import io
from typing import Optional

from app.models import (
    JobCreate, JobResponse, AutomationStatus, ScrapingRequest, FormDataRequest, FormActivityLog,
    ResumeRecord, ParsedResumeData, ResumeResponse, ResumeListResponse, SetActiveResumeRequest,
    FormAnalysisRequest, FormFieldInfo, EnhancedFormDataResponse, UserResponseRequest, MissingFieldInfo
)
from app.services.database import DatabaseManager
from app.services.job_queue import JobQueueManager
from app.services.automation import AutomationManager
from app.services.job_scraper import JobScraperService
from app.services.form_filler_service import FormFillerService
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_storage_service import ResumeStorageService
from app.core.config import settings

# Global managers
db_manager = None
queue_manager = None
automation_manager = None
scraper_service = None
form_filler_service = None
resume_parser_service = None
resume_storage_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_manager, queue_manager, automation_manager, scraper_service, form_filler_service, resume_parser_service, resume_storage_service
    
    logger.info("Starting Job Automation API server...")
    
    db_manager = DatabaseManager()
    await db_manager.initialize()
    
    queue_manager = JobQueueManager()
    await queue_manager.initialize(db_manager)
    
    automation_manager = AutomationManager(db_manager, queue_manager)
    scraper_service = JobScraperService(db_manager, queue_manager)
    form_filler_service = FormFillerService(db_manager)
    
    # Initialize resume services
    resume_parser_service = ResumeParserService()
    resume_storage_service = ResumeStorageService()
    await resume_storage_service.initialize_database()
    
    logger.info("✅ All services initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down services...")
    if automation_manager:
        await automation_manager.cleanup()
    if scraper_service:
        await scraper_service.cleanup()
    if form_filler_service:
        await form_filler_service.cleanup()

app = FastAPI(
    title="Job Automation Tool",
    description="Automated job application system with local LLM integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for React frontend and browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for extension compatibility
    allow_credentials=False,  # Disable credentials for simpler CORS
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/api/status")
async def get_status():
    """Get current automation status and statistics"""
    try:
        stats = await db_manager.get_application_stats()
        queue_jobs = await queue_manager.get_all_jobs()
        
        return {
            "running": automation_manager.is_running if automation_manager else False,
            "stats": stats,
            "queue": queue_jobs
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/start")
async def start_automation(background_tasks: BackgroundTasks):
    """Start the job automation process"""
    try:
        if automation_manager.is_running:
            return {"success": False, "message": "Automation already running"}
        
        background_tasks.add_task(automation_manager.start)
        logger.info("🚀 Automation started")
        
        return {"success": True, "message": "Automation started"}
    except Exception as e:
        logger.error(f"Error starting automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stop")
async def stop_automation():
    """Stop the job automation process"""
    try:
        await automation_manager.stop()
        logger.info("⏹️ Automation stopped")
        
        return {"success": True, "message": "Automation stopped"}
    except Exception as e:
        logger.error(f"Error stopping automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scrape")
async def scrape_jobs(request: ScrapingRequest, background_tasks: BackgroundTasks):
    """Scrape jobs from various platforms"""
    try:
        logger.info("🔍 Starting job scraping...")
        
        # Add scraping task to background
        background_tasks.add_task(
            scraper_service.scrape_jobs,
            request.search_terms,
            request.locations
        )
        
        return {
            "success": True,
            "message": "Job scraping started",
            "status": "processing"
        }
    except Exception as e:
        logger.error(f"Error starting scrape: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/add-sample-jobs")
async def add_sample_jobs():
    """Add sample jobs for testing"""
    try:
        sample_jobs = [
            {
                "title": "Software Engineer",
                "company": "Stripe",
                "platform": "linkedin",
                "description": "Build scalable web applications using React and Node.js",
                "requirements": "JavaScript, React, Node.js, 2+ years experience",
                "location": "Remote",
                "url": "https://stripe.com/jobs/listing/software-engineer"
            },
            {
                "title": "Data Engineer", 
                "company": "Airbnb",
                "platform": "indeed",
                "description": "Design and maintain data pipelines for analytics",
                "requirements": "Python, SQL, AWS, ETL experience",
                "location": "San Francisco",
                "url": "https://careers.airbnb.com/positions/data-engineer"
            },
            {
                "title": "Full Stack Developer",
                "company": "Notion",
                "platform": "linkedin",
                "description": "Join our growing team to build innovative products",
                "requirements": "JavaScript, Python, React, PostgreSQL",
                "location": "Remote",
                "url": "https://www.notion.so/careers/full-stack-engineer"
            }
        ]
        
        added_count = 0
        for job_data in sample_jobs:
            job_id = await queue_manager.add_job(job_data)
            await db_manager.add_job(job_id, job_data)
            added_count += 1
            logger.info(f"📋 Added sample job: {job_data['title']} at {job_data['company']}")
        
        logger.info(f"✅ Added {added_count} sample jobs")
        
        return {
            "success": True, 
            "message": f"Added {added_count} sample jobs",
            "jobs_added": added_count
        }
    except Exception as e:
        logger.error(f"Error adding sample jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs")
async def get_jobs():
    """Get all jobs in the system"""
    try:
        jobs = await db_manager.get_all_jobs()
        return {"jobs": jobs}
    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a specific job"""
    try:
        await db_manager.delete_job(job_id)
        await queue_manager.remove_job(job_id)
        
        logger.info(f"🗑️ Deleted job: {job_id}")
        return {"success": True, "message": "Job deleted"}
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear-jobs")
async def clear_all_jobs():
    """Clear all jobs from database and queue"""
    try:
        await queue_manager.clear_queue()
        
        # Clear database
        async with db_manager.connection.execute("DELETE FROM jobs") as cursor:
            pass
        await db_manager.connection.commit()
        
        logger.info("🧹 All jobs cleared")
        return {"success": True, "message": "All jobs cleared"}
    except Exception as e:
        logger.error(f"Error clearing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Browser Extension API Endpoints
@app.get("/api/health")
async def health_check():
    """Health check for browser extension"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/generate-form-data")
async def generate_form_data(request: FormDataRequest):
    """Generate intelligent form data for browser extension with AI field detection"""
    try:
        form_data = await form_filler_service.generate_form_data(request)
        logger.info(f"📝 Generated form data for {request.url}")
        return form_data
    except Exception as e:
        logger.error(f"Error generating form data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze-form")
async def analyze_form(request: FormAnalysisRequest):
    """Analyze form fields using AI without generating form data"""
    try:
        # Run analysis only
        context = {
            'page_title': request.page_title or '',
            'page_url': request.url,
            'form_purpose': request.form_purpose or ''
        }
        
        analysis_results = []
        for field in request.form_fields:
            field_dict = field.dict()
            category, field_type, confidence = form_filler_service.smart_field_detector.detect_field_type(field_dict, context)
            
            analysis_results.append({
                'field_id': field.id,
                'field_name': field.name,
                'detected_category': category,
                'detected_type': field_type,
                'confidence': confidence
            })
        
        logger.info(f"🔍 Analyzed {len(request.form_fields)} form fields")
        return {
            'url': request.url,
            'fields_analyzed': len(request.form_fields),
            'analysis_results': analysis_results,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error analyzing form: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/log-form-activity")
async def log_form_activity(activity: FormActivityLog):
    """Log form filling activity for learning"""
    try:
        await form_filler_service.log_form_activity(activity)
        return {"success": True, "message": "Activity logged"}
    except Exception as e:
        logger.error(f"Error logging form activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user-stats")
async def get_user_stats():
    """Get user statistics for browser extension"""
    try:
        stats = await form_filler_service.get_user_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/learning-insights/{domain}")
async def get_learning_insights(domain: str):
    """Get learning insights for specific domain"""
    try:
        insights = await form_filler_service.get_learning_insights(domain)
        return insights
    except Exception as e:
        logger.error(f"Error getting learning insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit-user-response")
async def submit_user_response(request: UserResponseRequest):
    """Submit user response for missing form field information"""
    try:
        await form_filler_service.store_user_response(
            request.resume_id,
            request.field_key, 
            request.question,
            request.response
        )
        
        return {
            "success": True,
            "message": "User response stored successfully",
            "field_key": request.field_key
        }
    except Exception as e:
        logger.error(f"Error storing user response: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Resume API Endpoints
@app.post("/api/resumes/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Upload and parse a resume file"""
    try:
        # Validate file type (allow text files for testing)
        allowed_types = ["application/pdf", "application/msword", 
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "text/plain"]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail="Only PDF, DOC, DOCX, and TXT files are allowed"
            )
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Extract text based on file type
        resume_text = ""
        if file.content_type == "application/pdf":
            resume_text = extract_pdf_text(file_content)
        elif file.content_type == "text/plain":
            resume_text = file_content.decode('utf-8')
        else:
            # For DOC/DOCX, we'll need additional libraries
            raise HTTPException(
                status_code=400,
                detail="DOC/DOCX support coming soon. Please use PDF files."
            )
        
        # Parse resume with LLM
        parsed_data = await resume_parser_service.parse_resume_text(resume_text)
        
        # Create resume record
        resume_id = str(uuid.uuid4())
        safe_filename = f"{resume_id}_{file.filename}"
        
        resume_record = ResumeRecord(
            id=resume_id,
            filename=safe_filename,
            original_filename=file.filename,
            parsed_data=parsed_data,
            file_size=file_size,
            content_type=file.content_type
        )
        
        # Save to storage
        await resume_storage_service.save_resume(resume_record, file_content)
        
        logger.info(f"📄 Successfully uploaded and parsed resume: {file.filename}")
        
        return {
            "success": True,
            "message": "Resume uploaded and parsed successfully",
            "resume_id": resume_id,
            "parsed_summary": await resume_parser_service.extract_resume_summary(parsed_data)
        }
        
    except Exception as e:
        logger.error(f"Error uploading resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/resumes", response_model=ResumeListResponse)
async def get_all_resumes():
    """Get list of all uploaded resumes"""
    try:
        resumes = await resume_storage_service.get_all_resumes()
        return resumes
    except Exception as e:
        logger.error(f"Error getting resumes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/resumes/{resume_id}")
async def get_resume(resume_id: str):
    """Get detailed resume data by ID"""
    try:
        resume = await resume_storage_service.get_resume_by_id(resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        return {
            "success": True,
            "resume": resume.model_dump()
        }
    except Exception as e:
        logger.error(f"Error getting resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/resumes/set-active")
async def set_active_resume(request: SetActiveResumeRequest):
    """Set a resume as the active one for form filling"""
    try:
        success = await resume_storage_service.set_active_resume(request.resume_id)
        if not success:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        logger.info(f"✅ Set resume {request.resume_id} as active")
        return {"success": True, "message": "Active resume updated"}
        
    except Exception as e:
        logger.error(f"Error setting active resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/resumes/active")
async def get_active_resume():
    """Get the currently active resume"""
    try:
        active_resume = await resume_storage_service.get_active_resume()
        if not active_resume:
            return {"success": False, "message": "No active resume found"}
        
        return {
            "success": True,
            "resume": active_resume.model_dump()
        }
    except Exception as e:
        logger.error(f"Error getting active resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/resumes/{resume_id}")
async def delete_resume(resume_id: str):
    """Delete a resume"""
    try:
        success = await resume_storage_service.delete_resume(resume_id)
        if not success:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        logger.info(f"🗑️ Deleted resume: {resume_id}")
        return {"success": True, "message": "Resume deleted"}
        
    except Exception as e:
        logger.error(f"Error deleting resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/resumes/{resume_id}/file")
async def get_resume_file(resume_id: str):
    """Get resume file content for upload"""
    try:
        # Validate resume_id format
        if not resume_id or len(resume_id) > 100 or len(resume_id) < 10:
            logger.error(f"Invalid resume ID format: {resume_id[:100]}...")
            raise HTTPException(status_code=400, detail="Invalid resume ID format")
        
        resume = await resume_storage_service.get_resume_by_id(resume_id)
        if not resume:
            logger.error(f"Resume not found for ID: {resume_id}")
            raise HTTPException(status_code=404, detail="Resume not found")
        
        file_content = await resume_storage_service.get_resume_file_content(resume_id)
        if not file_content:
            raise HTTPException(status_code=404, detail="Resume file not found")
        
        # Return file info for browser extension
        import base64
        file_data = base64.b64encode(file_content).decode('utf-8')
        
        return {
            "success": True,
            "file_data": file_data,
            "filename": resume.original_filename,
            "content_type": resume.content_type,
            "file_size": resume.file_size
        }
        
    except Exception as e:
        logger.error(f"Error getting resume file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def extract_pdf_text(file_content: bytes) -> str:
    """Extract text from PDF file content"""
    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting PDF text: {e}")
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

# Serve React static files
app.mount("/", StaticFiles(directory="../public", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )