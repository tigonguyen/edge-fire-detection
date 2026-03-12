"""
Organize downloaded dataset into train/val splits.
"""

import os
import shutil
import random
from pathlib import Path

def organize_dataset(raw_dir='model/data/raw/fire_dataset', output_dir='model/data/fire_dataset', val_split=0.2):
    """
    Organize raw dataset into train/val structure for 2 classes: fire and normal.
    
    Expected raw structure:
        data/raw/fire_dataset/
            fire_images/
            non_fire_images/
    
    Output structure:
        model/data/fire_dataset/
            train/
                fire/
                normal/
            val/
                fire/
                normal/
    """
    
    raw_path = Path(raw_dir)
    output_path = Path(output_dir)
    
    print(f"Raw data directory: {raw_path}")
    print(f"Output directory: {output_path}")
    
    # Create output directories for 2 classes
    for split in ['train', 'val']:
        for category in ['fire', 'normal']:
            (output_path / split / category).mkdir(parents=True, exist_ok=True)
    
    # Find fire images
    fire_dir = raw_path / 'fire_images'
    if not fire_dir.exists():
        print(f"❌ Fire images directory not found: {fire_dir}")
        return
    
    fire_images = list(fire_dir.glob('*.jpg')) + \
                  list(fire_dir.glob('*.jpeg')) + \
                  list(fire_dir.glob('*.png'))
    
    # Find non-fire images (normal)
    normal_dir = raw_path / 'non_fire_images'
    if not normal_dir.exists():
        print(f"❌ Non-fire images directory not found: {normal_dir}")
        return
    
    normal_images = list(normal_dir.glob('*.jpg')) + \
                    list(normal_dir.glob('*.jpeg')) + \
                    list(normal_dir.glob('*.png'))
    
    print(f"\n✅ Found {len(fire_images)} fire images")
    print(f"✅ Found {len(normal_images)} normal images")
    
    # Shuffle and split
    random.seed(42)
    random.shuffle(fire_images)
    random.shuffle(normal_images)
    
    # Split fire images (80% train, 20% val)
    fire_split = int(len(fire_images) * (1 - val_split))
    fire_train = fire_images[:fire_split]
    fire_val = fire_images[fire_split:]
    
    # Split normal images (80% train, 20% val)
    normal_split = int(len(normal_images) * (1 - val_split))
    normal_train = normal_images[:normal_split]
    normal_val = normal_images[normal_split:]
    
    # Copy files
    print("\n📦 Organizing dataset...")
    
    print("  Copying fire training images...")
    for img in fire_train:
        shutil.copy(img, output_path / 'train' / 'fire' / img.name)
    
    print("  Copying fire validation images...")
    for img in fire_val:
        shutil.copy(img, output_path / 'val' / 'fire' / img.name)
    
    print("  Copying normal training images...")
    for img in normal_train:
        shutil.copy(img, output_path / 'train' / 'normal' / img.name)
    
    print("  Copying normal validation images...")
    for img in normal_val:
        shutil.copy(img, output_path / 'val' / 'normal' / img.name)
    
    print("\n" + "="*60)
    print("✅ Dataset organized successfully!")
    print("="*60)
    print(f"\nTrain set:")
    print(f"  🔥 Fire:   {len(fire_train)} images")
    print(f"  ✅ Normal: {len(normal_train)} images")
    print(f"  Total:    {len(fire_train) + len(normal_train)} images")
    
    print(f"\nValidation set:")
    print(f"  🔥 Fire:   {len(fire_val)} images")
    print(f"  ✅ Normal: {len(normal_val)} images")
    print(f"  Total:    {len(fire_val) + len(normal_val)} images")
    
    print(f"\nDataset location: {output_path.absolute()}")
    print("\n🚀 Next step: python model/train_fire_detection.py")

if __name__ == '__main__':
    organize_dataset()
