class FormFillerPopup {
    constructor() {
        this.backendUrl = 'http://localhost:8000';
        this.initialized = false;
        this.feedbackCache = new Map(); // Cache feedback to avoid duplicates
        this.init();
    }

    async init() {
        if (this.initialized) return;
        this.initialized = true;
        
        await this.checkConnection();
        await this.loadUserStats();
        await this.loadResumes();
        this.setupEventListeners();
        await this.detectForms();
    }

    async sendMessageWithRetry(tabId, message, maxRetries = 3) {
        let lastError;
        
        for (let i = 0; i < maxRetries; i++) {
            try {
                const response = await chrome.tabs.sendMessage(tabId, message);
                return response;
            } catch (error) {
                lastError = error;
                console.log(`Retry ${i + 1}: Failed to send message`, error.message);
                
                // If context invalidated or no connection, try to inject content script
                if (error.message.includes('context invalidated') || 
                    error.message.includes('Could not establish connection') ||
                    error.message.includes('Receiving end does not exist')) {
                    
                    console.log(`Attempting to inject content script (attempt ${i + 1})`);
                    
                    try {
                        await chrome.scripting.executeScript({
                            target: { tabId },
                            files: ['content.js']
                        });
                        
                        // Wait for content script to initialize
                        await new Promise(resolve => setTimeout(resolve, 1000 + (i * 500)));
                        
                    } catch (injectError) {
                        console.log('Content script injection failed:', injectError.message);
                        
                        // If injection failed, this might be a restricted page
                        if (injectError.message.includes('Cannot access')) {
                            throw new Error('Cannot access this page type. Try navigating to a job application page.');
                        }
                    }
                } else {
                    // For other errors, wait before retrying
                    await new Promise(resolve => setTimeout(resolve, 500 * (i + 1)));
                }
            }
        }
        
        throw lastError || new Error('Failed to communicate with content script');
    }

