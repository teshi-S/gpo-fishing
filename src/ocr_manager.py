"""
OCR Manager for text recognition from game screenshots
Supports multiple OCR engines with graceful fallbacks
"""

import logging
from typing import Optional, Tuple
import time

# Always import numpy and cv2 for fallback detection
try:
    import numpy as np
    import cv2
    FALLBACK_AVAILABLE = True
except ImportError:
    FALLBACK_AVAILABLE = False
    print("⚠️ NumPy/OpenCV not available - text detection disabled")

# Try OCR engines - prioritize EasyOCR since it's more commonly installed
try:
    # Try EasyOCR first
    import easyocr
    from PIL import Image, ImageEnhance
    OCR_AVAILABLE = True
    OCR_ENGINE = "easy"
    print("✅ EasyOCR loaded successfully - text recognition available!")
except ImportError as e:
    print(f"🔍 EasyOCR import failed: {e}")
    try:
        # Fallback to PaddleOCR
        import paddleocr
        from PIL import Image, ImageEnhance
        OCR_AVAILABLE = True
        OCR_ENGINE = "paddle"
        print("✅ PaddleOCR loaded successfully - lightweight text recognition!")
    except ImportError as e2:
        print(f"🔍 PaddleOCR import failed: {e2}")
        OCR_AVAILABLE = False
        OCR_ENGINE = None
        # Create dummy classes for type hints when OCR not available
        class DummyImage:
            Image = object
            LANCZOS = 1
        class DummyEnhance:
            pass
        
        Image = DummyImage()
        ImageEnhance = DummyEnhance()
        if FALLBACK_AVAILABLE:
            print("⚠️ No OCR engine available - using fallback text detection")
        else:
            print("❌ No text detection available - install numpy and opencv-python")

