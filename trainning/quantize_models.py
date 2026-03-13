import torch
import timm
import os
from onnxruntime.quantization import quantize_dynamic, QuantType

def export_and_quantize(pth_path, model_name_timm, num_classes=2, img_size=224):
    if not os.path.exists(pth_path):
        print(f"❌ Model file not found: {pth_path}")
        return

    print(f"\n{'-'*50}")
    print(f"Processing: {pth_path}")
    print(f"Architecture: {model_name_timm}")
    
    # 1. Load PyTorch Model
    device = torch.device('cpu') # Exporting is safer on CPU
    model = timm.create_model(model_name_timm, pretrained=False, num_classes=num_classes)
    
    checkpoint = torch.load(pth_path, map_location=device, weights_only=False)
    if 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'])
    else:
        model.load_state_dict(checkpoint)
        
    model.eval()
    
    # 2. Export to ONNX (FP32)
    onnx_fp32_path = pth_path.replace('.pth', '_fp32.onnx')
    dummy_input = torch.randn(1, 3, img_size, img_size, device=device)
    
    print(f"📦 Exporting to FP32 ONNX -> {onnx_fp32_path}")
    torch.onnx.export(
        model, 
        dummy_input, 
        onnx_fp32_path,
        export_params=True,
        opset_version=13,
        do_constant_folding=True,
        input_names=['input'],
        output_names=['output'],
        dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
    )
    
    # 3. Quantize to INT8
    onnx_int8_path = pth_path.replace('.pth', '_int8.onnx')
    print(f"🗜️  Quantizing to INT8 ONNX -> {onnx_int8_path}")
    
    quantize_dynamic(
        model_input=onnx_fp32_path,
        model_output=onnx_int8_path,
        weight_type=QuantType.QUInt8
    )
    
    # Compare sizes
    pth_size = os.path.getsize(pth_path) / (1024 * 1024)
    fp32_size = os.path.getsize(onnx_fp32_path) / (1024 * 1024)
    int8_size = os.path.getsize(onnx_int8_path) / (1024 * 1024)
    
    print(f"✅ Success!")
    print(f"📊 Size reduction:")
    print(f"   Original (.pth): {pth_size:.2f} MB")
    print(f"   ONNX FP32:       {fp32_size:.2f} MB")
    print(f"   ONNX INT8:       {int8_size:.2f} MB ({(1 - int8_size/pth_size)*100:.1f}% smaller)")

def main():
    print("🚀 Starting Model Export & Quantization Pipeline")
    
    models_to_process = [
        # (File path, timm architecture name)
        ("trainning/knowledge_distillation/models/fire_detection_b0_best.pth", "efficientnet_b0"),
        ("trainning/knowledge_distillation/models/fire_detection_lite0_best.pth", "efficientnet_lite0"),
        ("trainning/knowledge_distillation/models/student_distilled_best.pth", "efficientnet_lite0")
    ]
    
    for pth_path, arch in models_to_process:
        export_and_quantize(pth_path, arch)

    print(f"\n{'-'*50}")
    print("🎉 All models have been successfully exported and quantized!")

if __name__ == "__main__":
    main()
