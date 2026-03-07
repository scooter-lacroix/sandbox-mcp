"""
Code validation and formatting utility for the sandbox environment.
"""

import ast
import re
import sys
import logging
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class CodeValidator:
    """Validates and formats Python code for safe execution in the sandbox."""
    
    def __init__(self):
        self.common_issues = []
        self.warnings = []
        self.suggestions = []
        
    def validate_and_format(self, code: str) -> Dict[str, Any]:
        """
        Validate and format Python code for execution.
        
        Args:
            code: Raw Python code string
            
        Returns:
            Dictionary with validation results and formatted code
        """
        result = {
            'valid': True,
            'formatted_code': code,
            'issues': [],
            'warnings': [],
            'suggestions': [],
            'auto_fixes': []
        }
        
        # Step 1: Basic syntax validation
        syntax_result = self._validate_syntax(code)
        if not syntax_result['valid']:
            result['valid'] = False
            result['issues'].extend(syntax_result['issues'])
            return result
        
        # Step 2: Apply automatic fixes
        formatted_code = self._apply_auto_fixes(code)
        result['formatted_code'] = formatted_code
        
        # Step 3: Check for common issues
        issues = self._check_common_issues(formatted_code)
        result['issues'].extend(issues)
        
        # Step 4: Generate warnings and suggestions
        warnings = self._generate_warnings(formatted_code)
        result['warnings'].extend(warnings)
        
        suggestions = self._generate_suggestions(formatted_code)
        result['suggestions'].extend(suggestions)
        
        # Step 5: Security and safety checks
        safety_issues = self._check_safety(formatted_code)
        result['issues'].extend(safety_issues)
        
        return result
    
    def _validate_syntax(self, code: str) -> Dict[str, Any]:
        """Check basic Python syntax."""
        try:
            ast.parse(code)
            return {'valid': True, 'issues': []}
        except SyntaxError as e:
            return {
                'valid': False,
                'issues': [f"Syntax error at line {e.lineno}: {e.msg}"]
            }
        except Exception as e:
            return {
                'valid': False,
                'issues': [f"Parse error: {str(e)}"]
            }
    
    def _apply_auto_fixes(self, code: str) -> str:
        """Apply automatic code formatting fixes."""
        fixed_code = code

        # Fix: Remove trailing backslashes from strings (only at end of line)
        # This fixes incomplete escape sequences without breaking legitimate escapes
        fixed_code = re.sub(r'(["\'])\\+\s*$', r'\1', fixed_code, flags=re.MULTILINE)

        # Fix: Convert Windows-style paths to Unix-style in string literals
        fixed_code = re.sub(r'(["\'])[^"\']*\\\\[^"\']*\1', 
                           lambda m: m.group(0).replace('\\\\', '/'), 
                           fixed_code)

        # Fix 5: Ensure proper artifact directory usage
        fixed_code = re.sub(
            r'(["\'])/sandbox/artifacts/',
            r'\1/artifacts/',
            fixed_code
        )

        # Fix 6: Add missing imports for common operations
        fixed_code = self._add_missing_imports(fixed_code)

        return fixed_code
    
    def _add_missing_imports(self, code: str) -> str:
        """Add commonly needed imports if they're missing."""
        imports_to_add = []

        # Check for matplotlib usage
        if any(pattern in code for pattern in ['plt.', 'matplotlib']):
            if 'import matplotlib.pyplot' not in code:
                imports_to_add.append('import matplotlib.pyplot as plt')

        # Check for numpy usage
        if any(pattern in code for pattern in ['np.', 'numpy']):
            if 'import numpy' not in code:
                imports_to_add.append('import numpy as np')

        # Check for pandas usage
        if any(pattern in code for pattern in ['pd.', 'pandas']):
            if 'import pandas' not in code:
                imports_to_add.append('import pandas as pd')

        # Check for os operations
        if any(pattern in code for pattern in ['os.', 'makedirs', 'listdir']):
            if 'import os' not in code:
                imports_to_add.append('import os')

        # Check for Path operations
        if 'Path(' in code:
            if 'from pathlib import Path' not in code:
                imports_to_add.append('from pathlib import Path')

        # Add imports at the beginning
        if imports_to_add:
            import_block = '\n'.join(imports_to_add) + '\n\n'
            return import_block + code

        return code
    
    def _check_common_issues(self, code: str) -> List[str]:
        """Check for common coding issues."""
        issues = []
        
        # Check for hardcoded paths outside artifacts
        if re.search(r'["\'][^"\']*?/(?!artifacts)[^"\']*?["\']', code):
            issues.append("Warning: Hardcoded paths detected. Use '/artifacts/' for file storage.")
        
        # Check for network operations
        network_patterns = ['requests.', 'urllib.', 'socket.', 'http.client']
        if any(pattern in code for pattern in network_patterns):
            issues.append("Error: Network operations are not allowed in the sandbox.")
        
        # Check for file operations outside artifacts
        dangerous_paths = ['/etc/', '/var/', '/usr/', '/sys/', '/proc/']
        for path in dangerous_paths:
            if path in code:
                issues.append(f"Error: Access to {path} is not allowed.")
        
        # Check for shell command execution
        shell_patterns = ['subprocess.', 'os.system', 'exec(', 'eval(']
        if any(pattern in code for pattern in shell_patterns):
            issues.append("Warning: Shell command execution may be restricted.")
        
        return issues
    
    def _generate_warnings(self, code: str) -> List[str]:
        """Generate warnings for potentially problematic code."""
        warnings = []
        
        # Large data operations
        if any(pattern in code for pattern in ['range(10000', 'range(100000']):
            warnings.append("Large range operations may exceed memory limits.")
        
        # Infinite loops
        if 'while True:' in code:
            warnings.append("Infinite loops may cause execution timeout.")
        
        # Memory-intensive operations
        if any(pattern in code for pattern in ['numpy.zeros((10000', 'numpy.random.randn(10000']):
            warnings.append("Large array operations may exceed memory limits.")
        
        return warnings
    
    def _generate_suggestions(self, code: str) -> List[str]:
        """Generate helpful suggestions for code improvement."""
        suggestions = []
        
        # Suggest using context managers for files
        if 'open(' in code and 'with ' not in code:
            suggestions.append("Consider using 'with' statement for file operations.")
        
        # Suggest error handling
        if 'try:' not in code and any(op in code for op in ['open(', 'json.load', 'requests.']):
            suggestions.append("Consider adding error handling with try/except blocks.")
        
        # Suggest using artifacts directory
        if 'savefig(' in code and '/artifacts/' not in code:
            suggestions.append("Save plots to '/artifacts/plots/' directory for persistent storage.")
        
        # Suggest memory management
        if 'numpy' in code and 'del ' not in code:
            suggestions.append("Consider using 'del' to free memory for large arrays.")
        
        return suggestions
    
    def _check_safety(self, code: str) -> List[str]:
        """Check for security and safety issues."""
        issues = []
        
        # Check for dangerous built-ins
        dangerous_builtins = ['__import__', 'globals()', 'locals()', 'vars()', 'dir()']
        for builtin in dangerous_builtins:
            if builtin in code:
                issues.append(f"Warning: Use of {builtin} may be restricted.")
        
        # Check for file system modifications
        dangerous_ops = ['os.remove', 'os.rmdir', 'shutil.rmtree', 'os.chmod']
        for op in dangerous_ops:
            if op in code:
                issues.append(f"Warning: {op} operations may be restricted.")
        
        return issues
    
    def get_code_template(self, template_type: str) -> str:
        """Get code templates for common tasks."""
        templates = {
            'plot': '''
import matplotlib.pyplot as plt
import numpy as np
import os

# Create artifacts directory
os.makedirs('/artifacts/plots', exist_ok=True)

# Generate sample data
x = np.linspace(0, 10, 100)
y = np.sin(x)

# Create plot
plt.figure(figsize=(10, 6))
plt.plot(x, y, 'b-', linewidth=2)
plt.title('Sample Plot')
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.grid(True)

# Save plot
plt.savefig('/artifacts/plots/sample_plot.png', dpi=300, bbox_inches='tight')
plt.show()
''',
            
            'data_analysis': '''
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# Create artifacts directory
os.makedirs('/artifacts/data', exist_ok=True)

# Generate sample data
data = {
    'x': np.random.randn(1000),
    'y': np.random.randn(1000),
    'category': np.random.choice(['A', 'B', 'C'], 1000)
}

df = pd.DataFrame(data)

# Basic analysis
print("Data shape:", df.shape)
print("\\nData summary:")
print(df.describe())

# Save data
df.to_csv('/artifacts/data/sample_data.csv', index=False)

# Create visualization
plt.figure(figsize=(12, 4))

plt.subplot(1, 2, 1)
plt.scatter(df['x'], df['y'], c=df['category'].astype('category').cat.codes, alpha=0.6)
plt.title('Scatter Plot')
plt.xlabel('X')
plt.ylabel('Y')

plt.subplot(1, 2, 2)
df['category'].value_counts().plot(kind='bar')
plt.title('Category Distribution')
plt.xlabel('Category')
plt.ylabel('Count')

plt.tight_layout()
plt.savefig('/artifacts/plots/data_analysis.png', dpi=300, bbox_inches='tight')
plt.show()
''',
            
            'web_app': '''
from flask import Flask, render_template_string
import os

app = Flask(__name__)

# HTML template
template = """
<!DOCTYPE html>
<html>
<head>
    <title>Sandbox Web App</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { background: #007bff; color: white; padding: 20px; }
        .content { padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Sandbox Web Application</h1>
        </div>
        <div class="content">
            <h2>Welcome to your sandbox web app!</h2>
            <p>This is a sample Flask application running in the sandbox environment.</p>
            <p>Current working directory: {{ cwd }}</p>
            <p>Available artifacts: {{ artifacts }}</p>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    artifacts = []
    if os.path.exists('/artifacts'):
        artifacts = os.listdir('/artifacts')
    
    return render_template_string(
        template,
        cwd=os.getcwd(),
        artifacts=artifacts
    )

if __name__ == '__main__':
    print("🌐 Starting web application...")
    print("📍 Access at: http://127.0.0.1:8000")
    app.run(host='0.0.0.0', port=8000, debug=True)
''',
            
            'manim_animation': '''
from manim import *
import os

# Ensure manim directory exists
os.makedirs('/artifacts/manim', exist_ok=True)

class SampleAnimation(Scene):
    def construct(self):
        # Create title
        title = Text("Manim Animation", font_size=48)
        title.set_color(BLUE)
        title.to_edge(UP)
        
        # Create shapes
        circle = Circle(radius=1.5, color=RED)
        square = Square(side_length=3, color=GREEN)
        triangle = Triangle(color=YELLOW)
        
        # Position shapes
        circle.move_to(LEFT * 3)
        square.move_to(ORIGIN)
        triangle.move_to(RIGHT * 3)
        
        # Animate
        self.play(Write(title))
        self.wait(0.5)
        
        self.play(
            Create(circle),
            Create(square),
            Create(triangle)
        )
        self.wait(1)
        
        # Transform
        self.play(
            circle.animate.set_color(PURPLE),
            square.animate.rotate(PI/4),
            triangle.animate.scale(1.5)
        )
        self.wait(1)
        
        # Final animation
        self.play(
            FadeOut(title),
            circle.animate.move_to(ORIGIN),
            square.animate.move_to(LEFT * 3),
            triangle.animate.move_to(RIGHT * 3)
        )
        self.wait(1)

# Note: To render this animation, run:
# manim -pql your_file.py SampleAnimation
'''
        }
        
        return templates.get(template_type, "Template not found")
    
    def get_available_templates(self) -> List[str]:
        """Get list of available code templates."""
        return ['plot', 'data_analysis', 'web_app', 'manim_animation']