class OCRManager:
    """Manages text recognition from screenshot areas using EasyOCR"""
    
    def __init__(self):
        self.ocr_available = OCR_AVAILABLE
        self.last_text = ""
        self.last_capture_time = 0
        self.capture_cooldown = 1.0  # Minimum seconds between captures
        self.reader = None
        
        # Only real GPO items for better recognition
        self.gpo_items = {
            # Real GPO Items from fishing
            'candycorn': 'Candy Corn',
            'candy corn': 'Candy Corn',
            
            # Devil Fruits (important for webhook logging)
            'devilfruit': 'Devil Fruit',
            'devil fruit': 'Devil Fruit',
        }
        
        if self.ocr_available:
            try:
                if OCR_ENGINE == "easy":
                    print("🔧 Initializing EasyOCR...")
                    # Initialize EasyOCR with English language
                    self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                    print("✅ EasyOCR ready - text recognition available!")
                elif OCR_ENGINE == "paddle":
                    print("🔧 Initializing PaddleOCR (lightweight engine)...")
                    # Initialize PaddleOCR with English language
                    self.reader = paddleocr.PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                    print("✅ PaddleOCR ready - lightweight text recognition!")
            except Exception as e:
                logging.error(f"Failed to initialize {OCR_ENGINE}OCR: {e}")
                self.ocr_available = False
                self.reader = None
    
    def is_available(self) -> bool:
        """Check if OCR is available and configured"""
        return self.ocr_available
    
    def extract_text(self, screenshot_area) -> Optional[str]:
        """
        Extract text from screenshot area using available OCR engine
        
        Args:
            screenshot_area: numpy array of screenshot region
            
        Returns:
            Extracted and filtered text, or None if no text found
        """
        if not self.ocr_available or not self.reader:
            # Fallback: Basic text detection without OCR
            if FALLBACK_AVAILABLE:
                return self.detect_text_fallback(screenshot_area)
            else:
                return None
            
        # Check cooldown to prevent spam
        current_time = time.time()
        if current_time - self.last_capture_time < self.capture_cooldown:
            return None
            
        try:
            # Convert BGR to RGB if needed
            if len(screenshot_area.shape) == 3:
                screenshot_area = cv2.cvtColor(screenshot_area, cv2.COLOR_BGR2RGB)
            
            # Preprocess image for better recognition
            processed_img = self.preprocess_for_easyocr(screenshot_area)
            
            # Use appropriate OCR engine
            if OCR_ENGINE == "paddle":
                # PaddleOCR returns different format: [[[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, confidence]
                results = self.reader.ocr(processed_img, cls=True)
                if results and results[0]:
                    texts = [item[1][0] for item in results[0] if item[1][1] > 0.5]  # confidence > 0.5
                    raw_text = ' '.join(texts)
                else:
                    raw_text = ""
            else:
                # EasyOCR format
                results = self.reader.readtext(processed_img, detail=0, paragraph=True)
                raw_text = ' '.join(results) if results else ""
            
            # Filter and clean text
            if raw_text:
                filtered_text = self.filter_and_clean_text(raw_text)
                
                # Apply item name corrections
                if filtered_text:
                    corrected_text = self.correct_item_names(filtered_text)
                    
                    if corrected_text and corrected_text != self.last_text:
                        self.last_text = corrected_text
                        self.last_capture_time = current_time
                        print(f"📝 {OCR_ENGINE.title()}OCR extracted: {corrected_text}")
                        return corrected_text
                
        except Exception as e:
            logging.error(f"{OCR_ENGINE.title() if OCR_ENGINE else 'OCR'} extraction failed: {e}")
            # Fall back to basic text detection if OCR fails
            if FALLBACK_AVAILABLE:
                return self.detect_text_fallback(screenshot_area)
            else:
                return None
            
        return None
    
    def preprocess_for_easyocr(self, img_array):
        """
        Enhance image for better EasyOCR recognition
        
        Args:
            img_array: numpy array of image
            
        Returns:
            Processed numpy array
        """
        try:
            # Convert to grayscale if needed
            if len(img_array.shape) == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # Scale up for better recognition (2x is enough for EasyOCR)
            height, width = img_array.shape
            img_array = cv2.resize(img_array, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
            
            # Enhance contrast using CLAHE (better than simple contrast)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            img_array = clahe.apply(img_array)
            
            # Denoise
            img_array = cv2.fastNlMeansDenoising(img_array)
            
            # Sharpen
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            img_array = cv2.filter2D(img_array, -1, kernel)
            
            return img_array
            
        except Exception as e:
            logging.error(f"Image preprocessing failed: {e}")
            return img_array
    
    def filter_and_clean_text(self, text: str) -> str:
        """
        Filter out unwanted text and clean up the result
        
        Args:
            text: Raw OCR text
            
        Returns:
            Cleaned and filtered text
        """
        if not text:
            return ""
        
        # First, fix common OCR spacing issues
        text = self.fix_spacing_issues(text)
            
        lines = text.split('\n')
        filtered_lines = []
        
        # Filter patterns to ignore
        ignore_patterns = [
            "SAFE ZONE",
            "safe zone",
            "Safe Zone",
            "LOADING",
            "loading",
            "Loading"
        ]
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Skip lines with ignore patterns
            if any(pattern in line for pattern in ignore_patterns):
                continue
                
            # Skip lines that are too short (likely noise)
            if len(line) < 3:
                continue
                
            # Skip lines with mostly special characters
            if len([c for c in line if c.isalnum()]) < len(line) * 0.5:
                continue
                
            filtered_lines.append(line)
        
        result = '\n'.join(filtered_lines)
        return result.strip()
    
    def fix_spacing_issues(self, text: str) -> str:
        """
        Fix common OCR spacing and formatting issues
        
        Args:
            text: Raw OCR text
            
        Returns:
            Text with improved spacing and formatting
        """
        import re
        
        # Fix common spacing issues
        fixes = [
            # Add space before "for" when it's connected to other words
            (r'([a-z])for([A-Z])', r'\1 for \2'),
            (r'([a-z])for\s+([a-z])', r'\1 for \2'),
            
            # Add space after "capacity" when connected
            (r'capacity([a-z])', r'capacity \1'),
            
            # Fix "reached" spacing
            (r'([a-z])reached', r'\1 reached'),
            
            # Fix specific GPO item names - Fish and other items
            (r'candycorn', r'candy corn'),
            (r'Candycorn', r'Candy Corn'),
            (r'CANDYCORN', r'CANDY CORN'),
            
            # Devil Fruit detection (important for webhook logging)
            (r'devilfruit', r'devil fruit'),
            (r'Devilfruit', r'Devil Fruit'),
            (r'DEVILFRUIT', r'DEVIL FRUIT'),
            
            # Pity counter detection for legendary drops
            (r'pity', r'pity'),
            (r'Pity', r'Pity'),
            (r'PITY', r'PITY'),
            (r'legendary', r'legendary'),
            (r'Legendary', r'Legendary'),
            (r'LEGENDARY', r'LEGENDARY'),
            
            # Fix capacity/inventory related text
            (r'maxcapacity', r'max capacity'),
            (r'Maxcapacity', r'Max capacity'),
            (r'MAXCAPACITY', r'MAX CAPACITY'),
            
            (r'inventoryfull', r'inventory full'),
            (r'Inventoryfull', r'Inventory full'),
            (r'INVENTORYFULL', r'INVENTORY FULL'),
            
            # Add space before capital letters that should be separate words
            (r'([a-z])([A-Z][a-z])', r'\1 \2'),
            
            # Fix common item name patterns
            (r'([a-z])([A-Z][a-z]+\s+[A-Z][a-z]+)', r'\1 \2'),  # "candyCandy Corn" -> "candy Candy Corn"
            
            # Clean up multiple spaces
            (r'\s+', ' '),
        ]
        
        result = text
        for pattern, replacement in fixes:
            result = re.sub(pattern, replacement, result)
        
        # Capitalize first letter of sentences
        sentences = result.split('. ')
        sentences = [s.strip().capitalize() if s else s for s in sentences]
        result = '. '.join(sentences)
        
        return result.strip()
    
    def correct_item_names(self, text: str) -> str:
        """
        Correct GPO item names using the real items database
        
        Args:
            text: Text that may contain GPO item names
            
        Returns:
            Text with corrected item names
        """
        import re
        
        result = text
        
        # Check for each real GPO item in our database
        for incorrect_name, correct_name in self.gpo_items.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(incorrect_name) + r'\b'
            result = re.sub(pattern, correct_name, result, flags=re.IGNORECASE)
        
        return result
    
    def test_ocr(self) -> Tuple[bool, str]:
        """
        Test EasyOCR functionality
        
        Returns:
            Tuple of (success, message)
        """
        if not self.ocr_available or not self.reader:
            return False, f"{OCR_ENGINE or 'OCR'} not available"
            
        try:
            # Create a simple test image with text
            test_img = np.ones((50, 200, 3), dtype=np.uint8) * 255  # White background
            cv2.putText(test_img, 'TEST', (50, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            
            # Try to extract text based on engine
            if OCR_ENGINE == "paddle":
                results = self.reader.ocr(test_img, cls=True)
                success = results and results[0] and any('TEST' in item[1][0].upper() for item in results[0])
            else:
                results = self.reader.readtext(test_img, detail=0)
                success = results and 'TEST' in ' '.join(results).upper()
            
            if success:
                return True, f"{OCR_ENGINE.title()}OCR is working correctly"
            else:
                return True, f"{OCR_ENGINE.title()}OCR loaded but may have issues with text detection"
            
        except Exception as e:
            return False, f"{OCR_ENGINE.title()}OCR test failed: {e}"
    
    def get_stats(self) -> dict:
        """Get OCR statistics"""
        return {
            "available": self.ocr_available,
            "last_text": self.last_text,
            "last_capture_time": self.last_capture_time,
            "cooldown": self.capture_cooldown
        }
    
    def detect_text_fallback(self, screenshot_area) -> Optional[str]:
        """
        Fallback text detection without OCR - detects text-like patterns
        
        Args:
            screenshot_area: numpy array of screenshot region
            
        Returns:
            Simple text detection result or None
        """
        if not FALLBACK_AVAILABLE:
            return None
            
        try:
            # Check cooldown
            current_time = time.time()
            if current_time - self.last_capture_time < self.capture_cooldown:
                return None
            
            height, width = screenshot_area.shape[:2]
            
            # Multiple detection methods for better accuracy
            text_score = 0
            
            # Method 1: Color variance detection (text has different colors than background)
            if len(screenshot_area.shape) == 3:
                # Calculate color variance across the image
                color_variance = np.var(screenshot_area, axis=(0, 1))
                avg_variance = np.mean(color_variance)
                if avg_variance > 500:  # High color variance suggests text
                    text_score += 1
                    print(f"🎨 Color variance detected: {avg_variance:.1f}")
            
            # Method 2: Edge detection (text has many edges)
            gray = np.mean(screenshot_area, axis=2).astype(np.uint8) if len(screenshot_area.shape) == 3 else screenshot_area
            
            # Simple edge detection using gradients
            edges = 0
            for y in range(1, height - 1):
                for x in range(1, width - 1):
                    # Calculate gradient magnitude
                    gx = abs(int(gray[y, x+1]) - int(gray[y, x-1]))
                    gy = abs(int(gray[y+1, x]) - int(gray[y-1, x]))
                    gradient = gx + gy
                    if gradient > 30:  # Edge threshold
                        edges += 1
            
            edge_density = edges / (height * width)
            if edge_density > 0.02:  # Significant edge density
                text_score += 1
                print(f"📐 Edge density: {edge_density:.3f}")
            
            # Method 3: Horizontal line detection (text forms horizontal patterns)
            horizontal_patterns = 0
            for y in range(height):
                line_changes = 0
                for x in range(1, width):
                    if abs(int(gray[y, x]) - int(gray[y, x-1])) > 20:
                        line_changes += 1
                if line_changes > width * 0.1:  # Line has enough changes to be text
                    horizontal_patterns += 1
            
            if horizontal_patterns > height * 0.1:  # Enough horizontal text patterns
                text_score += 1
                print(f"📏 Horizontal patterns: {horizontal_patterns}/{height}")
            
            # Method 4: Check for non-uniform background (text creates patterns)
            background_uniformity = np.std(gray)
            if background_uniformity > 15:  # Non-uniform background suggests text
                text_score += 1
                print(f"🌈 Background variation: {background_uniformity:.1f}")
            
            print(f"📊 Text detection score: {text_score}/4 (Area: {width}x{height})")
            
            # More strict requirements for drop detection
            # We need high confidence (3+ indicators) OR very high color variance (indicating colorful text)
            high_confidence = text_score >= 3
            very_colorful = len(screenshot_area.shape) == 3 and np.mean(np.var(screenshot_area, axis=(0, 1))) > 800
            
            if high_confidence or very_colorful:
                self.last_capture_time = current_time
                # Try to extract some basic info about what we detected
                return f"TEXT_DETECTED_NO_OCR (score: {text_score}/4, area: {width}x{height})"
            
            return None
            
        except Exception as e:
            logging.error(f"Fallback text detection failed: {e}")
            return None