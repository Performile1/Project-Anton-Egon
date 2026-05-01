#!/usr/bin/env python3
"""
Project Anton Egon - Model Download Script
Automatically downloads Llama-3-8B (GGUF) and Whisper-turbo models
"""

import os
import sys
from pathlib import Path
import requests
from tqdm import tqdm


def print_section(title):
    """Print a section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def download_file(url, destination, chunk_size=8192):
    """Download a file with progress bar"""
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(destination, 'wb') as f, tqdm(
        desc=destination.name,
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in response.iter_content(chunk_size=chunk_size):
            size = f.write(chunk)
            bar.update(size)


def download_llama_model():
    """Download Llama-3-8B GGUF model"""
    print_section("LLAMA-3-8B MODEL DOWNLOAD")
    
    models_dir = Path("models")
    if not models_dir.exists():
        models_dir.mkdir(parents=True)
        print(f"✅ Created models directory")
    
    # Llama-3-8B-Instruct GGUF (Q4_K_M - good balance of speed/quality)
    # URL from HuggingFace
    llama_url = "https://huggingface.co/MaziyarPanahi/Llama-3-8B-Instruct-GGUF/resolve/main/Llama-3-8B-Instruct-Q4_K_M.gguf"
    llama_dest = models_dir / "llama-3-8b-instruct-q4_k_m.gguf"
    
    if llama_dest.exists():
        print(f"✅ Llama model already exists: {llama_dest}")
        response = input("Download anyway? (y/n): ").strip().lower()
        if response != 'y':
            return
    
    print(f"Downloading Llama-3-8B-Instruct (Q4_K_M)...")
    print(f"Size: ~4.9 GB")
    print(f"Destination: {llama_dest}\n")
    
    try:
        download_file(llama_url, llama_dest)
        print(f"\n✅ Llama model downloaded successfully")
    except Exception as e:
        print(f"\n❌ Error downloading Llama model: {e}")
        print("\nAlternative: Download manually from:")
        print("https://huggingface.co/MaziyarPanahi/Llama-3-8B-Instruct-GGUF")
        print("Save as: models/llama-3-8b-instruct-q4_k_m.gguf")


def download_whisper_model():
    """Download Whisper-turbo model"""
    print_section("WHISPER-TURBO MODEL DOWNLOAD")
    
    models_dir = Path("models")
    if not models_dir.exists():
        models_dir.mkdir(parents=True)
    
    # Whisper-turbo is downloaded automatically by Whisper library
    # But we can pre-download it
    print("Whisper-turbo is downloaded automatically by Whisper library")
    print("It will be downloaded on first use (~374 MB)")
    print("\nTo pre-download, run:")
    print("  python -c \"import whisper; whisper.load_model('turbo')\"")
    
    response = input("\nPre-download now? (y/n): ").strip().lower()
    if response == 'y':
        try:
            import whisper
            print("\nDownloading Whisper-turbo model...")
            model = whisper.load_model('turbo')
            print(f"✅ Whisper-turbo downloaded successfully")
        except ImportError:
            print("❌ Whisper not installed. Run: pip install openai-whisper")
        except Exception as e:
            print(f"❌ Error downloading Whisper-turbo: {e}")


def update_config_with_model_paths():
    """Update config/settings.json with model paths"""
    print_section("UPDATE CONFIG FILE")
    
    import json
    
    config_path = Path("config/settings.json")
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Update LLM model path
    llama_path = "models/llama-3-8b-instruct-q4_k_m.gguf"
    config["llm"]["model_path"] = llama_path
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Updated config/settings.json with LLM model path")
    print(f"   Model path: {llama_path}")


def main():
    """Main download function"""
    print("\n" + "="*80)
    print("  ANTON EGON - MODEL DOWNLOAD")
    print("="*80)
    print("\nThis script will download the required models for Anton Egon:")
    print("  - Llama-3-8B-Instruct (GGUF) - ~4.9 GB")
    print("  - Whisper-turbo - ~374 MB (auto-downloaded)")
    print("\nTotal download size: ~5.3 GB\n")
    
    input("Press Enter to continue...")
    
    # Download Llama model
    download_llama_model()
    
    # Download Whisper model
    download_whisper_model()
    
    # Update config
    update_config_with_model_paths()
    
    print_section("DOWNLOAD COMPLETE")
    print("""
    ✅ Model download complete!
    
    Next steps:
    1. Verify models exist in models/ directory
    2. Update config/settings.json if needed
    3. Test LLM: python -c \"from llama_cpp import Llama; Llama('models/llama-3-8b-instruct-q4_k_m.gguf')\"
    4. Test Whisper: python -c \"import whisper; whisper.load_model('turbo')\"
    
    Troubleshooting:
    - If download fails, download manually from HuggingFace
    - Ensure you have enough disk space (~10 GB recommended)
    - Check your internet connection
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during download: {e}")
        sys.exit(1)
