import os
import glob

src_dir = r"c:\Users\nashf\.gemini\antigravity-ide\scratch\ddi-prediction\src"
for py_file in glob.glob(os.path.join(src_dir, "*.py")):
    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace('→', '->').replace('—', '-')
    
    with open(py_file, 'w', encoding='utf-8') as f:
        f.write(content)
print("Fixed encoding issues.")
