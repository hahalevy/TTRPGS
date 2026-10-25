"""The rich-text editor behind the Notes pane. Every formatting operation is a
method here (the toolbar and shortcuts only call them), so there is one
implementation of each, and `state()` is the one place the toolbar reads from.
"""
from __future__ import annotations

import uuid

from PySide6.QtCore import QMimeData, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor, QFont, QImage, QKeyEvent, QTextBlock, QTextBlockFormat, QTextCharFormat, QTextCursor,
    QTextFrameFormat, QTextImageFormat, QTextLength, QTextListFormat, QTextTableFormat,
)
from PySide6.QtWidgets import QInputDialog, QMenu, QTextEdit

from ...io.note_document import (
    add_image_resources, encode_image, known_image, note_document, referenced_images, remember_image,
)

LIST = QTextListFormat.Style
LIST_STYLES = {  # nesting level 1, 2, 3 (then repeats)
    "numbered": (LIST.ListDecimal, LIST.ListLowerAlpha, LIST.ListLowerRoman),
    "bullets": (LIST.ListDisc, LIST.ListCircle, LIST.ListSquare),
}
HEADING_SCALE = {0: 1.0, 1: 2.0, 2: 1.5, 3: 1.17, 4: 1.0, 5: 0.83, 6: 0.67}
MAX_STORED_IMAGE_WIDTH = 1600  # larger pictures are shrunk before they are stored
DEFAULT_IMAGE_WIDTH = 480  # initial display width in the note
MAX_LIST_LEVEL = 8
LINK_COLORS = {"note": "#1f7a5c", "web": "#1a5fb4"}
ALIGNMENTS = {
    "left": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute,
    "center": Qt.AlignmentFlag.AlignHCenter,
    "right": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute,
    "justify": Qt.AlignmentFlag.AlignJustify,
}
TABLE_OPS = ("row_above", "row_below", "col_left", "col_right", "delete_row", "delete_col",
             "merge", "split", "delete_table")


def _list_kind(block: QTextBlock) -> str | None:
    text_list = block.textList()
    if text_list is None:
        return None
    return "numbered" if text_list.format().style() in LIST_STYLES["numbered"] else "bullets"


