"""
Test the trained fire detection model.
"""

import torch
import timm
from PIL import Image
from torchvision import transforms

def load_trained_model(checkpoint_path='fire_detection_best.pth'):
    """Load the trained model."""
    print(f"Loading trained model from {checkpoint_path}...")
    
    # Load checkpoint
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    
    # Get number of classes from checkpoint
    class_names = checkpoint.get('class_names', ['fire', 'normal'])
    num_classes = len(class_names)
    
    # Create model with same architecture
    model = timm.create_model('efficientnet_b0', pretrained=False, num_classes=num_classes)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    print(f"✅ Model loaded successfully!")
    print(f"   Epoch: {checkpoint['epoch']}")
    print(f"   Val Accuracy: {checkpoint['val_acc']:.2f}%")
    print(f"   Classes: {class_names}")
    
    return model, class_names

def predict_image(model, image_path, class_names):
    """Predict on a single image."""
    
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

def main():
    # Load trained model
    model, class_names = load_trained_model()
    
    # Test on image
    image_path = 'fireForrest.jpg'
    print(f"\nTesting on image: {image_path}")
    
    predicted_class, confidence, probs = predict_image(model, image_path, class_names)
    
    print(f"\n{'='*60}")
    print(f"PREDICTION RESULTS (TRAINED MODEL)")
    print(f"{'='*60}")
    print(f"Predicted class: {class_names[predicted_class]}")
    print(f"Confidence: {confidence:.4f} ({confidence*100:.2f}%)")
    print(f"\nClass probabilities:")
    for i, class_name in enumerate(class_names):
        print(f"  {class_name}: {probs[i]:.4f} ({probs[i]*100:.2f}%)")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()

