import subprocess
import glob
import os

# Procura todas as imagens que começam com 'fly' e terminam com '.png'
image_files = glob.glob("fly*.png")

for image in image_files:
    name, ext = os.path.splitext(image)
    output = f"{name}_trim{ext}"
    
    cmd = [
        "magick", image, 
        "-trim", "+repage", 
        output
    ]
    
    print(f"Processing {image} -> {output}")
    subprocess.run(cmd, check=True)

print("All images processed!")
