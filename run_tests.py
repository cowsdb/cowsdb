#!/usr/bin/env python3
"""
CowsDB Test Runner
Simple script to run tests and demos from the project root
"""

import sys
import os
import subprocess

def run_tests():
    """Run the test suite"""
    print("🧪 Running CowsDB Test Suite...")
    result = subprocess.run([sys.executable, "test/test_suite.py"], cwd=os.getcwd())
    return result.returncode == 0

def run_demo():
    """Run the demo"""
    print("🎯 Running CowsDB Demo...")
    result = subprocess.run([sys.executable, "test/demo.py"], cwd=os.getcwd())
    return result.returncode == 0

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python run_tests.py [tests|demo|all]")
        print("  tests - Run the test suite")
        print("  demo  - Run the demo")
        print("  all   - Run both tests and demo")
        return 1
    
    command = sys.argv[1].lower()
    
    if command == "tests":
        success = run_tests()
    elif command == "demo":
        success = run_demo()
    elif command == "all":
        print("🚀 Running all tests and demo...")
        success = run_tests() and run_demo()
    else:
        print(f"Unknown command: {command}")
        return 1
    
    if success:
        print("✅ All operations completed successfully!")
        return 0
    else:
        print("❌ Some operations failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 