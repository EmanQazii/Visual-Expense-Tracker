import cv2
import numpy as np
from PIL import Image
import os

def load_image(image_path):
    """Load image from path"""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image from {image_path}")
    return image

# ─────────────────────────────────────────
# QUALITY CHECK (runs first)
# Member 3 — Quality Assessment
# ─────────────────────────────────────────

def check_image_quality(image):
    """
    Check if image is usable before processing.
    Returns (is_ok, reason)
    """
    # Check resolution — too small means unreadable
    height, width = image.shape[:2]
    if height < 100 or width < 100:
        return False, "Image too small to process"

    # Check blur using Laplacian variance
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur_score < 20:
        return False, "Image too blurry, please retake"

    # Check brightness
    brightness = gray.mean()
    if brightness < 30:
        return False, "Image too dark, please retake"
    if brightness > 240:
        return False, "Image too bright/overexposed"

    return True, "OK"


# ─────────────────────────────────────────
# MEMBER 1 — Image Enhancement
# ─────────────────────────────────────────

def convert_grayscale(image):
    """Convert BGR image to grayscale"""
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

def apply_gaussian_blur(gray):
    """
    Smooth noise using Gaussian filter.
    Kernel size 3x3 — small enough to not blur text
    """
    return cv2.GaussianBlur(gray, (3, 3), 0)

def apply_median_filter(gray):
    """
    Handle salt and pepper noise using median filter.
    Good for receipt images with specks/dots
    """
    return cv2.medianBlur(gray, 3)

def apply_clahe(gray):
    """
    CLAHE — Contrast Limited Adaptive Histogram Equalization.
    Better than basic histogram equalization for receipts
    because it works on local regions, handling uneven lighting.
    """
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)

def apply_gamma_correction(gray, gamma=1.5):
    """
    Gamma correction to brighten dark receipt images.
    gamma > 1 brightens, gamma < 1 darkens
    """
    inv_gamma = 1.0 / gamma
    table = np.array([
        ((i / 255.0) ** inv_gamma) * 255
        for i in range(256)
    ]).astype("uint8")
    return cv2.LUT(gray, table)


# ─────────────────────────────────────────
# MEMBER 2 — Segmentation + Binarization
# ─────────────────────────────────────────

def deskew(gray):
    """
    Straighten tilted receipt images.
    Detects the angle of text lines and rotates to correct.
    """
    coords = np.column_stack(np.where(gray > 0))
    if len(coords) < 10:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # Only deskew if tilt is significant
    if abs(angle) < 0.5:
        return gray

    h, w = gray.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )
    return rotated

def apply_adaptive_threshold(gray):
    """
    Adaptive thresholding — converts image to pure black/white.
    Adaptive means it calculates threshold for small regions
    separately, handling shadows and uneven lighting on receipts.
    """
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )

def morphological_clean(binary):
    """
    Clean up broken characters using morphological operations.
    Dilation fills gaps, erosion removes small noise dots.
    """
    kernel = np.ones((1, 1), np.uint8)
    # Remove small noise
    cleaned = cv2.erode(binary, kernel, iterations=1)
    # Fill small gaps in characters
    cleaned = cv2.dilate(cleaned, kernel, iterations=1)
    return cleaned


# ─────────────────────────────────────────
# MEMBER 3 — Sharpening + Output
# ─────────────────────────────────────────

def apply_laplacian_sharpening(gray):
    """
    Sharpen text edges using Laplacian filter.
    Makes character edges crisp for better OCR reading.
    """
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    laplacian = np.uint8(np.absolute(laplacian))
    sharpened = cv2.subtract(gray, laplacian)
    return sharpened

def save_comparison(original, processed, output_dir="ocr/debug"):
    """
    Save before/after images for debugging and demonstration.
    """
    os.makedirs(output_dir, exist_ok=True)
    cv2.imwrite(f"{output_dir}/original.png", original)
    cv2.imwrite(f"{output_dir}/processed.png", processed)


# ─────────────────────────────────────────
# MAIN PIPELINE — Combines Everything
# ─────────────────────────────────────────
def preprocess(image_path, save_debug=True):
    image = load_image(image_path)
    original = image.copy()

    is_ok, reason = check_image_quality(image)
    if not is_ok:
        raise ValueError(f"Image rejected: {reason}")

    # Use red channel for blue ink
    b, g, r = cv2.split(image)
    gray = r.copy()

    # Resize to improve OCR — bigger = better
    scale = 2.0
    gray = cv2.resize(gray, None, fx=scale, fy=scale, 
                      interpolation=cv2.INTER_CUBIC)

    # Strong denoise to kill background grain
    gray = cv2.fastNlMeansDenoising(gray, h=15, 
                                     templateWindowSize=7, 
                                     searchWindowSize=21)

    # CLAHE
    gray = apply_clahe(gray)

    # Deskew
    gray = deskew(gray)

    # Sharpen before threshold
    gray = apply_laplacian_sharpening(gray)

    # Threshold
    binary = cv2.threshold(gray, 0, 255, 
                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    # Remove noise dots
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    if save_debug:
        save_comparison(original, binary)

    return binary