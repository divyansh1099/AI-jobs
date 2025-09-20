"""
Advanced Semantic Field Detection Service using NLP and ML techniques
"""
import re
import json
import nltk
import spacy
from typing import Dict, List, Any, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from loguru import logger
import numpy as np
import threading
from functools import lru_cache
import time

class SpacyModelCache:
    """Singleton class for caching spaCy models across instances"""
    _instance = None
    _lock = threading.Lock()
    _models = {}
    _load_times = {}
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SpacyModelCache, cls).__new__(cls)
        return cls._instance
    
    @lru_cache(maxsize=2)
    def get_model(self, model_name: str):
        """Get cached spaCy model with LRU caching"""
        if model_name not in self._models:
            with self._lock:
                if model_name not in self._models:
                    start_time = time.time()
                    try:
                        logger.info(f"🔄 Loading spaCy model: {model_name}")
                        # Disable unnecessary components for better performance
                        model = spacy.load(model_name, disable=['parser', 'ner', 'textcat'])
                        # Keep only tokenizer, tagger, and lemmatizer for field analysis
                        self._models[model_name] = model
                        load_time = time.time() - start_time
                        self._load_times[model_name] = load_time
                        logger.info(f"✅ spaCy model loaded in {load_time:.2f}s with optimized pipeline")
                    except OSError as e:
                        logger.error(f"❌ Failed to load spaCy model {model_name}: {e}")
                        return None
        
        return self._models.get(model_name)
    
    def get_load_stats(self) -> Dict[str, Any]:
        """Get model loading statistics"""
        return {
            'cached_models': list(self._models.keys()),
            'load_times': self._load_times,
            'cache_size': len(self._models)
        }

