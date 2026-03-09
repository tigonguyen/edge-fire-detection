import os
import sys

# Add current dir to path
sys.path.append(os.path.dirname(__file__))

from fire_detector import FireDetector

def main():
    model_path = "../model/fire_detection.onnx"
    print(f"Testing FireDetector with {model_path}")
    
    detector = FireDetector(model_path=model_path)
    
    # Create a dummy image
    from PIL import Image
    import io
    img = Image.new('RGB', (224, 224), color = 'red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()
    
    print("Running detection...")
    result = detector.detect(img_bytes)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
