import timm
import torch
from PIL import Image
from torchvision import transforms

print("Starting model loading...")
print("This may take a few minutes on first run (downloading pretrained weights ~21MB)")

# Create EfficientNet-B0 model
# 3 classes: 0=normal, 1=fire, 2=smoke
print("Loading EfficientNet-B0 model...")
model = timm.create_model('efficientnet_b0', pretrained=True, num_classes=3)
model.eval()
print("Model loaded successfully!")

# Load and preprocess the image
print("\nLoading image: fireForrest.jpg")
image = Image.open('fireForrest.jpg').convert('RGB')
print(f"Original image size: {image.size}")

# Preprocessing pipeline
preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Preprocess image
input_tensor = preprocess(image).unsqueeze(0)  # Add batch dimension
print(f"Input tensor shape: {input_tensor.shape}")

# Run inference
print("\nRunning inference...")
with torch.no_grad():
    output = model(input_tensor)

print(f"Output shape: {output.shape}")
print(f"Output logits: {output}")

# Get predictions
probs = torch.softmax(output, dim=1)
predicted_class = torch.argmax(probs, dim=1).item()
confidence = probs[0][predicted_class].item()

class_names = {0: 'normal', 1: 'fire', 2: 'smoke'}
print(f"\n{'='*60}")
print(f"PREDICTION RESULTS:")
print(f"{'='*60}")
print(f"Predicted class: {predicted_class} ({class_names[predicted_class]})")
print(f"Confidence: {confidence:.4f} ({confidence*100:.2f}%)")
print(f"\nClass probabilities:")
print(f"  Normal: {probs[0][0]:.4f} ({probs[0][0]*100:.2f}%)")
print(f"  Fire:   {probs[0][1]:.4f} ({probs[0][1]*100:.2f}%)")
print(f"  Smoke:  {probs[0][2]:.4f} ({probs[0][2]*100:.2f}%)")
print(f"{'='*60}")
