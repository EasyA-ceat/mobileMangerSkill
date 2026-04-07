"""
静态安全分析测试 - 检查代码中的安全问题
包含：命令注入、硬编码凭证、SQL注入等
"""
import os
import sys
import re
import ast
from pathlib import Path
from typing import List, Dict, Tuple

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


class StaticSecurityAnalyzer:
    """静态安全分析器"""
    
    def __init__(self):
        self.issues = []
        self.source_files = self._find_python_files()
    
    def _find_python_files(self) -> List[Path]:
        """查找所有Python源文件"""
        py_files = []
        for root, _, files in os.walk(PROJECT_ROOT):
            for file in files:
                if file.endswith(".py") and "venv" not in root and "__pycache__" not in root:
                    py_files.append(Path(root) / file)
        return py_files
    
    def _add_issue(self, file_path: Path, line_num: int, issue_type: str, description: str):
        """添加问题记录"""
        self.issues.append({
            "file": str(file_path.relative_to(PROJECT_ROOT)),
            "line": line_num,
            "type": issue_type,
            "description": description
        })
    
    def analyze_command_injection(self):
        """分析命令注入漏洞"""
        # 检查subprocess调用的模式
        subprocess_patterns = [
            (r"subprocess\.run\s*\(\s*[\"'].*[\"']\s*,\s*shell\s*=\s*True", "subprocess.run with shell=True and string command"),
            (r"subprocess\.call\s*\(\s*[\"'].*[\"']\s*,\s*shell\s*=\s*True", "subprocess.call with shell=True and string command"),
            (r"subprocess\.check_output\s*\(\s*[\"'].*[\"']\s*,\s*shell\s*=\s*True", "subprocess.check_output with shell=True and string command"),
            (r"os\.system\s*\(", "os.system() call - high risk"),
            (r"os\.popen\s*\(", "os.popen() call - high risk"),
        ]
        
        for file_path in self.source_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    for pattern, desc in subprocess_patterns:
                        if re.search(pattern, line):
                            self._add_issue(file_path, line_num, "COMMAND_INJECTION", desc)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    
    def analyze_hardcoded_credentials(self):
        """分析硬编码凭证"""
        credential_patterns = [
            (r"password\s*=\s*[\"'].*[\"']", "Hardcoded password"),
            (r"api_key\s*=\s*[\"'].*[\"']", "Hardcoded API key"),
            (r"secret\s*=\s*[\"'].*[\"']", "Hardcoded secret"),
            (r"token\s*=\s*[\"'].*[\"']", "Hardcoded token"),
        ]
        
        for file_path in self.source_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    for pattern, desc in credential_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            # 检查是否是示例或注释
                            if "#" in line and "example" in line.lower():
                                continue
                            self._add_issue(file_path, line_num, "HARDCODED_CREDENTIAL", desc)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    
    def analyze_sql_injection(self):
        """分析SQL注入漏洞"""
        sql_patterns = [
            (r"execute\s*\(\s*f[\"'].*[\"']\s*\)", "f-string in SQL execute"),
            (r"execute\s*\(\s*\"[^\"]*%s[^\"]*\"\s*%\s*", "String formatting in SQL"),
            (r"execute\s*\(\s*'[^']*%s[^']*'\s*%\s*", "String formatting in SQL"),
            (r"execute\s*\(\s*\"[^\"]*\{.*\}[^\"]*\"\s*\.format", "format() in SQL"),
        ]
        
        for file_path in self.source_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    for pattern, desc in sql_patterns:
                        if re.search(pattern, line):
                            self._add_issue(file_path, line_num, "SQL_INJECTION", desc)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    
    def analyze_input_validation(self):
        """分析输入验证"""
        # 检查是否使用了Pydantic模型
        uses_pydantic = False
        for file_path in self.source_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "pydantic" in content and "BaseModel" in content:
                        uses_pydantic = True
                        break
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        if not uses_pydantic:
            self._add_issue(Path("main.py"), 1, "INPUT_VALIDATION", "No Pydantic models found for input validation")
    
    def analyze_security_headers(self):
        """分析安全HTTP头"""
        found_headers = {
            "X-Content-Type-Options": False,
            "X-Frame-Options": False,
            "X-XSS-Protection": False
        }
        
        main_py = Path(PROJECT_ROOT) / "main.py"
        if main_py.exists():
            try:
                with open(main_py, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "X-Content-Type-Options" in content:
                        found_headers["X-Content-Type-Options"] = True
                    if "X-Frame-Options" in content:
                        found_headers["X-Frame-Options"] = True
                    if "X-XSS-Protection" in content:
                        found_headers["X-XSS-Protection"] = True
            except Exception as e:
                print(f"Error reading main.py: {e}")
        
        for header, found in found_headers.items():
            if not found:
                self._add_issue(main_py, 1, "SECURITY_HEADER", f"Missing security header: {header}")
    
    def analyze_cors_config(self):
        """分析CORS配置"""
        main_py = Path(PROJECT_ROOT) / "main.py"
        if main_py.exists():
            try:
                with open(main_py, "r", encoding="utf-8") as f:
                    content = f.read()
                    if 'allow_origins=["*"]' in content:
                        self._add_issue(main_py, 1, "CORS_CONFIG", "CORS allow_origins is set to '*' - too permissive")
            except Exception as e:
                print(f"Error reading main.py: {e}")
    
    def analyze_rate_limiting(self):
        """分析速率限制"""
        found_rate_limit = False
        main_py = Path(PROJECT_ROOT) / "main.py"
        if main_py.exists():
            try:
                with open(main_py, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "slowapi" in content or "limiter" in content:
                        found_rate_limit = True
            except Exception as e:
                print(f"Error reading main.py: {e}")
        
        if not found_rate_limit:
            self._add_issue(main_py, 1, "RATE_LIMITING", "No rate limiting found")
    
    def analyze_api_authentication(self):
        """分析API认证"""
        found_auth = False
        main_py = Path(PROJECT_ROOT) / "main.py"
        if main_py.exists():
            try:
                with open(main_py, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "APIKeyQuery" in content or "APIKeyHeader" in content or "Depends" in content:
                        found_auth = True
            except Exception as e:
                print(f"Error reading main.py: {e}")
        
        if not found_auth:
            self._add_issue(main_py, 1, "API_AUTHENTICATION", "No API authentication found")
    
    def run_all_analyses(self) -> List[Dict]:
        """运行所有分析"""
        print("Running static security analysis...")
        print(f"Found {len(self.source_files)} Python files")
        
        self.analyze_command_injection()
        print(f"  - Command injection analysis: {len([i for i in self.issues if i['type'] == 'COMMAND_INJECTION'])} issues")
        
        self.analyze_hardcoded_credentials()
        print(f"  - Hardcoded credentials analysis: {len([i for i in self.issues if i['type'] == 'HARDCODED_CREDENTIAL'])} issues")
        
        self.analyze_sql_injection()
        print(f"  - SQL injection analysis: {len([i for i in self.issues if i['type'] == 'SQL_INJECTION'])} issues")
        
        self.analyze_input_validation()
        print(f"  - Input validation analysis: {len([i for i in self.issues if i['type'] == 'INPUT_VALIDATION'])} issues")
        
        self.analyze_security_headers()
        print(f"  - Security headers analysis: {len([i for i in self.issues if i['type'] == 'SECURITY_HEADER'])} issues")
        
        self.analyze_cors_config()
        print(f"  - CORS config analysis: {len([i for i in self.issues if i['type'] == 'CORS_CONFIG'])} issues")
        
        self.analyze_rate_limiting()
        print(f"  - Rate limiting analysis: {len([i for i in self.issues if i['type'] == 'RATE_LIMITING'])} issues")
        
        self.analyze_api_authentication()
        print(f"  - API authentication analysis: {len([i for i in self.issues if i['type'] == 'API_AUTHENTICATION'])} issues")
        
        print(f"\nTotal issues found: {len(self.issues)}")
        return self.issues


def test_static_security_analysis():
    """静态安全分析测试"""
    print("=" * 60)
    print("静态安全分析测试")
    print("=" * 60)
    
    analyzer = StaticSecurityAnalyzer()
    issues = analyzer.run_all_analyses()
    
    print("\n" + "=" * 60)
    print("详细问题报告")
    print("=" * 60)
    
    if not issues:
        print("✅ 未发现安全问题")
        return
    
    # 按问题类型分组
    issues_by_type = {}
    for issue in issues:
        issue_type = issue["type"]
        if issue_type not in issues_by_type:
            issues_by_type[issue_type] = []
        issues_by_type[issue_type].append(issue)
    
    for issue_type, type_issues in issues_by_type.items():
        print(f"\n🔴 {issue_type} ({len(type_issues)}个问题):")
        for issue in type_issues:
            print(f"  - {issue['file']}:{issue['line']} - {issue['description']}")
    
    print("\n" + "=" * 60)
    print(f"总计: {len(issues)} 个安全问题")
    print("=" * 60)
    
    # 返回issues供后续使用
    return issues


if __name__ == "__main__":
    test_static_security_analysis()
