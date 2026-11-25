"""Dark studio theme."""

ACCENT = "#d6404e"
STYLESHEET = f"""
* {{ font-family: "Segoe UI", "Inter", sans-serif; font-size: 10pt; color: #e6e6ea; }}
QMainWindow, QWidget#Root {{ background: #121216; }}
QWidget {{ background: transparent; }}
QFrame#Sidebar {{ background: #0c0c0f; border-right: 1px solid #23232b; }}
QFrame#RightPanel, QFrame#BottomPanel {{ background: #16161b; border: 1px solid #23232b; }}
QFrame#Card {{ background: #1c1c23; border: 1px solid #2a2a34; border-radius: 8px; }}
QLabel#Logo {{ font-size: 15pt; font-weight: 700; color: #ffffff; padding: 14px 12px 4px 12px; }}
QLabel#LogoSub {{ color: #7d7d8c; padding: 0 12px 12px 12px; font-size: 8.5pt; }}
QLabel#H1 {{ font-size: 16pt; font-weight: 600; }}
QLabel#H2 {{ font-size: 11pt; font-weight: 600; color: #f0f0f4; }}
QLabel#Muted {{ color: #8b8b99; }}
QLabel#Badge {{ background: #2a2a34; border-radius: 4px; padding: 2px 6px; color: #b9b9c6; font-size: 8.5pt; }}
QPushButton#NavButton {{ text-align: left; padding: 9px 14px; border: none; border-radius: 6px;
    margin: 1px 8px; color: #b3b3c0; background: transparent; }}
QPushButton#NavButton:hover {{ background: #1b1b22; color: #ffffff; }}
QPushButton#NavButton:checked {{ background: #24141a; color: #ffffff; border-left: 3px solid {ACCENT}; }}
QPushButton {{ background: #262630; border: 1px solid #34343f; border-radius: 6px; padding: 6px 12px; }}
QPushButton:hover {{ background: #30303c; }}
QPushButton:disabled {{ color: #5d5d68; background: #1c1c22; }}
QPushButton#Primary {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: white; font-weight: 600; }}
QPushButton#Primary:hover {{ background: #e3505e; }}
QPushButton#Approve {{ background: #1f7a4a; border: 1px solid #2a9a5f; color: white; font-weight: 600; }}
QPushButton#Reject {{ background: #3a2026; border: 1px solid #6b2a35; color: #ffc9cf; }}
QPushButton#Stop {{ background: #b3121f; border: 2px solid #ff4d5a; color: white; font-weight: 800;
    padding: 8px 18px; letter-spacing: 1px; }}
QPushButton#Stop:hover {{ background: #d4141f; }}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QListWidget {{
    background: #1a1a21; border: 1px solid #2e2e38; border-radius: 6px; padding: 5px;
    selection-background-color: {ACCENT}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {ACCENT}; }}
QComboBox QAbstractItemView {{ background: #1a1a21; }}
QListWidget::item {{ padding: 6px; border-radius: 4px; }}
QListWidget::item:selected {{ background: #2b1a20; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #33333d; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QProgressBar {{ background: #1a1a21; border: 1px solid #2e2e38; border-radius: 4px; height: 10px;
    text-align: center; font-size: 8pt; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QSplitter::handle {{ background: #1d1d24; }}
QFrame#UserBubble {{ background: #24242e; border-radius: 10px; }}
QFrame#AiBubble {{ background: #18181f; border: 1px solid #2a2a34; border-radius: 10px; }}
QFrame#ErrorBubble {{ background: #2a1519; border: 1px solid #6b2a35; border-radius: 10px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #55555f; border-radius: 3px;
    background: #1a1a21; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}
QRadioButton::indicator {{ width: 13px; height: 13px; border: 1px solid #55555f; border-radius: 7px;
    background: #1a1a21; }}
QRadioButton::indicator:checked {{ background: {ACCENT}; border: 3px solid #1a1a21; outline: none; }}
QPushButton#Primary:disabled, QPushButton#Reject:disabled, QPushButton#Approve:disabled {{
    background: #1c1c22; border: 1px solid #2a2a32; color: #5d5d68; }}
QToolTip {{ background: #24242e; color: #eee; border: 1px solid #3a3a46; }}
"""
