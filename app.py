from __future__ import annotations

import glob
import io
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlretrieve

from flask import Flask, render_template, request, send_file

app = Flask(__name__)


class AozoraProcessingError(RuntimeError):
    """Raised when the requested Aozora resource cannot be processed."""


def fetch_aozora_text(zip_url: str) -> str:
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
    text = re.sub(r"《.+?》", "", text)  # remove ruby
    text = re.sub(r"［＃.+?］", "", text)  # remove annotations
    text = text.replace("\u3000", "")
    text = text.replace("\r\n", "\n")  # preserve paragraph breaks
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse excessive blank lines
    return text.strip()


@app.route("/", methods=["GET", "POST"])
def index():
    cleaned_text: Optional[str] = None
    error: Optional[str] = None
    submitted_url = ""

    if request.method == "POST":
        action = request.form.get("action", "convert")
        submitted_url = (request.form.get("url") or "").strip()
        if action == "clear":
            submitted_url = ""
            cleaned_text = None
        else:
            if not submitted_url:
                error = "ZIPファイルのURLを入力してください。"
            else:
                try:
                    cleaned_text = fetch_aozora_text(submitted_url)
                except AozoraProcessingError as exc:
                    error = str(exc)
                except Exception:
                    error = "予期しないエラーが発生しました。URLをご確認ください。"

    return render_template(
        "index.html",
        url=submitted_url,
        text=cleaned_text,
        error=error,
    )


@app.post("/download")
def download():
    submitted_url = (request.form.get("url") or "").strip()
    if not submitted_url:
        return (
            render_template(
                "index.html",
                url="",
                text=None,
                error="URLが空です。ダウンロードできません。",
            ),
            400,
        )

    try:
        cleaned_text = fetch_aozora_text(submitted_url)
    except AozoraProcessingError as exc:
        return (
            render_template(
                "index.html",
                url=submitted_url,
                text=None,
                error=str(exc),
            ),
            400,
        )

    buffer = io.BytesIO()
    buffer.write(cleaned_text.encode("utf-8"))
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name="aozora_cleaned.txt",
    )


if __name__ == "__main__":
    app.run(debug=True)
