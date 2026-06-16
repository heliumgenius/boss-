"""Edge Cookie 数据库直读脚本——绕过 browser-cookie3 的限制。

支持两种模式：
1. Edge 未运行：直接读取 SQLite 数据库
2. Edge 正在运行：通过 Volume Shadow Copy 读取（需 shadowcopy 包）
   或自动关闭 Edge 后读取

使用方法:
    python -m boss_cli.edge_cookie_extractor
    输出格式: __zp_stoken__=xxx; wt2=xxx; wbg=xxx; zp_at=xxx
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import win32crypt
except ImportError:
    win32crypt = None


EDGE_COOKIE_PATH = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Microsoft" / "Edge" / "User Data" / "Default" / "Network" / "Cookies"
)

TARGET_COOKIES = {"__zp_stoken__", "wt2", "wbg", "zp_at", "bst"}


def _get_edge_pids() -> list[int]:
    pids = []
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq msedge.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.strip('"').split('","')
            if len(parts) >= 2:
                try:
                    pids.append(int(parts[1]))
                except ValueError:
                    pass
    except Exception:
        pass
    return pids


def _kill_edge() -> None:
    logger.warning("Edge 正在运行，Cookie 文件被锁定，尝试自动关闭...")
    pids = _get_edge_pids()
    if not pids:
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/PID"] + [str(p) for p in pids],
            capture_output=True, timeout=5,
        )
        time.sleep(2)
        logger.warning(f"已关闭 Edge (PID: {', '.join(str(p) for p in pids)})")
    except Exception as e:
        logger.error(f"关闭 Edge 失败: {e}")


def _copy_cookie_db(target_path: str) -> bool:
    try:
        shutil.copy2(str(EDGE_COOKIE_PATH), target_path)
        return True
    except PermissionError:
        pass
    try:
        from shadowcopy import copy_file
        copy_file(str(EDGE_COOKIE_PATH), target_path)
        return True
    except ImportError:
        logger.debug("shadowcopy 未安装")
    except Exception as e:
        logger.debug(f"shadowcopy 失败: {e}")
        try:
            shutil.copy2(str(EDGE_COOKIE_PATH) + "-wal", target_path + "-wal")
            shutil.copy2(str(EDGE_COOKIE_PATH) + "-shm", target_path + "-shm")
        except Exception:
            pass
    return False


def _decrypt_value(encrypted_value: bytes) -> str | None:
    if not encrypted_value or encrypted_value == b"":
        return None
    try:
        decrypted, _ = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)
        return decrypted.decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug(f"DPAPI 解密失败: {e}")
        return None


def extract_edge_cookies(kill_edge_if_locked: bool = False) -> dict[str, str]:
    if win32crypt is None:
        raise ImportError("pywin32 未安装。执行: pip install pywin32")

    if not EDGE_COOKIE_PATH.exists():
        raise FileNotFoundError(f"Edge Cookie 文件不存在: {EDGE_COOKIE_PATH}")

    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp_path = tmp.name
    tmp.close()

    copied = _copy_cookie_db(tmp_path)
    if not copied:
        if kill_edge_if_locked:
            _kill_edge()
            try:
                shutil.copy2(str(EDGE_COOKIE_PATH), tmp_path)
            except PermissionError:
                raise RuntimeError(
                    "无法读取 Edge Cookie 数据库。请手动关闭 Edge 后重试。\n"
                    "  命令: taskkill /F /IM msedge.exe"
                )
        else:
            raise RuntimeError(
                "Edge Cookie 文件被锁定（Edge 正在运行）。\n"
                "  方案 A: 关闭 Edge 后重试\n"
                "  方案 B: 使用 kill_edge_if_locked=True\n"
                "  命令: taskkill /F /IM msedge.exe"
            )

    try:
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, encrypted_value, host_key "
            "FROM cookies "
            "WHERE host_key LIKE '%zhipin.com' "
            "   OR host_key LIKE '%.zhipin.com'"
        )

        results: dict[str, str] = {}
        for name, encrypted_value, host_key in cursor.fetchall():
            if name in TARGET_COOKIES:
                value = _decrypt_value(encrypted_value)
                if value:
                    results[name] = value

        conn.close()

        if not results:
            logger.warning(
                "数据库中未找到 BOSS直聘 Cookie。"
                "请先在 Edge 中登录 https://www.zhipin.com"
            )

        return results

    except sqlite3.Error as e:
        raise RuntimeError(f"SQLite 读取失败: {e}") from e
    finally:
        try:
            os.unlink(tmp_path)
        except PermissionError:
            pass
        for ext in ("-wal", "-shm"):
            try:
                os.unlink(tmp_path + ext)
            except (FileNotFoundError, PermissionError):
                pass


def format_as_env_string(cookies: dict[str, str]) -> str:
    parts = []
    for name in ["__zp_stoken__", "wt2", "wbg", "zp_at", "bst"]:
        value = cookies.get(name)
        if value:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    auto_kill = "--auto-kill" in sys.argv

    print(f"[*] Edge Cookie 路径: {EDGE_COOKIE_PATH}")
    print(f"[*] 文件存在: {EDGE_COOKIE_PATH.exists()}")

    if not EDGE_COOKIE_PATH.exists():
        print("[!] Edge Cookie 文件不存在。请先登录 BOSS直聘。")
        return

    if auto_kill:
        edge_pids = _get_edge_pids()
        if edge_pids:
            print(f"[!] Edge 正在运行 (PID: {', '.join(str(p) for p in edge_pids)})")

    try:
        cookies = extract_edge_cookies(kill_edge_if_locked=auto_kill)
    except ImportError:
        print("[!] pywin32 未安装。执行: pip install pywin32")
        return
    except RuntimeError as e:
        print(f"[!] {e}")
        print("\n  自动关闭 Edge 重试:")
        print(f"    {sys.executable} -m boss_cli.edge_cookie_extractor --auto-kill")
        return
    except Exception as e:
        print(f"[!] 错误: {e}")
        return

    if not cookies:
        print("[!] 未找到 BOSS直聘 Cookie。请先在 Edge 中登录:")
        print("    1. 打开 https://www.zhipin.com")
        print("    2. 登录你的账号")
        print("    3. 关闭 Edge")
        print("    4. 重新运行本脚本")
        return

    print(f"\n[✓] 找到 {len(cookies)} 个 Cookie:")

    has_stoken = "__zp_stoken__" in cookies
    for name, value in cookies.items():
        masked = value[:20] + "..." if len(value) > 24 else value
        print(f"    {name}: {masked}")

    if not has_stoken:
        print(
            "\n[!] __zp_stoken__ 未找到（Edge 80+ 使用 AES 加密，DPAPI 无法解密）\n"
            "    但 wt2/wbg/zp_at 三个 Cookie 已足够使用大部分功能。\n"
            "    部分受限接口会提示「环境异常」"
        )

    cookie_str = format_as_env_string(cookies)
    if cookie_str:
        print(f"\n[✓] 复制下面整行到终端执行:\n")
        print(f"    $env:BOSS_COOKIES=\"{cookie_str}\"")
        print(f"    boss login")
        print()

    if "--json" in sys.argv:
        print(json.dumps(cookies, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
