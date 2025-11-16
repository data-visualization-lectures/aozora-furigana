from __future__ import annotations

import glob
import os
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlretrieve


class AozoraProcessingError(RuntimeError):
    """Raised when the requested Aozora resource cannot be processed."""


def fetch_clean_text(zip_url: str) -> str:
    """
    Download the given Aozora Bunko ZIP, extract the first text file,
    and return the cleaned text content.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = _download_zip(zip_url, tmp_dir)
        extracted = _extract_text_path(zip_path, tmp_dir)
        raw_text = Path(extracted).read_bytes().decode("shift_jis")
    return _strip_ruby_and_notes(raw_text)


def _download_zip(zip_url: str, tmp_dir: str) -> str:
    parsed_path = Path(urlparse(zip_url).path or "aozora.zip").name
    destination = os.path.join(tmp_dir, parsed_path)
    try:
        urlretrieve(zip_url, destination)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise AozoraProcessingError("ZIPファイルのダウンロードに失敗しました。") from exc
    return destination


def _extract_text_path(zip_path: str, tmp_dir: str) -> str:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(tmp_dir)
    except zipfile.BadZipFile as exc:
        raise AozoraProcessingError("ZIPファイルを展開できません。") from exc

    text_files = glob.glob(os.path.join(tmp_dir, "*.txt"))
    if not text_files:
        raise AozoraProcessingError("ZIPファイルからテキストが見つかりません。")
    return text_files[0]


def _strip_ruby_and_notes(text: str) -> str:
    sections = re.split(r"\-{5,}", text)
    if len(sections) >= 3:
        text = sections[2]
    text = text.split("底本：", 1)[0]
    text = re.sub(r"《.+?》", "", text)
    text = re.sub(r"［＃.+?］", "", text)
    text = text.replace("\u3000", "")
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
