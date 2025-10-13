#!/usr/bin/env python3
"""
Verify the basic structure of the load testing automation setup
"""
import os
import json
from pathlib import Path

def verify_files_exist():
    """Verify that all required files exist"""
    required_files = [
        "main.py",
        "config.py", 
        "api.py",
        "requirements.txt",
        "Dockerfile",
        "README.md",
        "templates/dashboard.html"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files exist")
        return True

def verify_dockerfile():
    """Verify Dockerfile has required components"""
    dockerfile_path = Path("Dockerfile")
    if not dockerfile_path.exists():
        print("❌ Dockerfile not found")
        return False
    
    content = dockerfile_path.read_text()
    required_elements = [
        "FROM python:3.11-slim",
        "WORKDIR /app",
        "COPY requirements.txt",
        "RUN pip install",
        "EXPOSE 8080",
        "CMD [\"uvicorn\", \"main:app\"",
        "HEALTHCHECK"
    ]
    
    missing_elements = []
    for element in required_elements:
        if element not in content:
            missing_elements.append(element)
    
    if missing_elements:
        print(f"❌ Dockerfile missing elements: {missing_elements}")
        return False
    else:
        print("✅ Dockerfile has all required elements")
        return True

def verify_requirements():
    """Verify requirements.txt has necessary dependencies"""
    req_path = Path("requirements.txt")
    if not req_path.exists():
        print("❌ requirements.txt not found")
        return False
    
    content = req_path.read_text()
    required_deps = [
        "fastapi",
        "uvicorn",
        "aiohttp",
        "pydantic",
        "pydantic-settings"
    ]
    
    missing_deps = []
    for dep in required_deps:
        if dep not in content:
            missing_deps.append(dep)
    
    if missing_deps:
        print(f"❌ requirements.txt missing dependencies: {missing_deps}")
        return False
    else:
        print("✅ requirements.txt has all required dependencies")
        return True

def verify_python_syntax():
    """Verify Python files have valid syntax"""
    python_files = ["main.py", "config.py", "api.py"]
    
    for file_path in python_files:
        try:
            with open(file_path, 'r') as f:
                compile(f.read(), file_path, 'exec')
            print(f"✅ {file_path} has valid syntax")
        except SyntaxError as e:
            print(f"❌ {file_path} has syntax error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error checking {file_path}: {e}")
            return False
    
    return True

def verify_template():
    """Verify HTML template exists and has basic structure"""
    template_path = Path("templates/dashboard.html")
    if not template_path.exists():
        print("❌ Dashboard template not found")
        return False
    
    content = template_path.read_text()
    required_elements = [
        "<!DOCTYPE html>",
        "<title>Load Testing Automation</title>",
        "bootstrap",
        "config-display",
        "/api/config",
        "/api/status"
    ]
    
    missing_elements = []
    for element in required_elements:
        if element not in content:
            missing_elements.append(element)
    
    if missing_elements:
        print(f"❌ Dashboard template missing elements: {missing_elements}")
        return False
    else:
        print("✅ Dashboard template has all required elements")
        return True

def main():
    """Run all verification checks"""
    print("🔍 Verifying Load Testing Automation basic structure...")
    print()
    
    checks = [
        verify_files_exist,
        verify_dockerfile,
        verify_requirements,
        verify_python_syntax,
        verify_template
    ]
    
    all_passed = True
    for check in checks:
        if not check():
            all_passed = False
        print()
    
    if all_passed:
        print("🎉 All verification checks passed!")
        print("The basic structure for Load Testing Automation is ready.")
        return True
    else:
        print("❌ Some verification checks failed.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)