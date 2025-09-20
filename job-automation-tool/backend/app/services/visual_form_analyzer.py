"""
Computer Vision-based Form Analysis for enhanced field detection
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from typing import Dict, List, Any, Tuple, Optional
from loguru import logger
import base64
import io
import json

class VisualFormAnalyzer:
    def __init__(self):
        self.field_detection_model = None
        self.ocr_config = '--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@.-_'
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize computer vision models"""
        try:
            # Check if tesseract is available
            pytesseract.get_tesseract_version()
            logger.info("✅ Tesseract OCR initialized")
        except Exception as e:
            logger.warning(f"⚠️ Tesseract OCR not available: {e}")
    
    async def analyze_form_screenshot(self, screenshot_base64: str, dom_elements: List[Dict]) -> Dict[str, Any]:
        """
        Analyze form using computer vision on screenshot
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            dom_elements: DOM element data from browser
            
        Returns:
            Enhanced field analysis with visual context
        """
        try:
            # Decode screenshot
            image = self._decode_screenshot(screenshot_base64)
            
            # Extract visual features
            visual_features = self._extract_visual_features(image)
            
            # Detect form regions
            form_regions = self._detect_form_regions(image)
            
            # OCR analysis
            ocr_results = self._perform_ocr(image)
            
            # Match DOM elements with visual elements
            enhanced_elements = self._match_dom_with_visual(dom_elements, visual_features, ocr_results)
            
            return {
                'success': True,
                'visual_features': visual_features,
                'form_regions': form_regions,
                'ocr_results': ocr_results,
                'enhanced_elements': enhanced_elements,
                'confidence_score': self._calculate_visual_confidence(visual_features)
            }
            
        except Exception as e:
            logger.error(f"❌ Visual analysis error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _decode_screenshot(self, screenshot_base64: str) -> np.ndarray:
        """Decode base64 screenshot to OpenCV image"""
        try:
            # Remove data URL prefix if present
            if ',' in screenshot_base64:
                screenshot_base64 = screenshot_base64.split(',')[1]
            
            # Decode base64
            image_data = base64.b64decode(screenshot_base64)
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to OpenCV format
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            return opencv_image
            
        except Exception as e:
            logger.error(f"❌ Screenshot decode error: {e}")
            raise
    
    def _extract_visual_features(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract comprehensive visual features from form image"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect edges
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Find contours (potential input fields)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours to find rectangular shapes (likely input fields)
            potential_fields = []
            for contour in contours:
                # Approximate contour to polygon
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Check if it's rectangular
                if len(approx) == 4:
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # Filter by size (likely input field dimensions)
                    if w > 50 and h > 15 and w < 800 and h < 100:
                        aspect_ratio = w / h
                        area = cv2.contourArea(contour)
                        
                        potential_fields.append({
                            'bbox': [x, y, w, h],
                            'area': area,
                            'aspect_ratio': aspect_ratio,
                            'contour': contour.tolist(),
                            'field_type': self._classify_field_by_shape(w, h, aspect_ratio)
                        })
            
            # Detect lines (form structure)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=50, maxLineGap=10)
            
            # Color analysis
            color_features = self._analyze_colors(image)
            
            # Text region detection
            text_regions = self._detect_text_regions(gray)
            
            return {
                'potential_fields': potential_fields,
                'lines': lines.tolist() if lines is not None else [],
                'color_features': color_features,
                'text_regions': text_regions,
                'image_dimensions': image.shape[:2]
            }
            
        except Exception as e:
            logger.error(f"❌ Visual feature extraction error: {e}")
            return {}
    
    def _classify_field_by_shape(self, width: int, height: int, aspect_ratio: float) -> str:
        """Classify field type based on visual dimensions"""
        if aspect_ratio > 10:  # Very wide fields
            return 'text_input'
        elif aspect_ratio > 3:  # Wide fields
            return 'short_text'
        elif aspect_ratio < 1.5:  # Square-ish fields
            if width < 100:
                return 'checkbox'
            else:
                return 'textarea'
        else:
            return 'standard_input'
    
    def _detect_form_regions(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect major form regions using visual clustering"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply morphological operations to group related elements
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 5))
            morph = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            
            # Find contours of form regions
            contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            form_regions = []
            for i, contour in enumerate(contours):
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter for reasonable form section sizes
                if w > 200 and h > 100:
                    region_area = w * h
                    form_regions.append({
                        'region_id': i,
                        'bbox': [x, y, w, h],
                        'area': region_area,
                        'estimated_field_count': self._estimate_field_count(w, h)
                    })
            
            return form_regions
            
        except Exception as e:
            logger.error(f"❌ Form region detection error: {e}")
            return []
    
    def _estimate_field_count(self, width: int, height: int) -> int:
        """Estimate number of form fields in a region based on dimensions"""
        # Rough estimation based on typical field sizes
        estimated_fields = max(1, (height // 50) * max(1, width // 300))
        return min(estimated_fields, 20)  # Cap at reasonable number
    
    def _perform_ocr(self, image: np.ndarray) -> Dict[str, Any]:
        """Perform OCR to extract text and labels"""
        try:
            # Convert to PIL Image for OCR
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            # Get detailed OCR results
            ocr_data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT, config=self.ocr_config)
            
            # Process OCR results
            text_elements = []
            for i in range(len(ocr_data['text'])):
                if int(ocr_data['conf'][i]) > 30:  # Confidence threshold
                    text = ocr_data['text'][i].strip()
                    if text:  # Non-empty text
                        text_elements.append({
                            'text': text,
                            'bbox': [
                                ocr_data['left'][i],
                                ocr_data['top'][i],
                                ocr_data['width'][i],
                                ocr_data['height'][i]
                            ],
                            'confidence': ocr_data['conf'][i],
                            'likely_label': self._is_likely_label(text)
                        })
            
            # Identify potential field labels
            field_labels = [elem for elem in text_elements if elem['likely_label']]
            
            return {
                'all_text': text_elements,
                'field_labels': field_labels,
                'full_text': ' '.join([elem['text'] for elem in text_elements])
            }
            
        except Exception as e:
            logger.error(f"❌ OCR error: {e}")
            return {'all_text': [], 'field_labels': [], 'full_text': ''}
    
    def _is_likely_label(self, text: str) -> bool:
        """Determine if text is likely a form field label"""
        # Common label patterns
        label_indicators = [
            'name', 'email', 'phone', 'address', 'city', 'state', 'zip',
            'company', 'title', 'experience', 'education', 'skills',
            'password', 'username', 'first', 'last', 'middle',
            'contact', 'information', 'required', '*', ':'
        ]
        
        text_lower = text.lower()
        
        # Check for label indicators
        has_indicator = any(indicator in text_lower for indicator in label_indicators)
        
        # Check for typical label formatting (ends with :, *, etc.)
        has_label_format = text.endswith((':', '*')) or '*' in text
        
        # Length check (labels are usually short)
        reasonable_length = 3 <= len(text) <= 50
        
        return (has_indicator or has_label_format) and reasonable_length
    
    def _analyze_colors(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze color scheme to understand form styling"""
        try:
            # Convert to different color spaces
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Analyze dominant colors
            pixels = image.reshape(-1, 3)
            
            # Simple color analysis
            mean_color = np.mean(pixels, axis=0)
            dominant_hue = np.mean(hsv[:, :, 0])
            
            # Detect if it's a dark or light theme
            brightness = np.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
            theme = 'dark' if brightness < 128 else 'light'
            
            return {
                'mean_color': mean_color.tolist(),
                'dominant_hue': float(dominant_hue),
                'theme': theme,
                'brightness': float(brightness)
            }
            
        except Exception as e:
            logger.error(f"❌ Color analysis error: {e}")
            return {}
    
    def _detect_text_regions(self, gray_image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect regions likely to contain text"""
        try:
            # Use EAST text detector if available, otherwise use simple method
            return self._simple_text_detection(gray_image)
            
        except Exception as e:
            logger.error(f"❌ Text region detection error: {e}")
            return []
    
    def _simple_text_detection(self, gray_image: np.ndarray) -> List[Dict[str, Any]]:
        """Simple text region detection using morphological operations"""
        try:
            # Apply morphological operations to connect text
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1))
            connected = cv2.morphologyEx(gray_image, cv2.MORPH_CLOSE, kernel)
            
            # Find contours
            contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            text_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter for text-like dimensions
                if w > 20 and h > 8 and w < 500 and h < 50:
                    aspect_ratio = w / h
                    if 1 < aspect_ratio < 20:  # Text aspect ratio
                        text_regions.append({
                            'bbox': [x, y, w, h],
                            'area': w * h,
                            'aspect_ratio': aspect_ratio
                        })
            
            return text_regions
            
        except Exception as e:
            logger.error(f"❌ Simple text detection error: {e}")
            return []
    
    def _match_dom_with_visual(self, dom_elements: List[Dict], visual_features: Dict, ocr_results: Dict) -> List[Dict]:
        """Match DOM elements with visual analysis results"""
        try:
            enhanced_elements = []
            
            for dom_element in dom_elements:
                enhanced_element = dom_element.copy()
                
                # Try to match with visual fields
                visual_match = self._find_closest_visual_match(dom_element, visual_features)
                if visual_match:
                    enhanced_element['visual_features'] = visual_match
                
                # Try to match with OCR labels
                label_match = self._find_closest_label_match(dom_element, ocr_results)
                if label_match:
                    enhanced_element['nearby_labels'] = label_match
                
                # Add visual confidence
                enhanced_element['visual_confidence'] = self._calculate_element_confidence(enhanced_element)
                
                enhanced_elements.append(enhanced_element)
            
            return enhanced_elements
            
        except Exception as e:
            logger.error(f"❌ DOM-Visual matching error: {e}")
            return dom_elements
    
    def _find_closest_visual_match(self, dom_element: Dict, visual_features: Dict) -> Optional[Dict]:
        """Find the closest visual field match for a DOM element"""
        try:
            if 'bbox' not in dom_element:
                return None
            
            dom_bbox = dom_element['bbox']  # [x, y, width, height]
            best_match = None
            best_overlap = 0
            
            for visual_field in visual_features.get('potential_fields', []):
                visual_bbox = visual_field['bbox']
                
                # Calculate overlap
                overlap = self._calculate_bbox_overlap(dom_bbox, visual_bbox)
                
                if overlap > best_overlap and overlap > 0.3:  # Minimum overlap threshold
                    best_overlap = overlap
                    best_match = visual_field
            
            return best_match
            
        except Exception as e:
            logger.error(f"❌ Visual matching error: {e}")
            return None
    
    def _find_closest_label_match(self, dom_element: Dict, ocr_results: Dict) -> List[Dict]:
        """Find nearby labels for a DOM element"""
        try:
            if 'bbox' not in dom_element:
                return []
            
            dom_bbox = dom_element['bbox']
            nearby_labels = []
            
            for text_element in ocr_results.get('field_labels', []):
                text_bbox = text_element['bbox']
                
                # Calculate distance between DOM element and text
                distance = self._calculate_bbox_distance(dom_bbox, text_bbox)
                
                # Consider labels within reasonable proximity
                if distance < 100:  # pixels
                    nearby_labels.append({
                        'text': text_element['text'],
                        'distance': distance,
                        'confidence': text_element['confidence']
                    })
            
            # Sort by distance (closest first)
            nearby_labels.sort(key=lambda x: x['distance'])
            
            return nearby_labels[:3]  # Return top 3 closest labels
            
        except Exception as e:
            logger.error(f"❌ Label matching error: {e}")
            return []
    
    def _calculate_bbox_overlap(self, bbox1: List[int], bbox2: List[int]) -> float:
        """Calculate overlap ratio between two bounding boxes"""
        try:
            x1, y1, w1, h1 = bbox1
            x2, y2, w2, h2 = bbox2
            
            # Calculate intersection
            x_left = max(x1, x2)
            y_top = max(y1, y2)
            x_right = min(x1 + w1, x2 + w2)
            y_bottom = min(y1 + h1, y2 + h2)
            
            if x_right < x_left or y_bottom < y_top:
                return 0.0
            
            intersection_area = (x_right - x_left) * (y_bottom - y_top)
            bbox1_area = w1 * h1
            bbox2_area = w2 * h2
            union_area = bbox1_area + bbox2_area - intersection_area
            
            return intersection_area / union_area if union_area > 0 else 0.0
            
        except Exception as e:
            logger.error(f"❌ Overlap calculation error: {e}")
            return 0.0
    
    def _calculate_bbox_distance(self, bbox1: List[int], bbox2: List[int]) -> float:
        """Calculate distance between centers of two bounding boxes"""
        try:
            x1, y1, w1, h1 = bbox1
            x2, y2, w2, h2 = bbox2
            
            # Calculate centers
            center1_x = x1 + w1 / 2
            center1_y = y1 + h1 / 2
            center2_x = x2 + w2 / 2
            center2_y = y2 + h2 / 2
            
            # Euclidean distance
            distance = np.sqrt((center2_x - center1_x) ** 2 + (center2_y - center1_y) ** 2)
            
            return float(distance)
            
        except Exception as e:
            logger.error(f"❌ Distance calculation error: {e}")
            return float('inf')
    
    def _calculate_element_confidence(self, element: Dict) -> float:
        """Calculate confidence score for enhanced element"""
        try:
            confidence = 0.5  # Base confidence
            
            # Boost confidence if visual features match
            if 'visual_features' in element:
                confidence += 0.3
            
            # Boost confidence if nearby labels found
            if 'nearby_labels' in element and element['nearby_labels']:
                confidence += 0.2
            
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"❌ Confidence calculation error: {e}")
            return 0.5
    
    def _calculate_visual_confidence(self, visual_features: Dict) -> float:
        """Calculate overall visual analysis confidence"""
        try:
            confidence = 0.0
            
            # Factor in number of detected fields
            field_count = len(visual_features.get('potential_fields', []))
            if field_count > 0:
                confidence += min(0.3, field_count * 0.05)
            
            # Factor in text regions
            text_regions = len(visual_features.get('text_regions', []))
            if text_regions > 0:
                confidence += min(0.3, text_regions * 0.03)
            
            # Factor in form structure
            if visual_features.get('lines'):
                confidence += 0.2
            
            # Base confidence for having visual features
            confidence += 0.2
            
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"❌ Visual confidence calculation error: {e}")
            return 0.5