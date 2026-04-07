#!/usr/bin/env python3
"""
手机控制技能包 - 综合测试脚本
"""
import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestResult:
    """测试结果类"""
    def __init__(self, test_name: str, passed: bool, details: str = ""):
        self.test_name = test_name
        self.passed = passed
        self.details = details
        self.timestamp = time.time()


class TestReport:
    """综合测试报告生成器"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        
    def add_result(self, test_name: str, passed: bool, details: str = ""):
        """添加测试结果"""
        result = TestResult(test_name, passed, details)
        self.results.append(result)
        status = "PASS" if passed else "FAIL"
        logger.info(f"[{status}] {test_name}")
        if details and not passed:
            logger.info(f"  Details: {details}")
    
    def generate_report(self) -> str:
        """生成测试报告"""
        end_time = time.time()
        duration = end_time - self.start_time
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        report = []
        report.append("=" * 80)
        report.append("手机控制技能包 - 综合测试报告")
        report.append("=" * 80)
        report.append(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"测试耗时: {duration:.2f} 秒")
        report.append(f"总计: {total} 个测试")
        report.append(f"通过: {passed} 个")
        report.append(f"失败: {failed} 个")
        report.append(f"通过率: {(passed/total*100):.1f}%" if total > 0 else "通过率: N/A")
        report.append("")
        
        # 分类统计
        report.append("-" * 80)
        report.append("详细结果:")
        report.append("-" * 80)
        
        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            report.append(f"{status} - {result.test_name}")
            if result.details:
                report.append(f"  {result.details}")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)


class CodeQualityAnalyzer:
    """代码质量分析器"""
    
    def __init__(self, report: TestReport):
        self.report = report
        self.project_root = Path(__file__).parent
        
    def analyze_imports(self) -> Tuple[int, List[str]]:
        """分析导入问题"""
        issues = []
        
        # 检查 main.py
        main_file = self.project_root / "main.py"
        if main_file.exists():
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查未使用的导入（根据 flake8 结果）
            unused_imports = [
                'import base64', 'import traceback', 'import asyncio',
                'from fastapi import Response'
            ]
            for imp in unused_imports:
                if imp in content:
                    issues.append(f"main.py: 未使用的导入 '{imp}'")
        
        return len(issues), issues
    
    def analyze_security(self) -> Tuple[int, List[str]]:
        """安全分析"""
        issues = []
        
        # 检查 bandit 报告
        bandit_file = self.project_root / "bandit_report.json"
        if bandit_file.exists():
            with open(bandit_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for issue in data.get('results', []):
                severity = issue['issue_severity']
                filename = issue['filename']
                line = issue['line_number']
                text = issue['issue_text']
                issues.append(f"[{severity}] {filename}:{line} - {text}")
        
        return len(issues), issues
    
    def run_analysis(self):
        """运行代码质量分析"""
        logger.info("开始代码质量分析...")
        
        # 导入分析
        import_count, import_issues = self.analyze_imports()
        if import_issues:
            self.report.add_result(
                "代码质量 - 导入检查", 
                False, 
                f"发现 {import_count} 个导入问题: {'; '.join(import_issues[:3])}"
            )
        else:
            self.report.add_result("代码质量 - 导入检查", True)
        
        # 安全分析
        sec_count, sec_issues = self.analyze_security()
        medium_issues = [i for i in sec_issues if '[MEDIUM]' in i]
        if medium_issues:
            self.report.add_result(
                "代码质量 - 安全检查", 
                False, 
                f"发现 {len(medium_issues)} 个中等以上安全问题: {'; '.join(medium_issues[:3])}"
            )
        else:
            self.report.add_result(
                "代码质量 - 安全检查", 
                True, 
                f"无中等以上安全问题，共 {sec_count} 个低级警告"
            )


class UnitTestRunner:
    """单元测试运行器（不依赖 pytest）"""
    
    def __init__(self, report: TestReport):
        self.report = report
        self.project_root = Path(__file__).parent
    
    def test_device_manager(self):
        """测试设备管理器"""
        try:
            from src.device_manager import (
                DeviceManager, Device, DeviceStatus, DeviceType
            )
            
            # 测试 1: 创建设备管理器
            manager = DeviceManager()
            self.report.add_result("单元测试 - DeviceManager 初始化", True)
            
            # 测试 2: 设备枚举
            devices = manager.list_devices(refresh=False)
            self.report.add_result("单元测试 - DeviceManager 列表设备", True)
            
            # 测试 3: 设备状态枚举
            statuses = list(DeviceStatus)
            assert len(statuses) > 0
            self.report.add_result("单元测试 - DeviceStatus 枚举", True)
            
        except Exception as e:
            self.report.add_result("单元测试 - DeviceManager", False, str(e))
    
    def test_point_parsing(self):
        """测试坐标解析"""
        try:
            from src.adb_client import Point
            
            # 测试有效坐标
            point = Point.from_string("100,200")
            assert point.x == 100
            assert point.y == 200
            self.report.add_result("单元测试 - Point 解析有效坐标", True)
            
            # 测试带空格的坐标
            point2 = Point.from_string("  300 ,  400  ")
            assert point2.x == 300
            assert point2.y == 400
            self.report.add_result("单元测试 - Point 解析带空格坐标", True)
            
        except Exception as e:
            self.report.add_result("单元测试 - Point 解析", False, str(e))
    
    def test_command_parsing(self):
        """测试命令解析"""
        try:
            from src.command_handler import CommandHandler, CommandType
            
            handler = CommandHandler()
            
            # 测试点击命令
            parsed = handler.parse("点击 500,1000")
            assert parsed.command_type == CommandType.CLICK
            self.report.add_result("单元测试 - CommandHandler 解析点击", True)
            
            # 测试滑动命令
            parsed = handler.parse("滑动 100,200 100,800")
            assert parsed.command_type == CommandType.SWIPE
            self.report.add_result("单元测试 - CommandHandler 解析滑动", True)
            
        except Exception as e:
            self.report.add_result("单元测试 - CommandHandler", False, str(e))
    
    def test_database_models(self):
        """测试数据库模型"""
        try:
            from src.database import DeviceRecord, ScriptRecord, OperationLogRecord
            from datetime import datetime
            
            # 测试设备记录
            device = DeviceRecord(
                device_id="test-123",
                device_name="Test Device",
                status="connected",
                last_connect_time=datetime.now()
            )
            assert device.device_id == "test-123"
            self.report.add_result("单元测试 - DeviceRecord 创建", True)
            
            # 测试脚本记录
            script = ScriptRecord(
                script_name="Test Script",
                script_content='[]',
                status="active"
            )
            assert script.script_name == "Test Script"
            self.report.add_result("单元测试 - ScriptRecord 创建", True)
            
        except Exception as e:
            self.report.add_result("单元测试 - 数据库模型", False, str(e))
    
    def run_tests(self):
        """运行所有单元测试"""
        logger.info("开始单元测试...")
        self.test_device_manager()
        self.test_point_parsing()
        self.test_command_parsing()
        self.test_database_models()


class DocumentationChecker:
    """文档检查器"""
    
    def __init__(self, report: TestReport):
        self.report = report
        self.project_root = Path(__file__).parent
    
    def check_required_files(self):
        """检查必需的文件"""
        required_files = [
            "README.md", "requirements.txt", "main.py",
            "manifest.json", "SKILL.md"
        ]
        
        missing = []
        for filename in required_files:
            if not (self.project_root / filename).exists():
                missing.append(filename)
        
        if missing:
            self.report.add_result(
                "文档检查 - 必需文件", 
                False, 
                f"缺少文件: {', '.join(missing)}"
            )
        else:
            self.report.add_result("文档检查 - 必需文件", True)
    
    def check_documentation_content(self):
        """检查文档内容"""
        doc_files = [
            "SKILL.md", "README.md", "接口规范.md",
            "测试计划.md"
        ]
        
        checked = 0
        has_content = 0
        
        for filename in doc_files:
            filepath = self.project_root / filename
            if filepath.exists():
                checked += 1
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if len(content) > 100:
                        has_content += 1
        
        if checked > 0:
            self.report.add_result(
                "文档检查 - 文档完整性", 
                has_content >= 2,
                f"检查了 {checked} 个文档，{has_content} 个有实质内容"
            )
    
    def check_api_docs(self):
        """检查API文档"""
        main_file = self.project_root / "main.py"
        if main_file.exists():
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_fastapi = 'FastAPI' in content
            has_routes = '@app.' in content
            
            if has_fastapi and has_routes:
                self.report.add_result("文档检查 - API结构", True)
            else:
                self.report.add_result(
                    "文档检查 - API结构", 
                    False,
                    "未检测到完整的FastAPI结构"
                )
    
    def run_checks(self):
        """运行文档检查"""
        logger.info("开始文档检查...")
        self.check_required_files()
        self.check_documentation_content()
        self.check_api_docs()


class SecurityValidator:
    """安全功能验证器"""
    
    def __init__(self, report: TestReport):
        self.report = report
        self.project_root = Path(__file__).parent
    
    def check_api_key_auth(self):
        """检查API Key认证"""
        main_file = self.project_root / "main.py"
        if main_file.exists():
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_api_key = 'API_KEY' in content
            has_get_api_key = 'get_api_key' in content
            has_depends = 'Depends(get_api_key)' in content
            
            if has_api_key and has_get_api_key and has_depends:
                self.report.add_result("安全验证 - API Key认证", True)
            else:
                self.report.add_result(
                    "安全验证 - API Key认证", 
                    False,
                    "API Key认证机制不完整"
                )
    
    def check_security_headers(self):
        """检查安全HTTP头"""
        main_file = self.project_root / "main.py"
        if main_file.exists():
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_xcto = 'X-Content-Type-Options' in content
            has_xfo = 'X-Frame-Options' in content
            has_xss = 'X-XSS-Protection' in content
            
            if has_xcto and has_xfo and has_xss:
                self.report.add_result("安全验证 - 安全HTTP头", True)
            else:
                missing = []
                if not has_xcto:
                    missing.append('X-Content-Type-Options')
                if not has_xfo:
                    missing.append('X-Frame-Options')
                if not has_xss:
                    missing.append('X-XSS-Protection')
                self.report.add_result(
                    "安全验证 - 安全HTTP头", 
                    False,
                    f"缺少安全头: {', '.join(missing)}"
                )
    
    def check_rate_limiting(self):
        """检查速率限制"""
        main_file = self.project_root / "main.py"
        if main_file.exists():
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_slowapi = 'slowapi' in content
            has_limiter = 'limiter.limit' in content
            
            if has_slowapi and has_limiter:
                self.report.add_result("安全验证 - 速率限制", True)
            else:
                self.report.add_result(
                    "安全验证 - 速率限制", 
                    False,
                    "速率限制机制不完整"
                )
    
    def check_cors_config(self):
        """检查CORS配置"""
        main_file = self.project_root / "main.py"
        if main_file.exists():
            with open(main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_cors = 'CORSMiddleware' in content
            has_origins = 'ALLOWED_ORIGINS' in content
            
            if has_cors and has_origins:
                self.report.add_result("安全验证 - CORS配置", True)
            else:
                self.report.add_result(
                    "安全验证 - CORS配置", 
                    False,
                    "CORS配置不完整"
                )
    
    def run_validation(self):
        """运行安全验证"""
        logger.info("开始安全功能验证...")
        self.check_api_key_auth()
        self.check_security_headers()
        self.check_rate_limiting()
        self.check_cors_config()


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("手机控制技能包 - 综合测试")
    print("=" * 80 + "\n")
    
    # 创建测试报告
    report = TestReport()
    
    # 1. 代码质量分析
    code_analyzer = CodeQualityAnalyzer(report)
    code_analyzer.run_analysis()
    print()
    
    # 2. 单元测试
    unit_runner = UnitTestRunner(report)
    unit_runner.run_tests()
    print()
    
    # 3. 安全验证
    security_validator = SecurityValidator(report)
    security_validator.run_validation()
    print()
    
    # 4. 文档检查
    doc_checker = DocumentationChecker(report)
    doc_checker.run_checks()
    print()
    
    # 生成并保存报告
    final_report = report.generate_report()
    print(final_report)
    
    # 保存到文件
    report_file = Path(__file__).parent / "comprehensive_test_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(final_report)
    
    print(f"\n报告已保存到: {report_file}")
    
    # 返回退出码
    failed = sum(1 for r in report.results if not r.passed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
