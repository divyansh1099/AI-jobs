class JobFormDetector {
    constructor() {
        this.forms = [];
        this.formFields = new Map();
        this.isInitialized = false;
        this.messageListenerActive = false;
        this.contextInvalidated = false;
        this.init();
    }

    async init() {
        if (this.isInitialized) return;
        
        try {
            // Notify background script that content script is ready
            await chrome.runtime.sendMessage({ action: 'contentScriptReady' });
            
            this.detectJobForms();
            this.setupMessageListener();
            this.setupDynamicDetection();
            this.setupKeepAlive();
            
            this.isInitialized = true;
            console.log('🚀 JobFormDetector initialized successfully');
        } catch (error) {
            console.error('❌ JobFormDetector initialization failed:', error);
        }
    }

    setupDynamicDetection() {
        // Watch for DOM changes to detect dynamically loaded forms
        const observer = new MutationObserver((mutations) => {
            let shouldRedetect = false;
            
            mutations.forEach(mutation => {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            if (node.tagName === 'FORM' || 
                                node.querySelector('form') ||
                                node.querySelector('input, textarea, select')) {
                                shouldRedetect = true;
                            }
                        }
                    });
                }
            });
            
            if (shouldRedetect) {
                setTimeout(() => this.detectJobForms(), 500);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        this.mutationObserver = observer;
    }

    setupMessageListener() {
        if (this.messageListenerActive) return;
        
        const messageHandler = (request, sender, sendResponse) => {
            try {
                console.log('📨 Content: Received message:', request.action);
                
                switch (request.action) {
                    case 'detectForms':
                        this.detectJobForms();
                        const response = {
                            formsFound: this.forms.length,
                            formTypes: this.getFormTypes(),
                            timestamp: Date.now()
                        };
                        console.log('📤 Content: Sending response:', response);
                        sendResponse(response);
                        break;
                        
                    case 'fillForm':
                        this.fillFormWithData(request.data)
                            .then(result => {
                                console.log('✅ Form filling completed:', result);
                                sendResponse(result);
                            })
                            .catch(error => {
                                console.error('❌ Form filling failed:', error);
                                sendResponse({ success: false, error: error.message });
                            });
                        return true; // Keep message channel open for async response
                        
                    case 'oneClickApply':
                        this.performOneClickApply(request.data)
                            .then(result => sendResponse(result))
                            .catch(error => sendResponse({ success: false, error: error.message }));
                        return true;
                        
                    case 'analyzeForm':
                        this.analyzeFormStructure()
                            .then(result => sendResponse(result))
                            .catch(error => sendResponse({ success: false, error: error.message }));
                        return true;
                        
                    case 'ping':
                        sendResponse({ success: true, alive: true });
                        break;
                        
                    case 'getFormFields':
                        const fields = this.extractFormFieldsInfo();
                        const pageContext = this.extractPageContext();
                        sendResponse({ 
                            success: true, 
                            fields,
                            pageContext 
                        });
                        break;
                        
                    case 'getFormBounds':
                        const bounds = this.getFormBounds();
                        sendResponse({ success: true, bounds });
                        break;
                        
                    default:
                        console.warn('❌ Unknown action:', request.action);
                        sendResponse({ success: false, error: 'Unknown action' });
                }
            } catch (error) {
                console.error('❌ Message handler error:', error);
                sendResponse({ success: false, error: error.message });
            }
        };
        
        chrome.runtime.onMessage.addListener(messageHandler);
        this.messageListenerActive = true;
    }
    
    setupKeepAlive() {
        // Check if we're on a problematic site (like Greenhouse) and adjust behavior
        const isGreenhouseOrIframe = window.location.href.includes('greenhouse.io') || window !== window.top;
        const pingInterval = isGreenhouseOrIframe ? 20000 : 15000; // Less frequent pinging for problematic sites
        
        // Send periodic ping to background script to maintain connection
        this.pingInterval = setInterval(async () => {
            try {
                // Only ping if we're initialized and the runtime is available
                if (!this.isInitialized || !chrome.runtime?.id || this.contextInvalidated) {
                    return;
                }
                
                // Extra check for Greenhouse sites
                if (isGreenhouseOrIframe && document.visibilityState !== 'visible') {
                    return; // Skip ping when page is not visible
                }
                
                await chrome.runtime.sendMessage({ action: 'ping' });
            } catch (error) {
                // Runtime context invalidated, handle gracefully
                if (error.message && (
                    error.message.includes('context invalidated') || 
                    error.message.includes('Extension context invalidated') ||
                    error.message.includes('Could not establish connection') ||
                    error.message.includes('The message port closed')
                )) {
                    console.warn('⚠️ Extension context invalidated:', error.message);
                    this.handleContextInvalidation();
                    
                    // Clear the interval to stop further ping attempts
                    if (this.pingInterval) {
                        clearInterval(this.pingInterval);
                        this.pingInterval = null;
                    }
                }
            }
        }, pingInterval); // Variable ping interval based on site
    }
    
    handleContextInvalidation() {
        try {
            // Prevent multiple calls
            if (this.contextInvalidated) {
                return;
            }
            
            console.warn('🔄 Handling extension context invalidation...');
            
            // Mark as uninitialized and invalidated
            this.isInitialized = false;
            this.messageListenerActive = false;
            this.contextInvalidated = true;
            
            // Clear existing indicators
            try {
                const existingIndicator = document.getElementById('ai-form-filler-indicator');
                if (existingIndicator) {
                    existingIndicator.remove();
                }
            } catch (e) {
                console.warn('Failed to remove existing indicator:', e);
            }
            
            // Clear mutation observer
            try {
                if (this.mutationObserver) {
                    this.mutationObserver.disconnect();
                    this.mutationObserver = null;
                }
            } catch (e) {
                console.warn('Failed to disconnect mutation observer:', e);
            }
            
            // Clear ping interval
            try {
                if (this.pingInterval) {
                    clearInterval(this.pingInterval);
                    this.pingInterval = null;
                }
            } catch (e) {
                console.warn('Failed to clear ping interval:', e);
            }
            
            // Show user notification
            try {
                this.showContextInvalidationMessage();
            } catch (e) {
                console.warn('Failed to show invalidation message:', e);
            }
            
            // Don't auto-reinitialize as it may cause duplicate injections
            // User will need to refresh the page or click extension icon
        } catch (error) {
            console.error('Error in handleContextInvalidation:', error);
        }
    }
    
    showContextInvalidationMessage() {
        try {
            // Check if a notification already exists
            const existingNotification = document.getElementById('ai-form-filler-context-error');
            if (existingNotification) {
                return; // Don't show multiple notifications
            }
            
            const notification = document.createElement('div');
            notification.id = 'ai-form-filler-context-error';
            notification.innerHTML = `
                <div style="
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: #ef4444;
                    color: white;
                    padding: 16px 20px;
                    border-radius: 8px;
                    font-size: 14px;
                    font-family: system-ui;
                    z-index: 10001;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
                    text-align: center;
                    max-width: 400px;
                ">
                    <div style="margin-bottom: 8px;">⚠️ AI Form Filler Extension Error</div>
                    <div style="font-size: 12px; opacity: 0.9;">Extension context invalidated. Please refresh the page to continue using the form filler.</div>
                    <button onclick="location.reload()" style="
                        margin-top: 12px;
                        background: white;
                        color: #ef4444;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 12px;
                    ">Refresh Page</button>
                </div>
            `;
            
            // Ensure body exists before appending
            if (document.body) {
                document.body.appendChild(notification);
            } else {
                console.warn('Document body not available, cannot show notification');
                return;
            }
            
            // Auto-remove after 10 seconds
            setTimeout(() => {
                try {
                    if (notification && notification.parentNode) {
                        notification.remove();
                    }
                } catch (e) {
                    console.warn('Failed to remove notification:', e);
                }
            }, 10000);
            
        } catch (error) {
            console.error('Error showing context invalidation message:', error);
        }
    }
    
    extractFormFieldsForAI() {
        console.log('🔍 Extracting form fields for AI analysis...');
        const formFields = [];
        
        // Get all input, select, and textarea elements
        const allFields = document.querySelectorAll('input, select, textarea');
        
        allFields.forEach((field, index) => {
            // Skip hidden fields and buttons
            if (field.type === 'hidden' || field.type === 'button' || field.type === 'submit') {
                return;
            }
            
            const fieldInfo = {
                id: field.id || `field_${index}`,
                name: field.name || '',
                type: field.type || field.tagName.toLowerCase(),
                placeholder: field.placeholder || '',
                label: this.getFieldLabel(field) || '',
                classes: Array.from(field.classList).join(' '),
                aria_label: field.getAttribute('aria-label') || '',
                required: field.required || false,
                value: field.value || '',
                parent_element: field.parentElement?.tagName || '',
                position: {
                    index: index,
                    section: this.getFieldSection(field)
                }
            };
            
            // Add options for select fields
            if (field.tagName.toLowerCase() === 'select') {
                fieldInfo.options = Array.from(field.options).map(opt => opt.text).filter(text => text.trim());
            }
            
            formFields.push(fieldInfo);
        });
        
        console.log(`📊 Extracted ${formFields.length} fields for AI analysis`);
        return formFields;
    }
    
    getFieldSection(field) {
        // Try to determine which section/fieldset this field belongs to
        let current = field.parentElement;
        let depth = 0;
        
        while (current && depth < 5) {
            if (current.tagName === 'FIELDSET') {
                const legend = current.querySelector('legend');
                return legend ? legend.textContent.trim() : 'fieldset';
            }
            
            // Look for section-like containers
            const className = current.className.toLowerCase();
            if (className.includes('section') || className.includes('group') || className.includes('step')) {
                return className;
            }
            
            current = current.parentElement;
            depth++;
        }
        
        return 'main';
    }
    
    getFormBounds() {
        console.log('📐 Calculating form boundaries for screenshot cropping...');
        
        if (this.forms.length === 0) {
            console.log('📐 No forms detected, cannot get bounds');
            return null;
        }
        
        // Find the bounding box that encompasses all detected forms
        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;
        let validFormFound = false;
        
        this.forms.forEach((form, index) => {
            try {
                let bounds;
                
                // Handle virtual forms (input clusters)
                if (form.isVirtual && form.inputs) {
                    bounds = this.getVirtualFormBounds(form.inputs);
                } else if (form.getBoundingClientRect) {
                    bounds = form.getBoundingClientRect();
                } else {
                    console.warn(`📐 Form ${index} has no getBoundingClientRect method`);
                    return;
                }
                
                if (bounds && bounds.width > 0 && bounds.height > 0) {
                    console.log(`📐 Form ${index} bounds:`, bounds);
                    
                    minX = Math.min(minX, bounds.left);
                    minY = Math.min(minY, bounds.top);
                    maxX = Math.max(maxX, bounds.right);
                    maxY = Math.max(maxY, bounds.bottom);
                    validFormFound = true;
                }
            } catch (error) {
                console.warn(`📐 Error getting bounds for form ${index}:`, error);
            }
        });
        
        if (!validFormFound) {
            console.log('📐 No valid form bounds found');
            return null;
        }
        
        // Add some padding and ensure bounds are within viewport
        const padding = 20;
        const viewport = {
            width: window.innerWidth,
            height: window.innerHeight
        };
        
        const formBounds = {
            left: Math.max(0, minX - padding),
            top: Math.max(0, minY - padding),
            width: Math.min(viewport.width, maxX - minX + 2 * padding),
            height: Math.min(viewport.height, maxY - minY + 2 * padding)
        };
        
        // Ensure minimum size for meaningful screenshot
        formBounds.width = Math.max(formBounds.width, 300);
        formBounds.height = Math.max(formBounds.height, 200);
        
        console.log('📐 Calculated form bounds:', formBounds);
        return formBounds;
    }
    
    getVirtualFormBounds(inputs) {
        if (!inputs || inputs.length === 0) return null;
        
        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;
        
        inputs.forEach(input => {
            const bounds = input.getBoundingClientRect();
            if (bounds.width > 0 && bounds.height > 0) {
                minX = Math.min(minX, bounds.left);
                minY = Math.min(minY, bounds.top);
                maxX = Math.max(maxX, bounds.right);
                maxY = Math.max(maxY, bounds.bottom);
            }
        });
        
        if (minX === Infinity) return null;
        
        return {
            left: minX,
            top: minY,
            right: maxX,
            bottom: maxY,
            width: maxX - minX,
            height: maxY - minY
        };
    }

    detectJobForms() {
        this.forms = [];
        this.formFields.clear();

        console.log('🔍 Starting form detection...');
        
        // Detect ATS platform first
        const atsType = this.detectATSPlatform();
        console.log(`🏢 ATS Platform detected: ${atsType}`);

        // Find all forms on the page
        const allForms = document.querySelectorAll('form');
        console.log(`📋 Found ${allForms.length} total forms on page`);
        
        allForms.forEach((form, index) => {
            const isJobForm = this.isJobApplicationForm(form);
            console.log(`📝 Form ${index}: isJobForm=${isJobForm}, classes="${form.className}", id="${form.id}"`);
            
            if (isJobForm) {
                this.forms.push(form);
                this.mapFormFields(form, index);
                console.log(`✅ Added job form ${index} to detection list`);
            }
        });

        // Check for forms without <form> tags (SPAs, custom implementations)
        const potentialSelectors = [
            '[class*="form"]', '[class*="application"]', '[id*="form"]', '[id*="application"]',
            '[class*="job"]', '[class*="career"]', '[class*="apply"]', '[class*="candidate"]',
            '.application-form', '.job-form', '.apply-form', '.contact-form',
            '[role="form"]', '[data-form]', '[data-application]'
        ];
        
        const potentialForms = document.querySelectorAll(potentialSelectors.join(', '));
        console.log(`📋 Found ${potentialForms.length} potential form containers`);
        
        potentialForms.forEach((container, index) => {
            const hasJobFields = this.hasJobFormFields(container);
            console.log(`📦 Container ${index}: hasJobFields=${hasJobFields}, classes="${container.className}", id="${container.id}"`);
            
            if (hasJobFields && !this.forms.includes(container)) {
                this.forms.push(container);
                this.mapFormFields(container, `container-${index}`);
                console.log(`✅ Added container ${index} to detection list`);
            }
        });

        // Look for standalone input clusters (common in modern SPAs)
        this.detectInputClusters();

        console.log(`✅ Job form detection complete. Found ${this.forms.length} forms`);
        
        // Debug: show what forms were detected
        if (this.forms.length > 0) {
            console.log('📋 Detected job forms:', this.forms.map((form, i) => ({
                index: i,
                tagName: form.tagName || 'virtual',
                className: form.className || 'none',
                id: form.id || 'none',
                fieldCount: this.formFields.get(form)?.length || 0
            })));
        } else {
            console.log('❌ No job application forms detected on this page');
            console.log('💡 Page URL:', window.location.href);
            console.log('💡 Page title:', document.title);
        }
        
        // Update visual indicator
        this.updateFormIndicator();
    }

    detectInputClusters() {
        // Find clusters of related inputs that might not be in a form container
        const allInputs = document.querySelectorAll('input, textarea, select');
        const processedInputs = new Set();
        
        allInputs.forEach(input => {
            if (processedInputs.has(input)) return;
            
            const cluster = this.findInputCluster(input);
            if (cluster.length >= 3 && this.isJobInputCluster(cluster)) {
                // Create virtual form container
                const virtualForm = {
                    inputs: cluster,
                    isVirtual: true,
                    getBoundingClientRect: () => this.getClusterBounds(cluster)
                };
                
                this.forms.push(virtualForm);
                this.mapVirtualFormFields(virtualForm, `cluster-${this.forms.length}`);
                
                cluster.forEach(inp => processedInputs.add(inp));
            }
        });
    }

    findInputCluster(startInput) {
        const cluster = [startInput];
        const visited = new Set([startInput]);
        const queue = [startInput];
        
        while (queue.length > 0) {
            const current = queue.shift();
            const nearby = this.findNearbyInputs(current, 200); // 200px radius
            
            nearby.forEach(input => {
                if (!visited.has(input)) {
                    visited.add(input);
                    cluster.push(input);
                    queue.push(input);
                }
            });
        }
        
        return cluster;
    }

    findNearbyInputs(element, radius) {
        const rect = element.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        const allInputs = document.querySelectorAll('input, textarea, select');
        return Array.from(allInputs).filter(input => {
            if (input === element) return false;
            
            const inputRect = input.getBoundingClientRect();
            const inputCenterX = inputRect.left + inputRect.width / 2;
            const inputCenterY = inputRect.top + inputRect.height / 2;
            
            const distance = Math.sqrt(
                Math.pow(centerX - inputCenterX, 2) + 
                Math.pow(centerY - inputCenterY, 2)
            );
            
            return distance <= radius;
        });
    }

    isJobInputCluster(inputs) {
        const fieldTypes = inputs.map(input => this.identifyField(input));
        const validFields = fieldTypes.filter(field => field.category !== null);
        
        // At least 60% of inputs should be identifiable job-related fields
        return validFields.length >= Math.ceil(inputs.length * 0.6);
    }

    getClusterBounds(inputs) {
        if (inputs.length === 0) return { top: 0, left: 0, right: 0, bottom: 0 };
        
        const rects = inputs.map(input => input.getBoundingClientRect());
        return {
            top: Math.min(...rects.map(r => r.top)),
            left: Math.min(...rects.map(r => r.left)),
            right: Math.max(...rects.map(r => r.right)),
            bottom: Math.max(...rects.map(r => r.bottom))
        };
    }

    mapVirtualFormFields(virtualForm, formIndex) {
        const fields = {
            personalInfo: {},
            experience: {},
            education: {},
            skills: {},
            other: {}
        };

        virtualForm.inputs.forEach(input => {
            const fieldInfo = this.identifyField(input);
            if (fieldInfo.category && fieldInfo.type) {
                fields[fieldInfo.category][fieldInfo.type] = {
                    element: input,
                    selector: this.getElementSelector(input),
                    type: input.type,
                    required: input.required,
                    confidence: fieldInfo.confidence || 0
                };
            }
        });

        this.formFields.set(formIndex, fields);
    }

    isJobApplicationForm(form) {
        const formText = form.innerText?.toLowerCase() || '';
        const formClasses = form.className?.toLowerCase() || '';
        const formId = form.id?.toLowerCase() || '';
        const formAction = form.action?.toLowerCase() || '';
        
        console.log(`🔍 Checking form: classes="${formClasses}", id="${formId}", action="${formAction}"`);

        // Enhanced job application indicators
        const strongJobIndicators = [
            'application', 'apply', 'resume', 'cv', 'career', 'hiring',
            'candidate', 'applicant', 'job application', 'employment'
        ];

        const mediumJobIndicators = [
            'job', 'position', 'work experience', 'education', 'contact us',
            'get in touch', 'join us', 'opportunities'
        ];

        // Check all text sources
        const allText = `${formText} ${formClasses} ${formId} ${formAction}`;
        
        // Strong indicators (high confidence)
        const hasStrongIndicators = strongJobIndicators.some(keyword => 
            allText.includes(keyword)
        );

        // Medium indicators (need additional validation)
        const hasMediumIndicators = mediumJobIndicators.some(keyword => 
            allText.includes(keyword)
        );

        // URL-based detection
        const url = window.location.href.toLowerCase();
        const hasJobUrl = ['career', 'job', 'apply', 'hiring', 'employment', 'opportunities'].some(keyword =>
            url.includes(keyword)
        );

        // Field-based validation
        const hasJobFields = this.hasJobFormFields(form);
        const fieldScore = this.calculateJobFieldScore(form);

        // Combined scoring system
        let confidence = 0;
        if (hasStrongIndicators) confidence += 0.6;
        if (hasMediumIndicators) confidence += 0.2;
        if (hasJobUrl) confidence += 0.2;
        if (hasJobFields) confidence += 0.3;
        if (fieldScore > 0.5) confidence += 0.2;

        console.log(`📊 Form analysis: strongIndicators=${hasStrongIndicators}, mediumIndicators=${hasMediumIndicators}, jobUrl=${hasJobUrl}, hasJobFields=${hasJobFields}, fieldScore=${fieldScore.toFixed(2)}, confidence=${confidence.toFixed(2)}`);

        // Consider form as job application if confidence > 0.3 (lowered threshold)
        const isJobForm = confidence > 0.3;
        console.log(`✅ Form is job application: ${isJobForm}`);
        return isJobForm;
    }

    detectATSPlatform() {
        const url = window.location.href.toLowerCase();
        const pageHTML = document.documentElement.outerHTML.toLowerCase();
        
        // Major ATS platform detection
        const atsSignatures = {
            'workday': [
                'workday.com', 'wd1.workdaycdn.com', '[data-automation-id]', 'workday-application'
            ],
            'greenhouse': [
                'greenhouse.io', 'boards.greenhouse.io', 'job-boards.greenhouse.io', 
                'greenhouse-application', '.application--form'
            ],
            'icims': [
                'icims.com', 'icitms', 'icims-application', '.icims'
            ],
            'taleo': [
                'taleo.net', 'tbe.taleo.net', 'taleo-application'
            ],
            'avature': [
                'avature.net', 'avature-application'
            ],
            'lever': [
                'lever.co', 'jobs.lever.co', 'lever-application'
            ],
            'smartrecruiters': [
                'smartrecruiters.com', 'jobs.smartrecruiters.com', 'smartrecruiters-application'
            ],
            'indeed': [
                'indeed.com', 'indeed-apply'
            ],
            'linkedin': [
                'linkedin.com/jobs', 'linkedin-job-apply'
            ]
        };

        for (const [platform, signatures] of Object.entries(atsSignatures)) {
            for (const signature of signatures) {
                if (url.includes(signature) || pageHTML.includes(signature)) {
                    return platform;
                }
            }
        }

        return 'generic';
    }

    calculateJobFieldScore(form) {
        const inputs = form.querySelectorAll ? 
            form.querySelectorAll('input, textarea, select') : 
            form.inputs || [];
            
        if (inputs.length === 0) return 0;

        let jobFieldCount = 0;
        inputs.forEach(input => {
            const fieldInfo = this.identifyField(input);
            if (fieldInfo.category !== null) {
                jobFieldCount++;
            }
        });

        return jobFieldCount / inputs.length;
    }

    hasJobFormFields(container) {
        const inputs = container.querySelectorAll('input, textarea, select');
        const fieldNames = Array.from(inputs).map(input => 
            (input.name || input.id || input.placeholder || '').toLowerCase()
        );

        const jobFieldKeywords = [
            'first name', 'last name', 'email', 'phone', 'resume', 'cv',
            'experience', 'education', 'cover letter', 'salary', 'skills',
            'portfolio', 'linkedin', 'github', 'years', 'degree'
        ];

        return jobFieldKeywords.some(keyword =>
            fieldNames.some(fieldName => fieldName.includes(keyword))
        );
    }

    mapFormFields(form, formIndex) {
        const fields = {
            personalInfo: {},
            experience: {},
            education: {},
            skills: {},
            other: {}
        };

        const inputs = form.querySelectorAll ? 
            form.querySelectorAll('input, textarea, select') : 
            form.inputs || [];
        
        inputs.forEach(input => {
            const fieldInfo = this.identifyField(input);
            if (fieldInfo.category && fieldInfo.type) {
                fields[fieldInfo.category][fieldInfo.type] = {
                    element: input,
                    selector: this.getElementSelector(input),
                    type: input.type,
                    required: input.required,
                    confidence: fieldInfo.confidence || 0,
                    detected: Date.now()
                };
            }
        });

        this.formFields.set(formIndex, fields);
    }

    identifyField(input) {
        const name = (input.name || '').toLowerCase();
        const id = (input.id || '').toLowerCase();
        const placeholder = (input.placeholder || '').toLowerCase();
        const label = this.getFieldLabel(input);
        const ariaLabel = (input.getAttribute('aria-label') || '').toLowerCase();
        const title = (input.title || '').toLowerCase();
        
        const allText = `${name} ${id} ${placeholder} ${label} ${ariaLabel} ${title}`.toLowerCase();

        // Enhanced field patterns with fuzzy matching
        const fieldPatterns = {
            personalInfo: {
                fullName: [
                    'full_name', 'fullname', 'name', 'full-name', 'candidate_name',
                    'applicant_name', 'user_name', 'your_name', 'contact_name'
                ],
                firstName: [
                    'first', 'fname', 'given', 'name_first', 'firstname', 'givenname',
                    'forename', 'first_name', 'name-first', 'user_first', 'personal_first',
                    'first-name', 'given_name', 'given-name'
                ],
                lastName: [
                    'last', 'lname', 'family', 'surname', 'name_last', 'lastname', 
                    'familyname', 'name-last', 'user_last', 'personal_last',
                    'last-name', 'family_name', 'family-name', 'sur_name'
                ],
                email: [
                    'email', 'mail', 'e-mail', 'email_address', 'emailaddress',
                    'user_email', 'contact_email', 'work_email'
                ],
                phone: [
                    'phone', 'mobile', 'cell', 'tel', 'telephone', 'contact',
                    'phone_number', 'phonenumber', 'mobile_number', 'cell_phone',
                    'work_phone', 'home_phone', 'phone-number', 'mobile-number',
                    'contact_number', 'contact-number', 'contact_phone', 'primary_phone',
                    'phone_primary', 'tel_number', 'telephone_number'
                ],
                address: [
                    'address', 'street', 'location', 'address_line', 'street_address',
                    'home_address', 'mailing_address', 'residence'
                ],
                city: [
                    'city', 'town', 'municipality', 'locality'
                ],
                state: [
                    'state', 'province', 'region', 'territory'
                ],
                zipCode: [
                    'zip', 'postal', 'postcode', 'zip_code', 'postal_code'
                ],
                country: [
                    'country', 'nation', 'nationality'
                ],
                linkedin: [
                    'linkedin', 'linked_in', 'linkedin_url', 'linkedin_profile',
                    'linkedin-url', 'linkedin-profile', 'linked-in', 'linkedinurl',
                    'linkedin_link', 'linkedin-link', 'professional_profile',
                    'social_linkedin', 'linkedin_username'
                ],
                portfolio: [
                    'portfolio', 'website', 'github', 'personal_site', 'web',
                    'homepage', 'blog', 'portfolio_url'
                ]
            },
            experience: {
                summary: [
                    'experience', 'work_experience', 'professional_experience',
                    'background', 'work_history', 'career_summary', 'summary',
                    'bio', 'about', 'description'
                ],
                company: [
                    'company', 'employer', 'organization', 'current_company',
                    'workplace', 'firm', 'corporation'
                ],
                title: [
                    'title', 'position', 'role', 'job_title', 'current_title',
                    'current_position', 'job_role', 'designation'
                ],
                years: [
                    'years', 'experience_years', 'years_experience', 'tenure',
                    'duration', 'work_years', 'total_experience'
                ]
            },
            education: {
                degree: [
                    'degree', 'education', 'education_level', 'qualification',
                    'diploma', 'certificate', 'academic_degree'
                ],
                university: [
                    'university', 'college', 'school', 'institution', 'alma_mater',
                    'educational_institution', 'academy'
                ],
                major: [
                    'major', 'field', 'study', 'subject', 'specialization',
                    'concentration', 'discipline', 'area_of_study'
                ],
                graduationYear: [
                    'graduation', 'grad_year', 'completion', 'year_graduated',
                    'finish_year', 'completion_year'
                ],
                gpa: [
                    'gpa', 'grade', 'marks', 'score', 'cgpa', 'average'
                ]
            },
            skills: {
                technical: [
                    'skills', 'technical_skills', 'programming', 'technologies',
                    'languages', 'frameworks', 'tools', 'competencies'
                ]
            },
            other: {
                coverLetter: [
                    'cover', 'letter', 'motivation', 'why', 'cover_letter',
                    'personal_statement', 'objective', 'interest'
                ],
                salary: [
                    'salary', 'compensation', 'expected_salary', 'pay',
                    'wage', 'remuneration', 'salary_expectation'
                ],
                availability: [
                    'availability', 'start_date', 'available', 'notice',
                    'when_available', 'start_time'
                ],
                workAuthorization: [
                    'authorization', 'visa', 'eligible', 'authorized', 'sponsor',
                    'work_permit', 'legal_status', 'employment_authorization',
                    'work_authorization', 'work-authorization', 'visa_status',
                    'visa-status', 'sponsorship', 'legally_authorized', 'work_eligible',
                    'employment_eligible', 'require_sponsorship', 'visa_required',
                    'work_visa', 'employment_visa', 'legal_work', 'us_citizen'
                ],
                willingToRelocate: [
                    'relocate', 'relocation', 'move', 'willing_to_move',
                    'open_to_relocation'
                ],
                remoteWork: [
                    'remote', 'work_from_home', 'telecommute', 'wfh'
                ],
                resume: [
                    'resume', 'cv', 'curriculum_vitae', 'resume_upload', 'cv_upload',
                    'attach_resume', 'upload_resume', 'resume_file', 'cv_file',
                    'resume_attachment', 'cv_attachment', 'document_upload', 'file_upload',
                    'document', 'attachment', 'upload', 'file', 'resume-upload',
                    'cv-upload', 'resume-file', 'cv-file', 'upload-resume', 'upload-cv',
                    'resumefile', 'cvfile', 'resume_doc', 'cv_doc', 'documents'
                ],
                coverLetterFile: [
                    'cover_letter_file', 'cover_letter_upload', 'letter_upload',
                    'attach_cover_letter', 'cover_letter_attachment'
                ]
            }
        };

        // Use enhanced fuzzy matching
        for (const [category, categoryPatterns] of Object.entries(fieldPatterns)) {
            for (const [fieldType, patterns] of Object.entries(categoryPatterns)) {
                if (this.fuzzyMatchField(allText, patterns)) {
                    return { category, type: fieldType, confidence: this.calculateMatchConfidence(allText, patterns) };
                }
            }
        }

        return { category: null, type: null, confidence: 0 };
    }

    matchesKeywords(text, keywords) {
        return keywords.some(keyword => text.includes(keyword));
    }

    fuzzyMatchField(text, patterns) {
        // Check for exact matches first
        for (const pattern of patterns) {
            if (text.includes(pattern)) {
                return true;
            }
        }

        // Check for partial matches with word boundaries
        const words = text.split(/\s+|[_-]+/);
        for (const pattern of patterns) {
            const patternWords = pattern.split(/\s+|[_-]+/);
            if (this.hasWordOverlap(words, patternWords)) {
                return true;
            }
        }

        // Check for fuzzy string similarity
        for (const pattern of patterns) {
            if (this.calculateSimilarity(text, pattern) > 0.7) {
                return true;
            }
        }

        return false;
    }

    hasWordOverlap(words1, words2) {
        const set1 = new Set(words1.filter(w => w.length > 2));
        const set2 = new Set(words2.filter(w => w.length > 2));
        
        for (const word of set2) {
            if (set1.has(word)) {
                return true;
            }
        }
        return false;
    }

    calculateSimilarity(str1, str2) {
        const longer = str1.length > str2.length ? str1 : str2;
        const shorter = str1.length > str2.length ? str2 : str1;
        
        if (longer.length === 0) return 1.0;
        
        const editDistance = this.levenshteinDistance(longer, shorter);
        return (longer.length - editDistance) / longer.length;
    }

    levenshteinDistance(str1, str2) {
        const matrix = Array(str2.length + 1).fill().map(() => Array(str1.length + 1).fill(0));
        
        for (let i = 0; i <= str1.length; i++) matrix[0][i] = i;
        for (let j = 0; j <= str2.length; j++) matrix[j][0] = j;
        
        for (let j = 1; j <= str2.length; j++) {
            for (let i = 1; i <= str1.length; i++) {
                const cost = str1[i - 1] === str2[j - 1] ? 0 : 1;
                matrix[j][i] = Math.min(
                    matrix[j - 1][i] + 1,
                    matrix[j][i - 1] + 1,
                    matrix[j - 1][i - 1] + cost
                );
            }
        }
        
        return matrix[str2.length][str1.length];
    }

    calculateMatchConfidence(text, patterns) {
        let maxConfidence = 0;
        
        for (const pattern of patterns) {
            if (text.includes(pattern)) {
                maxConfidence = Math.max(maxConfidence, 1.0);
            } else {
                const similarity = this.calculateSimilarity(text, pattern);
                maxConfidence = Math.max(maxConfidence, similarity);
            }
        }
        
        return maxConfidence;
    }

    getFieldLabel(input) {
        // Try to find associated label
        const labels = document.querySelectorAll('label');
        for (const label of labels) {
            if (label.getAttribute('for') === input.id || label.contains(input)) {
                return label.textContent;
            }
        }

        // Check for nearby text
        const parent = input.parentElement;
        if (parent) {
            const prevSibling = input.previousElementSibling;
            if (prevSibling && prevSibling.textContent) {
                return prevSibling.textContent;
            }
        }

        return '';
    }

    getElementSelector(element) {
        // Priority order for selector reliability
        
        // 1. ID selector (most reliable) - but only if valid
        if (element.id && this.isValidCSSSelector(element.id)) {
            try {
                const escapedId = CSS.escape(element.id);
                if (document.querySelectorAll(`#${escapedId}`).length === 1) {
                    return `#${escapedId}`;
                }
            } catch (error) {
                console.warn('Invalid ID selector:', element.id);
            }
        }
        
        // 2. Name attribute (good reliability)
        if (element.name && document.querySelectorAll(`[name="${element.name}"]`).length === 1) {
            return `[name="${element.name}"]`;
        }
        
        // 3. Data attributes (often stable)
        for (const attr of element.attributes) {
            if (attr.name.startsWith('data-') && 
                document.querySelectorAll(`[${attr.name}="${attr.value}"]`).length === 1) {
                return `[${attr.name}="${attr.value}"]`;
            }
        }
        
        // 4. Unique class combination
        if (element.className) {
            const classes = element.className.split(' ')
                .filter(c => c.trim() && this.isValidCSSClass(c))
                .map(c => CSS.escape(c));
            if (classes.length > 0) {
                try {
                    const classSelector = '.' + classes.join('.');
                    if (document.querySelectorAll(classSelector).length === 1) {
                        return classSelector;
                    }
                } catch (error) {
                    console.warn('Invalid class selector:', classes);
                }
            }
        }
        
        // 5. Type + placeholder combination
        if (element.type && element.placeholder) {
            const selector = `${element.tagName.toLowerCase()}[type="${element.type}"][placeholder="${element.placeholder}"]`;
            if (document.querySelectorAll(selector).length === 1) {
                return selector;
            }
        }
        
        // 6. Enhanced xpath-like selector with more context
        return this.generateRobustSelector(element);
    }

    generateRobustSelector(element) {
        const path = [];
        let current = element;
        
        while (current && current !== document.body && current !== document.documentElement) {
            let selector = current.tagName.toLowerCase();
            
            // Add distinguishing attributes
            if (current.id && this.isValidCSSSelector(current.id)) {
                selector += `#${CSS.escape(current.id)}`;
            } else if (current.className) {
                const classes = current.className.split(' ')
                    .filter(c => c.trim() && this.isValidCSSClass(c))
                    .map(c => CSS.escape(c));
                if (classes.length > 0) {
                    selector += '.' + classes.slice(0, 2).join('.');
                }
            } else {
                // Use nth-child as fallback
                const siblings = Array.from(current.parentNode?.children || []);
                const index = siblings.indexOf(current);
                if (index >= 0) {
                    selector += `:nth-child(${index + 1})`;
                }
            }
            
            path.unshift(selector);
            current = current.parentElement;
            
            // Limit path depth to prevent overly long selectors
            if (path.length > 5) break;
        }
        
        return path.join(' > ');
    }

    isValidCSSSelector(id) {
        // Check if ID contains invalid characters for CSS selectors
        return !/^[0-9]/.test(id) && !/[\[\]{}:()\s]/.test(id);
    }

    isValidCSSClass(className) {
        // Check if class name is valid for CSS
        return className.length > 0 && !/[\[\]{}:()\s]/.test(className);
    }

    getFormTypes() {
        const types = new Set();
        
        this.forms.forEach(form => {
            const text = (form.innerText || '').toLowerCase();
            if (text.includes('application')) types.add('Application');
            if (text.includes('career') || text.includes('job')) types.add('Career');
            if (text.includes('resume') || text.includes('cv')) types.add('Resume Upload');
            if (text.includes('contact')) types.add('Contact');
        });

        return Array.from(types);
    }

    async fillFormWithData(formData) {
        try {
            let filledFields = 0;
            let totalFields = 0;

            for (const [formIndex, fields] of this.formFields.entries()) {
                for (const [category, categoryFields] of Object.entries(fields)) {
                    for (const [fieldType, fieldInfo] of Object.entries(categoryFields)) {
                        totalFields++;
                        
                        const value = this.getValueForField(formData, category, fieldType);
                        console.log(`🔍 Field: ${category}.${fieldType} = "${value}" (element: ${fieldInfo.element?.tagName})`);
                        
                        if (value && fieldInfo.element && fieldInfo.element.tagName) {
                            // Special handling for file uploads - pass resumeId instead of value
                            if (fieldInfo.element.type === 'file' && (fieldType === 'resume' || fieldType === 'coverLetterFile')) {
                                console.log(`📁 File upload detected: ${fieldType}, element type: ${fieldInfo.element.type}`);
                                if (formData.resumeId) {
                                    console.log(`📤 Uploading resume with ID: ${formData.resumeId}`);
                                    await this.fillField(fieldInfo.element, formData.resumeId);
                                } else {
                                    console.warn('❌ No resumeId found in formData for file upload');
                                }
                            } else {
                                console.log(`📝 Filling ${fieldType} with: "${value}"`);
                                await this.fillField(fieldInfo.element, value);
                            }
                            filledFields++;
                        } else if (!value) {
                            console.log(`⚠️ No value found for ${category}.${fieldType}`);
                        } else if (!fieldInfo.element) {
                            console.log(`⚠️ No element found for ${category}.${fieldType}`);
                        } else if (fieldInfo.element && !value) {
                            console.log(`⚠️ No value for field: ${category}.${fieldType}`);
                        }
                    }
                }
            }

            // Log the filling activity for learning
            await this.logFillingActivity(formData, filledFields, totalFields);

            return {
                success: true,
                filledFields,
                totalFields,
                accuracy: totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : 0
            };

        } catch (error) {
            console.error('Form filling error:', error);
            return { success: false, error: error.message };
        }
    }

    getValueForField(formData, category, fieldType) {
        // Try direct field access first
        const directValue = formData[category]?.[fieldType];
        if (directValue) return directValue;
        
        // Try flat structure (API response format)
        const flatValue = formData[fieldType];
        if (flatValue) return flatValue;
        
        // Special handling for common field mappings
        const fieldMappings = {
            firstName: ['first_name', 'fname', 'given_name'],
            lastName: ['last_name', 'lname', 'family_name', 'surname'],
            email: ['user_email', 'email_address', 'mail'],
            phone: ['phone_number', 'telephone', 'mobile'],
            company: ['current_company', 'employer'],
            position: ['job_title', 'current_position', 'role'],
        };
        
        // Check alternative field names
        if (fieldMappings[fieldType]) {
            for (const altName of fieldMappings[fieldType]) {
                const altValue = formData[altName];
                if (altValue) return altValue;
            }
        }
        
        // Special handling for name fields
        if (category === 'personalInfo' && fieldType === 'firstName') {
            const fullName = formData.firstName || formData.name || formData.fullName;
            if (fullName && typeof fullName === 'string') {
                const parts = fullName.trim().split(/\s+/);
                console.log(`🔤 Splitting name "${fullName}" -> firstName: "${parts[0]}"`);
                return parts[0] || null;
            }
        }
        
        if (category === 'personalInfo' && fieldType === 'lastName') {
            const fullName = formData.lastName || formData.name || formData.fullName;
            if (fullName && typeof fullName === 'string') {
                const parts = fullName.trim().split(/\s+/);
                const lastName = parts.slice(1).join(' ');
                console.log(`🔤 Splitting name "${fullName}" -> lastName: "${lastName}"`);
                return lastName || null;
            }
        }
        
        // Handle common field patterns with sensible defaults
        if (fieldType === 'workAuthorization' || fieldType.includes('sponsor') || fieldType.includes('visa')) {
            return 'Yes, I am authorized to work';
        }
        
        if (fieldType.includes('relocate') || fieldType.includes('location')) {
            return 'Open to relocation';
        }
        
        // Provide defaults for common missing fields
        if (fieldType.includes('phone') || category === 'personalInfo' && fieldType === 'phone') {
            return '+1 (555) 123-4567'; // Placeholder phone number
        }
        
        if (fieldType.includes('linkedin') || fieldType.includes('profile')) {
            return 'https://linkedin.com/in/divyanshgupta';
        }
        
        if (fieldType.includes('github') || fieldType.includes('portfolio')) {
            return 'https://github.com/divyanshgupta';
        }
        
        if (fieldType.includes('company') || fieldType.includes('employer')) {
            return 'Tech Innovations Inc.';
        }
        
        if (fieldType.includes('position') || fieldType.includes('title') || fieldType.includes('role')) {
            return 'Senior Software Engineer';
        }
        
        if (fieldType.includes('experience') || fieldType.includes('years')) {
            return '5+ years';
        }
        
        if (fieldType.includes('degree') || fieldType.includes('education')) {
            return 'Bachelor of Computer Science';
        }
        
        if (fieldType.includes('school') || fieldType.includes('university')) {
            return 'University of Technology';
        }
        
        if (fieldType.includes('hear') || fieldType.includes('referral') || fieldType.includes('source')) {
            return 'Job search engines';
        }
        
        return null;
    }

    async performOneClickApply(data) {
        console.log('🚀 Starting one-click apply process...');
        const startTime = Date.now();
        
        try {
            // Step 1: Extract job information
            const jobInfo = this.extractJobInformation();
            console.log('📋 Extracted job info:', jobInfo);
            
            // Step 2: Fill form with data
            const fillResult = await this.fillFormWithData(data);
            if (!fillResult.success) {
                throw new Error('Form filling failed: ' + fillResult.error);
            }
            
            // Step 3: Find and click submit button
            const submitResult = await this.findAndClickSubmitButton();
            if (!submitResult.success) {
                throw new Error('Submit button not found or failed to click');
            }
            
            // Step 4: Track application
            const timeSpent = Math.round((Date.now() - startTime) / 1000);
            await this.trackJobApplication({
                ...jobInfo,
                ats_platform: this.detectATSPlatform(),
                form_fields_detected: fillResult.analysis?.totalFields || 0,
                form_fields_filled: fillResult.analysis?.filledFields || 0,
                time_spent_seconds: timeSpent
            });
            
            console.log('✅ One-click apply completed successfully');
            return { 
                success: true, 
                message: 'Application submitted successfully!',
                timeSpent: timeSpent,
                jobInfo: jobInfo
            };
            
        } catch (error) {
            console.error('❌ One-click apply failed:', error);
            return { success: false, error: error.message };
        }
    }

    extractJobInformation() {
        const url = window.location.href;
        
        // Extract job title - try multiple selectors
        const titleSelectors = [
            'h1[data-automation-id="jobPostingHeader"]', // Workday
            '.job__title h1', // Greenhouse
            '.job-title', '.position-title', 'h1.job-post-title',
            '[data-testid="job-title"]', '.job-header h1'
        ];
        
        let jobTitle = 'Unknown Position';
        for (const selector of titleSelectors) {
            const element = document.querySelector(selector);
            if (element && element.textContent.trim()) {
                jobTitle = element.textContent.trim();
                break;
            }
        }
        
        // Extract company name
        const companySelectors = [
            '[data-automation-id="jobPostingCompany"]', // Workday
            '.job__company', // Greenhouse
            '.company-name', '.employer-name',
            '[data-testid="company-name"]'
        ];
        
        let company = 'Unknown Company';
        for (const selector of companySelectors) {
            const element = document.querySelector(selector);
            if (element && element.textContent.trim()) {
                company = element.textContent.trim();
                break;
            }
        }
        
        // Extract location
        const locationSelectors = [
            '[data-automation-id="jobPostingLocation"]',
            '.job__location', '.location', '.job-location'
        ];
        
        let location = null;
        for (const selector of locationSelectors) {
            const element = document.querySelector(selector);
            if (element && element.textContent.trim()) {
                location = element.textContent.trim();
                break;
            }
        }
        
        // Extract job description
        const descriptionSelectors = [
            '[data-automation-id="jobPostingDescription"]',
            '.job__description', '.job-description', '.job-details'
        ];
        
        let jobDescription = null;
        for (const selector of descriptionSelectors) {
            const element = document.querySelector(selector);
            if (element && element.textContent.trim()) {
                jobDescription = element.textContent.trim();
                break;
            }
        }
        
        return {
            job_title: jobTitle,
            company: company,
            job_url: url,
            location: location,
            job_description: jobDescription
        };
    }

    async findAndClickSubmitButton() {
        console.log('🔍 Looking for submit button...');
        
        const submitSelectors = [
            'button[data-automation-id="submitApplication"]', // Workday
            'button[type="submit"]', // Generic
            '.application--submit button', // Greenhouse
            'input[type="submit"]',
            'button[aria-label*="Submit"], button[aria-label*="Apply"]',
            '[data-testid="submit-button"]'
        ];
        
        for (const selector of submitSelectors) {
            const buttons = document.querySelectorAll(selector);
            for (const button of buttons) {
                const text = button.textContent.toLowerCase();
                if (text.includes('submit') || text.includes('apply') || 
                    text.includes('send') || button.type === 'submit') {
                    
                    console.log('✅ Found submit button:', button.textContent);
                    
                    // Scroll to button
                    button.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    await new Promise(resolve => setTimeout(resolve, 500));
                    
                    // Click the button
                    button.focus();
                    await new Promise(resolve => setTimeout(resolve, 100));
                    button.click();
                    
                    return { success: true };
                }
            }
        }
        
        console.warn('❌ Submit button not found');
        return { success: false, error: 'Submit button not found' };
    }

    async trackJobApplication(applicationData) {
        try {
            console.log('📊 Tracking job application:', applicationData);
            
            const response = await fetch('http://localhost:8000/api/track-application', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(applicationData)
            });
            
            if (response.ok) {
                console.log('✅ Application tracked successfully');
            } else {
                console.warn('⚠️ Failed to track application');
            }
        } catch (error) {
            console.warn('⚠️ Error tracking application:', error);
        }
    }

    async fillField(element, value) {
        if (!element || !value) return;

        // Add human-like delay
        await this.humanDelay();

        const elementType = element.type?.toLowerCase() || element.tagName.toLowerCase();
        const stringValue = String(value).trim();

        try {
            // Handle different field types
            switch (elementType) {
                case 'select':
                case 'select-one':
                    await this.fillSelectField(element, stringValue);
                    break;
                    
                case 'checkbox':
                    await this.fillCheckboxField(element, stringValue);
                    break;
                    
                case 'radio':
                    await this.fillRadioField(element, stringValue);
                    break;
                    
                case 'file':
                    await this.fillFileField(element, value);
                    break;
                    
                default:
                    // Text, email, tel, textarea, etc.
                    await this.fillTextField(element, stringValue);
                    break;
            }
        } catch (error) {
            console.error(`Error filling field ${element.name || element.id}:`, error);
        }
    }

    async fillTextField(element, value) {
        // Check if this is a location field with autocomplete
        const isLocationField = this.isLocationField(element);
        
        // Focus the element
        element.focus();
        await new Promise(resolve => setTimeout(resolve, 100));

        // Clear existing value properly
        element.select();
        element.value = '';

        if (isLocationField) {
            // Handle location autocomplete fields specially
            await this.fillLocationField(element, value);
        } else {
            // Set value directly for regular text fields
            element.value = value;
            this.triggerFieldEvents(element);
        }
        
        await new Promise(resolve => setTimeout(resolve, 200));
        element.blur();
        
        // Verify the value was set correctly (skip for location fields with autocomplete)
        if (element.value !== value && !isLocationField) {
            console.warn(`Text field value mismatch: expected "${value}", got "${element.value}"`);
        }
    }

    isLocationField(element) {
        const fieldText = (element.name + ' ' + element.id + ' ' + element.placeholder + ' ' + 
                          element.className + ' ' + (element.getAttribute('aria-label') || '')).toLowerCase();
        
        return fieldText.includes('location') || fieldText.includes('city') || 
               fieldText.includes('address') || fieldText.includes('where');
    }

    async fillLocationField(element, value) {
        console.log(`📍 Location field detected, trying autocomplete for: ${value}`);
        
        // Try different location formats for autocomplete
        const locationFormats = this.getLocationFormats(value);
        
        for (const format of locationFormats) {
            console.log(`📍 Trying location format: ${format}`);
            
            // Clear and type the location format
            element.value = '';
            element.value = format;
            
            // Trigger input events to activate autocomplete
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('keyup', { bubbles: true }));
            element.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
            
            // Wait for autocomplete dropdown
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Look for autocomplete dropdown
            const dropdown = this.findAutocompleteDropdown(element);
            if (dropdown) {
                console.log(`📍 Found autocomplete dropdown`);
                const matchingOption = this.findMatchingLocationOption(dropdown, value);
                if (matchingOption) {
                    console.log(`✅ Found matching location option: ${matchingOption.textContent}`);
                    matchingOption.click();
                    await new Promise(resolve => setTimeout(resolve, 500));
                    return;
                }
            }
        }
        
        // If no autocomplete worked, just set the original value
        console.log(`📍 No autocomplete match found, using original value: ${value}`);
        element.value = value;
        this.triggerFieldEvents(element);
    }

    getLocationFormats(location) {
        // Generate different format variations for location
        const formats = [location];
        
        // If it's "City, State" format, expand variations
        if (location.match(/^[^,]+,\s*[A-Z]{2}$/)) {
            const parts = location.split(', ');
            const city = parts[0];
            const state = parts[1];
            
            // Add expanded formats
            formats.push(`${location}, United States`);
            formats.push(`${city}, ${state}, United States`);
            
            // Add state expansions
            const stateExpansions = {
                'AZ': 'Arizona', 'CA': 'California', 'NY': 'New York', 'TX': 'Texas',
                'FL': 'Florida', 'WA': 'Washington', 'GA': 'Georgia', 'NC': 'North Carolina',
                'TN': 'Tennessee'
            };
            if (stateExpansions[state]) {
                formats.push(`${city}, ${stateExpansions[state]}`);
                formats.push(`${city}, ${stateExpansions[state]}, United States`);
            }
        }
        
        return formats;
    }

    findAutocompleteDropdown(element) {
        // Look for common autocomplete dropdown patterns
        const selectors = [
            '.autocomplete-dropdown',
            '.location-dropdown', 
            '.typeahead-dropdown',
            '[role="listbox"]',
            '.dropdown-menu',
            '.suggestions',
            '.autocomplete-suggestions',
            '.pac-container' // Google Places autocomplete
        ];
        
        for (const selector of selectors) {
            const dropdown = document.querySelector(selector);
            if (dropdown && dropdown.offsetHeight > 0) {
                console.log(`📍 Found dropdown with selector: ${selector}`);
                return dropdown;
            }
        }
        
        // Look for dropdowns near the input element
        const parent = element.closest('.form-group, .field, .input-group') || element.parentElement;
        const nearbyDropdown = parent?.querySelector('[role="listbox"], .dropdown');
        if (nearbyDropdown && nearbyDropdown.offsetHeight > 0) {
            console.log(`📍 Found nearby dropdown`);
            return nearbyDropdown;
        }
        
        return null;
    }

    findMatchingLocationOption(dropdown, targetLocation) {
        const options = dropdown.querySelectorAll('[role="option"], li, .option, .suggestion, .pac-item');
        const targetCity = targetLocation.toLowerCase().split(',')[0].trim();
        
        console.log(`📍 Searching ${options.length} dropdown options for: ${targetCity}`);
        
        for (const option of options) {
            const optionText = option.textContent.toLowerCase();
            console.log(`📍 Checking option: ${optionText}`);
            
            // Match if option contains our city name
            if (optionText.includes(targetCity)) {
                return option;
            }
        }
        return null;
    }

    async fillSelectField(element, value) {
        console.log(`🔽 Dropdown: Attempting to select "${value}" from ${element.options.length} options`);
        
        // Focus the select
        element.focus();
        await new Promise(resolve => setTimeout(resolve, 100));

        // Get all options and log them for debugging
        const options = Array.from(element.options);
        const validOptions = options.filter(opt => opt.value && opt.text.trim());
        
        console.log(`🔍 Available options:`, validOptions.map(o => `"${o.text}" (value: ${o.value})`).slice(0, 10));
        
        // Skip filling if this looks like inappropriate field for this value
        if (this.shouldSkipDropdownFill(element, value, validOptions)) {
            console.log(`🚫 Skipping dropdown fill for "${value}" - inappropriate match`);
            element.blur();
            return;
        }
        
        let matchedOption = null;

        // First try exact matches
        matchedOption = validOptions.find(opt => 
            opt.text.toLowerCase() === value.toLowerCase() || 
            opt.value.toLowerCase() === value.toLowerCase()
        );

        // If no exact match, try partial matches
        if (!matchedOption) {
            matchedOption = validOptions.find(opt => 
                opt.text.toLowerCase().includes(value.toLowerCase()) ||
                value.toLowerCase().includes(opt.text.toLowerCase())
            );
        }

        // Smart matching for common patterns
        if (!matchedOption) {
            matchedOption = this.smartSelectMatch(validOptions, value);
        }

        if (matchedOption) {
            console.log(`✅ Found match: "${matchedOption.text}" (value: ${matchedOption.value})`);
            
            // Set the option as selected
            matchedOption.selected = true;
            element.value = matchedOption.value;
            element.selectedIndex = Array.from(element.options).indexOf(matchedOption);
            
            // Trigger change events
            this.triggerFieldEvents(element);
            console.log(`✅ Selected: "${matchedOption.text}" for value: "${value}"`);
            
            // Verify selection worked
            console.log(`🔍 Verification: selectedIndex=${element.selectedIndex}, value="${element.value}"`);
        } else {
            console.warn(`❌ No match for "${value}". Available options:`, 
                validOptions.map(o => `"${o.text}" (value: ${o.value})`).slice(0, 5));
        }

        element.blur();
    }
    
    shouldSkipDropdownFill(element, value, options) {
        const valueLower = value.toLowerCase();
        const optionTexts = options.map(opt => opt.text.toLowerCase());
        
        // Skip if trying to fill email in non-email dropdowns
        if (valueLower.includes('@') && !optionTexts.some(text => text.includes('email') || text.includes('@'))) {
            return true;
        }
        
        // Skip if trying to fill personal names in demographic/categorical dropdowns
        const isDemographicDropdown = optionTexts.some(text => 
            text.includes('american indian') || text.includes('asian') || 
            text.includes('black') || text.includes('hispanic') || 
            text.includes('white') || text.includes('decline') || 
            text.includes('prefer not') || text.includes('select...') ||
            text.includes('bachelor') || text.includes('master') ||
            text.includes('high school') || text.includes('doctorate')
        );
        
        const isPersonalName = /^[a-zA-Z\s]+$/.test(value) && value.split(' ').length >= 2 && !value.includes('bachelor') && !value.includes('master');
        
        if (isDemographicDropdown && isPersonalName) {
            return true;
        }
        
        // Skip if value doesn't make sense for the available options
        const hasReasonableMatch = optionTexts.some(text => 
            text.includes(valueLower) || valueLower.includes(text) ||
            this.calculateSimilarity(text, valueLower) > 0.3
        );
        
        if (!hasReasonableMatch && options.length > 2) {
            return true;
        }
        
        return false;
    }

    smartSelectMatch(options, value) {
        if (!value || !options.length) return null;
        
        const valueLower = value.toLowerCase().trim();
        const optionTexts = options.map(opt => opt.text.toLowerCase());
        
        // Check if this looks like a race/ethnicity/demographics dropdown
        const isDemographicDropdown = optionTexts.some(text => 
            text.includes('american indian') || text.includes('asian') || 
            text.includes('black') || text.includes('hispanic') || 
            text.includes('white') || text.includes('decline') || 
            text.includes('prefer not')
        );
        
        // Skip demographic dropdowns for personal names/emails
        if (isDemographicDropdown && (valueLower.includes('@') || /^[a-z\s]+$/.test(valueLower))) {
            console.log('🚫 Skipping demographic dropdown for personal data:', value);
            return options.find(opt => 
                opt.text.toLowerCase().includes('decline') || 
                opt.text.toLowerCase().includes('prefer not') ||
                opt.text.toLowerCase().includes('not specified')
            );
        }
        
        // Work authorization patterns - improved matching
        if (valueLower.includes('authorized') || valueLower.includes('eligible') || 
            valueLower.includes('citizen') || valueLower.includes('yes') && valueLower.includes('work')) {
            return options.find(opt => {
                const text = opt.text.toLowerCase();
                // Look for positive work authorization responses
                return text.includes('yes') || text.includes('authorized') || 
                       text.includes('eligible') || text.includes('citizen') ||
                       text.includes('legally') || text.includes('able to work') ||
                       (text.includes('no') && text.includes('sponsor')) ||
                       text.includes('do not require');
            });
        }
        
        // Handle sponsorship requirement patterns
        if (valueLower.includes('sponsor') || valueLower.includes('visa') || 
            valueLower.includes('require') && valueLower.includes('work')) {
            return options.find(opt => {
                const text = opt.text.toLowerCase();
                return text.includes('sponsor') || text.includes('visa') || 
                       text.includes('require') || text.includes('yes') && text.includes('future');
            });
        }
        
        // Handle relocation questions
        if (valueLower.includes('relocate') || valueLower.includes('location')) {
            return options.find(opt => {
                const text = opt.text.toLowerCase();
                return text.includes('yes') || text.includes('willing') || text.includes('open');
            });
        }

        // Experience patterns
        if (valueLower.includes('senior') || valueLower.includes('5+') || valueLower.includes('5-')) {
            return options.find(opt => {
                const text = opt.text.toLowerCase();
                return text.includes('senior') || text.includes('5+') || 
                       text.includes('7+') || text.includes('lead') ||
                       text.includes('5-') || text.includes('3-5');
            });
        }

        // Education patterns
        if (valueLower.includes('master')) {
            return options.find(opt => opt.text.toLowerCase().includes('master'));
        }
        
        if (valueLower.includes('bachelor')) {
            return options.find(opt => opt.text.toLowerCase().includes('bachelor'));
        }
        
        // Yes/No patterns
        if (valueLower === 'yes' || valueLower === 'true') {
            return options.find(opt => opt.text.toLowerCase().includes('yes'));
        }
        
        if (valueLower === 'no' || valueLower === 'false') {
            return options.find(opt => opt.text.toLowerCase().includes('no'));
        }

        return null;
    }

    async fillCheckboxField(element, value) {
        element.focus();
        await new Promise(resolve => setTimeout(resolve, 50));

        // Check if value indicates checked state
        const shouldCheck = ['true', 'yes', '1', 'on', 'checked'].includes(value.toLowerCase());
        
        if (element.checked !== shouldCheck) {
            element.checked = shouldCheck;
            this.triggerFieldEvents(element);
        }

        element.blur();
    }

    async fillRadioField(element, value) {
        element.focus();
        await new Promise(resolve => setTimeout(resolve, 50));

        // For radio buttons, check if this option matches the value
        const shouldCheck = element.value.toLowerCase() === value.toLowerCase() ||
                           element.nextSibling?.textContent?.toLowerCase()?.includes(value.toLowerCase());

        if (shouldCheck && !element.checked) {
            element.checked = true;
            this.triggerFieldEvents(element);
        }

        element.blur();
    }

    async fillFileField(element, resumeId) {
        try {
            console.log(`🚀 fillFileField called with resumeId: ${resumeId}`);
            console.log(`📏 ResumeId length: ${resumeId ? resumeId.length : 'undefined'}`);
            console.log(`📄 Element details:`, { 
                tagName: element.tagName, 
                type: element.type, 
                name: element.name, 
                id: element.id 
            });
            
            // Validate resumeId format
            if (!resumeId || typeof resumeId !== 'string' || resumeId.length > 100) {
                console.error(`❌ Invalid resumeId format. Expected UUID, got: ${resumeId ? resumeId.substring(0, 100) + '...' : 'undefined'}`);
                return;
            }
            
            // Get resume file data from backend
            const response = await fetch(`http://localhost:8000/api/resumes/${resumeId}/file`);
            if (!response.ok) {
                console.error(`❌ Failed to fetch resume file: ${response.status}`);
                return;
            }
            
            const fileData = await response.json();
            if (!fileData.success) {
                console.error('Failed to get resume file data');
                return;
            }
            
            // Convert base64 to blob
            const byteCharacters = atob(fileData.file_data);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: fileData.content_type });
            
            // Create File object
            const file = new File([blob], fileData.filename, { 
                type: fileData.content_type,
                lastModified: Date.now()
            });
            
            // Create FileList-like object
            const dt = new DataTransfer();
            dt.items.add(file);
            
            // Focus and set files
            element.focus();
            await new Promise(resolve => setTimeout(resolve, 100));
            
            // Set the files
            element.files = dt.files;
            
            // Trigger events
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            
            element.blur();
            
            console.log(`✅ Successfully uploaded resume: ${fileData.filename}`);
            
        } catch (error) {
            console.error('Error uploading resume file:', error);
        }
    }

    triggerFieldEvents(element) {
        // Trigger all relevant events for better compatibility
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.dispatchEvent(new Event('keyup', { bubbles: true }));
        element.dispatchEvent(new Event('blur', { bubbles: true }));
    }

    async typeWithDelay(element, text, baseDelay) {
        // This method is now unused but kept for potential future use
        element.value = '';
        for (let i = 0; i < text.length; i++) {
            element.value += text[i];
            await new Promise(resolve => setTimeout(resolve, baseDelay + Math.random() * 20));
        }
    }

    async humanDelay() {
        const delay = 200 + Math.random() * 300; // 200-500ms
        await new Promise(resolve => setTimeout(resolve, delay));
    }

    async analyzeFormStructure() {
        const analysis = {
            forms: this.forms.length,
            fields: {},
            patterns: {},
            suggestions: []
        };

        for (const [formIndex, fields] of this.formFields.entries()) {
            for (const [category, categoryFields] of Object.entries(fields)) {
                if (!analysis.fields[category]) {
                    analysis.fields[category] = 0;
                }
                analysis.fields[category] += Object.keys(categoryFields).length;
            }
        }

        return { success: true, analysis };
    }

    async logFillingActivity(formData, filledFields, totalFields) {
        try {
            await fetch('http://localhost:8000/api/log-form-activity', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: window.location.href,
                    domain: window.location.hostname,
                    filled_fields: filledFields,
                    total_fields: totalFields,
                    accuracy: totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : 0,
                    timestamp: new Date().toISOString()
                })
            });
        } catch (error) {
            console.log('Failed to log activity:', error);
        }
    }

    updateFormIndicator() {
        // Remove existing indicator
        const existingIndicator = document.getElementById('ai-form-filler-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }

        // Add new indicator if forms detected
        if (this.forms.length > 0) {
            const indicator = document.createElement('div');
            indicator.id = 'ai-form-filler-indicator';
            indicator.innerHTML = `
                <div style="
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: #3b82f6;
                    color: white;
                    padding: 8px 12px;
                    border-radius: 6px;
                    font-size: 12px;
                    font-family: system-ui;
                    z-index: 10000;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    cursor: pointer;
                    transition: all 0.3s ease;
                ">
                    🤖 ${this.forms.length} form(s) detected
                </div>
            `;
            
            indicator.addEventListener('click', () => {
                chrome.runtime.sendMessage({ action: 'openPopup' });
            });

            document.body.appendChild(indicator);
        }
    }

    extractFormFieldsInfo() {
        console.log('🔍 Extracting form fields for LLM analysis...');
        const formFields = [];
        
        this.forms.forEach(form => {
            const inputs = form.inputs || [];
            inputs.forEach(input => {
                if (input && input.offsetHeight > 0) { // Only visible fields
                    const fieldInfo = {
                        name: input.name || '',
                        id: input.id || '',
                        type: input.type || input.tagName.toLowerCase(),
                        placeholder: input.placeholder || '',
                        label: this.getFieldLabel(input) || '',
                        classes: input.className || '',
                        aria_label: input.getAttribute('aria-label') || '',
                        title: input.title || '',
                        surrounding_text: this.getSurroundingText(input),
                        parent_text: this.getParentText(input),
                        required: input.required || false,
                        maxlength: input.maxLength || null
                    };
                    
                    // Only include fields that look like questions or important inputs
                    if (this.isImportantField(fieldInfo)) {
                        formFields.push(fieldInfo);
                        console.log('📝 Added important field:', fieldInfo.label || fieldInfo.name || fieldInfo.placeholder);
                    }
                }
            });
        });
        
        console.log(`🔍 Found ${formFields.length} important form fields`);
        return formFields;
    }

    getFieldLabel(input) {
        // Try multiple methods to find the label
        const id = input.id;
        if (id) {
            const label = document.querySelector(`label[for="${id}"]`);
            if (label) return label.textContent.trim();
        }
        
        // Check for nearby label elements
        const parent = input.parentElement;
        const label = parent?.querySelector('label');
        if (label) return label.textContent.trim();
        
        // Check for aria-labelledby
        const labelledBy = input.getAttribute('aria-labelledby');
        if (labelledBy) {
            const labelElement = document.getElementById(labelledBy);
            if (labelElement) return labelElement.textContent.trim();
        }
        
        return '';
    }

    getSurroundingText(input) {
        // Get text from nearby elements
        const parent = input.closest('.form-group, .field, .input-group') || input.parentElement;
        if (parent) {
            return parent.textContent.trim().replace(/\s+/g, ' ').substring(0, 200);
        }
        return '';
    }

    getParentText(input) {
        const parent = input.parentElement;
        return parent ? parent.textContent.trim().replace(/\s+/g, ' ').substring(0, 100) : '';
    }

    isImportantField(fieldInfo) {
        const allText = `${fieldInfo.name} ${fieldInfo.label} ${fieldInfo.placeholder} ${fieldInfo.surrounding_text}`.toLowerCase();
        
        // Skip basic personal info fields (already handled)
        const skipPatterns = ['first name', 'last name', 'email', 'phone', 'location'];
        if (skipPatterns.some(pattern => allText.includes(pattern))) {
            return false;
        }
        
        // Include text areas and question-like fields
        if (fieldInfo.type === 'textarea') return true;
        
        // Include fields with question indicators
        const questionPatterns = ['why', 'what', 'how', 'describe', 'tell us', 'explain', 'appeal', 'interest', 'experience'];
        return questionPatterns.some(pattern => allText.includes(pattern));
    }

    extractPageContext() {
        console.log('📄 Extracting page context...');
        const context = {
            title: document.title || '',
            url: window.location.href,
            headings: this.extractHeadings(),
            job_description: this.extractJobDescription(),
            company_info: this.extractCompanyInfo()
        };
        
        console.log('📄 Page context extracted:', context);
        return context;
    }

    extractHeadings() {
        const headings = [];
        const headingElements = document.querySelectorAll('h1, h2, h3');
        headingElements.forEach(h => {
            const text = h.textContent.trim();
            if (text && text.length < 200) {
                headings.push(text);
            }
        });
        return headings.slice(0, 10); // Limit to first 10 headings
    }

    extractJobDescription() {
        // Look for common job description containers
        const selectors = [
            '.job-description', '.job-details', '.position-description',
            '[class*="description"]', '[class*="job"]', '[class*="role"]'
        ];
        
        for (const selector of selectors) {
            const element = document.querySelector(selector);
            if (element) {
                const text = element.textContent.trim();
                if (text.length > 100) {
                    return text.substring(0, 1000); // Limit length
                }
            }
        }
        return '';
    }

    extractCompanyInfo() {
        // Extract company name from various sources
        const titleText = document.title.toLowerCase();
        
        // Look for company indicators in title
        const titleWords = titleText.split(/[\s\-\|]+/);
        for (const word of titleWords) {
            if (word.length > 3 && !['jobs', 'career', 'careers', 'application'].includes(word)) {
                return word;
            }
        }
        
        return '';
    }
}

// Initialize when content script loads with error handling
let formDetector;

try {
    // Ensure we only initialize once per context
    if (!window.jobFormDetectorInitialized) {
        formDetector = new JobFormDetector();
        window.jobFormDetectorInitialized = true;
        
        // Add initial indicator after a short delay
        setTimeout(() => {
            if (formDetector && formDetector.isInitialized) {
                formDetector.updateFormIndicator();
            }
        }, 1000);
        
        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && formDetector) {
                formDetector.detectJobForms();
                formDetector.updateFormIndicator();
            }
        });
    }
} catch (error) {
    console.error('❌ Failed to initialize JobFormDetector:', error);
}

// Global error handler for extension context issues
window.addEventListener('error', (event) => {
    if (event.error && event.error.message && (
        event.error.message.includes('context invalidated') ||
        event.error.message.includes('Extension context invalidated') ||
        event.error.message.includes('Could not establish connection')
    )) {
        console.warn('🚨 Global error caught - Extension context invalidated:', event.error.message);
        // Try to handle context invalidation if form detector exists
        if (window.formDetector && typeof window.formDetector.handleContextInvalidation === 'function') {
            window.formDetector.handleContextInvalidation();
        }
    }
});

// Export for debugging
window.formDetector = formDetector;