    displayAIInsights(aiAnalysis, fieldAnalysis) {
        console.log('🧠 Displaying AI insights:', aiAnalysis);
        
        // Create or update AI insights section
        let insightsSection = document.getElementById('aiInsights');
        if (!insightsSection) {
            insightsSection = document.createElement('div');
            insightsSection.id = 'aiInsights';
            insightsSection.className = 'ai-insights-section';
            
            // Insert after form status
            const formStatus = document.getElementById('formStatus');
            formStatus.parentNode.insertBefore(insightsSection, formStatus.nextSibling);
        }
        
        // Build insights HTML
        const confidenceColor = aiAnalysis.average_confidence > 70 ? '#10b981' : 
                               aiAnalysis.average_confidence > 40 ? '#f59e0b' : '#ef4444';
        
        insightsSection.innerHTML = `
            <div class="insights-header">
                <h4>🧠 AI Analysis Results</h4>
                <div class="confidence-indicator">
                    <span class="confidence-label">Confidence:</span>
                    <span class="confidence-value" style="color: ${confidenceColor}">
                        ${Math.round(aiAnalysis.average_confidence)}%
                    </span>
                </div>
            </div>
            
            <div class="insights-stats">
                <div class="stat">
                    <span class="stat-value">${aiAnalysis.fields_analyzed}</span>
                    <span class="stat-label">Fields Analyzed</span>
                </div>
                <div class="stat">
                    <span class="stat-value">${Math.round(aiAnalysis.analysis_time_ms)}ms</span>
                    <span class="stat-label">Analysis Time</span>
                </div>
                <div class="stat">
                    <span class="stat-value">${aiAnalysis.services_used?.length || 0}</span>
                    <span class="stat-label">AI Services</span>
                </div>
            </div>
            
            ${this.buildFieldAnalysisHTML(fieldAnalysis)}
        `;
        
        // Add some basic styling
        if (!document.getElementById('aiInsightsStyles')) {
            const style = document.createElement('style');
            style.id = 'aiInsightsStyles';
            style.textContent = `
                .ai-insights-section {
                    margin: 10px 0;
                    padding: 12px;
                    border: 1px solid #e5e7eb;
                    border-radius: 6px;
                    background: #f9fafb;
                    font-size: 12px;
                }
                .insights-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                }
                .insights-header h4 {
                    margin: 0;
                    font-size: 13px;
                }
                .confidence-indicator {
                    font-size: 11px;
                }
                .confidence-value {
                    font-weight: bold;
                }
                .insights-stats {
                    display: flex;
                    gap: 12px;
                    margin-bottom: 8px;
                }
                .stat {
                    text-align: center;
                }
                .stat-value {
                    display: block;
                    font-weight: bold;
                    color: #3b82f6;
                }
                .stat-label {
                    font-size: 10px;
                    color: #6b7280;
                }
                .field-analysis {
                    max-height: 150px;
                    overflow-y: auto;
                }
                .field-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 4px 8px;
                    margin: 2px 0;
                    background: white;
                    border-radius: 3px;
                    font-size: 11px;
                }
                .field-name {
                    font-weight: 500;
                    max-width: 120px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .field-confidence {
                    font-size: 10px;
                    padding: 1px 4px;
                    border-radius: 2px;
                    color: white;
                }
                .confidence-bar {
                    width: 50px;
                    height: 4px;
                    background-color: #e5e7eb;
                    border-radius: 2px;
                    margin-left: 4px;
                    overflow: hidden;
                }
                .confidence-fill {
                    height: 100%;
                    transition: width 0.3s ease;
                }
                .feedback-btn {
                    border: none;
                    background: none;
                    font-size: 10px;
                    cursor: pointer;
                    padding: 2px 4px;
                    border-radius: 2px;
                    transition: all 0.2s ease;
                }
                .feedback-btn.correct {
                    color: #10b981;
                    border: 1px solid #10b981;
                }
                .feedback-btn.correct:hover {
                    background-color: #10b981;
                    color: white;
                }
                .feedback-btn.incorrect {
                    color: #ef4444;
                    border: 1px solid #ef4444;
                }
                .feedback-btn.incorrect:hover {
                    background-color: #ef4444;
                    color: white;
                }
                .feedback-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }
                .feedback-provided {
                    background-color: #f3f4f6 !important;
                    opacity: 0.7;
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    buildFieldAnalysisHTML(fieldAnalysis) {
        if (!fieldAnalysis || Object.keys(fieldAnalysis).length === 0) {
            return '<div class="no-analysis">No field-specific analysis available</div>';
        }
        
        let html = '<div class="field-analysis"><h5 style="margin: 8px 0 4px 0; font-size: 12px;">Field Analysis:</h5>';
        
        Object.entries(fieldAnalysis).slice(0, 5).forEach(([fieldId, analysis]) => {
            const confidenceColor = analysis.confidence > 70 ? '#10b981' : 
                                   analysis.confidence > 40 ? '#f59e0b' : '#ef4444';
            
            html += `
                <div class="field-item" data-field-id="${fieldId}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="field-name" title="${fieldId}">${fieldId}</span>
                        <div class="feedback-buttons" style="display: flex; gap: 2px;">
                            <button class="feedback-btn correct" onclick="window.formFillerPopup.provideFeedback('${fieldId}', '${analysis.detected_type}', true)" title="Correct prediction">✓</button>
                            <button class="feedback-btn incorrect" onclick="window.formFillerPopup.provideFeedback('${fieldId}', '${analysis.detected_type}', false)" title="Wrong prediction">✗</button>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 4px; margin-top: 2px;">
                        <span class="field-type" style="font-size: 10px; color: #6b7280;">${analysis.detected_type || 'unknown'}</span>
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width: ${analysis.confidence}%; background-color: ${confidenceColor};"></div>
                        </div>
                        <span class="field-confidence" style="background-color: ${confidenceColor}">
                            ${Math.round(analysis.confidence)}%
                        </span>
                    </div>
                </div>
            `;
        });
        
        if (Object.keys(fieldAnalysis).length > 5) {
            html += `<div style="text-align: center; color: #6b7280; font-size: 10px;">... and ${Object.keys(fieldAnalysis).length - 5} more fields</div>`;
        }
        
        html += '</div>';
        return html;
    }

    async checkConnection() {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        
        try {
            const response = await fetch(`${this.backendUrl}/api/health`);
            if (response.ok) {
                statusDot.classList.add('connected');
                statusText.textContent = 'Connected to local backend';
            } else {
                throw new Error('Backend not responding');
            }
        } catch (error) {
            statusText.textContent = 'Backend disconnected';
        }
    }

    async loadUserStats() {
        try {
            const response = await fetch(`${this.backendUrl}/api/user-stats`);
            if (response.ok) {
                const stats = await response.json();
                document.getElementById('formsFilledCount').textContent = stats.forms_filled || 0;
                document.getElementById('accuracyRate').textContent = `${stats.accuracy || 0}%`;
            }
        } catch (error) {
            console.log('Failed to load user stats:', error);
        }
    }

    async loadResumes() {
        const resumeSelect = document.getElementById('resumeSelect');
        const activeResumeInfo = document.getElementById('activeResumeInfo');
        const activeResumeName = document.getElementById('activeResumeName');
        
        try {
            const response = await fetch(`${this.backendUrl}/api/resumes`);
            if (response.ok) {
                const data = await response.json();
                
                // Clear existing options
                resumeSelect.innerHTML = '';
                
                if (data.resumes.length === 0) {
                    resumeSelect.innerHTML = '<option value="">No resumes uploaded</option>';
                    activeResumeInfo.style.display = 'none';
                } else {
                    // Add resumes to dropdown
                    data.resumes.forEach(resume => {
                        const option = document.createElement('option');
                        option.value = resume.id;
                        option.textContent = resume.parsed_summary || resume.original_filename;
                        if (resume.is_active) {
                            option.selected = true;
                        }
                        resumeSelect.appendChild(option);
                    });
                    
                    // Show active resume info
                    if (data.active_resume_id) {
                        const activeResume = data.resumes.find(r => r.id === data.active_resume_id);
                        if (activeResume) {
                            activeResumeName.textContent = `Active: ${activeResume.parsed_summary || activeResume.original_filename}`;
                            activeResumeInfo.style.display = 'flex';
                        }
                    } else {
                        activeResumeInfo.style.display = 'none';
                    }
                }
            } else {
                resumeSelect.innerHTML = '<option value="">Error loading resumes</option>';
            }
        } catch (error) {
            console.log('Failed to load resumes:', error);
            resumeSelect.innerHTML = '<option value="">Connection error</option>';
        }
    }

    setupEventListeners() {
        // One-click apply button
        document.getElementById('oneClickApply').addEventListener('click', () => {
            this.performOneClickApply();
        });
        
        // Fill form button
        document.getElementById('fillForm').addEventListener('click', () => {
            this.fillForm();
        });

        // Analyze form button
        document.getElementById('analyzeForm').addEventListener('click', () => {
            this.analyzeForm();
        });

        // Resume selection
        document.getElementById('resumeSelect').addEventListener('change', (e) => {
            this.setActiveResume(e.target.value);
        });

        // Upload resume button
        document.getElementById('uploadResume').addEventListener('click', () => {
            this.showUploadModal();
        });

        // Manage resumes button
        document.getElementById('manageResumes').addEventListener('click', () => {
            this.openResumeManager();
        });

        // Settings button
        document.getElementById('openSettings').addEventListener('click', () => {
            this.openSettings();
        });

        // Upload modal event listeners
        this.setupUploadModalListeners();
    }

    async detectForms() {
        const formStatusText = document.getElementById('formStatusText');
        const fillButton = document.getElementById('fillForm');
        
        console.log('🔍 Popup: Starting form detection...');
        
        try {
            // Get active tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            console.log('📋 Popup: Found active tab:', tab.url);
            
            // Check if this is a valid tab for form detection
            if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
                throw new Error('Cannot detect forms on this page type');
            }
            
            let response = await this.sendMessageWithRetry(tab.id, { action: 'detectForms' }, 3);
            console.log('📨 Popup: Received response from content script:', response);

            if (response && response.formsFound > 0) {
                console.log(`✅ Popup: ${response.formsFound} forms detected, updating UI`);
                formStatusText.textContent = `${response.formsFound} form(s) detected`;
                document.getElementById('formStatus').className = 'info-box success';
                fillButton.disabled = false;
                document.getElementById('oneClickApply').disabled = false;
                
                // Show form details
                if (response.formTypes) {
                    formStatusText.textContent += ` (${response.formTypes.join(', ')})`;
                }
            } else {
                console.log('❌ Popup: No forms found or response was null/undefined');
                console.log('🔍 Popup: Response details:', {
                    response: response,
                    hasResponse: !!response,
                    formsFound: response?.formsFound,
                    responseType: typeof response
                });
                formStatusText.textContent = 'No job application forms found';
                document.getElementById('formStatus').className = 'info-box warning';
                fillButton.disabled = true;
            }
        } catch (error) {
            console.log('💥 Popup: Error during form detection:', error);
            
            // Provide user-friendly error messages
            let errorMessage = 'Unable to scan page';
            if (error.message.includes('Cannot access')) {
                errorMessage = 'Cannot scan this page type. Navigate to a job application page.';
            } else if (error.message.includes('context invalidated')) {
                errorMessage = 'Extension needs refresh. Try reloading the page.';
            } else if (error.message.includes('communicate with content script')) {
                errorMessage = 'Page communication error. Try refreshing the page.';
            } else if (error.message.includes('Cannot detect forms on this page type')) {
                errorMessage = 'Navigate to a job application page to use this extension.';
            }
            
            formStatusText.textContent = errorMessage;
            document.getElementById('formStatus').className = 'info-box warning';
            fillButton.disabled = true;
            document.getElementById('oneClickApply').disabled = true;
        }
    }

    async fillForm() {
        const fillButton = document.getElementById('fillForm');
        const originalText = fillButton.textContent;
        
        // Prevent multiple clicks
        if (fillButton.disabled) {
            return;
        }
        
        fillButton.textContent = '⏳ Filling...';
        fillButton.disabled = true;

        try {
            // Get selected resume
            const resumeId = document.getElementById('resumeSelect').value;
            if (!resumeId) {
                throw new Error('Please select a resume first');
            }
            
            // Get fill options
            const options = {
                fillBasicInfo: document.getElementById('fillBasicInfo').checked,
                fillExperience: document.getElementById('fillExperience').checked,
                fillEducation: document.getElementById('fillEducation').checked,
                fillCoverLetter: document.getElementById('fillCoverLetter').checked
            };

            // Get current tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

            // First, get form fields from content script for AI analysis
            const formFields = await this.sendMessageWithRetry(tab.id, { action: 'getFormFields' });
            console.log('📋 Form fields extracted:', formFields);
            
            // Capture screenshot for visual analysis
            let screenshotBase64 = null;
            try {
                screenshotBase64 = await this.captureFormScreenshot(tab);
                console.log('📸 Screenshot captured for visual analysis');
            } catch (screenshotError) {
                console.warn('📸 Screenshot capture failed:', screenshotError.message);
                // Continue without screenshot - AI can still work with field data
            }
            
            // Enhanced form data generation with AI analysis
            const formDataResponse = await fetch(`${this.backendUrl}/api/generate-form-data`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    resumeId: resumeId,
                    options: {
                        ...options,
                        useAI: true // Enable AI analysis
                    },
                    url: tab.url,
                    page_title: tab.title,
                    form_fields: formFields?.fields || [], // Include form field information for AI
                    page_context: formFields?.pageContext || {}, // Include page context for LLM
                    form_purpose: 'job_application',
                    screenshot_base64: screenshotBase64 // Include screenshot for visual analysis
                })
            });

            if (!formDataResponse.ok) {
                const errorText = await formDataResponse.text();
                throw new Error(`Failed to generate form data: ${errorText}`);
            }

            const formData = await formDataResponse.json();
            console.log('📊 Enhanced FormData with AI analysis:', formData);
            
            // Display AI insights to user if available
            if (formData.ai_analysis) {
                this.displayAIInsights(formData.ai_analysis, formData.field_analysis);
            }

            // Send to content script to fill forms
            const result = await chrome.tabs.sendMessage(tab.id, {
                action: 'fillForm',
                data: formData
            });

            if (result && result.success) {
                fillButton.textContent = '✅ Filled Successfully';
            } else {
                throw new Error(result?.error || 'Form filling failed');
            }

        } catch (error) {
            console.error('Fill form error:', error);
            fillButton.textContent = '❌ Failed';
        } finally {
            // Always restore button after 2 seconds
            setTimeout(() => {
                fillButton.textContent = originalText;
                fillButton.disabled = false;
            }, 2000);
        }
    }

    async performOneClickApply() {
        const applyButton = document.getElementById('oneClickApply');
        const originalText = applyButton.textContent;
        
        // Prevent multiple clicks
        if (applyButton.disabled) {
            return;
        }
        
        applyButton.textContent = '⚡ Applying...';
        applyButton.disabled = true;

        try {
            // Get selected resume
            const resumeId = document.getElementById('resumeSelect').value;
            if (!resumeId) {
                throw new Error('Please select a resume first');
            }
            
            // Get fill options
            const options = {
                fillBasicInfo: document.getElementById('fillBasicInfo').checked,
                fillExperience: document.getElementById('fillExperience').checked,
                fillEducation: document.getElementById('fillEducation').checked,
                fillCoverLetter: document.getElementById('fillCoverLetter').checked
            };

            // Get current tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

            // Get form data from backend using resume
            const formDataResponse = await fetch(`${this.backendUrl}/api/generate-form-data`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    resumeId: resumeId,
                    options: options,
                    url: tab.url
                })
            });

            if (!formDataResponse.ok) {
                throw new Error('Failed to generate form data');
            }

            const formData = await formDataResponse.json();
            console.log('📊 FormData for one-click apply:', formData);

            // Send to content script for one-click apply
            const result = await chrome.tabs.sendMessage(tab.id, {
                action: 'oneClickApply',
                data: formData
            });

            if (result && result.success) {
                applyButton.textContent = '✅ Applied Successfully!';
                
                // Show success details
                if (result.jobInfo) {
                    console.log('🎉 Application submitted:', result.jobInfo);
                }
                
                // Auto-reset after 3 seconds
                setTimeout(() => {
                    applyButton.textContent = originalText;
                    applyButton.disabled = false;
                }, 3000);
                
            } else {
                throw new Error(result?.error || 'One-click apply failed');
            }

        } catch (error) {
            console.error('One-click apply error:', error);
            applyButton.textContent = '❌ Apply Failed';
            
            // Reset after 2 seconds
            setTimeout(() => {
                applyButton.textContent = originalText;
                applyButton.disabled = false;
            }, 2000);
        }
    }

    async analyzeForm() {
        const analyzeButton = document.getElementById('analyzeForm');
        const originalText = analyzeButton.textContent;
        
        try {
            analyzeButton.textContent = '🔍 Analyzing...';
            analyzeButton.disabled = true;
            
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            
            // Get form fields for AI analysis
            const formFields = await this.sendMessageWithRetry(tab.id, { action: 'getFormFields' });
            
            if (!formFields || !formFields.fields || formFields.fields.length === 0) {
                throw new Error('No form fields found to analyze');
            }
            
            console.log('📋 Sending fields for AI analysis:', formFields.fields.length);
            
            // Capture screenshot for visual analysis
            let screenshotBase64 = null;
            try {
                screenshotBase64 = await this.captureFormScreenshot(tab);
                console.log('📸 Screenshot captured for analysis');
            } catch (screenshotError) {
                console.warn('📸 Screenshot capture failed, continuing without visual analysis:', screenshotError.message);
            }
            
            // Send to backend for AI analysis
            const analysisResponse = await fetch(`${this.backendUrl}/api/analyze-form`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: tab.url,
                    page_title: tab.title,
                    form_fields: formFields.fields,
                    form_purpose: 'job_application',
                    screenshot_base64: screenshotBase64 // Include screenshot for visual analysis
                })
            });
            
            if (!analysisResponse.ok) {
                const errorText = await analysisResponse.text();
                throw new Error(`Analysis failed: ${errorText}`);
            }
            
            const analysisResult = await analysisResponse.json();
            console.log('🧠 AI Analysis completed:', analysisResult);
            
            // Display the analysis results
            this.displayAnalysisResults(analysisResult);
            
        } catch (error) {
            console.error('Form analysis failed:', error);
            
            // Show error to user
            let errorMessage = 'Analysis failed. Please try again.';
            if (error.message.includes('No form fields found')) {
                errorMessage = 'No analyzable form fields found on this page.';
            } else if (error.message.includes('Cannot access')) {
                errorMessage = 'Cannot analyze this page type.';
            }
            
            // Create temporary error display
            const errorDiv = document.createElement('div');
            errorDiv.className = 'analysis-error';
            errorDiv.style.cssText = 'color: #ef4444; font-size: 12px; padding: 8px; text-align: center;';
            errorDiv.textContent = errorMessage;
            
            const formStatus = document.getElementById('formStatus');
            formStatus.parentNode.insertBefore(errorDiv, formStatus.nextSibling);
            
            // Remove error after 5 seconds
            setTimeout(() => errorDiv.remove(), 5000);
            
        } finally {
            analyzeButton.textContent = originalText;
            analyzeButton.disabled = false;
        }
    }
    
    displayAnalysisResults(analysisResult) {
        // Create or update analysis results section
        let resultsSection = document.getElementById('analysisResults');
        if (!resultsSection) {
            resultsSection = document.createElement('div');
            resultsSection.id = 'analysisResults';
            resultsSection.className = 'analysis-results-section';
            
            const formStatus = document.getElementById('formStatus');
            formStatus.parentNode.insertBefore(resultsSection, formStatus.nextSibling);
        }
        
        const overall = analysisResult.overall_analysis;
        const confidenceColor = overall.average_confidence > 70 ? '#10b981' : 
                              overall.average_confidence > 40 ? '#f59e0b' : '#ef4444';
        
        resultsSection.innerHTML = `
            <div class="analysis-header">
                <h4>🔬 Detailed Form Analysis</h4>
                <button class="close-analysis" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            
            <div class="analysis-summary">
                <div class="summary-stat">
                    <span class="stat-value" style="color: ${confidenceColor}">${Math.round(overall.average_confidence)}%</span>
                    <span class="stat-label">Overall Confidence</span>
                </div>
                <div class="summary-stat">
                    <span class="stat-value">${overall.total_fields}</span>
                    <span class="stat-label">Total Fields</span>
                </div>
                <div class="summary-stat">
                    <span class="stat-value">${Math.round(overall.analysis_time_ms)}ms</span>
                    <span class="stat-label">Analysis Time</span>
                </div>
            </div>
            
            <div class="complexity-indicator">
                <span class="complexity-label">Form Complexity:</span>
                <span class="complexity-value ${overall.form_complexity}">${overall.form_complexity.toUpperCase()}</span>
            </div>
            
            ${this.buildDetailedFieldAnalysis(analysisResult.analysis_results)}
        `;
        
        // Add styling for analysis results
        if (!document.getElementById('analysisResultsStyles')) {
            const style = document.createElement('style');
            style.id = 'analysisResultsStyles';
            style.textContent = `
                .analysis-results-section {
                    margin: 10px 0;
                    padding: 12px;
                    border: 1px solid #d1d5db;
                    border-radius: 8px;
                    background: #ffffff;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    font-size: 12px;
                    max-height: 300px;
                    overflow-y: auto;
                }
                .analysis-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 12px;
                    border-bottom: 1px solid #e5e7eb;
                    padding-bottom: 8px;
                }
                .analysis-header h4 {
                    margin: 0;
                    font-size: 14px;
                }
                .close-analysis {
                    background: none;
                    border: none;
                    font-size: 18px;
                    cursor: pointer;
                    color: #6b7280;
                }
                .analysis-summary {
                    display: flex;
                    gap: 16px;
                    margin-bottom: 12px;
                }
                .summary-stat {
                    text-align: center;
                    flex: 1;
                }
                .summary-stat .stat-value {
                    display: block;
                    font-weight: bold;
                    font-size: 16px;
                    margin-bottom: 2px;
                }
                .summary-stat .stat-label {
                    font-size: 10px;
                    color: #6b7280;
                }
                .complexity-indicator {
                    text-align: center;
                    margin-bottom: 12px;
                    padding: 6px;
                    background: #f3f4f6;
                    border-radius: 4px;
                }
                .complexity-value {
                    font-weight: bold;
                    margin-left: 4px;
                }
                .complexity-value.low { color: #10b981; }
                .complexity-value.medium { color: #f59e0b; }
                .complexity-value.high { color: #ef4444; }
            `;
            document.head.appendChild(style);
        }
    }
    
    buildDetailedFieldAnalysis(analysisResults) {
        if (!analysisResults || Object.keys(analysisResults).length === 0) {
            return '<div class="no-detailed-analysis">No detailed field analysis available</div>';
        }
        
        let html = '<div class="detailed-analysis"><h5 style="margin: 8px 0 4px 0; font-size: 12px;">Field Details:</h5>';
        
        Object.entries(analysisResults).slice(0, 10).forEach(([fieldId, analysis]) => {
            const confidenceColor = analysis.confidence > 70 ? '#10b981' : 
                                   analysis.confidence > 40 ? '#f59e0b' : '#ef4444';
            
            html += `
                <div class="detailed-field-item" style="margin: 4px 0; padding: 6px; background: #f9fafb; border-radius: 4px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="field-id" style="font-weight: 500; font-size: 11px;">${fieldId}</span>
                        <span style="background-color: ${confidenceColor}; color: white; padding: 1px 4px; border-radius: 2px; font-size: 10px;">
                            ${Math.round(analysis.confidence)}%
                        </span>
                    </div>
                    <div style="font-size: 10px; color: #6b7280; margin-top: 2px;">
                        Type: <strong>${analysis.detected_type || 'unknown'}</strong>
                    </div>
                    ${analysis.field_purpose ? `<div style="font-size: 10px; color: #6b7280; margin-top: 1px;">${analysis.field_purpose}</div>` : ''}
                </div>
            `;
        });
        
        html += '</div>';
        return html;
    }

    async captureFormScreenshot(tab) {
        try {
            console.log('📸 Starting screenshot capture...');
            
            // First, ensure the tab is active and ready
            await chrome.tabs.update(tab.id, { active: true });
            
            // Wait a moment for the tab to become active
            await new Promise(resolve => setTimeout(resolve, 500));
            
            // Capture the visible tab
            const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, {
                format: 'png',
                quality: 90
            });
            
            console.log('📸 Tab screenshot captured successfully');
            
            // Extract just the base64 part (remove data:image/png;base64,)
            const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
            
            // Optional: Try to crop to form area (if we can identify it)
            try {
                const croppedBase64 = await this.cropToFormArea(tab, base64);
                return croppedBase64 || base64;
            } catch (cropError) {
                console.warn('📸 Form cropping failed, using full screenshot:', cropError.message);
                return base64;
            }
            
        } catch (error) {
            console.error('📸 Screenshot capture failed:', error);
            throw new Error(`Screenshot capture failed: ${error.message}`);
        }
    }
    
    async cropToFormArea(tab, base64Screenshot) {
        try {
            // Get form boundaries from content script
            const formBounds = await this.sendMessageWithRetry(tab.id, { action: 'getFormBounds' });
            
            if (!formBounds || !formBounds.bounds) {
                console.log('📸 No form bounds available, using full screenshot');
                return null;
            }
            
            console.log('📸 Form bounds received:', formBounds.bounds);
            
            // Create canvas to crop the screenshot
            return new Promise((resolve, reject) => {
                const img = new Image();
                img.onload = () => {
                    try {
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
                        
                        const bounds = formBounds.bounds;
                        const padding = 20; // Add some padding around the form
                        
                        // Set canvas dimensions with padding
                        const cropX = Math.max(0, bounds.left - padding);
                        const cropY = Math.max(0, bounds.top - padding);
                        const cropWidth = Math.min(img.width - cropX, bounds.width + 2 * padding);
                        const cropHeight = Math.min(img.height - cropY, bounds.height + 2 * padding);
                        
                        canvas.width = cropWidth;
                        canvas.height = cropHeight;
                        
                        // Draw cropped image
                        ctx.drawImage(img, cropX, cropY, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);
                        
                        // Convert back to base64
                        const croppedDataUrl = canvas.toDataURL('image/png', 0.9);
                        const croppedBase64 = croppedDataUrl.replace(/^data:image\/png;base64,/, '');
                        
                        console.log('📸 Screenshot cropped to form area successfully');
                        resolve(croppedBase64);
                    } catch (error) {
                        console.warn('📸 Canvas cropping failed:', error);
                        resolve(null);
                    }
                };
                
                img.onerror = () => {
                    console.warn('📸 Image loading failed for cropping');
                    resolve(null);
                };
                
                img.src = `data:image/png;base64,${base64Screenshot}`;
            });
            
        } catch (error) {
            console.warn('📸 Form area cropping failed:', error.message);
            return null;
        }
    }

    async provideFeedback(fieldId, predictedType, isCorrect) {
        try {
            console.log(`📝 User feedback: ${fieldId} -> ${predictedType} is ${isCorrect ? 'correct' : 'incorrect'}`);
            
            // Check if feedback already provided for this field
            const feedbackKey = `${fieldId}-${predictedType}`;
            if (this.feedbackCache.has(feedbackKey)) {
                console.log('📝 Feedback already provided for this field');
                return;
            }
            
            // Get current tab for context
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            
            // Collect field information for feedback
            const formFields = await this.sendMessageWithRetry(tab.id, { action: 'getFormFields' });
            const fieldInfo = formFields?.fields?.find(f => f.id === fieldId || f.name === fieldId);
            
            if (!fieldInfo) {
                throw new Error('Field information not found');
            }
            
            let correctType = predictedType;
            
            // If incorrect, prompt user for correct type
            if (!isCorrect) {
                correctType = await this.promptForCorrectType(fieldId, predictedType);
                if (!correctType) {
                    console.log('📝 User cancelled feedback');
                    return;
                }
            }
            
            // Send feedback to backend
            const feedbackData = {
                url: tab.url,
                domain: new URL(tab.url).hostname,
                field_info: fieldInfo,
                predicted_type: predictedType,
                actual_type: correctType,
                is_correct: isCorrect,
                user_feedback: isCorrect ? 'correct' : 'incorrect',
                timestamp: new Date().toISOString()
            };
            
            const response = await fetch(`${this.backendUrl}/api/log-form-activity`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...feedbackData,
                    user_corrections: [{
                        field_id: fieldId,
                        predicted_type: predictedType,
                        actual_type: correctType,
                        user_feedback: isCorrect ? 'correct' : `corrected to ${correctType}`
                    }]
                })
            });
            
            if (response.ok) {
                console.log('📝 Feedback sent successfully');
                
                // Cache feedback to prevent duplicates
                this.feedbackCache.set(feedbackKey, true);
                
                // Update UI to show feedback was provided
                this.markFeedbackProvided(fieldId, isCorrect);
                
                // Show success message
                this.showFeedbackMessage(`Feedback recorded! ${isCorrect ? 'Thanks for confirming!' : 'Thanks for the correction!'}`, 'success');
                
            } else {
                throw new Error(`Failed to send feedback: ${response.status}`);
            }
            
        } catch (error) {
            console.error('📝 Feedback failed:', error);
            this.showFeedbackMessage('Failed to record feedback. Please try again.', 'error');
        }
    }
    
    async promptForCorrectType(fieldId, predictedType) {
        // Create a simple prompt modal for field type correction
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: system-ui;
            `;
            
            const commonTypes = [
                'personal_info/name', 'personal_info/email', 'personal_info/phone',
                'experience/company', 'experience/title', 'experience/summary',
                'education/degree', 'education/university',
                'other/cover_letter', 'other/salary', 'other/work_authorization'
            ];
            
            const optionsHtml = commonTypes.map(type => 
                `<option value="${type}" ${type === predictedType ? 'selected' : ''}>${type}</option>`
            ).join('');
            
            modal.innerHTML = `
                <div style="background: white; padding: 20px; border-radius: 8px; max-width: 300px; width: 90%;">
                    <h3 style="margin: 0 0 12px 0; font-size: 14px;">Correct Field Type</h3>
                    <p style="margin: 0 0 12px 0; font-size: 12px; color: #6b7280;">
                        Field: <strong>${fieldId}</strong><br>
                        Predicted: <strong>${predictedType}</strong>
                    </p>
                    <select id="correctTypeSelect" style="width: 100%; padding: 6px; margin-bottom: 12px; font-size: 12px;">
                        ${optionsHtml}
                        <option value="other">Other...</option>
                    </select>
                    <div style="display: flex; gap: 8px; justify-content: flex-end;">
                        <button id="cancelBtn" style="padding: 6px 12px; border: 1px solid #d1d5db; background: white; border-radius: 4px; cursor: pointer; font-size: 12px;">Cancel</button>
                        <button id="submitBtn" style="padding: 6px 12px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">Submit</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            const select = modal.querySelector('#correctTypeSelect');
            const cancelBtn = modal.querySelector('#cancelBtn');
            const submitBtn = modal.querySelector('#submitBtn');
            
            cancelBtn.onclick = () => {
                document.body.removeChild(modal);
                resolve(null);
            };
            
            submitBtn.onclick = () => {
                const value = select.value;
                document.body.removeChild(modal);
                
                if (value === 'other') {
                    const customType = prompt('Enter custom field type:');
                    resolve(customType || null);
                } else {
                    resolve(value);
                }
            };
        });
    }
    
    markFeedbackProvided(fieldId, isCorrect) {
        const fieldItem = document.querySelector(`[data-field-id="${fieldId}"]`);
        if (fieldItem) {
            fieldItem.classList.add('feedback-provided');
            
            const buttons = fieldItem.querySelectorAll('.feedback-btn');
            buttons.forEach(btn => {
                btn.disabled = true;
            });
            
            // Add feedback indicator
            if (!fieldItem.querySelector('.feedback-indicator')) {
                const indicator = document.createElement('span');
                indicator.className = 'feedback-indicator';
                indicator.style.cssText = `
                    font-size: 10px;
                    margin-left: 4px;
                    color: ${isCorrect ? '#10b981' : '#f59e0b'};
                `;
                indicator.textContent = isCorrect ? '✓ confirmed' : '✓ corrected';
                
                const typeSpan = fieldItem.querySelector('.field-type');
                typeSpan.parentNode.insertBefore(indicator, typeSpan.nextSibling);
            }
        }
    }
    
    showFeedbackMessage(message, type) {
        const messageDiv = document.createElement('div');
        messageDiv.style.cssText = `
            position: fixed;
            top: 10px;
            left: 10px;
            right: 10px;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            text-align: center;
            z-index: 10001;
            background-color: ${type === 'success' ? '#10b981' : '#ef4444'};
            color: white;
        `;
        messageDiv.textContent = message;
        
        document.body.appendChild(messageDiv);
        
        setTimeout(() => {
            if (document.body.contains(messageDiv)) {
                document.body.removeChild(messageDiv);
            }
        }, 3000);
    }

    async setActiveResume(resumeId) {
        if (!resumeId) return;
        
        try {
            const response = await fetch(`${this.backendUrl}/api/resumes/set-active`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ resume_id: resumeId })
            });
            
            if (response.ok) {
                // Reload resume list to update active status
                await this.loadResumes();
            }
        } catch (error) {
            console.error('Failed to set active resume:', error);
        }
    }

    showUploadModal() {
        document.getElementById('uploadModal').style.display = 'flex';
    }

    hideUploadModal() {
        document.getElementById('uploadModal').style.display = 'none';
        document.getElementById('fileInput').value = '';
        document.getElementById('confirmUpload').disabled = true;
        document.getElementById('uploadProgress').style.display = 'none';
        document.querySelector('.modal-actions').style.display = 'flex';
    }

    setupUploadModalListeners() {
        const modal = document.getElementById('uploadModal');
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const cancelBtn = document.getElementById('cancelUpload');
        const confirmBtn = document.getElementById('confirmUpload');

        // Cancel upload
        cancelBtn.addEventListener('click', () => {
            this.hideUploadModal();
        });

        // Close modal on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideUploadModal();
            }
        });

        // Upload area click
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                this.handleFileSelect(file);
            }
        });

        // Confirm upload
        confirmBtn.addEventListener('click', () => {
            const file = fileInput.files[0];
            if (file) {
                this.uploadResume(file);
            }
        });

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileSelect(files[0]);
            }
        });
    }

    handleFileSelect(file) {
        const uploadArea = document.getElementById('uploadArea');
        const confirmBtn = document.getElementById('confirmUpload');

        if (file.type !== 'application/pdf') {
            uploadArea.innerHTML = '<p style="color: red;">Please select a PDF file</p>';
            confirmBtn.disabled = true;
            return;
        }

        uploadArea.innerHTML = `<p>📄 ${file.name}</p><p style="font-size: 12px; color: #64748b;">Ready to upload</p>`;
        confirmBtn.disabled = false;
    }

    async uploadResume(file) {
        const progressDiv = document.getElementById('uploadProgress');
        const progressFill = document.querySelector('.progress-fill');
        const statusText = document.getElementById('uploadStatus');
        const modalActions = document.querySelector('.modal-actions');

        // Show progress
        modalActions.style.display = 'none';
        progressDiv.style.display = 'block';
        statusText.textContent = 'Uploading and parsing...';

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`${this.backendUrl}/api/resumes/upload`, {
                method: 'POST',
                body: formData
            });

            // Simulate progress
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 30;
                if (progress > 90) progress = 90;
                progressFill.style.width = `${progress}%`;
            }, 200);

            if (response.ok) {
                const result = await response.json();
                clearInterval(progressInterval);
                progressFill.style.width = '100%';
                statusText.textContent = 'Upload successful!';
                
                // Reload resumes and close modal after delay
                setTimeout(async () => {
                    await this.loadResumes();
                    this.hideUploadModal();
                }, 1500);
            } else {
                throw new Error('Upload failed');
            }
        } catch (error) {
            statusText.textContent = 'Upload failed. Please try again.';
            console.error('Upload error:', error);
            
            // Show actions again after delay
            setTimeout(() => {
                modalActions.style.display = 'flex';
                progressDiv.style.display = 'none';
            }, 2000);
        }
    }

    openResumeManager() {
        // Open resume management page (could be implemented later)
        chrome.tabs.create({
            url: chrome.runtime.getURL('resumes.html')
        });
    }

    openSettings() {
        // Open settings page
        chrome.tabs.create({
            url: chrome.runtime.getURL('settings.html')
        });
    }
}

// Basic test to see if JavaScript is running
console.log('🚀 POPUP SCRIPT LOADED - Check if you see this message!');

// Initialize popup when DOM is loaded (only once)
let popupInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    console.log('🔄 DOM LOADED - Initializing popup...');
    if (!popupInstance) {
        try {
            popupInstance = new FormFillerPopup();
            window.formFillerPopup = popupInstance; // Make available globally for onclick handlers
            console.log('✅ FormFillerPopup created successfully');
        } catch (error) {
            console.log('💥 Error creating FormFillerPopup:', error);
        }
    }
});