try:
    import docx
    print("python-docx is available")
except ImportError:
    print("python-docx not available, need to install")
    import subprocess
    subprocess.run(["python", "-m", "pip", "install", "python-docx", "lxml"])
    print("installed")
