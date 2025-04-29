# setup.py
import subprocess
import sys
import os

def install_requirements():
    """Install the required packages."""
    requirements = [
        'flask',
        'torch',
        'torchvision',
        'transformers',
        'pillow',
        'numpy',
        'scikit-learn',
        'requests',
        'matplotlib',
        'firebase-admin',
        'tabulate',
        'folium'
    ]
    
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + requirements)
    print("All packages installed successfully!")

def create_directories():
    """Create necessary directories."""
    directories = ['sample_images']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")

def main():
    """Main setup function."""
    print("Setting up CivicChain API...")

    # Install requirements
    install_requirements()

    # Create directories
    create_directories()

    print("\nSetup complete! Follow these steps to run the application:")
    print("1. Start the Flask API server:")
    print("   python app.py")
    print("2. In a separate terminal, run the test client:")
    print("   python firebase_test_client.py")

if __name__ == "__main__":
    main()
