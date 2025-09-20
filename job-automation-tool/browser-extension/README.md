# Advanced AI Job Form Filler Browser Extension

A state-of-the-art semi-automatic browser extension that intelligently fills job application forms using multi-modal AI analysis and local LLM integration.

## Advanced AI Features

🧠 **Multi-Modal AI Analysis** - Combines NLP, computer vision, and machine learning for superior form understanding  
🎯 **Semantic Field Detection** - Uses spaCy NLP models to understand field context and meaning  
👁️ **Computer Vision Analysis** - OpenCV-powered visual form analysis with OCR capabilities  
🤖 **Machine Learning Adaptation** - Random Forest classifier that learns and improves from user corrections  
📝 **Enhanced Form Filling** - AI-powered field mapping with confidence scoring (35%+ accuracy)  
👤 **Intelligent Profiles** - Multiple resume profiles with smart field matching  
🧠 **Advanced Learning** - Comprehensive accuracy tracking and performance optimization  
🔒 **Privacy First** - All AI processing happens locally, no data sent to external services  

## Installation

### 1. Install Dependencies
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Start Local Backend
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Load Extension in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (top right toggle)
3. Click "Load unpacked"
4. Select the `browser-extension` folder
5. Extension should now appear in your toolbar

## Usage

1. **Navigate** to any job application page
2. **Click** the extension icon when forms are detected
3. **Select** your preferred resume profile
4. **Choose** which sections to fill (basic info, experience, etc.)
5. **Click** "Fill Form" to automatically populate fields
6. **Review** and submit the application

## Profiles

- **Default**: General software engineer profile
- **Senior**: Senior developer with leadership experience
- **Data**: Data engineer specializing in pipelines and analytics
- **Frontend**: Frontend specialist with modern web technologies

## Advanced Learning System

The extension uses sophisticated AI techniques for continuous improvement:

### Multi-Modal Analysis
- **Semantic Analysis**: NLP-powered field context understanding
- **Visual Analysis**: Computer vision for form layout and element detection
- **Pattern Recognition**: Machine learning classifier for field type prediction
- **Contextual Understanding**: Page context and form purpose analysis

### Learning Capabilities
- Tracks form filling accuracy per domain with detailed metrics
- Improves field detection through adaptive ML algorithms
- Learns from user corrections via feedback loop
- Adapts to site-specific form structures and patterns
- Provides comprehensive performance insights and analytics
- Confidence-based field mapping with ensemble scoring

## Enhanced API Endpoints

### Core Endpoints
- `GET /api/health` - Health check with AI service status
- `POST /api/generate-form-data` - Enhanced form data generation with AI analysis
- `POST /api/log-form-activity` - Log filling activity with accuracy metrics
- `GET /api/user-stats` - Comprehensive user statistics and performance
- `GET /api/learning-insights/{domain}` - Domain-specific insights and patterns

### New AI Endpoints
- `POST /api/analyze-form` - Pure AI field analysis with confidence scoring
- AI services integration for semantic, visual, and ML analysis

## Privacy & Security

✅ All AI processing happens locally on your machine  
✅ No external API calls for sensitive data  
✅ Advanced local AI models (spaCy, OpenCV, scikit-learn)  
✅ Ollama framework for local LLM inference  
✅ User data and training data never leave your machine  
✅ Encrypted local storage for ML training data  
✅ Complete independence from cloud AI services  