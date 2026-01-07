"""
Extract frames from video and test with trained fire detection model.
"""

import cv2
import torch
import timm
from PIL import Image
from torchvision import transforms
from pathlib import Path
import os

def load_trained_model(checkpoint_path='fire_detection_best.pth'):
    """Load the trained model."""
    print(f"Loading trained model from {checkpoint_path}...")
    
    if not Path(checkpoint_path).exists():
        print(f"❌ Model checkpoint not found: {checkpoint_path}")
        print("Please train the model first: python model/train_fire_detection.py")
        return None, None
    
    # Load checkpoint
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    
    # Get class names and number of classes
    class_names = checkpoint.get('class_names', ['fire', 'normal'])
    num_classes = checkpoint.get('num_classes', 2)
    
    # Create model with same architecture
    model = timm.create_model('efficientnet_b0', pretrained=False, num_classes=num_classes)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    print(f"✅ Model loaded successfully!")
    print(f"   Classes: {class_names}")
    
    return model, class_names

def extract_frames(video_path, output_dir='video_frames', frame_interval=30):
    """
    Extract frames from video.
    
    Args:
        video_path: Path to video file
        output_dir: Directory to save frames
        frame_interval: Extract every Nth frame (e.g., 30 = 1 frame per second at 30fps)
    
    Returns:
        List of extracted frame paths
    """
    if not Path(video_path).exists():
        print(f"❌ Video not found: {video_path}")
        return []
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print(f"📹 Extracting frames from: {video_path}")
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"❌ Failed to open video: {video_path}")
        return []
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"   FPS: {fps:.2f}")
    print(f"   Total frames: {total_frames}")
    print(f"   Duration: {duration:.2f} seconds")
    print(f"   Extracting every {frame_interval} frames...")
    
    frame_paths = []
    frame_count = 0
    saved_count = 0
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            break
        
        # Save frame at intervals
        if frame_count % frame_interval == 0:
            frame_filename = output_path / f"frame_{saved_count:04d}.jpg"
            cv2.imwrite(str(frame_filename), frame)
            frame_paths.append(frame_filename)
            saved_count += 1
        
        frame_count += 1
    
    cap.release()
    
    print(f"✅ Extracted {saved_count} frames to {output_dir}/")
    
    return frame_paths

def predict_frame(model, image_path, class_names):
    """Predict on a single frame."""
    
    # Load and preprocess image
    image = Image.open(image_path).convert('RGB')
    
    preprocess = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    
    input_tensor = preprocess(image).unsqueeze(0)
    
    # Predict
    with torch.no_grad():
        output = model(input_tensor)
        probs = torch.softmax(output, dim=1)
        predicted_class = torch.argmax(probs, dim=1).item()
        confidence = probs[0][predicted_class].item()
    
    return predicted_class, confidence, probs[0]

def test_video_frames(video_path, model, class_names, frame_interval=30, confidence_threshold=0.7):
    """Extract frames from video and test with model."""
    
    # Extract frames
    output_dir = f"video_frames_{Path(video_path).stem}"
    frame_paths = extract_frames(video_path, output_dir, frame_interval)
    
    if not frame_paths:
        return
    
    print(f"\n{'='*60}")
    print(f"🔍 Testing {len(frame_paths)} frames with fire detection model")
    print(f"{'='*60}\n")
    
    fire_detections = []
    
    for i, frame_path in enumerate(frame_paths):
        predicted_class, confidence, probs = predict_frame(model, frame_path, class_names)
        
        # Display results
        fire_prob = probs[class_names.index('fire')].item() if 'fire' in class_names else probs[1].item()
        
        status = ""
        if predicted_class == class_names.index('fire') and confidence > confidence_threshold:
            status = "🔥 FIRE DETECTED!"
            fire_detections.append((i, frame_path, confidence))
        else:
            status = "✅ Normal"
        
        print(f"Frame {i:3d}: {status:<20} Fire: {fire_prob*100:5.2f}% | Normal: {probs[0]*100:5.2f}%")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 DETECTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total frames analyzed: {len(frame_paths)}")
    print(f"Fire detections: {len(fire_detections)}")
    
    if fire_detections:
        print(f"\n🔥 Fire detected in frames:")
        for frame_num, frame_path, conf in fire_detections:
            print(f"   Frame {frame_num}: {frame_path.name} (confidence: {conf*100:.2f}%)")
    else:
        print(f"\n✅ No fire detected in any frame")
    
    print(f"{'='*60}")

def main():
    print("="*60)
    print("🎥 Video Frame Fire Detection")
    print("="*60)
    
    # Load trained model
    model, class_names = load_trained_model()
    
    if model is None:
        return
    
    # List available videos
    print(f"\n📁 Available videos:")
    video_files = list(Path('.').glob('*.mp4')) + list(Path('.').glob('*.avi'))
    
    if not video_files:
        print("   No video files found in current directory")
        print("   Please specify video path manually")
        return
    
    for i, video in enumerate(video_files, 1):
        print(f"   {i}. {video.name}")
    
    # Get user choice
    print(f"\nChoose video (1-{len(video_files)}) or press Enter for all: ", end='')
    choice = input().strip()
    
    if choice == '':
        # Test all videos
        for video in video_files:
            print(f"\n{'='*60}")
            print(f"Testing: {video.name}")
            print(f"{'='*60}")
            test_video_frames(str(video), model, class_names, frame_interval=30)
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(video_files):
                video = video_files[idx]
                test_video_frames(str(video), model, class_names, frame_interval=30)
            else:
                print("Invalid choice")
        except ValueError:
            print("Invalid input")

if __name__ == '__main__':
    main()

