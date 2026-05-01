#!/usr/bin/env python3
"""
Project Anton Egon - Phase 2: Name Reader
OCR module for reading name labels from Teams window
"""

import asyncio
import cv2
import numpy as np
from typing import Optional, Callable, Dict, Any, List, Tuple
from datetime import datetime, timezone
from pathlib import Path

import easyocr
import mss
from PIL import Image

from loguru import logger


class OCRConfig:
    """OCR configuration"""
    TARGET_FPS = 0.5  # OCR is slow, run at 0.5 FPS (every 2 seconds)
    CONFIDENCE_THRESHOLD = 0.6
    LANGUAGES = ['en', 'sv']  # English and Swedish
    NAME_REGIONS = [
        # Teams typically shows names in bottom corners of participant tiles
        {"relative_y": 0.85, "relative_h": 0.15, "relative_x": 0.05, "relative_w": 0.4},  # Bottom-left
        {"relative_y": 0.85, "relative_h": 0.15, "relative_x": 0.55, "relative_w": 0.4}  # Bottom-right
    ]


class NameReader:
    """
    OCR-based name reader for Teams participant labels
    Focuses on name regions to minimize processing overhead
    """
    
    def __init__(
        self,
        target_fps: float = OCRConfig.TARGET_FPS,
        on_name_detected: Optional[Callable] = None,
        window_title: Optional[str] = "Microsoft Teams"
    ):
        """
        Initialize name reader
        
        Args:
            target_fps: Target frames per second (default: 0.5)
            on_name_detected: Callback for name detection results
            window_title: Window title to capture (e.g., "Microsoft Teams")
        """
        self.target_fps = target_fps
        self.on_name_detected = on_name_detected
        self.window_title = window_title
        
        self.running = False
        self.ocr_task = None
        self.window_region = None
        
        logger.info(f"Initializing NameReader at {target_fps} FPS")
        
        # Initialize EasyOCR
        self._init_ocr()
        
        # Initialize screen capture
        self._init_screen_capture()
    
    def _init_ocr(self):
        """Initialize EasyOCR reader"""
        try:
            logger.info("Loading EasyOCR model")
            # Use GPU if available, otherwise CPU
            use_gpu = False  # Keep OCR on CPU to save GPU for critical components
            
            self.ocr_reader = easyocr.Reader(
                OCRConfig.LANGUAGES,
                gpu=use_gpu,
                verbose=False
            )
            
            logger.info("EasyOCR loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load EasyOCR: {e}")
            raise
    
    def _init_screen_capture(self):
        """Initialize screen capture (MSS)"""
        try:
            self.screen_capture = mss.mss()
            
            # Find window region
            if self.window_title:
                self._find_window_region()
            
            logger.info("Screen capture initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize screen capture: {e}")
            raise
    
    def _find_window_region(self):
        """Find window region by title (Windows only)"""
        try:
            import win32gui
            import win32con
            
            def callback(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if self.window_title.lower() in title.lower():
                        rect = win32gui.GetWindowRect(hwnd)
                        self.window_region = {
                            "top": rect[1],
                            "left": rect[0],
                            "width": rect[2] - rect[0],
                            "height": rect[3] - rect[1]
                        }
                        logger.info(f"Found window region: {self.window_region}")
            
            win32gui.EnumWindows(callback, None)
            
            if not self.window_region:
                logger.warning(f"Window '{self.window_title}' not found, using full screen")
            
        except ImportError:
            logger.warning("win32gui not available, using full screen capture")
        except Exception as e:
            logger.error(f"Failed to find window region: {e}")
    
    def _capture_screen(self) -> np.ndarray:
        """Capture screen or window region"""
        try:
            if self.window_region:
                monitor = self.window_region
            else:
                monitor = self.screen_capture.monitors[0]  # Primary monitor
            
            # Capture screen
            screenshot = self.screen_capture.grab(monitor)
            
            # Convert to numpy array (BGR format for OpenCV)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            return img
            
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return np.zeros((480, 640, 3), dtype=np.uint8)
    
    def _extract_name_regions(self, image: np.ndarray) -> List[Tuple[np.ndarray, Dict[str, Any]]]:
        """Extract name regions from image based on predefined areas"""
        height, width = image.shape[:2]
        regions = []
        
        for i, region_config in enumerate(OCRConfig.NAME_REGIONS):
            # Calculate absolute coordinates
            y = int(region_config["relative_y"] * height)
            h = int(region_config["relative_h"] * height)
            x = int(region_config["relative_x"] * width)
            w = int(region_config["relative_w"] * width)
            
            # Extract region
            region = image[y:y+h, x:x+w]
            
            # Preprocess for OCR
            # Convert to grayscale
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            
            # Apply threshold to improve text detection
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(binary)
            
            regions.append((denoised, {
                "region_id": i,
                "bbox": [x, y, w, h],
                "relative_coords": region_config
            }))
        
        return regions
    
    def _read_text(self, region_image: np.ndarray) -> List[Dict[str, Any]]:
        """Read text from image region using EasyOCR"""
        try:
            # Run OCR
            results = self.ocr_reader.readtext(region_image)
            
            texts = []
            for (bbox, text, confidence) in results:
                if confidence >= OCRConfig.CONFIDENCE_THRESHOLD:
                    # Clean up text
                    cleaned_text = text.strip()
                    if cleaned_text:
                        texts.append({
                            "text": cleaned_text,
                            "confidence": float(confidence),
                            "bbox": bbox
                        })
            
            return texts
            
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return []
    
    def _filter_names(self, texts: List[str]) -> List[str]:
        """Filter OCR results to extract likely names"""
        names = []
        
        # Common non-name patterns to filter out
        stop_words = {
            "muted", "unmuted", "video", "audio", "share", "screen",
            "recording", "meeting", "call", "join", "leave", "hand",
            "raise", "lower", "chat", "reactions", "more", "options"
        }
        
        for text in texts:
            # Remove common UI elements
            text_lower = text.lower()
            
            # Skip if it's a stop word
            if text_lower in stop_words:
                continue
            
            # Skip if it's too short or too long
            if len(text) < 2 or len(text) > 50:
                continue
            
            # Skip if it contains numbers (likely not a name)
            if any(char.isdigit() for char in text):
                continue
            
            # Skip if it's mostly special characters
            if sum(not char.isalnum() and char not in " -'" for char in text) > len(text) / 2:
                continue
            
            names.append(text)
        
        return names
    
    async def _ocr_loop(self):
        """Main OCR loop"""
        logger.info("Starting name reader OCR loop")
        
        frame_interval = 1.0 / self.target_fps
        
        while self.running:
            start_time = asyncio.get_event_loop().time()
            
            try:
                # Capture screen
                image = self._capture_screen()
                
                # Extract name regions
                regions = self._extract_name_regions(image)
                
                # Read text from each region
                all_names = []
                for region_image, region_info in regions:
                    texts = self._read_text(region_image)
                    for text_info in texts:
                        all_names.append({
                            "text": text_info["text"],
                            "confidence": text_info["confidence"],
                            "region_id": region_info["region_id"],
                            "bbox": region_info["bbox"]
                        })
                
                # Filter to extract likely names
                raw_texts = [item["text"] for item in all_names]
                filtered_names = self._filter_names(raw_texts)
                
                # Emit results
                if filtered_names and self.on_name_detected:
                    result = {
                        "names": filtered_names,
                        "raw_detections": all_names,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "num_names": len(filtered_names)
                    }
                    await self.on_name_detected(result)
                    
                    logger.info(f"Detected names: {filtered_names}")
                
                # Sleep to maintain target FPS
                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"OCR loop error: {e}")
                await asyncio.sleep(2.0)
    
    async def start(self):
        """Start name reading"""
        if self.running:
            logger.warning("Name reader already running")
            return
        
        logger.info("Starting name reader")
        self.running = True
        
        # Start OCR task
        self.ocr_task = asyncio.create_task(self._ocr_loop())
    
    async def stop(self):
        """Stop name reading"""
        if not self.running:
            return
        
        logger.info("Stopping name reader")
        self.running = False
        
        # Cancel OCR task
        if self.ocr_task:
            self.ocr_task.cancel()
            try:
                await self.ocr_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Name reader stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current reader status"""
        return {
            "running": self.running,
            "target_fps": self.target_fps,
            "window_title": self.window_title,
            "window_region": self.window_region,
            "languages": OCRConfig.LANGUAGES,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the name reader"""
    from loguru import logger
    
    logger.add("logs/name_reader_{time}.log", rotation="10 MB")
    
    # Test callback
    async def on_name_detected(result):
        logger.info(f"Detected {result['num_names']} name(s): {result['names']}")
    
    # Create name reader
    reader = NameReader(target_fps=0.5, on_name_detected=on_name_detected)
    
    try:
        await reader.start()
        logger.info("Reading names... Press Ctrl+C to stop")
        
        # Run for 60 seconds
        await asyncio.sleep(60)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await reader.stop()


if __name__ == "__main__":
    asyncio.run(main())
