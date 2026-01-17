#!/usr/bin/env python3
"""
Export trained PyTorch model to TorchScript format for C++ inference.
"""

import torch
import timm
import sys
from pathlib import Path

def export_to_torchscript(checkpoint_path='fire_detection_best.pth', 
                          output_path='fire_detection_scripted.pt'):
    """
    Export PyTorch model to TorchScript format.
    
    Args:
        checkpoint_path: Path to trained model checkpoint
        output_path: Path to save TorchScript model
    """
    print("="*60)
    print("🔄 Exporting PyTorch Model to TorchScript")
    print("="*60)
    
    # Check if checkpoint exists
    if not Path(checkpoint_path).exists():
        print(f"❌ Error: Checkpoint not found at {checkpoint_path}")
        print("Please train the model first using: python model/train_fire_detection.py")
        sys.exit(1)
    
    print(f"\n📂 Loading checkpoint from: {checkpoint_path}")
    
    # Load checkpoint
    try:
        checkpoint = torch.load(checkpoint_path, map_location='cpu')
        num_classes = checkpoint.get('num_classes', 2)
        class_names = checkpoint.get('class_names', ['fire', 'normal'])
        val_acc = checkpoint.get('val_acc', 0)
        
        print(f"   Classes: {class_names}")
        print(f"   Validation accuracy: {val_acc:.2f}%")
        print(f"   Number of classes: {num_classes}")
    except Exception as e:
        print(f"❌ Error loading checkpoint: {e}")
        sys.exit(1)
    
    # Create model architecture
    print(f"\n🤖 Creating EfficientNet-B0 model...")
    try:
        model = timm.create_model('efficientnet_b0', pretrained=False, num_classes=num_classes)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        
        total_params = sum(p.numel() for p in model.parameters())
        print(f"   Total parameters: {total_params:,}")
        print(f"   Model size (FP32): ~{total_params * 4 / (1024**2):.2f} MB")
    except Exception as e:
        print(f"❌ Error creating model: {e}")
        sys.exit(1)
    
    # Create example input
    print(f"\n🔄 Converting to TorchScript...")
    example_input = torch.rand(1, 3, 224, 224)
    
    # Trace the model
    try:
        traced_script_module = torch.jit.trace(model, example_input)
        
        # Verify the traced model
        print("   Verifying traced model...")
        with torch.no_grad():
            original_output = model(example_input)
            traced_output = traced_script_module(example_input)
            
            # Check if outputs match
            if torch.allclose(original_output, traced_output, rtol=1e-3):
                print("   ✅ Model trace verification passed")
            else:
                print("   ⚠️  Warning: Model outputs differ slightly (may be acceptable)")
    except Exception as e:
        print(f"❌ Error tracing model: {e}")
        sys.exit(1)
    
    # Save the model
    print(f"\n💾 Saving TorchScript model to: {output_path}")
    try:
        traced_script_module.save(output_path)
        
        # Check file size
        file_size = Path(output_path).stat().st_size / (1024**2)
        print(f"   File size: {file_size:.2f} MB")
    except Exception as e:
        print(f"❌ Error saving model: {e}")
        sys.exit(1)
    
    # Test loading the saved model
    print(f"\n🧪 Testing saved model...")
    try:
        loaded_model = torch.jit.load(output_path)
        loaded_model.eval()
        
        with torch.no_grad():
            test_output = loaded_model(example_input)
            probabilities = torch.softmax(test_output, dim=1)
            predicted_class = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0][predicted_class].item()
            
            print(f"   Test inference successful!")
            print(f"   Predicted class: {class_names[predicted_class]}")
            print(f"   Confidence: {confidence*100:.1f}%")
    except Exception as e:
        print(f"❌ Error loading saved model: {e}")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("✅ Export completed successfully!")
    print("="*60)
    print(f"\n📝 Next steps:")
    print(f"   1. Build the C++ application:")
    print(f"      cd app/build")
    print(f"      cmake ..")
    print(f"      make")
    print(f"\n   2. Run fire detection:")
    print(f"      ./fire_detector --video <video_file> --model ../{output_path}")
    print()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Export PyTorch model to TorchScript')
    parser.add_argument('--checkpoint', type=str, default='fire_detection_best.pth',
                       help='Path to trained model checkpoint')
    parser.add_argument('--output', type=str, default='fire_detection_scripted.pt',
                       help='Path to save TorchScript model')
    
    args = parser.parse_args()
    
    export_to_torchscript(args.checkpoint, args.output)

