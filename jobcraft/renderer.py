"""Render CV and cover letter as HTML (and optionally PDF)."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_cv(docs: dict[str, Any], job: dict[str, Any]) -> str:
    """Render CV HTML from generated document dict."""
    tpl = _env.get_template("cv.html")
    return tpl.render(cv=docs["cv"], job=job)


def render_cover(docs: dict[str, Any], job: dict[str, Any]) -> str:
    """Render cover letter HTML from generated document dict."""
    tpl = _env.get_template("cover.html")
    return tpl.render(
        cv=docs["cv"],
        cover=docs["cover_letter"],
        job=job,
        date=datetime.now().strftime("%d %B %Y"),
    )


def html_to_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Try to convert HTML to PDF using available tools.
    Returns True if successful, False otherwise.
    """
    # Try WeasyPrint first (best quality)
    try:
        import weasyprint  # type: ignore
        weasyprint.HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return True
    except ImportError:
        pass

    # Try wkhtmltopdf
    try:
        result = subprocess.run(
            ["wkhtmltopdf", "--quiet", "--enable-local-file-access",
             str(html_path), str(pdf_path)],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try Chromium/Chrome headless
    for browser in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        try:
            result = subprocess.run(
                [browser, "--headless", "--no-sandbox", "--disable-gpu",
                 f"--print-to-pdf={pdf_path}", str(html_path)],
                capture_output=True, timeout=30,
            )
            if result.returncode == 0 and pdf_path.exists():
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    return False
