"""
Machine Learning-based Form Pattern Learning and Prediction
"""
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import LabelEncoder
import joblib
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger
from pathlib import Path
import sqlite3
from datetime import datetime

class MLFormLearner:
    def __init__(self, model_path: str = "models/form_classifier.joblib"):
        self.model_path = Path(model_path)
        self.model_path.parent.mkdir(exist_ok=True)
        
        self.classifier = None
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.label_encoder = LabelEncoder()
        self.feature_columns = []
        
        # Database for storing training data
        self.db_path = "data/form_training_data.db"
        Path(self.db_path).parent.mkdir(exist_ok=True)
        self._init_database()
        
        # Try to load existing model
        self._load_model()
        
        # Field type mapping
        self.field_type_categories = {
            'personal_info': ['name', 'first_name', 'last_name', 'email', 'phone', 'address', 'city', 'state', 'zip', 'country'],
            'experience': ['company', 'title', 'start_date', 'end_date', 'description', 'salary'],
            'education': ['school', 'degree', 'major', 'gpa', 'graduation_date'],
            'application': ['cover_letter', 'work_authorization', 'visa', 'availability', 'willing_to_relocate'],
            'files': ['resume', 'portfolio', 'transcript', 'references']
        }
        
    def _init_database(self):
        """Initialize SQLite database for training data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS field_training_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_id TEXT,
                    field_name TEXT,
                    field_type TEXT,
                    field_placeholder TEXT,
                    field_label TEXT,
                    field_classes TEXT,
                    surrounding_text TEXT,
                    predicted_category TEXT,
                    predicted_field_type TEXT,
                    actual_category TEXT,
                    actual_field_type TEXT,
                    confidence_score REAL,
                    is_correct INTEGER,
                    ats_platform TEXT,
                    page_url TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_version TEXT,
                    accuracy REAL,
                    precision_macro REAL,
                    recall_macro REAL,
                    f1_macro REAL,
                    training_samples INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("✅ ML training database initialized")
            
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
    
    def extract_features(self, field_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive features from field data"""
        try:
            features = {}
            
            # Text-based features
            text_content = ' '.join([
                str(field_data.get('id', '')),
                str(field_data.get('name', '')),
                str(field_data.get('placeholder', '')),
                str(field_data.get('label', '')),
                str(field_data.get('surrounding_text', ''))
            ]).lower()
            
            # Basic text features
            features['text_content'] = text_content
            features['text_length'] = len(text_content)
            features['word_count'] = len(text_content.split())
            
            # Field attributes
            features['field_type'] = field_data.get('type', 'text')
            features['is_required'] = int(field_data.get('required', False))
            features['has_placeholder'] = int(bool(field_data.get('placeholder')))
            features['has_label'] = int(bool(field_data.get('label')))
            features['has_id'] = int(bool(field_data.get('id')))
            features['has_name'] = int(bool(field_data.get('name')))
            
            # Pattern-based features
            features['contains_name'] = int('name' in text_content)
            features['contains_email'] = int('email' in text_content or '@' in text_content)
            features['contains_phone'] = int(any(word in text_content for word in ['phone', 'tel', 'mobile']))
            features['contains_address'] = int('address' in text_content)
            features['contains_company'] = int('company' in text_content)
            features['contains_title'] = int('title' in text_content)
            features['contains_date'] = int(any(word in text_content for word in ['date', 'year', 'month']))
            features['contains_experience'] = int('experience' in text_content)
            features['contains_education'] = int(any(word in text_content for word in ['education', 'school', 'degree']))
            features['contains_visa'] = int(any(word in text_content for word in ['visa', 'sponsor', 'authorization']))
            features['contains_cover'] = int('cover' in text_content)
            features['contains_resume'] = int(any(word in text_content for word in ['resume', 'cv']))
            
            # Visual/structural features
            classes = str(field_data.get('classes', ''))
            features['class_count'] = len(classes.split()) if classes else 0
            features['has_icon_class'] = int(any(icon in classes for icon in ['icon', 'fa-', 'glyphicon']))
            
            # Context features
            features['ats_platform'] = field_data.get('ats_platform', 'unknown')
            features['form_section'] = field_data.get('form_section', 'unknown')
            
            return features
            
        except Exception as e:
            logger.error(f"❌ Feature extraction error: {e}")
            return {}
    
    def record_prediction(self, field_data: Dict[str, Any], prediction: Tuple[str, str, float], 
                         actual_category: str = None, actual_field_type: str = None):
        """Record prediction for training data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            predicted_category, predicted_field_type, confidence = prediction
            is_correct = None
            
            if actual_category and actual_field_type:
                is_correct = int(predicted_category == actual_category and predicted_field_type == actual_field_type)
            
            cursor.execute('''
                INSERT INTO field_training_data 
                (field_id, field_name, field_type, field_placeholder, field_label, field_classes,
                 surrounding_text, predicted_category, predicted_field_type, actual_category,
                 actual_field_type, confidence_score, is_correct, ats_platform, page_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                field_data.get('id', ''),
                field_data.get('name', ''),
                field_data.get('type', ''),
                field_data.get('placeholder', ''),
                field_data.get('label', ''),
                field_data.get('classes', ''),
                field_data.get('surrounding_text', ''),
                predicted_category,
                predicted_field_type,
                actual_category,
                actual_field_type,
                confidence,
                is_correct,
                field_data.get('ats_platform', ''),
                field_data.get('page_url', '')
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"📊 Recorded prediction: {predicted_category}.{predicted_field_type}")
            
        except Exception as e:
            logger.error(f"❌ Prediction recording error: {e}")
    
    def learn_from_correction(self, field_data: Dict[str, Any], correct_category: str, correct_field_type: str):
        """Learn from user correction"""
        try:
            # Update the database with correct label
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find the most recent prediction for this field
            cursor.execute('''
                SELECT id FROM field_training_data 
                WHERE field_id = ? OR (field_name = ? AND field_placeholder = ?)
                ORDER BY timestamp DESC LIMIT 1
            ''', (
                field_data.get('id', ''),
                field_data.get('name', ''),
                field_data.get('placeholder', '')
            ))
            
            result = cursor.fetchone()
            if result:
                cursor.execute('''
                    UPDATE field_training_data 
                    SET actual_category = ?, actual_field_type = ?, is_correct = ?
                    WHERE id = ?
                ''', (correct_category, correct_field_type, 0, result[0]))  # 0 = correction needed
            else:
                # Insert new training record
                cursor.execute('''
                    INSERT INTO field_training_data 
                    (field_id, field_name, field_type, field_placeholder, field_label, field_classes,
                     surrounding_text, actual_category, actual_field_type, is_correct, ats_platform, page_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    field_data.get('id', ''),
                    field_data.get('name', ''),
                    field_data.get('type', ''),
                    field_data.get('placeholder', ''),
                    field_data.get('label', ''),
                    field_data.get('classes', ''),
                    field_data.get('surrounding_text', ''),
                    correct_category,
                    correct_field_type,
                    1,  # Correct from user
                    field_data.get('ats_platform', ''),
                    field_data.get('page_url', '')
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"📚 Learned correction: {correct_category}.{correct_field_type}")
            
            # Retrain model if we have enough new data
            self._check_and_retrain()
            
        except Exception as e:
            logger.error(f"❌ Learning error: {e}")
    
    def train_model(self, min_samples: int = 50) -> Dict[str, Any]:
        """Train the machine learning model"""
        try:
            # Get training data from database
            training_data = self._get_training_data()
            
            if len(training_data) < min_samples:
                logger.warning(f"⚠️ Not enough training data: {len(training_data)} < {min_samples}")
                return {'success': False, 'reason': 'insufficient_data', 'samples': len(training_data)}
            
            # Prepare features and labels
            X, y = self._prepare_training_data(training_data)
            
            if len(X) == 0:
                logger.warning("⚠️ No valid training features extracted")
                return {'success': False, 'reason': 'no_features'}
            
            # Split data - handle case where some classes have only 1 sample
            try:
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
            except ValueError as e:
                logger.warning(f"⚠️ Stratified split failed, using simple split: {e}")
                # Fall back to simple train_test_split without stratification
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Train model
            self.classifier = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
            self.classifier.fit(X_train, y_train)
            
            # Evaluate model
            y_pred = self.classifier.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            report = classification_report(y_test, y_pred, output_dict=True)
            
            # Save model
            self._save_model()
            
            # Record performance
            self._record_model_performance(accuracy, report, len(training_data))
            
            logger.info(f"✅ Model trained successfully - Accuracy: {accuracy:.3f}")
            
            return {
                'success': True,
                'accuracy': accuracy,
                'training_samples': len(training_data),
                'test_samples': len(X_test),
                'classification_report': report
            }
            
        except Exception as e:
            logger.error(f"❌ Model training error: {e}")
            return {'success': False, 'error': str(e)}
    
    def predict_field_type(self, field_data: Dict[str, Any]) -> Tuple[str, str, float]:
        """Predict field type using trained model"""
        try:
            if not self.classifier:
                logger.warning("⚠️ No trained model available")
                return 'unknown', 'unknown', 0.0
            
            # Extract features
            features = self.extract_features(field_data)
            
            # Prepare feature vector
            feature_vector = self._prepare_feature_vector(features)
            
            if feature_vector is None:
                return 'unknown', 'unknown', 0.0
            
            # Make prediction
            prediction = self.classifier.predict([feature_vector])[0]
            probabilities = self.classifier.predict_proba([feature_vector])[0]
            confidence = float(max(probabilities))
            
            # Decode prediction
            category, field_type = prediction.split('.')
            
            logger.debug(f"🎯 ML Prediction: {category}.{field_type} (confidence: {confidence:.3f})")
            
            return category, field_type, confidence
            
        except Exception as e:
            logger.error(f"❌ ML Prediction error: {e}")
            return 'unknown', 'unknown', 0.0
    
    def _get_training_data(self) -> List[Dict[str, Any]]:
        """Get training data from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM field_training_data 
                WHERE actual_category IS NOT NULL AND actual_field_type IS NOT NULL
            ''')
            
            columns = [desc[0] for desc in cursor.description]
            training_data = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            conn.close()
            
            return training_data
            
        except Exception as e:
            logger.error(f"❌ Training data retrieval error: {e}")
            return []
    
    def _prepare_training_data(self, training_data: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data for ML model"""
        try:
            features_list = []
            labels = []
            
            for record in training_data:
                # Create field data dict from database record
                field_data = {
                    'id': record['field_id'],
                    'name': record['field_name'],
                    'type': record['field_type'],
                    'placeholder': record['field_placeholder'],
                    'label': record['field_label'],
                    'classes': record['field_classes'],
                    'surrounding_text': record['surrounding_text'],
                    'ats_platform': record['ats_platform']
                }
                
                # Extract features
                features = self.extract_features(field_data)
                
                if features:
                    features_list.append(features)
                    labels.append(f"{record['actual_category']}.{record['actual_field_type']}")
            
            if not features_list:
                return np.array([]), np.array([])
            
            # Convert to DataFrame for easier handling
            features_df = pd.DataFrame(features_list)
            
            # Handle categorical features
            categorical_columns = ['field_type', 'ats_platform', 'form_section']
            for col in categorical_columns:
                if col in features_df.columns:
                    features_df[col] = features_df[col].astype('category').cat.codes
            
            # Store feature columns for future use
            self.feature_columns = features_df.columns.tolist()
            
            # Convert to numpy arrays
            X = features_df.values
            y = np.array(labels)
            
            return X, y
            
        except Exception as e:
            logger.error(f"❌ Training data preparation error: {e}")
            return np.array([]), np.array([])
    
    def _prepare_feature_vector(self, features: Dict[str, Any]) -> Optional[np.ndarray]:
        """Prepare feature vector for prediction"""
        try:
            if not self.feature_columns:
                return None
            
            # Create feature vector with same structure as training data
            feature_vector = []
            
            for col in self.feature_columns:
                if col in features:
                    value = features[col]
                    # Handle categorical encoding
                    if col in ['field_type', 'ats_platform', 'form_section']:
                        # Simple hash-based encoding for unknown categories
                        feature_vector.append(hash(str(value)) % 100)
                    else:
                        feature_vector.append(value)
                else:
                    feature_vector.append(0)  # Default value
            
            return np.array(feature_vector)
            
        except Exception as e:
            logger.error(f"❌ Feature vector preparation error: {e}")
            return None
    
    def _save_model(self):
        """Save the trained model to disk"""
        try:
            model_data = {
                'classifier': self.classifier,
                'vectorizer': self.vectorizer,
                'label_encoder': self.label_encoder,
                'feature_columns': self.feature_columns,
                'version': datetime.now().isoformat()
            }
            
            joblib.dump(model_data, self.model_path)
            logger.info(f"✅ Model saved to {self.model_path}")
            
        except Exception as e:
            logger.error(f"❌ Model saving error: {e}")
    
    def _load_model(self) -> bool:
        """Load trained model from disk"""
        try:
            if not self.model_path.exists():
                return False
            
            model_data = joblib.load(self.model_path)
            
            self.classifier = model_data['classifier']
            self.vectorizer = model_data['vectorizer']
            self.label_encoder = model_data['label_encoder']
            self.feature_columns = model_data['feature_columns']
            
            logger.info(f"✅ Model loaded from {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Model loading error: {e}")
            return False
    
    def _record_model_performance(self, accuracy: float, report: Dict, training_samples: int):
        """Record model performance metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO model_performance 
                (model_version, accuracy, precision_macro, recall_macro, f1_macro, training_samples)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                accuracy,
                report['macro avg']['precision'],
                report['macro avg']['recall'],
                report['macro avg']['f1-score'],
                training_samples
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Performance recording error: {e}")
    
    def _check_and_retrain(self):
        """Check if model should be retrained based on new data"""
        try:
            # Get count of new corrections since last training
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) FROM field_training_data 
                WHERE actual_category IS NOT NULL 
                AND timestamp > (
                    SELECT COALESCE(MAX(timestamp), '2000-01-01') 
                    FROM model_performance
                )
            ''')
            
            new_samples = cursor.fetchone()[0]
            conn.close()
            
            # Retrain if we have enough new samples
            if new_samples >= 10:
                logger.info(f"🔄 Retraining model with {new_samples} new samples")
                self.train_model()
            
        except Exception as e:
            logger.error(f"❌ Retrain check error: {e}")
    
    def get_model_stats(self) -> Dict[str, Any]:
        """Get model statistics and performance"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get training data stats
            cursor.execute('SELECT COUNT(*) FROM field_training_data WHERE actual_category IS NOT NULL')
            total_training_samples = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM field_training_data WHERE is_correct = 1')
            correct_predictions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM field_training_data WHERE is_correct = 0')
            incorrect_predictions = cursor.fetchone()[0]
            
            # Get latest model performance
            cursor.execute('''
                SELECT * FROM model_performance 
                ORDER BY timestamp DESC LIMIT 1
            ''')
            
            latest_performance = cursor.fetchone()
            
            conn.close()
            
            stats = {
                'total_training_samples': total_training_samples,
                'correct_predictions': correct_predictions,
                'incorrect_predictions': incorrect_predictions,
                'model_loaded': self.classifier is not None,
                'feature_count': len(self.feature_columns) if self.feature_columns else 0
            }
            
            if latest_performance:
                stats['latest_accuracy'] = latest_performance[2]
                stats['latest_training_date'] = latest_performance[7]
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Stats retrieval error: {e}")
            return {}