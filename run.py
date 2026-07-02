import subprocess
import sys
import os

def install_dependencies():
    print("CWA-Windy: Verifying Python dependencies...")
    req_path = os.path.join("backend", "requirements.txt")
    if not os.path.exists(req_path):
        print(f"Error: {req_path} not found.")
        return False
        
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", req_path
        ])
        print("CWA-Windy: Dependencies verified successfully.\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"CWA-Windy: Warning: Dependency installation failed with code {e.returncode}.")
        return False
    except Exception as e:
        print(f"CWA-Windy: Error: {e}")
        return False

def start_server():
    print("CWA-Windy: Booting FastAPI app...")
    print("--------------------------------------------------")
    print("Web Interface URL:  http://127.0.0.1:8000")
    print("Health Check URL:   http://127.0.0.1:8000/api/health")
    print("API Data URL:       http://127.0.0.1:8000/api/temperature/latest")
    print("--------------------------------------------------")
    print("Press Ctrl+C to shutdown the server.\n")
    
    try:
        import uvicorn
    except ImportError:
        print("CWA-Windy: Uvicorn not found. Installing uvicorn...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn"])
            import uvicorn
        except Exception as e:
            print(f"CWA-Windy: Error installing uvicorn: {e}")
            sys.exit(1)
            
    # Run the uvicorn server
    # We specify host and port matching the config file
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    # Ensure current working directory is the workspace root
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    install_dependencies()
    start_server()