class NoteEditor(QTextEdit):
    linkActivated = Signal(str)  # Ctrl+click on a hyperlink: its href

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(True)
        self.setTabChangesFocus(False)
        self._images: dict[str, str] = {}  # image name -> base64 PNG, for the images in this note
        self.setDocument(note_document(parent=self))

    # --- loading / saving ---
    def load(self, html: str, images: dict) -> None:
        """Shows a note; a fresh document means a fresh undo history."""
        self._images = dict(images)
        old = self.document()
        self.setDocument(note_document(html, images, self))
        old.deleteLater()

    def dump(self) -> tuple[str, dict]:
        """(html, images actually used by that html)."""
        html = self.toHtml()
        return html, {name: self._images[name] for name in referenced_images(html) if name in self._images}

    # --- what the toolbar shows ---
    def state(self) -> dict:
        fmt = self.currentCharFormat()
        block = self.textCursor().block()
        block_format = block.blockFormat()
        return {
            "bold": fmt.fontWeight() > QFont.Weight.Normal, "italic": fmt.fontItalic(),
            "underline": fmt.fontUnderline() and not fmt.isAnchor(), "strike": fmt.fontStrikeOut(),
            "heading": block_format.headingLevel(), "list": _list_kind(block),
            "rtl": block.textDirection() == Qt.LayoutDirection.RightToLeft,
            "link": fmt.anchorHref() if fmt.isAnchor() else "",
        }

    # --- characters ---
    def toggle_char(self, key: str) -> None:
        """Toggles bold / italic / underline / strike for the selection (or what is typed next)."""
        fmt = QTextCharFormat()
        now = self.state()[key]
        if key == "bold":
            fmt.setFontWeight(QFont.Weight.Normal if now else QFont.Weight.Bold)
        elif key == "italic":
            fmt.setFontItalic(not now)
        elif key == "underline":
            fmt.setFontUnderline(not now)
        else:
            fmt.setFontStrikeOut(not now)
        self.mergeCurrentCharFormat(fmt)

    def set_color(self, color: str, background: bool = False) -> None:
        fmt = QTextCharFormat()
        (fmt.setBackground if background else fmt.setForeground)(QColor(color))
        self.mergeCurrentCharFormat(fmt)

    def clear_formatting(self) -> None:
        cursor = self.textCursor()
        cursor.setCharFormat(QTextCharFormat())
        self.setTextCursor(cursor)

    # --- paragraphs ---
    def _blocks(self) -> list[QTextBlock]:
        """The paragraphs touched by the selection (just the current one without a selection)."""
        cursor, document = self.textCursor(), self.document()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        if end > start:
            end -= 1  # a selection ending right at a paragraph start doesn't include that paragraph
        block, last = document.findBlock(start), document.findBlock(end)
        blocks = [block]
        while block != last:
            block = block.next()
            blocks.append(block)
        return blocks

    def _edit_blocks(self, change) -> None:
        """Applies change(block, QTextBlockFormat) -> None to every selected paragraph as one undo step."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block in self._blocks():
            block_cursor = QTextCursor(block)
            fmt = block_cursor.blockFormat()
            change(block, fmt)
            block_cursor.setBlockFormat(fmt)
        cursor.endEditBlock()

    def set_heading(self, level: int) -> None:
        size = self.document().defaultFont().pointSizeF() * HEADING_SCALE[level]
        char_format = QTextCharFormat()
        char_format.setFontPointSize(size)
        char_format.setFontWeight(QFont.Weight.Bold if level else QFont.Weight.Normal)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block in self._blocks():
            block_cursor = QTextCursor(block)
            block_format = block_cursor.blockFormat()
            block_format.setHeadingLevel(level)
            block_cursor.setBlockFormat(block_format)
            block_cursor.setBlockCharFormat(char_format)
            block_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            block_cursor.mergeCharFormat(char_format)
        cursor.endEditBlock()

    def set_direction(self, rtl: bool) -> None:
        """Right-to-left or left-to-right paragraphs; text goes to the leading side like in any editor."""
        direction = Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight

        def change(_block, fmt):
            fmt.setLayoutDirection(direction)
            fmt.setAlignment(Qt.AlignmentFlag.AlignLeading)

        self._edit_blocks(change)

    def set_alignment_name(self, name: str) -> None:
        def change(block, fmt):
            # Qt's HTML can't store "visually left" for a right-to-left paragraph (it reloads right-aligned),
            # so those paragraphs keep their alignment instead of silently changing after a reload.
            if not (name == "left" and block.textDirection() == Qt.LayoutDirection.RightToLeft):
                fmt.setAlignment(ALIGNMENTS[name])

        self._edit_blocks(change)

    # --- lists (numbered 1,2,3 -> a,b,c -> i,ii,iii ; bullets disc -> circle -> square) ---
    def toggle_list(self, kind: str) -> None:
        blocks = self._blocks()
        already = all(_list_kind(b) == kind for b in blocks)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block in blocks:
            if already:
                self._leave_list(block)
            else:
                level = block.textList().format().indent() if block.textList() else 1
                self._join_list(block, kind, level)
        cursor.endEditBlock()

    def change_indent(self, delta: int) -> None:
        """Nests / un-nests list items (restyling them for their new level);
        outside lists it indents the paragraph."""
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block in self._blocks():
            kind = _list_kind(block)
            if kind is None:
                block_cursor = QTextCursor(block)
                fmt = block_cursor.blockFormat()
                fmt.setIndent(max(0, fmt.indent() + delta))
                block_cursor.setBlockFormat(fmt)
                continue
            level = block.textList().format().indent() + delta
            if level < 1:
                self._leave_list(block)
            else:
                self._join_list(block, kind, min(level, MAX_LIST_LEVEL))
        cursor.endEditBlock()

    @staticmethod
    def _leave_list(block: QTextBlock) -> None:
        if block.textList() is not None:
            block.textList().remove(block)
            cursor = QTextCursor(block)
            fmt = cursor.blockFormat()
            fmt.setIndent(0)
            cursor.setBlockFormat(fmt)

    @staticmethod
    def _join_list(block: QTextBlock, kind: str, level: int) -> None:
        """Puts the paragraph into the list of this kind and level directly above it
        (so numbering continues across nested sub-items), or starts a new one."""
        style = LIST_STYLES[kind][(level - 1) % 3]
        previous = block.previous()
        while previous.isValid() and previous.textList() is not None:
            above = previous.textList().format()
            if above.indent() == level and above.style() == style:
                previous.textList().add(block)
                return
            if above.indent() <= level:
                break
            previous = previous.previous()  # skip deeper sub-items
        fmt = QTextListFormat()
        fmt.setStyle(style)
        fmt.setIndent(level)
        QTextCursor(block).createList(fmt)

    # --- links ---
    def _link_range(self) -> tuple[int, int] | None:
        """Start/end of the hyperlink under the cursor (or at the start of the selection),
        joining the differently styled pieces a link may consist of."""
        cursor = self.textCursor()
        position = cursor.selectionStart() + 1 if cursor.hasSelection() else cursor.position()
        block = self.document().findBlock(position)
        pieces = [(block.position() + r.start, block.position() + r.start + r.length, r.format.anchorHref())
                  for r in block.textFormats() if r.format.isAnchor()]
        hit = next((p for p in pieces if p[0] < position <= p[1]), None) or             next((p for p in pieces if p[0] <= position < p[1]), None)
        if hit is None:
            return None
        low, high, href = hit
        grown = True
        while grown:
            grown = False
            for start, end, other in pieces:
                if other == href and end == low and start < low:
                    low, grown = start, True
                if other == href and start == high and end > high:
                    high, grown = end, True
        return low, high

    def _link_cursor(self) -> QTextCursor | None:
        span = self._link_range()
        if span is None:
            return None
        cursor = QTextCursor(self.document())
        cursor.setPosition(span[0])
        cursor.setPosition(span[1], QTextCursor.MoveMode.KeepAnchor)
        return cursor

    def current_link(self) -> tuple[str, str]:
        """(text, href) of the link under the cursor, else (selected text, "")."""
        cursor = self._link_cursor()
        if cursor is None:
            return self.textCursor().selectedText(), ""
        return cursor.selectedText(), cursor.charFormat().anchorHref()

    def set_link(self, text: str, href: str) -> None:
        """Makes the selection (or the link under the cursor) a link to `href`; with
        nothing selected inserts `text` as a link. An empty href removes the link."""
        cursor = self._link_cursor() or self.textCursor()
        fmt = QTextCharFormat()
        if href:
            fmt.setAnchor(True)
            fmt.setAnchorHref(href)
            fmt.setForeground(QColor(LINK_COLORS["note" if href.startswith("note:") else "web"]))
            fmt.setFontUnderline(True)
            if not cursor.hasSelection():
                cursor.insertText(text or href, fmt)
            elif text and cursor.selectedText() != text:
                cursor.insertText(text, fmt)
            else:
                cursor.mergeCharFormat(fmt)
        else:
            fmt.setAnchor(False)
            fmt.setAnchorHref("")
            fmt.clearForeground()
            fmt.setFontUnderline(False)
            cursor.mergeCharFormat(fmt)
        cursor.clearSelection()
        cursor.setCharFormat(QTextCharFormat())  # what is typed next is not part of the link
        self.setTextCursor(cursor)

    def mouseMoveEvent(self, event) -> None:
        href = self.anchorAt(event.position().toPoint())
        self.viewport().setToolTip(f"Ctrl+click to open: {href}" if href and not href.startswith("note:")
                                   else "Ctrl+click to open this note" if href else "")
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        href = self.anchorAt(event.position().toPoint())
        if href and event.button() == Qt.MouseButton.LeftButton and \
                event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.linkActivated.emit(href)
            return
        super().mouseReleaseEvent(event)

    # --- images ---
    def insert_image(self, image: QImage) -> None:
        if image.isNull():
            return
        if image.width() > MAX_STORED_IMAGE_WIDTH:
            image = image.scaledToWidth(MAX_STORED_IMAGE_WIDTH, Qt.TransformationMode.SmoothTransformation)
        name = f"img-{uuid.uuid4().hex[:12]}.png"
        encoded = encode_image(image)
        self._images[name] = encoded
        remember_image(name, encoded)
        self.document().addResource(self.document().ResourceType.ImageResource, QUrl(name), image)
        width = min(image.width(), DEFAULT_IMAGE_WIDTH)
        fmt = QTextImageFormat()
        fmt.setName(name)
        fmt.setWidth(width)
        fmt.setHeight(round(width * image.height() / image.width()))
        self.textCursor().insertImage(fmt)

    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        return source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source: QMimeData) -> None:
        if source.hasImage():
            self.insert_image(QImage(source.imageData()))
            return
        local_images = [QImage(url.toLocalFile()) for url in source.urls() if url.isLocalFile()] if source.hasUrls() else []
        local_images = [i for i in local_images if not i.isNull()]
        if local_images:
            for image in local_images:
                self.insert_image(image)
            return
        if source.hasHtml():  # text copied out of another note may use that note's pictures
            for name in referenced_images(source.html()):
                if not self._images.get(name) and known_image(name):
                    self._images[name] = known_image(name)
            add_image_resources(self.document(), source.html(), self._images)
        super().insertFromMimeData(source)

    def _image_at(self, position: int) -> tuple[QTextImageFormat, QTextCursor] | None:
        for offset in (0, -1):
            cursor = QTextCursor(self.document())
            cursor.setPosition(max(0, position + offset))
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
            if cursor.charFormat().isImageFormat():
                return cursor.charFormat().toImageFormat(), cursor
        return None

    def resize_image_at(self, position: int) -> None:
        found = self._image_at(position)
        if found is None:
            return
        fmt, cursor = found
        width, accepted = QInputDialog.getInt(self, "Image size", "Width in pixels:", int(fmt.width()), 20, 4000)
        if accepted:
            ratio = fmt.height() / fmt.width() if fmt.width() else 1
            fmt.setWidth(width)
            fmt.setHeight(round(width * ratio))
            cursor.setCharFormat(fmt)

    def contextMenuEvent(self, event) -> None:
        menu = self.createStandardContextMenu()
        position = self.cursorForPosition(event.pos()).position()
        if self._image_at(position) is not None:
            menu.addSeparator()
            menu.addAction("Resize image...", lambda: self.resize_image_at(position))
        menu.exec(event.globalPos())

    # --- tables ---
    def insert_table(self, rows: int, columns: int) -> None:
        fmt = QTextTableFormat()
        fmt.setBorder(1)
        fmt.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        fmt.setCellPadding(4)
        fmt.setCellSpacing(0)
        fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        table = self.textCursor().insertTable(rows, columns, fmt)
        self.setTextCursor(table.cellAt(0, 0).firstCursorPosition())

    def table_op(self, name: str) -> None:
        cursor = self.textCursor()
        table = cursor.currentTable()
        if table is None:
            return
        cell = table.cellAt(cursor)
        if name == "row_above":
            table.insertRows(cell.row(), 1)
        elif name == "row_below":
            table.insertRows(cell.row() + 1, 1)
        elif name == "col_left":
            table.insertColumns(cell.column(), 1)
        elif name == "col_right":
            table.insertColumns(cell.column() + 1, 1)
        elif name == "delete_row" and table.rows() > 1:
            table.removeRows(cell.row(), 1)
        elif name == "delete_col" and table.columns() > 1:
            table.removeColumns(cell.column(), 1)
        elif name == "merge":
            table.mergeCells(cursor)
        elif name == "split":
            table.splitCell(cell.row(), cell.column(), 1, 1)
        elif name == "delete_table":
            cursor.setPosition(table.firstPosition() - 1)
            cursor.setPosition(table.lastPosition() + 1, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

    # --- templates ---
    def insert_html(self, html: str) -> None:
        self.textCursor().insertHtml(html)

    # --- keys ---
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Tab / Shift+Tab nest list items and move between table cells."""
        key, cursor = event.key(), self.textCursor()
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            backwards = key == Qt.Key.Key_Backtab
            table = cursor.currentTable()
            if cursor.currentList() is not None:
                self.change_indent(-1 if backwards else 1)
                return
            if table is not None:
                cell = table.cellAt(cursor)
                target_row, target_col = cell.row(), cell.column() + (-1 if backwards else 1)
                if target_col < 0:
                    target_row, target_col = target_row - 1, table.columns() - 1
                elif target_col >= table.columns():
                    target_row, target_col = target_row + 1, 0
                if target_row >= table.rows():
                    table.appendRows(1)
                if target_row >= 0:
                    self.setTextCursor(table.cellAt(target_row, target_col).firstCursorPosition())
                return
        super().keyPressEvent(event)
