"""Exports notes - any selection of them - as PDF, Markdown, HTML or OpenDocument,
or sends them to a printer. All formats start from one combined QTextDocument
(`build_document`), so they show the same content."""
from __future__ import annotations

import base64
import re
from pathlib import Path

from PySide6.QtCore import QMarginsF, Qt
from PySide6.QtGui import (
    QFont, QPageLayout, QPageSize, QPdfWriter, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument,
    QTextDocumentFragment, QTextDocumentWriter,
)

from ..models.notes import NOTE_LINK_PREFIX, Note
from ..models.project import Project
from ..models.targets import target_label
from .note_document import add_image_resources, note_document, referenced_images

FORMATS = {  # key -> (label, file extension)
    "pdf": ("PDF document", ".pdf"),
    "markdown": ("Markdown", ".md"),
    "html": ("HTML page", ".html"),
    "odt": ("OpenDocument text (Word, LibreOffice)", ".odt"),
}
_NOTE_LINK = re.compile(r'<a href="' + NOTE_LINK_PREFIX + r'([^"]*)"[^>]*>(.*?)</a>', re.S)
_MARKDOWN_IMAGE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\))")
_HTML_IMAGE = re.compile(r'(<img[^>]*?\bsrc=")([^"]+)(")')


def anchor_name(note_id: str) -> str:
    return f"note-{note_id}"


def _resolve_note_links(html: str, included: set[str], keep_links: bool) -> str:
    """Links to other notes only work as page anchors in HTML, and only for notes in the
    same export; elsewhere they become plain text."""
    def replace(match: re.Match) -> str:
        if keep_links and match.group(1) in included:
            return f'<a href="#{anchor_name(match.group(1))}">{match.group(2)}</a>'
        return match.group(2)

    return _NOTE_LINK.sub(replace, html)


def build_document(project: Project, notes: list[Note], page_breaks: bool = True,
                   keep_note_links: bool = False) -> QTextDocument:
    """One document: each note's title (a level-1 heading), where it is attached, then its text."""
    document = note_document()
    base_size = document.defaultFont().pointSizeF()
    included = {n.id for n in notes}
    cursor = QTextCursor(document)
    for index, note in enumerate(notes):
        title_block, title_chars = QTextBlockFormat(), QTextCharFormat()
        title_block.setHeadingLevel(1)
        if index and page_breaks:
            title_block.setPageBreakPolicy(QTextBlockFormat.PageBreakFlag.PageBreak_AlwaysBefore)
        title_chars.setFontPointSize(base_size * 2)
        title_chars.setFontWeight(QFont.Weight.Bold)
        title_chars.setAnchor(True)
        title_chars.setAnchorNames([anchor_name(note.id)])
        if index:
            cursor.insertBlock(title_block, title_chars)
        else:
            cursor.setBlockFormat(title_block)
        cursor.insertText(note.title, title_chars)

        where = target_label(project, note.target_id)
        if where:
            italic = QTextCharFormat()
            italic.setFontItalic(True)
            cursor.insertBlock(QTextBlockFormat(), italic)
            cursor.insertText(f"Attached to: {where}", italic)

        body_html = _resolve_note_links(note.html, included, keep_note_links)
        add_image_resources(document, note.html, note.images)
        cursor.insertBlock(QTextBlockFormat(), QTextCharFormat())
        cursor.insertFragment(QTextDocumentFragment(note_document(body_html, note.images)))
        cursor.movePosition(QTextCursor.MoveOperation.End)
    first = notes[0].title if notes else "Notes"
    document.setMetaInformation(QTextDocument.MetaInformation.DocumentTitle, first if len(notes) == 1 else "Hexcrawl notes")
    return document


def _image_files(html: str, notes: list[Note]) -> dict[str, bytes]:
    images = {name: base64.b64decode(enc) for note in notes for name, enc in note.images.items()}
    return {name: images[name] for name in referenced_images(html) if name in images}


def render(document: QTextDocument, notes: list[Note], fmt: str, path: Path) -> None:
    """Writes the document to `path` in the given format ("pdf", "markdown", "html", "odt")."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "pdf":
        writer = QPdfWriter(str(path))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(18, 18, 18, 18), QPageLayout.Unit.Millimeter)
        document.print_(writer)
    elif fmt == "odt":
        QTextDocumentWriter(str(path), b"ODF").write(document)
    elif fmt == "html":
        html = document.toHtml()
        files = _image_files(html, notes)
        html = _HTML_IMAGE.sub(
            lambda m: m.group(1) + (f"data:image/png;base64,{base64.b64encode(files[m.group(2)]).decode()}"
                                    if m.group(2) in files else m.group(2)) + m.group(3), html)
        path.write_text(html, encoding="utf-8")
    elif fmt == "markdown":
        text = document.toMarkdown()
        files = _image_files(document.toHtml(), notes)
        if files:  # pictures go beside the .md file, in a folder named after it
            folder = path.with_name(path.stem + "_files")
            folder.mkdir(exist_ok=True)
            for name, data in files.items():
                (folder / name).write_bytes(data)
            text = _MARKDOWN_IMAGE.sub(
                lambda m: m.group(1) + (f"{folder.name}/{m.group(2)}" if m.group(2) in files else m.group(2)) + m.group(3),
                text)
        path.write_text(text, encoding="utf-8")
    else:
        raise ValueError(f"Unknown export format: {fmt!r}")


def _file_stem(title: str, taken: set[str]) -> str:
    stem = re.sub(r'[\\/:*?"<>|]+', "_", title).strip(" .") or "note"
    unique, number = stem, 2
    while unique.lower() in taken:
        unique, number = f"{stem} ({number})", number + 1
    taken.add(unique.lower())
    return unique


def export_notes(project: Project, notes: list[Note], fmt: str, path: Path, separate_files: bool = False,
                 page_breaks: bool = True) -> list[Path]:
    """Exports to `path` (one combined file), or - with separate_files - one file
    per note inside the folder `path`. Returns the files written."""
    extension = FORMATS[fmt][1]
    keep_links = fmt == "html"
    if not separate_files:
        render(build_document(project, notes, page_breaks, keep_links), notes, fmt, path)
        return [path]
    taken: set[str] = set()
    written = []
    for note in notes:
        target = path / (_file_stem(note.title, taken) + extension)
        render(build_document(project, [note], page_breaks, keep_links), [note], fmt, target)
        written.append(target)
    return written


def print_notes(project: Project, notes: list[Note], printer, page_breaks: bool = True) -> None:
    build_document(project, notes, page_breaks).print_(printer)
