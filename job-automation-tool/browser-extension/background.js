// Enhanced background script for AI Job Form Filler with context management
const BACKEND_URL = 'http://localhost:8000';

// Track active tabs and their content script status
const tabStatus = new Map();

// Enhanced message listener with context validation
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    try {
        switch (request.action) {
            case 'openPopup':
                chrome.action.openPopup();
                sendResponse({ success: true });
                break;
                
            case 'checkConnection':
                checkBackendConnection()
                    .then(result => sendResponse(result))
                    .catch(error => sendResponse({ success: false, error: error.message }));
                return true;
                
            case 'getFormData':
                generateFormData(
                    request.profile, 
                    request.options, 
                    request.url,
                    request.formFields,
                    request.pageContext
                )
                    .then(result => sendResponse(result))
                    .catch(error => sendResponse({ success: false, error: error.message }));
                return true;
                
            case 'contentScriptReady':
                // Content script is ready, update tab status
                if (sender.tab) {
                    tabStatus.set(sender.tab.id, { ready: true, lastPing: Date.now() });
                    sendResponse({ success: true });
                }
                break;
                
            case 'ping':
                // Keep-alive ping from content script
                if (sender.tab) {
                    const status = tabStatus.get(sender.tab.id) || {};
                    status.lastPing = Date.now();
                    tabStatus.set(sender.tab.id, status);
                    sendResponse({ success: true });
                }
                break;
                
            default:
                sendResponse({ success: false, error: 'Unknown action' });
        }
    } catch (error) {
        console.error('Background script error:', error);
        sendResponse({ success: false, error: error.message });
    }
});

// Extension installed/updated
chrome.runtime.onInstalled.addListener(() => {
    console.log('AI Job Form Filler extension loaded');
});

// Check backend connection
async function checkBackendConnection() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/health`);
        return { connected: response.ok };
    } catch (error) {
        return { connected: false, error: error.message };
    }
}

// Generate form data with enhanced context and field information
async function generateFormData(profile, options, url, formFields = null, pageContext = null) {
    try {
        const requestData = {
            profile: profile || 'default',
            options: options || {},
            url: url,
            timestamp: new Date().toISOString()
        };
        
        // Add form fields for intelligent LLM responses
        if (formFields && formFields.length > 0) {
            requestData.form_fields = formFields;
        }
        
        // Add page context for job information extraction
        if (pageContext) {
            requestData.page_context = pageContext;
        }

        const response = await fetch(`${BACKEND_URL}/api/generate-form-data`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            throw new Error(`Backend error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        throw new Error(`Failed to generate form data: ${error.message}`);
    }
}

// Enhanced badge management with tab-specific updates
function updateBadge(tabId, formsCount) {
    const badgeText = formsCount > 0 ? formsCount.toString() : '';
    const badgeColor = formsCount > 0 ? '#3b82f6' : '#gray';
    
    chrome.action.setBadgeText({ tabId, text: badgeText });
    chrome.action.setBadgeBackgroundColor({ tabId, color: badgeColor });
}

// Utility functions for context management
function isValidUrl(url) {
    return url && !url.startsWith('chrome://') && !url.startsWith('chrome-extension://') && 
           !url.startsWith('moz-extension://') && !url.startsWith('about:');
}

async function waitForContentScript(tabId, maxWaitTime = 3000) {
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWaitTime) {
        const status = tabStatus.get(tabId);
        if (status && status.ready) {
            return true;
        }
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Try to inject content script if not ready
    try {
        await chrome.scripting.executeScript({
            target: { tabId },
            files: ['content.js']
        });
        
        // Wait a bit more for initialization
        await new Promise(resolve => setTimeout(resolve, 500));
        return true;
    } catch (error) {
        console.log(`Failed to inject content script into tab ${tabId}:`, error.message);
        return false;
    }
}

async function sendMessageWithRetry(tabId, message, maxRetries = 3) {
    let lastError;
    
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await chrome.tabs.sendMessage(tabId, message);
            return response;
        } catch (error) {
            lastError = error;
            
            // If context invalidated, try to re-inject content script
            if (error.message.includes('context invalidated') || error.message.includes('Could not establish connection')) {
                console.log(`Retry ${i + 1}: Re-injecting content script for tab ${tabId}`);
                
                try {
                    await chrome.scripting.executeScript({
                        target: { tabId },
                        files: ['content.js']
                    });
                    await new Promise(resolve => setTimeout(resolve, 500));
                } catch (injectError) {
                    console.log('Content script injection failed:', injectError.message);
                }
            }
            
            await new Promise(resolve => setTimeout(resolve, 500 * (i + 1)));
        }
    }
    
    throw lastError;
}

async function injectContentScriptsIntoExistingTabs() {
    try {
        const tabs = await chrome.tabs.query({});
        
        for (const tab of tabs) {
            if (isValidUrl(tab.url)) {
                // Check if content script is already injected
                const status = tabStatus.get(tab.id);
                if (status && status.ready) {
                    console.log(`Content script already active in tab ${tab.id}`);
                    continue;
                }
                
                try {
                    // Test if content script is already present
                    await chrome.tabs.sendMessage(tab.id, { action: 'ping' });
                    console.log(`Content script already present in tab ${tab.id}`);
                    tabStatus.set(tab.id, { ready: true, lastPing: Date.now() });
                } catch (error) {
                    // Content script not present, inject it
                    try {
                        await chrome.scripting.executeScript({
                            target: { tabId: tab.id },
                            files: ['content.js']
                        });
                        console.log(`Injected content script into existing tab: ${tab.url}`);
                    } catch (injectError) {
                        console.log(`Failed to inject into tab ${tab.id}:`, injectError.message);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Failed to inject content scripts into existing tabs:', error);
    }
}

// Enhanced tab management with context validation
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url && isValidUrl(tab.url)) {
        // Clear previous tab status
        tabStatus.delete(tabId);
        
        // Wait for content script to be ready
        await waitForContentScript(tabId);
        
        // Send message to detect forms with retry logic
        await sendMessageWithRetry(tabId, { action: 'detectForms' })
            .then(response => {
                if (response && response.formsFound > 0) {
                    updateBadge(tabId, response.formsFound);
                } else {
                    updateBadge(tabId, 0);
                }
            })
            .catch(error => {
                console.log(`Tab ${tabId}: Content script not ready or no forms detected`);
                updateBadge(tabId, 0);
            });
    }
});

// Clean up tab status when tabs are closed
chrome.tabs.onRemoved.addListener((tabId) => {
    tabStatus.delete(tabId);
});

// Handle service worker lifecycle
chrome.runtime.onStartup.addListener(() => {
    console.log('Extension startup - clearing tab status');
    tabStatus.clear();
});

chrome.runtime.onInstalled.addListener((details) => {
    console.log('Extension installed/updated:', details.reason);
    tabStatus.clear();
    
    // Inject content scripts into existing tabs
    if (details.reason === 'update') {
        injectContentScriptsIntoExistingTabs();
    }
});