class CodeFormatter:
    """Formats code for better readability and execution."""
    
    @staticmethod
    def format_for_display(code: str) -> str:
        """Format code for display purposes."""
        # Add line numbers
        lines = code.split('\n')
        formatted_lines = []

        for i, line in enumerate(lines, 1):
            formatted_lines.append(f"{i:3d} | {line}")

        return '\n'.join(formatted_lines)
    
    @staticmethod
    def highlight_issues(code: str, issues: List[str]) -> str:
        """Highlight problematic lines in code."""
        # This is a simplified version - in a real implementation,
        # you'd want to use a proper syntax highlighter
        highlighted = code

        for issue in issues:
            if "line" in issue.lower():
                # Extract line number from issue description
                match = re.search(r'line (\d+)', issue)
                if match:
                    line_num = int(match.group(1))
                    # Mark the problematic line
                    highlighted = highlighted.replace(
                        f"# Line {line_num}",
                        f"# Line {line_num} ⚠️ {issue}"
                    )

        return highlighted
    
    @staticmethod
    def create_executable_wrapper(code: str) -> str:
        """Wrap code with proper error handling and artifact setup."""
        wrapper = '''
import os
import sys
import traceback
from datetime import datetime

# Setup artifact directories
artifact_dirs = ['/artifacts', '/artifacts/plots', '/artifacts/data', '/artifacts/images', '/artifacts/videos']
for dir_path in artifact_dirs:
    os.makedirs(dir_path, exist_ok=True)

# Add current directory to path
sys.path.insert(0, '/artifacts')

print(f"🚀 Execution started at {{datetime.now()}}")
print(f"📁 Working directory: {{os.getcwd()}}")
print(f"📂 Artifact directory: /artifacts")
print("-" * 50)

try:
    # User code starts here
{code}

    print("-" * 50)
    print("✅ Execution completed successfully!")

    # List generated artifacts
    if os.path.exists('/artifacts'):
        artifacts = []
        for root, dirs, files in os.walk('/artifacts'):
            for file in files:
                artifacts.append(os.path.join(root, file))

        if artifacts:
            print(f"📁 Generated {{len(artifacts)}} artifacts:")
            for artifact in artifacts[:10]:  # Show first 10
                print(f"  - {{artifact}}")
            if len(artifacts) > 10:
                print(f"  ... and {{len(artifacts) - 10}} more")
        else:
            print("📄 No artifacts generated")

except Exception as e:
    print("-" * 50)
    print("❌ Execution failed!")
    print(f"Error: {{str(e)}}")
    print("\\nTraceback:")
    traceback.print_exc()

    # Save error log
    with open('/artifacts/error_log.txt', 'w') as f:
        f.write(f"Error occurred at {{datetime.now()}}\\n")
        f.write(f"Error: {{str(e)}}\\n")
        f.write(f"Traceback:\\n{{traceback.format_exc()}}")
'''

        # Indent the user code
        indented_code = '\n'.join(f'    {line}' for line in code.split('\n'))
        return wrapper.format(code=indented_code)
