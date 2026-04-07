#!/usr/bin/env python3
"""
手机控制CLI工具
通过命令行控制Android设备
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from rich.panel import Panel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.device_manager import get_device_manager, DeviceStatus
from src.adb_client import get_adb_client
from src.screen import get_screen_controller
from src.script_runner import get_script_runner, get_example_script


app = typer.Typer(
    name="mobile-cli",
    help="手机控制CLI工具 - 通过ADB远程控制Android设备",
    no_args_is_help=True
)

console = Console()


def get_default_device():
    """获取默认设备ID"""
    manager = get_device_manager()
    devices = manager.list_devices(refresh=True)
    for device in devices:
        if device.status == DeviceStatus.CONNECTED:
            return device.device_id
    return None


@app.command()
def version():
    """显示版本信息"""
    console.print(Panel.fit(
        "[bold blue]手机控制CLI工具[/bold blue]\n"
        "版本: 0.1.0\n"
        "通过ADB远程控制Android设备",
        title="mobile-cli"
    ))


# ==================== 设备管理命令 ====================

devices_app = typer.Typer(help="设备管理命令")
app.add_typer(devices_app, name="devices")


@devices_app.command("list")
def devices_list(refresh: bool = typer.Option(True, help="是否刷新设备列表")):
    """列出所有设备"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("正在扫描设备...", total=None)
        manager = get_device_manager()
        devices = manager.list_devices(refresh=refresh)
        progress.remove_task(task)

    if not devices:
        console.print("[yellow]未发现设备[/yellow]")
        return

    table = Table(title="设备列表")
    table.add_column("设备ID", style="cyan")
    table.add_column("名称", style="green")
    table.add_column("状态", style="magenta")
    table.add_column("类型", style="yellow")
    table.add_column("型号", style="blue")
    table.add_column("Android版本", style="white")

    for device in devices:
        status_style = {
            DeviceStatus.CONNECTED: "[green]已连接[/green]",
            DeviceStatus.OFFLINE: "[red]离线[/red]",
            DeviceStatus.UNAUTHORIZED: "[yellow]未授权[/yellow]",
            DeviceStatus.DISCONNECTED: "[dim]已断开[/dim]",
        }.get(device.status, f"[gray]{device.status.value}[/gray]")

        table.add_row(
            device.device_id,
            device.name or "-",
            status_style,
            device.type.value,
            device.model or "-",
            device.android_version or "-"
        )

    console.print(table)


