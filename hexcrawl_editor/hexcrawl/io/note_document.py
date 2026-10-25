"""How a note's stored HTML + images become a QTextDocument. The editor, the
link preview and the exporters all build their documents here, so a note
looks the same everywhere."""
from __future__ import annotations

import base64
import re

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QUrl
from PySide6.QtGui import QImage, QTextDocument

BODY_POINT_SIZE = 11
_IMG_SRC = re.compile(r'<img[^>]*?\bsrc="([^"]+)"')
_known_images: dict[str, str] = {}  # every image name seen this session -> base64 PNG (for paste between notes)


def encode_image(image: QImage) -> str:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return base64.b64encode(bytes(data)).decode("ascii")


def decode_image(encoded: str) -> QImage:
    return QImage.fromData(base64.b64decode(encoded), "PNG")


def referenced_images(html: str) -> set[str]:
    return set(_IMG_SRC.findall(html))


def remember_image(name: str, encoded: str) -> None:
    _known_images[name] = encoded


def known_image(name: str) -> str:
    return _known_images.get(name, "")


def add_image_resources(document: QTextDocument, html: str, images: dict) -> None:
    """Gives `document` every image `html` uses: from the note's own images,
    else from any image seen earlier (text copied from another note)."""
    for name in referenced_images(html):
        encoded = images.get(name) or known_image(name)
        if encoded:
            document.addResource(QTextDocument.ResourceType.ImageResource, QUrl(name), decode_image(encoded))


def note_document(html: str = "", images: dict | None = None, parent=None) -> QTextDocument:
    images = images or {}
    for name, encoded in images.items():
        remember_image(name, encoded)
    document = QTextDocument(parent)
    font = document.defaultFont()
    font.setPointSize(BODY_POINT_SIZE)
    document.setDefaultFont(font)
    option = document.defaultTextOption()
    option.setTextDirection(Qt.LayoutDirection.LayoutDirectionAuto)  # each paragraph follows its first strong character
    document.setDefaultTextOption(option)
    add_image_resources(document, html, images)
    document.setHtml(html)
    return document
