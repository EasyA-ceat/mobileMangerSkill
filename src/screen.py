"""
屏幕交互模块
提供截图、OCR文字识别、图片处理等功能
"""

import io
import os
import re
import base64
import tempfile
import subprocess
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 尝试导入pytesseract，如果不可用则给出警告
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("警告: pytesseract未安装，OCR功能将不可用")

from .device_manager import DeviceManager, Device


@dataclass
class TextMatch:
    """文字匹配结果"""
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0

    @property
    def center(self) -> Tuple[int, int]:
        """获取中心点坐标"""
        return (self.x + self.width // 2, self.y + self.height // 2)


class ScreenController:
    """
    屏幕控制器
    提供截图、OCR、图片处理等功能
    """

    def __init__(
        self,
        device_manager: DeviceManager,
        tesseract_cmd: Optional[str] = None,
        ocr_lang: str = "chi_sim+eng"
    ):
        """
        初始化屏幕控制器

        Args:
            device_manager: 设备管理器实例
            tesseract_cmd: Tesseract可执行文件路径
            ocr_lang: OCR识别语言，默认为中英文
        """
        self.device_manager = device_manager
        self.ocr_lang = ocr_lang

        # 设置Tesseract路径
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        # 检查OCR可用性
        self._ocr_available = self._check_ocr()

    def _check_ocr(self) -> bool:
        """检查OCR是否可用"""
        if not TESSERACT_AVAILABLE:
            return False
        try:
            # 尝试执行一个简单的OCR命令
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    @property
    def ocr_available(self) -> bool:
        """OCR是否可用"""
        return self._ocr_available

    def _get_device_id(self, device_id: Optional[str] = None) -> str:
        """获取设备ID"""
        if device_id:
            return device_id
        devices = self.device_manager.list_devices(refresh=True)
        for device in devices:
            if device.status.value == "connected":
                return device.device_id
        raise ValueError("没有可用的设备")

    def screenshot(
        self,
        device_id: Optional[str] = None,
        save_path: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """
        截取屏幕

        Args:
            device_id: 设备ID
            save_path: 保存路径(可选)

        Returns:
            OpenCV格式的图像(numpy数组)或None
        """
        try:
            device_id = self._get_device_id(device_id)

            # 使用adb exec-out screencap获取截图
            cmd = ["adb", "-s", device_id, "exec-out", "screencap", "-p"]
            result = subprocess.run(cmd, capture_output=True, timeout=30)

            if result.returncode != 0:
                print(f"截图失败: {result.stderr.decode()}")
                return None

            # 转换为OpenCV格式
            image_array = np.frombuffer(result.stdout, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

            if image is None:
                print("无法解码图像")
                return None

            # 保存到文件(如果需要)
            if save_path:
                cv2.imwrite(save_path, image)

            return image

        except Exception as e:
            print(f"截图出错: {e}")
            return None

    def screenshot_to_base64(
        self,
        device_id: Optional[str] = None,
        quality: int = 80
    ) -> Optional[str]:
        """
        截取屏幕并返回Base64编码

        Args:
            device_id: 设备ID
            quality: JPEG质量(1-100)

        Returns:
            Base64编码的图像字符串或None
        """
        image = self.screenshot(device_id)
        if image is None:
            return None

        try:
            # 编码为JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            _, buffer = cv2.imencode(".jpg", image, encode_params)

            # 转换为Base64
            base64_str = base64.b64encode(buffer).decode("utf-8")
            return base64_str

        except Exception as e:
            print(f"转换为Base64失败: {e}")
            return None

    def ocr_text(
        self,
        device_id: Optional[str] = None,
        image: Optional[np.ndarray] = None
    ) -> List[TextMatch]:
        """
        OCR识别文字

        Args:
            device_id: 设备ID(如果不提供image)
            image: OpenCV图像(如果提供则使用此图像，不截图)

        Returns:
            识别到的文字列表
        """
        if not self._ocr_available:
            print("OCR不可用，请安装tesseract")
            return []

        try:
            # 如果没有提供图像，先截图
            if image is None:
                image = self.screenshot(device_id)
                if image is None:
                    return []

            # 转换为PIL图像
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

            # 执行OCR
            data = pytesseract.image_to_data(
                pil_image,
                lang=self.ocr_lang,
                output_type=pytesseract.Output.DICT
            )

            # 解析结果
            results = []
            n_boxes = len(data['text'])
            for i in range(n_boxes):
                text = data['text'][i].strip()
                confidence = int(data['conf'][i])

                if text and confidence > 30:  # 过滤低置信度的结果
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    results.append(TextMatch(
                        text=text,
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                        confidence=confidence
                    ))

            return results

        except Exception as e:
            print(f"OCR识别失败: {e}")
            return []

    def find_text_position(
        self,
        target_text: str,
        device_id: Optional[str] = None,
        image: Optional[np.ndarray] = None,
        partial_match: bool = True
    ) -> Optional[TextMatch]:
        """
        查找指定文字的位置

        Args:
            target_text: 要查找的文字
            device_id: 设备ID
            image: 图像(如果提供则不截图)
            partial_match: 是否允许部分匹配

        Returns:
            TextMatch对象或None
        """
        results = self.ocr_text(device_id, image)

        for match in results:
            if partial_match:
                if target_text.lower() in match.text.lower():
                    return match
            else:
                if target_text.lower() == match.text.lower():
                    return match

        return None

    def click_by_text(
        self,
        text: str,
        device_id: Optional[str] = None,
        partial_match: bool = True
    ) -> bool:
        """
        点击指定文字

        Args:
            text: 要点击的文字
            device_id: 设备ID
            partial_match: 是否允许部分匹配

        Returns:
            是否成功
        """
        match = self.find_text_position(text, device_id, partial_match=partial_match)

        if match is None:
            print(f"未找到文字: {text}")
            return False

        # 点击文字中心
        x, y = match.center
        return self.click(x, y, device_id)

    def draw_text_boxes(
        self,
        image: np.ndarray,
        text_matches: List[TextMatch],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        在图像上绘制文字框

        Args:
            image: 原始图像
            text_matches: 文字匹配结果
            color: 框颜色(BGR)
            thickness: 线宽

        Returns:
            绘制后的图像
        """
        result = image.copy()

        for match in text_matches:
            # 绘制矩形框
            cv2.rectangle(
                result,
                (match.x, match.y),
                (match.x + match.width, match.y + match.height),
                color,
                thickness
            )

            # 绘制文字
            label = f"{match.text} ({match.confidence}%)"
            cv2.putText(
                result,
                label,
                (match.x, match.y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1
            )

        return result

    def preprocess_image(
        self,
        image: np.ndarray,
        grayscale: bool = True,
        denoise: bool = False,
        contrast: float = 1.0
    ) -> np.ndarray:
        """
        图像预处理

        Args:
            image: 原始图像
            grayscale: 是否转换为灰度
            denoise: 是否去噪
            contrast: 对比度增强系数

        Returns:
            处理后的图像
        """
        result = image.copy()

        # 对比度增强
        if contrast != 1.0:
            result = cv2.convertScaleAbs(result, alpha=contrast, beta=0)

        # 去噪
        if denoise:
            result = cv2.fastNlMeansDenoisingColored(result, None, 10, 10, 7, 21)

        # 转换为灰度
        if grayscale and len(result.shape) == 3:
            result = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

        return result


# 便捷函数
def get_screen_controller(
    device_manager: DeviceManager,
    tesseract_cmd: Optional[str] = None,
    ocr_lang: str = "chi_sim+eng"
) -> ScreenController:
    """
    获取屏幕控制器实例

    Args:
        device_manager: 设备管理器实例
        tesseract_cmd: Tesseract可执行文件路径
        ocr_lang: OCR识别语言

    Returns:
        ScreenController实例
    """
    return ScreenController(device_manager, tesseract_cmd, ocr_lang)


if __name__ == "__main__":
    # 简单测试
    from device_manager import get_device_manager
    from adb_client import get_adb_client

    manager = get_device_manager()
    controller = get_screen_controller(manager)

    # 截图测试
    image = controller.screenshot()
    if image is not None:
        print(f"截图成功，尺寸: {image.shape}")

        # OCR测试(如果可用)
        if controller.ocr_available:
            results = controller.ocr_text(image=image)
            print(f"OCR识别到 {len(results)} 个文字区域")
            for match in results[:5]:  # 只显示前5个
                print(f"  - {match.text} @ ({match.x}, {match.y})")
