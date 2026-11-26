"""用户文件名和受控目录的公共安全校验。"""

import os
from collections.abc import Iterable


WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
WINDOWS_INVALID_CHARS = set('<>:"/\\|?*')


def validate_filename(
    filename: str,
    allowed_extensions: Iterable[str] | None = None,
) -> str | None:
    """只接受单个普通文件名，不接受目录、绝对路径或系统保留名称。"""
    if not isinstance(filename, str):
        return None
    if not filename or filename != filename.strip() or len(filename) > 255:
        return None
    if filename in {".", ".."}:
        return None
    if os.path.basename(filename) != filename:
        return None
    if any(ord(character) < 32 for character in filename):
        return None
    if any(character in WINDOWS_INVALID_CHARS for character in filename):
        return None

    base_name = filename.split(".", 1)[0].rstrip(" .").upper()
    if base_name in WINDOWS_RESERVED_NAMES:
        return None

    if allowed_extensions is not None:
        allowed = {
            extension.lower() if extension.startswith(".") else f".{extension.lower()}"
            for extension in allowed_extensions
        }
        if os.path.splitext(filename)[1].lower() not in allowed:
            return None

    return filename


def resolve_file_in_directory(
    directory: str,
    filename: str,
    allowed_extensions: Iterable[str] | None = None,
) -> tuple[str, str] | None:
    """返回安全文件名和绝对路径，并保证真实路径没有离开指定目录。"""
    safe_filename = validate_filename(filename, allowed_extensions)
    if safe_filename is None:
        return None

    safe_directory = os.path.realpath(os.path.abspath(directory))
    candidate = os.path.realpath(
        os.path.abspath(os.path.join(safe_directory, safe_filename))
    )
    try:
        if os.path.commonpath((safe_directory, candidate)) != safe_directory:
            return None
    except ValueError:
        return None

    return safe_filename, candidate
