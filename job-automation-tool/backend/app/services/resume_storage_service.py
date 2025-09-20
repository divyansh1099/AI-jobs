"""
Resume storage service for managing resume files and parsed data
"""

import os
import json
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime
import aiosqlite
from loguru import logger
from app.models import ResumeRecord, ParsedResumeData, ResumeResponse, ResumeListResponse


class ResumeStorageService:
    def __init__(self, db_path: str = "app_data.db", uploads_dir: str = "uploads/resumes"):
        self.db_path = db_path
        self.uploads_dir = uploads_dir
        self._ensure_uploads_directory()
        
    def _ensure_uploads_directory(self):
        """Ensure uploads directory exists"""
        os.makedirs(self.uploads_dir, exist_ok=True)
        
    async def initialize_database(self):
        """Initialize the resume tables in the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    upload_date TIMESTAMP NOT NULL,
                    parsed_data TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT FALSE,
                    file_size INTEGER NOT NULL,
                    content_type TEXT NOT NULL
                )
            """)
            
            # Create index for faster queries
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_resume_active ON resumes(is_active)
            """)
            
            await db.commit()
            logger.info("Resume database tables initialized")
    
    async def save_resume(self, resume_record: ResumeRecord, file_content: bytes) -> str:
        """Save resume file and record to database"""
        try:
            # Save file to disk
            file_path = os.path.join(self.uploads_dir, resume_record.filename)
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Save record to database
            parsed_data_json = resume_record.parsed_data.model_dump_json()
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO resumes (
                        id, filename, original_filename, upload_date,
                        parsed_data, is_active, file_size, content_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    resume_record.id,
                    resume_record.filename,
                    resume_record.original_filename,
                    resume_record.upload_date.isoformat(),
                    parsed_data_json,
                    resume_record.is_active,
                    resume_record.file_size,
                    resume_record.content_type
                ))
                await db.commit()
            
            logger.info(f"Successfully saved resume: {resume_record.original_filename}")
            return resume_record.id
            
        except Exception as e:
            # Clean up file if database save fails
            file_path = os.path.join(self.uploads_dir, resume_record.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            logger.error(f"Error saving resume: {e}")
            raise
    
    async def get_resume_by_id(self, resume_id: str) -> Optional[ResumeRecord]:
        """Get resume record by ID"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, filename, original_filename, upload_date,
                           parsed_data, is_active, file_size, content_type
                    FROM resumes WHERE id = ?
                """, (resume_id,))
                
                row = await cursor.fetchone()
                if not row:
                    return None
                
                # Parse the stored data
                parsed_data = ParsedResumeData.model_validate_json(row[4])
                
                return ResumeRecord(
                    id=row[0],
                    filename=row[1],
                    original_filename=row[2],
                    upload_date=datetime.fromisoformat(row[3]),
                    parsed_data=parsed_data,
                    is_active=bool(row[5]),
                    file_size=row[6],
                    content_type=row[7]
                )
                
        except Exception as e:
            logger.error(f"Error getting resume by ID {resume_id}: {e}")
            return None
    
    async def get_all_resumes(self) -> ResumeListResponse:
        """Get all resume records"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, filename, original_filename, upload_date,
                           parsed_data, is_active, file_size, content_type
                    FROM resumes ORDER BY upload_date DESC
                """)
                
                rows = await cursor.fetchall()
                resumes = []
                active_resume_id = None
                
                for row in rows:
                    parsed_data = ParsedResumeData.model_validate_json(row[4])
                    
                    # Create summary for display
                    from app.services.resume_parser_service import ResumeParserService
                    parser = ResumeParserService()
                    summary = await parser.extract_resume_summary(parsed_data)
                    
                    resume_response = ResumeResponse(
                        id=row[0],
                        filename=row[1],
                        original_filename=row[2],
                        upload_date=datetime.fromisoformat(row[3]),
                        is_active=bool(row[5]),
                        file_size=row[6],
                        content_type=row[7],
                        parsed_summary=summary
                    )
                    
                    resumes.append(resume_response)
                    
                    if resume_response.is_active:
                        active_resume_id = resume_response.id
                
                return ResumeListResponse(
                    resumes=resumes,
                    active_resume_id=active_resume_id
                )
                
        except Exception as e:
            logger.error(f"Error getting all resumes: {e}")
            return ResumeListResponse(resumes=[], active_resume_id=None)
    
    async def set_active_resume(self, resume_id: str) -> bool:
        """Set a resume as active (deactivate others)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # First, deactivate all resumes
                await db.execute("UPDATE resumes SET is_active = FALSE")
                
                # Then activate the selected one
                cursor = await db.execute(
                    "UPDATE resumes SET is_active = TRUE WHERE id = ?",
                    (resume_id,)
                )
                
                if cursor.rowcount == 0:
                    logger.warning(f"No resume found with ID: {resume_id}")
                    return False
                
                await db.commit()
                logger.info(f"Set resume {resume_id} as active")
                return True
                
        except Exception as e:
            logger.error(f"Error setting active resume: {e}")
            return False
    
    async def get_active_resume(self) -> Optional[ResumeRecord]:
        """Get the currently active resume"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, filename, original_filename, upload_date,
                           parsed_data, is_active, file_size, content_type
                    FROM resumes WHERE is_active = TRUE LIMIT 1
                """)
                
                row = await cursor.fetchone()
                if not row:
                    return None
                
                parsed_data = ParsedResumeData.model_validate_json(row[4])
                
                return ResumeRecord(
                    id=row[0],
                    filename=row[1],
                    original_filename=row[2],
                    upload_date=datetime.fromisoformat(row[3]),
                    parsed_data=parsed_data,
                    is_active=bool(row[5]),
                    file_size=row[6],
                    content_type=row[7]
                )
                
        except Exception as e:
            logger.error(f"Error getting active resume: {e}")
            return None
    
    async def delete_resume(self, resume_id: str) -> bool:
        """Delete a resume record and its file"""
        try:
            # First get the resume to know the filename
            resume = await self.get_resume_by_id(resume_id)
            if not resume:
                return False
            
            # Delete from database
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM resumes WHERE id = ?",
                    (resume_id,)
                )
                
                if cursor.rowcount == 0:
                    return False
                
                await db.commit()
            
            # Delete file from disk
            file_path = os.path.join(self.uploads_dir, resume.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            logger.info(f"Deleted resume: {resume.original_filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting resume: {e}")
            return False
    
    async def get_resume_file_content(self, resume_id: str) -> Optional[bytes]:
        """Get the file content for a resume"""
        try:
            resume = await self.get_resume_by_id(resume_id)
            if not resume:
                return None
            
            file_path = os.path.join(self.uploads_dir, resume.filename)
            if not os.path.exists(file_path):
                logger.warning(f"Resume file not found: {file_path}")
                return None
            
            with open(file_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error getting resume file content: {e}")
            return None
    
    async def update_parsed_data(self, resume_id: str, parsed_data: ParsedResumeData) -> bool:
        """Update the parsed data for an existing resume"""
        try:
            # Convert parsed data to JSON
            parsed_data_json = parsed_data.model_dump_json()
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "UPDATE resumes SET parsed_data = ? WHERE id = ?",
                    (parsed_data_json, resume_id)
                )
                
                if cursor.rowcount == 0:
                    logger.warning(f"No resume found with ID: {resume_id}")
                    return False
                
                await db.commit()
                logger.info(f"Updated parsed data for resume: {resume_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating parsed data: {e}")
            return False