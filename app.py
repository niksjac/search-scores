import sys
import os
import json
import subprocess
import sqlite3
from typing import List
from rapidfuzz import fuzz
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QWidget,
    QLabel,
    QPushButton,
    QSpacerItem,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QRect, QSize
from PyQt5.QtGui import QGuiApplication, QIcon, QPixmap, QFont

# Set the working directory to the directory of this script
script_directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_directory)

DB_FILE = "file_index.db"  # SQLite database file created by indexer.py

def resource_path(relative_path: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

def load_cfg() -> dict:
    """ Load configuration from config.json """
    with open(resource_path('config.json')) as f:
        return json.load(f)

def connect_db(db_file: str) -> sqlite3.Connection:
    """ Connect to the SQLite database """
    return sqlite3.connect(db_file)

import unicodedata

def normalize_text(text: str) -> str:
    """ Normalize text by removing accents and converting to lowercase. """
    return ''.join(
        c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn'
    )

def search_pdfs(query: str, db_conn: sqlite3.Connection, limit: int = 20) -> List[str]:
    """ Search for PDFs with normalized text for better matching with special characters. """
    cursor = db_conn.cursor()
    tokens = query.lower().split()

    # Prepare the SQL query to match each token, with normalization for accents
    sql_query = "SELECT path FROM file_index WHERE " + " AND ".join(["lower(name) LIKE ?" for _ in tokens])
    sql_params = tuple(f"%{token}%" for token in tokens)

    cursor.execute(f"{sql_query} LIMIT ?", (*sql_params, limit))
    return [row[0] for row in cursor.fetchall()]

def fuzzy_token_match(query_tokens: List[str], filename: str) -> int:
    """ Perform fuzzy matching on each token with normalized filenames. """
    filename_lower = normalize_text(filename)
    total_score = 0
    for token in query_tokens:
        token_score = fuzz.partial_ratio(token, filename_lower)
        total_score += token_score
    return total_score // len(query_tokens)  # Average score


def update_list_view(
    search: QLineEdit,
    list_view: QListWidget,
    db_conn: sqlite3.Connection,
    icon_path: str,
) -> None:
    """ Update the list view based on the search query using token-based fuzzy matching. """
    query = search.text().lower()
    list_view.clear()

    if query.strip():
        # Split the query into tokens for matching
        query_tokens = query.split()

        # Search the database for files matching the tokens
        pdfs = search_pdfs(query, db_conn)

        # Perform fuzzy matching on the results
        matches = [(pdf, fuzzy_token_match(query_tokens, os.path.basename(pdf))) for pdf in pdfs]

        # Sort by the fuzzy match score in descending order
        matches = sorted(matches, key=lambda x: x[1], reverse=True)

        # Add results with a score above a certain threshold to the list
        for pdf, score in matches:
            if score > 50:  # Adjust threshold as needed
                item = QListWidgetItem(os.path.basename(pdf))
                item.setIcon(QIcon(icon_path))  # Set the file icon
                item.setData(Qt.UserRole, pdf)
                list_view.addItem(item)

        if list_view.count() > 0:
            list_view.setCurrentRow(0)


def open_pdf(item: QListWidgetItem, viewer: str) -> None:
    """ Open the selected PDF with the specified viewer """
    if viewer.lower() == "firefox":
        subprocess.Popen([viewer, "--new-window", "--kiosk", item.data(Qt.UserRole)])
    else:
        subprocess.Popen([viewer, item.data(Qt.UserRole)])

def handle_key_event(event: QGuiApplication, list_view: QListWidget, search: QLineEdit, viewer: str) -> None:
    """ Handle key events for navigation and selection """
    if event.key() in (Qt.Key_Up, Qt.Key_Down):
        if list_view.count() > 0:
            current_row = list_view.currentRow()
            if event.key() == Qt.Key_Up:
                list_view.setCurrentRow(max(current_row - 1, 0))
            elif event.key() == Qt.Key_Down:
                list_view.setCurrentRow(min(current_row + 1, list_view.count() - 1))
    elif event.key() == Qt.Key_Return:
        current_item = list_view.currentItem()
        if current_item:
            open_pdf(current_item, viewer)

def add_keyboard(layout: QVBoxLayout, target_input: QLineEdit) -> None:
    """Add centered on-screen keyboard with offset rows to mimic real keyboard layout."""
    cfg = load_cfg()
    osk_cfg = cfg["gui"]["osk"]

    button_size = osk_cfg["button_size"]
    space_button_size = osk_cfg["space_button_size"]
    backspace_button_size = osk_cfg["backspace_button_size"]
    toggle_case_button_size = osk_cfg["toggle_case_button_size"]
    delete_button_size = osk_cfg["delete_button_size"]
    font_size = osk_cfg["font_size"]
    button_spacing = osk_cfg["button_spacing"]
    row_spacing = osk_cfg["row_spacing"]
    rows = osk_cfg["rows"]

    # Dynamically set row offsets based on the number of rows
    row_offsets = [i * 20 for i in range(len(rows))]  # Adjust 20 as needed for spacing

    is_uppercase = False
    letter_buttons = {}
    toggle_case_button = None  # Placeholder for the Toggle Case button

    osk_widget = QWidget()
    osk_layout = QVBoxLayout()
    osk_layout.setSpacing(row_spacing)
    osk_layout.setContentsMargins(0, 0, 0, 0)

    osk_container_layout = QHBoxLayout()
    osk_container_layout.addStretch()
    osk_container_layout.addLayout(osk_layout)
    osk_container_layout.addStretch()
    osk_widget.setLayout(osk_container_layout)

    def toggle_case():
        nonlocal is_uppercase
        is_uppercase = not is_uppercase
        # Update the text/icon of the toggle case button
        if toggle_case_button:
            toggle_case_button.setText("󰬶" if is_uppercase else "󰬵")
        # Update all letter buttons to the current case
        for key, button in letter_buttons.items():
            button.setText(key.upper() if is_uppercase else key.lower())

    for i, row in enumerate(rows):
        row_layout = QHBoxLayout()
        row_layout.setSpacing(button_spacing)
        row_layout.setContentsMargins(row_offsets[i], 0, 0, 0)  # Set offset for each row

        row_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        for key in row:
            if key == "Space":
                button = QPushButton(" ")
                button.setFixedSize(space_button_size[0], space_button_size[1])
                button.clicked.connect(lambda checked: on_key_press(" ", target_input))
            elif key == "Backspace":
                button = QPushButton("󰭜 ")
                button.setFixedSize(backspace_button_size[0], backspace_button_size[1])
                button.clicked.connect(lambda checked: on_backspace_press(target_input))
            elif key == "Delete":
                button = QPushButton("󰹿 ")
                button.setFixedSize(delete_button_size[0], delete_button_size[1])
                button.clicked.connect(lambda checked: on_delete_press(target_input))
            elif key == "Toggle Case":
                # Create the Toggle Case button with initial text
                button = QPushButton( "󰬶" if is_uppercase else "󰬵")
                button.setFixedSize(toggle_case_button_size[0], toggle_case_button_size[1])
                button.clicked.connect(toggle_case)
                toggle_case_button = button # Store reference to update text/icon later
            elif key == "Left":
                button = QPushButton("←")  # Left arrow symbol
                button.setFixedSize(button_size[0], button_size[1])
                button.clicked.connect(lambda checked: move_cursor_left(target_input))  # Move cursor left
            elif key == "Right":
                button = QPushButton("→")  # Right arrow symbol
                button.setFixedSize(button_size[0], button_size[1])
                button.clicked.connect(lambda checked: move_cursor_right(target_input))  # Move cursor right
            elif key.isdigit():  # For number keys "0" - "9"
                button = QPushButton(key)
                button.setFixedSize(button_size[0], button_size[1])
                button.clicked.connect(lambda checked, char=key: on_key_press(char, target_input))
            else:
                button = QPushButton(key.upper() if is_uppercase else key.lower())
                button.setFixedSize(button_size[0], button_size[1])
                button.clicked.connect(lambda checked, char=key: on_key_press(char.upper() if is_uppercase else char.lower(), target_input))
                letter_buttons[key] = button

            # button.setStyleSheet(f'font-size: {font_size}px;')
            # row_layout.addWidget(button)

            # Apply font size and debug border to each button
            button.setStyleSheet(f'font-size: {font_size}px; border: 1px solid green; border-radius:4px; ')  # Border for each button
            row_layout.addWidget(button)

        row_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        osk_layout.addLayout(row_layout)

    layout.addWidget(osk_widget)

# Helper functions for key actions remain the same
def on_key_press(char: str, target_input: QLineEdit) -> None:
    cursor_position = target_input.cursorPosition()
    current_text = target_input.text()
    new_text = current_text[:cursor_position] + char + current_text[cursor_position:]
    target_input.setText(new_text)
    target_input.setCursorPosition(cursor_position + 1)
    target_input.setFocus()

def on_backspace_press(target_input: QLineEdit) -> None:
    cursor_position = target_input.cursorPosition()
    if cursor_position > 0:
        current_text = target_input.text()
        new_text = current_text[:cursor_position - 1] + current_text[cursor_position:]
        target_input.setText(new_text)
        target_input.setCursorPosition(cursor_position - 1)
    target_input.setFocus()

def on_delete_press(target_input: QLineEdit) -> None:
    """ Deletes the character at the current cursor position in the input field and keeps the focus in the field."""
    cursor_position = target_input.cursorPosition()
    current_text = target_input.text()
    if cursor_position < len(current_text):
        new_text = current_text[:cursor_position] + current_text[cursor_position + 1:]
        target_input.setText(new_text)
        target_input.setCursorPosition(cursor_position) # Keep cursor position
    target_input.setFocus() # Ensure focus stays in input field

def move_cursor_left(target_input: QLineEdit) -> None:
    """Move the cursor one position to the left in the input field."""
    cursor_position = target_input.cursorPosition()
    if cursor_position > 0:
        target_input.setCursorPosition(cursor_position - 1)
    target_input.setFocus()  # Ensure focus stays in input field

def move_cursor_right(target_input: QLineEdit) -> None:
    """Move the cursor one position to the right in the input field."""
    cursor_position = target_input.cursorPosition()
    if cursor_position < len(target_input.text()):
        target_input.setCursorPosition(cursor_position + 1)
    target_input.setFocus()  # Ensure focus stays in input field

def main() -> None:
    """ Main function to run the PDF Search application """
    cfg = load_cfg()
    viewer = cfg["pdf_viewer"]
    gui_cfg = cfg["gui"]

    icon_path = resource_path(gui_cfg["listview_icon_path"])  # Path to the list view icon
    logo_icon_path = resource_path(gui_cfg["logo_icon_path"])  # Path to the logo icon
    logo_title_text = gui_cfg["logo_title_text"]

    background_color = gui_cfg["background_color"]
    text_color = gui_cfg["text_color"]
    search_background_color = gui_cfg["search_background_color"]
    search_text_color = gui_cfg["search_text_color"]
    list_background_color = gui_cfg["list_background_color"]
    list_text_color = gui_cfg["list_text_color"]
    font_family = gui_cfg["font_family"]
    font_size = gui_cfg["font_size"]
    title_font_size = gui_cfg["title_font_size"]
    padding = gui_cfg["padding"]
    spacing = gui_cfg["spacing"]

    app = QApplication(sys.argv)
    app.setApplicationName("PDFSearchApp")
    app.setApplicationDisplayName("PDF Search Application")
    QGuiApplication.setDesktopFileName("pdfsearchapp.desktop")

    win = QMainWindow()
    win.setWindowTitle('PDF Search')
    win.setGeometry(100, 100, 800, 600)
    win.setStyleSheet(f'background-color: {background_color}; color: {text_color};')

    central = QWidget()
    win.setCentralWidget(central)

    layout = QVBoxLayout()
    layout.setContentsMargins(padding, padding, padding, padding)
    layout.setSpacing(spacing)

    logo_label = QLabel()
    original_pixmap = QPixmap(logo_icon_path).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    height = original_pixmap.height()
    crop_rect = QRect(0, int(height * 0.2), original_pixmap.width(), int(height * 0.6))  # Crop 10% from top and bottom
    cropped_pixmap = original_pixmap.copy(crop_rect)
    logo_label.setPixmap(cropped_pixmap)
    logo_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(logo_label)

    # title_label = QLabel(logo_title_text)
    title_label = QLabel()
    title_label.setAlignment(Qt.AlignCenter)
    title_label.setStyleSheet(
      f"""
      font-size: {title_font_size}px;
      color: {text_color};
      font-family: {font_family};
      """
    )
    layout.addWidget(title_label)

    search = QLineEdit()
    search.setPlaceholderText('Search PDFs...')
    search.setAlignment(Qt.AlignCenter)  # Center the text in the search field
    search.setStyleSheet(
      f"""
      background-color: {search_background_color};
      color: {search_text_color};
      font-size: {font_size}px;
      font-family: {font_family};
      padding: 10px 10px;
      text-align: center;
      border: none;
      border:1px solid white;
      border-radius:4px;
      """ # Center the placeholder text and remove border
    )

    # Connect to the database
    db_conn = connect_db(DB_FILE)
    search.textChanged.connect(lambda: update_list_view(search, list_view, db_conn, icon_path))
    layout.addWidget(search)

    # Function to open PDF when a list item is double-tapped
    def open_pdf_on_double_tap(item: QListWidgetItem) -> None:
        """ Open the selected PDF file when an item is double-tapped. """
        pdf_path = item.data(Qt.UserRole)  # Assuming the path is stored in UserRole
        viewer = cfg["pdf_viewer"]
        subprocess.Popen([viewer, pdf_path])  # Open the PDF in the specified viewer

    list_view = QListWidget()
    list_view.setIconSize(QSize(24, 24))
    list_view.setStyleSheet(
      f"""
      QListWidget {{
          background-color: {list_background_color};
          color: {list_text_color};
          font-size: {font_size}px;
          font-family: {font_family};
          border: 1px solid white;  /* Explicit border on QListWidget */
          border-radius: 4px;
          padding: 20px;
      }}

      /* Style individual items and set consistent row height */
      QListWidget::item {{
          padding: 0px;  /* Padding within items */
          min-height: 30px;  /* Set the minimum height for rows */
          max-height: 30px;  /* Set the maximum height for rows */
      }}

      /* Vertical scrollbar styling */
      QScrollBar:vertical {{
          width: 15px;
          background: lightgray;
      }}
      QScrollBar::handle:vertical {{
          background: gray;
          min-height: 20px;
      }}
      QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
          background: none;
      }}

      /* Horizontal scrollbar styling */
      QScrollBar:horizontal {{
          height: 15px;
          background: lightgray;
      }}
      QScrollBar::handle:horizontal {{
          background: gray;
          min-width: 20px;
      }}
      QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
          background: none;
      }}
      """
    )

    # Disable vertical and horizontal scroll bars
    # list_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    # list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    # Connect the itemDoubleClicked signal to open the PDF
    list_view.itemDoubleClicked.connect(open_pdf_on_double_tap)
    list_view.setSpacing(2)

    list_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    list_view.setVerticalScrollMode(QListWidget.ScrollPerPixel)
    list_view.setHorizontalScrollMode(QListWidget.ScrollPerPixel)

    list_view.setVerticalScrollMode(QListWidget.ScrollPerPixel)
    list_view.setHorizontalScrollMode(QListWidget.ScrollPerPixel)

    layout.addWidget(list_view)

    # Add the on-screen keyboard
    add_keyboard(layout, search)


    central.setLayout(layout)
    win.show()

    def keyPressEvent(event):
        handle_key_event(event, list_view, search, viewer)

    win.keyPressEvent = keyPressEvent

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
