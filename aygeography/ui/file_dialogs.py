from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path


class _OpenFileNameW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", wintypes.LPVOID),
        ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", wintypes.LPVOID),
        ("dwReserved", wintypes.DWORD),
        ("FlagsEx", wintypes.DWORD),
    ]


class WindowsProfileFileDialog:
    """Thin adapter over the native Windows common file dialog API."""

    _EXPLORER = 0x00080000
    _PATH_MUST_EXIST = 0x00000800
    _FILE_MUST_EXIST = 0x00001000
    _OVERWRITE_PROMPT = 0x00000002
    _NO_CHANGE_DIR = 0x00000008
    _BUFFER_SIZE = 32768
    _FILTER = "Профиль AYGeography\0*.ayprofile\0\0"

    @classmethod
    def open(cls, owner: int | None = None) -> Path | None:
        return cls._select(
            title="Импорт профиля",
            owner=owner,
            save=False,
        )

    @classmethod
    def save(cls, owner: int | None = None) -> Path | None:
        return cls._select(
            title="Экспорт профиля",
            owner=owner,
            save=True,
        )

    @classmethod
    def _select(
        cls,
        *,
        title: str,
        owner: int | None,
        save: bool,
    ) -> Path | None:
        if os.name != "nt":
            raise OSError("Диалог профиля поддерживается только в Windows")
        buffer = ctypes.create_unicode_buffer(cls._BUFFER_SIZE)
        dialog = _OpenFileNameW()
        dialog.lStructSize = ctypes.sizeof(_OpenFileNameW)
        dialog.hwndOwner = owner
        dialog.lpstrFilter = cls._FILTER
        dialog.nFilterIndex = 1
        dialog.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
        dialog.nMaxFile = cls._BUFFER_SIZE
        dialog.lpstrTitle = title
        dialog.lpstrDefExt = "ayprofile"
        dialog.Flags = cls._EXPLORER | cls._PATH_MUST_EXIST | cls._NO_CHANGE_DIR
        if save:
            dialog.Flags |= cls._OVERWRITE_PROMPT
            function = ctypes.windll.comdlg32.GetSaveFileNameW
        else:
            dialog.Flags |= cls._FILE_MUST_EXIST
            function = ctypes.windll.comdlg32.GetOpenFileNameW
        if function(ctypes.byref(dialog)):
            return Path(buffer.value)
        error = ctypes.windll.comdlg32.CommDlgExtendedError()
        if error:
            raise OSError(f"Ошибка системного диалога: 0x{error:04X}")
        return None
