[build]
base = "python:3.11"
build = ["pip install -r requirements.txt"]

[start]
cmd = "python main.py"
