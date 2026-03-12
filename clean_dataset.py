import os
from PIL import Image

def clean_images(directory):
    bad_files = []
    print(f"Scanning {directory} for corrupted images...")
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                filepath = os.path.join(root, file)
                try:
                    with Image.open(filepath) as img:
                        img.verify()  # verify that it is, in fact an image
                except (IOError, SyntaxError) as e:
                    bad_files.append(filepath)
                    print(f"Bad file identified: {filepath} - {e}")
    
    for bad_file in bad_files:
        print(f"Removing corrupted image: {bad_file}")
        os.remove(bad_file)
    print(f"Finished scanning. Removed {len(bad_files)} bad files.")

if __name__ == "__main__":
    clean_images("model/data/fire_dataset")
