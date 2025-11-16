from __future__ import annotations

from flask import Flask, jsonify, request

from aozora import AozoraProcessingError, fetch_clean_text

app = Flask(__name__)


@app.post("/api/convert")
def convert():
    payload = request.get_json(silent=True) or {}
    zip_url = (payload.get("url") or request.form.get("url") or "").strip()
    if not zip_url:
        return jsonify({"error": "ZIPファイルのURLを入力してください。"}), 400

    try:
        text = fetch_clean_text(zip_url)
    except AozoraProcessingError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return jsonify({"error": "予期しないエラーが発生しました。URLをご確認ください。"}), 500

    return jsonify({"text": text})


if __name__ == "__main__":  # local debug
    app.run(debug=True)