@devices_app.command("connect")
def devices_connect(
    device_id: str = typer.Argument(..., help="设备ID (IP:端口 或 序列号)"),
    timeout: int = typer.Option(30, help="连接超时时间(秒)")
):
    """连接设备"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(f"正在连接设备 {device_id}...", total=None)
        manager = get_device_manager()
        success, message = manager.connect_device(device_id, timeout=timeout)
        progress.remove_task(task)

    if success:
        rprint(f"[green]✓ {message}[/green]")
    else:
        rprint(f"[red]✗ {message}[/red]")
        raise typer.Exit(1)


@devices_app.command("disconnect")
def devices_disconnect(
    device_id: str = typer.Argument(..., help="设备ID")
):
    """断开设备"""
    manager = get_device_manager()
    success, message = manager.disconnect_device(device_id)

    if success:
        rprint(f"[green]✓ {message}[/green]")
    else:
        rprint(f"[red]✗ {message}[/red]")
        raise typer.Exit(1)


# ==================== 控制命令 ====================

control_app = typer.Typer(help="设备控制命令")
app.add_typer(control_app, name="control")


@control_app.command("tap")
def control_tap(
    target: str = typer.Argument(..., help="点击目标 (坐标: x,y 或 文字)"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="设备ID")
):
    """点击操作"""
    if not device_id:
        device_id = get_default_device()
        if not device_id:
            rprint("[red]✗ 没有可用的设备，请先连接设备[/red]")
            raise typer.Exit(1)

    manager = get_device_manager()

    if "," in target and all(part.strip().isdigit() for part in target.split(",")):
        client = get_adb_client(manager, device_id)
        parts = target.split(",")
        x, y = int(parts[0]), int(parts[1])
        success = client.click(x, y, device_id)
        msg = f"点击坐标 ({x}, {y})"
    else:
        screen = get_screen_controller(manager)
        success = screen.click_by_text(target, device_id)
        msg = f"点击文字 '{target}'"

    if success:
        rprint(f"[green]✓ {msg} 成功[/green]")
    else:
        rprint(f"[red]✗ {msg} 失败[/red]")
        raise typer.Exit(1)


@control_app.command("swipe")
def control_swipe(
    start: str = typer.Argument(..., help="起始位置 (格式: x,y)"),
    end: str = typer.Argument(..., help="结束位置 (格式: x,y)"),
    duration: int = typer.Option(500, help="滑动时长(毫秒)"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="设备ID")
):
    """滑动操作"""
    if not device_id:
        device_id = get_default_device()
        if not device_id:
            rprint("[red]✗ 没有可用的设备，请先连接设备[/red]")
            raise typer.Exit(1)

    try:
        start_parts = start.split(",")
        end_parts = end.split(",")
        if len(start_parts) != 2 or len(end_parts) != 2:
            raise ValueError("坐标格式错误")

        start_x, start_y = int(start_parts[0]), int(start_parts[1])
        end_x, end_y = int(end_parts[0]), int(end_parts[1])
    except ValueError:
        rprint("[red]✗ 坐标格式错误，应为 'x,y'[/red]")
        raise typer.Exit(1)

    manager = get_device_manager()
    client = get_adb_client(manager, device_id)
    success = client.swipe(start_x, start_y, end_x, end_y, duration, device_id)

    if success:
        rprint(f"[green]✓ 滑动从 ({start_x}, {start_y}) 到 ({end_x}, {end_y}) 成功[/green]")
    else:
        rprint("[red]✗ 滑动失败[/red]")
        raise typer.Exit(1)


@control_app.command("input")
def control_input(
    text: str = typer.Argument(..., help="要输入的文字"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="设备ID")
):
    """输入文字"""
    if not device_id:
        device_id = get_default_device()
        if not device_id:
            rprint("[red]✗ 没有可用的设备，请先连接设备[/red]")
            raise typer.Exit(1)

    manager = get_device_manager()
    client = get_adb_client(manager, device_id)
    success = client.input_text(text, device_id)

    if success:
        rprint(f"[green]✓ 输入文字 '{text}' 成功[/green]")
    else:
        rprint("[red]✗ 输入文字失败[/red]")
        raise typer.Exit(1)


@control_app.command("key")
def control_key(
    key: str = typer.Argument(..., help="按键名称 (home/back/power/volume_up等)"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="设备ID")
):
    """按键操作"""
    if not device_id:
        device_id = get_default_device()
        if not device_id:
            rprint("[red]✗ 没有可用的设备，请先连接设备[/red]")
            raise typer.Exit(1)

    manager = get_device_manager()
    client = get_adb_client(manager, device_id)
    success = client.press_key(key, device_id)

    if success:
        rprint(f"[green]✓ 按键 '{key}' 成功[/green]")
    else:
        rprint(f"[red]✗ 按键 '{key}' 失败[/red]")
        raise typer.Exit(1)


@control_app.command("screenshot")
def control_screenshot(
    save_path: Optional[Path] = typer.Option(None, "--save", "-s", help="保存路径"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="设备ID")
):
    """截图"""
    if not device_id:
        device_id = get_default_device()
        if not device_id:
            rprint("[red]✗ 没有可用的设备，请先连接设备[/red]")
            raise typer.Exit(1)

    manager = get_device_manager()
    screen = get_screen_controller(manager)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("正在截图...", total=None)
        image = screen.screenshot(device_id, str(save_path) if save_path else None)
        progress.remove_task(task)

    if image is not None:
        rprint(f"[green]✓ 截图成功[/green]")
        if save_path:
            rprint(f"  保存到: [blue]{save_path}[/blue]")
        rprint(f"  尺寸: {image.shape[1]}x{image.shape[0]}")
    else:
        rprint("[red]✗ 截图失败[/red]")
        raise typer.Exit(1)


# ==================== 脚本命令 ====================

script_app = typer.Typer(help="脚本管理命令")
app.add_typer(script_app, name="script")


@script_app.command("example")
def script_example():
    """显示示例脚本"""
    example = get_example_script()
    console.print(Panel(example, title="示例脚本", border_style="blue"))


@script_app.command("validate")
def script_validate(
    script_file: Path = typer.Argument(..., help="脚本文件路径 (JSON格式)")
):
    """验证脚本"""
    if not script_file.exists():
        rprint(f"[red]✗ 文件不存在: {script_file}[/red]")
        raise typer.Exit(1)

    with open(script_file, "r", encoding="utf-8") as f:
        script_content = f.read()

    manager = get_device_manager()
    runner = get_script_runner(manager)
    is_valid, message = runner.validate_script(script_content)

    if is_valid:
        rprint(f"[green]✓ {message}[/green]")
    else:
        rprint(f"[red]✗ {message}[/red]")
        raise typer.Exit(1)


@script_app.command("run")
def script_run(
    script_file: Path = typer.Argument(..., help="脚本文件路径"),
    device_id: Optional[str] = typer.Option(None, "--device", "-d", help="设备ID")
):
    """执行脚本"""
    if not script_file.exists():
        rprint(f"[red]✗ 文件不存在: {script_file}[/red]")
        raise typer.Exit(1)

    if not device_id:
        device_id = get_default_device()
        if not device_id:
            rprint("[red]✗ 没有可用的设备，请先连接设备[/red]")
            raise typer.Exit(1)

    with open(script_file, "r", encoding="utf-8") as f:
        script_content = f.read()

    manager = get_device_manager()
    runner = get_script_runner(manager, device_id)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("正在执行脚本...", total=None)
        results = runner.execute_script(script_content, device_id)
        progress.remove_task(task)

    summary = runner.get_execution_summary()

    table = Table(title="执行结果")
    table.add_column("#", style="cyan")
    table.add_column("动作", style="green")
    table.add_column("状态", style="magenta")
    table.add_column("消息", style="white")
    table.add_column("耗时", style="yellow")

    for i, result in enumerate(results, 1):
        status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
        table.add_row(
            str(i),
            result.action_type,
            status,
            result.message,
            f"{result.execution_time:.2f}s"
        )

    console.print(table)

    rprint(f"\n总计: {summary['total_actions']} 个动作, "
           f"[green]成功: {summary['successful']}[/green], "
           f"[red]失败: {summary['failed']}[/red], "
           f"总耗时: {summary['total_execution_time']:.2f}s")

    if summary['failed'] > 0:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