class SmartFieldDetector:
    def __init__(self):
        self.nlp = None
        self.field_embeddings = {}
        self.known_patterns = {}
        self.tfidf_vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        self._model_cache = SpacyModelCache()
        self._load_field_patterns()
        # Lazy load spaCy model only when needed
        
    def _initialize_nlp(self):
        """Initialize NLP models with caching and lazy loading"""
        if self.nlp is None:
            self.nlp = self._model_cache.get_model("en_core_web_sm")
            if self.nlp is None:
                logger.warning("⚠️ spaCy model not available. Install with: python -m spacy download en_core_web_sm")
                logger.warning("⚠️ Falling back to basic text processing without NLP features")
                
    def _ensure_nlp_loaded(self):
        """Ensure NLP model is loaded (lazy loading)"""
        if self.nlp is None:
            self._initialize_nlp()
        return self.nlp is not None
    
    @lru_cache(maxsize=128)
    def _basic_text_analysis(self, text_content: str) -> Dict[str, Dict[str, float]]:
        """Basic text analysis fallback when NLP is not available"""
        scores = {}
        words = text_content.lower().split()
        
        for category, fields in self.field_patterns.items():
            if category not in scores:
                scores[category] = {}
                
            for field_type, patterns in fields.items():
                semantic_keywords = patterns.get('semantic_keywords', [])
                
                # Simple keyword matching
                matches = sum(1 for word in words if any(keyword in word for keyword in semantic_keywords))
                score = matches / max(len(semantic_keywords), 1)
                scores[category][field_type] = min(score, 1.0)
        
        return scores
    
    @lru_cache(maxsize=256)  
    def _cached_semantic_analysis(self, text_hash: str, text_content: str) -> Dict[str, Dict[str, float]]:
        """Cached semantic analysis for performance"""
        return self._semantic_analysis_impl(text_content)
    
    def _semantic_analysis_impl(self, text_content: str) -> Dict[str, Dict[str, float]]:
        """Implementation of semantic analysis"""
        scores = {}
        
        if not self._ensure_nlp_loaded():
            return self._basic_text_analysis(text_content)
        
        # Process with spaCy
        doc = self.nlp(text_content)
        
        # Extract entities and keywords
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        keywords = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct]
        
        # Score against known patterns
        for category, fields in self.field_patterns.items():
            if category not in scores:
                scores[category] = {}
                
            for field_type, patterns in fields.items():
                semantic_keywords = patterns.get('semantic_keywords', [])
                
                # Calculate semantic similarity
                keyword_matches = sum(1 for kw in keywords if any(sem_kw in kw or kw in sem_kw for sem_kw in semantic_keywords))
                entity_matches = sum(1 for ent_text, ent_label in entities if any(sem_kw in ent_text for sem_kw in semantic_keywords))
                
                # Normalize score
                total_keywords = len(semantic_keywords)
                semantic_score = (keyword_matches + entity_matches * 2) / max(total_keywords, 1)
                semantic_score = min(semantic_score, 1.0)  # Cap at 1.0
                
                scores[category][field_type] = semantic_score
        
        return scores
            
    def _load_field_patterns(self):
        """Load comprehensive field patterns with semantic understanding"""
        self.field_patterns = {
            'personal_info': {
                'name': {
                    'semantic_keywords': ['name', 'full name', 'first name', 'last name', 'given name', 'surname', 'applicant name'],
                    'context_clues': ['who are you', 'your identity', 'introduce yourself'],
                    'regex_patterns': [
                        r'.*name.*', r'.*nom.*', r'.*nombre.*',  # Multi-language
                        r'.*fname.*', r'.*lname.*', r'.*given.*', r'.*family.*'
                    ],
                    'visual_clues': ['person icon', 'user icon', 'profile'],
                    'neighboring_text': ['mr.', 'ms.', 'dr.', 'prof.'],
                    'field_types': ['text', 'input'],
                    'confidence_weights': {
                        'semantic': 0.4,
                        'context': 0.3,
                        'visual': 0.2,
                        'regex': 0.1
                    }
                },
                'email': {
                    'semantic_keywords': ['email', 'e-mail', 'electronic mail', 'contact email', 'work email'],
                    'context_clues': ['how can we reach you', 'contact information', 'correspondence'],
                    'regex_patterns': [
                        r'.*email.*', r'.*mail.*', r'.*@.*',
                        r'.*correo.*', r'.*e-mail.*'
                    ],
                    'validation_patterns': [r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'],
                    'visual_clues': ['@ symbol', 'envelope icon'],
                    'field_types': ['email', 'text'],
                    'confidence_weights': {
                        'semantic': 0.5,
                        'validation': 0.3,
                        'regex': 0.2
                    }
                },
                'phone': {
                    'semantic_keywords': ['phone', 'telephone', 'mobile', 'cell', 'contact number', 'phone number'],
                    'context_clues': ['how can we call you', 'emergency contact', 'phone contact'],
                    'regex_patterns': [
                        r'.*phone.*', r'.*tel.*', r'.*mobile.*', r'.*cell.*',
                        r'.*número.*', r'.*telefono.*'
                    ],
                    'validation_patterns': [
                        r'^\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$',
                        r'^\+?[1-9]\d{1,14}$'  # International format
                    ],
                    'visual_clues': ['phone icon', 'mobile icon'],
                    'field_types': ['tel', 'text'],
                    'confidence_weights': {
                        'semantic': 0.4,
                        'validation': 0.3,
                        'regex': 0.3
                    }
                }
            },
            'experience': {
                'company': {
                    'semantic_keywords': ['company', 'employer', 'organization', 'workplace', 'firm', 'corporation'],
                    'context_clues': ['where do you work', 'current employer', 'previous employer'],
                    'regex_patterns': [r'.*company.*', r'.*employer.*', r'.*org.*', r'.*workplace.*'],
                    'neighboring_text': ['inc.', 'llc', 'corp.', 'ltd.'],
                    'confidence_weights': {
                        'semantic': 0.5,
                        'context': 0.3,
                        'regex': 0.2
                    }
                },
                'title': {
                    'semantic_keywords': ['title', 'position', 'role', 'job title', 'designation', 'occupation'],
                    'context_clues': ['what is your role', 'your position', 'job function'],
                    'regex_patterns': [r'.*title.*', r'.*position.*', r'.*role.*', r'.*job.*'],
                    'neighboring_text': ['sr.', 'jr.', 'manager', 'director', 'engineer'],
                    'confidence_weights': {
                        'semantic': 0.5,
                        'context': 0.3,
                        'regex': 0.2
                    }
                }
            },
            'application_specific': {
                'work_authorization': {
                    'semantic_keywords': ['work authorization', 'visa', 'sponsorship', 'eligible to work', 'authorized to work'],
                    'context_clues': ['do you need sponsorship', 'visa requirements', 'work permit'],
                    'regex_patterns': [r'.*visa.*', r'.*sponsor.*', r'.*authorization.*', r'.*eligible.*'],
                    'expected_values': ['yes', 'no', 'authorized', 'not authorized'],
                    'confidence_weights': {
                        'semantic': 0.6,
                        'context': 0.4
                    }
                },
                'cover_letter': {
                    'semantic_keywords': ['cover letter', 'motivation letter', 'personal statement', 'why interested'],
                    'context_clues': ['tell us why', 'why do you want', 'motivation'],
                    'regex_patterns': [r'.*cover.*letter.*', r'.*motivation.*', r'.*statement.*'],
                    'field_types': ['textarea', 'text'],
                    'confidence_weights': {
                        'semantic': 0.7,
                        'context': 0.3
                    }
                }
            }
        }

    def detect_field_type(self, field_element: Dict[str, Any], context: Dict[str, Any] = None) -> Tuple[str, str, float]:
        """
        Advanced field type detection using multiple AI techniques
        
        Returns:
            Tuple of (category, field_type, confidence_score)
        """
        try:
            # Extract field information
            field_info = self._extract_field_info(field_element, context)
            
            # Multi-modal analysis
            semantic_analysis = self._semantic_analysis(field_info)
            contextual_analysis = self._contextual_analysis(field_info, context)
            visual_analysis = self._visual_analysis(field_info)
            pattern_analysis = self._pattern_analysis(field_info)
            
            # Combine scores using weighted ensemble
            final_scores = self._ensemble_scoring([
                semantic_analysis,
                contextual_analysis, 
                visual_analysis,
                pattern_analysis
            ])
            
            # Get best prediction
            best_category, best_field_type, confidence = self._get_best_prediction(final_scores)
            
            logger.info(f"🎯 Field detection: {best_category}.{best_field_type} (confidence: {confidence:.2f})")
            return best_category, best_field_type, confidence
            
        except Exception as e:
            logger.error(f"❌ Field detection error: {e}")
            return 'unknown', 'unknown', 0.0

    def _extract_field_info(self, field_element: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract comprehensive field information"""
        return {
            'id': field_element.get('id', ''),
            'name': field_element.get('name', ''),
            'placeholder': field_element.get('placeholder', ''),
            'label': field_element.get('label', ''),
            'type': field_element.get('type', ''),
            'classes': field_element.get('classes', ''),
            'aria_label': field_element.get('aria-label', ''),
            'title': field_element.get('title', ''),
            'surrounding_text': field_element.get('surrounding_text', ''),
            'parent_text': field_element.get('parent_text', ''),
            'sibling_text': field_element.get('sibling_text', ''),
            'validation_pattern': field_element.get('pattern', ''),
            'required': field_element.get('required', False),
            'maxlength': field_element.get('maxlength', ''),
            'context': context or {}
        }

    def _semantic_analysis(self, field_info: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Advanced semantic analysis using NLP"""
        scores = {}
        
        if not self.nlp:
            return scores
        
        # Combine all text information (filter out None values)
        text_parts = [
            field_info['id'] or '', field_info['name'] or '', field_info['placeholder'] or '',
            field_info['label'] or '', field_info['surrounding_text'] or '', field_info['aria_label'] or ''
        ]
        text_content = ' '.join(text_parts).lower().strip()
        
        if not text_content.strip():
            return scores
        
        # Process with spaCy (lazy loading)
        if not self._ensure_nlp_loaded():
            # Fallback to basic analysis without NLP
            logger.warning("⚠️ NLP model not available, using basic text analysis")
            return self._basic_text_analysis(text_content)
        
        doc = self.nlp(text_content)
        
        # Extract entities and keywords
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        keywords = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct]
        
        # Score against known patterns
        for category, fields in self.field_patterns.items():
            if category not in scores:
                scores[category] = {}
                
            for field_type, patterns in fields.items():
                semantic_keywords = patterns.get('semantic_keywords', [])
                
                # Calculate semantic similarity
                keyword_matches = sum(1 for kw in keywords if any(sem_kw in kw or kw in sem_kw for sem_kw in semantic_keywords))
                entity_matches = sum(1 for ent_text, ent_label in entities if any(sem_kw in ent_text for sem_kw in semantic_keywords))
                
                # Normalize score
                total_keywords = len(semantic_keywords)
                semantic_score = (keyword_matches + entity_matches * 2) / max(total_keywords, 1)
                semantic_score = min(semantic_score, 1.0)  # Cap at 1.0
                
                scores[category][field_type] = semantic_score
        
        return scores

    def _contextual_analysis(self, field_info: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Dict[str, float]]:
        """Analyze field based on context clues"""
        scores = {}
        
        # Get contextual information
        page_title = context.get('page_title', '') if context else ''
        page_url = context.get('page_url', '') if context else ''
        form_purpose = context.get('form_purpose', '') if context else ''
        
        context_text = f"{page_title} {page_url} {form_purpose} {field_info.get('surrounding_text', '')}".lower()
        
        for category, fields in self.field_patterns.items():
            if category not in scores:
                scores[category] = {}
                
            for field_type, patterns in fields.items():
                context_clues = patterns.get('context_clues', [])
                
                # Check for context clue matches
                context_matches = sum(1 for clue in context_clues if clue in context_text)
                context_score = context_matches / max(len(context_clues), 1)
                
                scores[category][field_type] = min(context_score, 1.0)
        
        return scores

    def _visual_analysis(self, field_info: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Analyze visual clues (icons, styling, etc.)"""
        scores = {}
        
        # Analyze classes and visual indicators
        classes_text = (field_info['classes'] or '').lower()
        
        for category, fields in self.field_patterns.items():
            if category not in scores:
                scores[category] = {}
                
            for field_type, patterns in fields.items():
                visual_clues = patterns.get('visual_clues', [])
                
                visual_matches = sum(1 for clue in visual_clues if clue in classes_text)
                visual_score = visual_matches / max(len(visual_clues), 1)
                
                scores[category][field_type] = min(visual_score, 1.0)
        
        return scores

    def _pattern_analysis(self, field_info: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Traditional regex pattern analysis"""
        scores = {}
        
        # Combine relevant text fields (filter out None values)
        text_parts = [
            field_info['id'] or '', field_info['name'] or '', 
            field_info['placeholder'] or '', field_info['label'] or ''
        ]
        text_to_analyze = ' '.join(text_parts).lower().strip()
        
        for category, fields in self.field_patterns.items():
            if category not in scores:
                scores[category] = {}
                
            for field_type, patterns in fields.items():
                regex_patterns = patterns.get('regex_patterns', [])
                
                pattern_matches = 0
                for pattern in regex_patterns:
                    try:
                        if re.search(pattern, text_to_analyze):
                            pattern_matches += 1
                    except re.error:
                        continue
                
                pattern_score = pattern_matches / max(len(regex_patterns), 1)
                scores[category][field_type] = min(pattern_score, 1.0)
        
        return scores

    def _ensemble_scoring(self, analysis_results: List[Dict[str, Dict[str, float]]]) -> Dict[str, Dict[str, float]]:
        """Combine multiple analysis results using ensemble method"""
        combined_scores = {}
        
        # Get all categories and field types
        all_categories = set()
        for result in analysis_results:
            all_categories.update(result.keys())
        
        for category in all_categories:
            combined_scores[category] = {}
            
            # Get all field types for this category
            field_types = set()
            for result in analysis_results:
                if category in result:
                    field_types.update(result[category].keys())
            
            for field_type in field_types:
                # Collect scores from all analyses
                scores = []
                for result in analysis_results:
                    if category in result and field_type in result[category]:
                        scores.append(result[category][field_type])
                    else:
                        scores.append(0.0)
                
                # Use weighted average (can be made more sophisticated)
                if scores:
                    combined_score = np.mean(scores)
                    combined_scores[category][field_type] = combined_score
        
        return combined_scores

    def _get_best_prediction(self, scores: Dict[str, Dict[str, float]]) -> Tuple[str, str, float]:
        """Get the best field type prediction"""
        best_score = 0.0
        best_category = 'unknown'
        best_field_type = 'unknown'
        
        for category, fields in scores.items():
            for field_type, score in fields.items():
                if score > best_score:
                    best_score = score
                    best_category = category
                    best_field_type = field_type
        
        return best_category, best_field_type, best_score

    def learn_from_correction(self, field_info: Dict[str, Any], correct_category: str, correct_field_type: str):
        """Learn from user corrections to improve future predictions"""
        try:
            # Extract features from the corrected field
            text_features = self._extract_text_features(field_info)
            
            # Store the correction for future reference
            correction_key = f"{correct_category}_{correct_field_type}"
            if correction_key not in self.known_patterns:
                self.known_patterns[correction_key] = []
            
            self.known_patterns[correction_key].append(text_features)
            
            logger.info(f"📚 Learned from correction: {correct_category}.{correct_field_type}")
            
        except Exception as e:
            logger.error(f"❌ Learning error: {e}")

    def _extract_text_features(self, field_info: Dict[str, Any]) -> List[str]:
        """Extract text features for learning"""
        features = []
        
        for key in ['id', 'name', 'placeholder', 'label', 'classes']:
            value = field_info.get(key, '') or ''
            if value:
                features.extend(value.lower().split())
        
        return features