from setuptools import setup, find_packages

setup(
    name="readlooong",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "opencv-python-headless==4.7.0.72",
        "onnxruntime==1.14.1",
        "shapely",
        "pyclipper",
        "numpy>=1.21.0",
        "Pillow>=9.0.0"
    ]
) 