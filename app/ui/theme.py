"""全局 QSS 样式与配色规范（对应设计文档 §5.10）。"""

PRIMARY = "#2F6FED"
SUCCESS = "#2E9E5B"
WARNING = "#E6A23C"
DANGER = "#D64545"
BG = "#F5F6FA"
CARD = "#FFFFFF"
BORDER = "#E4E7EF"
TEXT = "#1F2937"
TEXT_MUTED = "#6B7280"

STYLESHEET = f"""
QWidget {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 13px;
    color: {TEXT};
}}
QWidget#central {{ background: {BG}; }}
QLabel#h1 {{ font-size: 24px; font-weight: 700; }}
QLabel#h2 {{ font-size: 16px; font-weight: 600; }}
QLabel#muted {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#warn {{ color: {DANGER}; font-size: 12px; }}
QLabel#stat {{ font-size: 14px; }}
QFrame#card {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
}}
QPushButton#primary {{
    background: {PRIMARY}; color: white; border: none; border-radius: 6px;
    padding: 10px 20px; font-size: 14px; font-weight: 600;
}}
QPushButton#primary:hover {{ background: #2563EB; }}
QPushButton#primary:pressed {{ background: #1D4ED8; }}
QPushButton#primary:disabled {{ background: #A5B4FC; }}
QPushButton#secondary {{
    background: {CARD}; color: {TEXT}; border: 1px solid #D1D5DB; border-radius: 6px;
    padding: 8px 16px;
}}
QPushButton#secondary:hover {{ background: #F3F4F6; }}
QPushButton#danger {{
    background: {DANGER}; color: white; border: none; border-radius: 6px;
    padding: 10px 20px; font-size: 14px; font-weight: 600;
}}
QPushButton#danger:hover {{ background: #C03A3A; }}
QFrame#nav {{ background: {CARD}; border-right: 1px solid {BORDER}; }}
QLabel#logo {{ font-size: 15px; font-weight: 700; padding: 18px 14px; }}
QListWidget#navlist {{
    border: none; background: transparent; outline: none;
    font-size: 14px;
}}
QListWidget#navlist::item {{
    padding: 12px 16px; border-radius: 6px; margin: 2px 10px;
}}
QListWidget#navlist::item:selected {{ background: #EAF1FE; color: {PRIMARY}; }}
QListWidget#navlist::item:hover {{ background: #F3F4F6; }}
QTreeWidget {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
    alternate-background-color: #FAFBFC;
}}
QTreeWidget::item {{ padding: 5px; }}
QTreeWidget::item:hover {{ background: #EAF1FE; }}
QTreeWidget::item:selected {{ background: {PRIMARY}; color: white; }}
QTreeWidget::item:selected:hover {{ background: {PRIMARY}; }}
QListWidget#catlist {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
}}
QListWidget#catlist::item {{ padding: 4px 8px; }}
QProgressBar {{
    border: none; border-radius: 5px; background: #E4E7EF;
    height: 10px; text-align: center;
}}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 5px; }}
QComboBox, QSpinBox {{
    background: {CARD}; border: 1px solid #D1D5DB; border-radius: 6px;
    padding: 6px 10px;
}}
QComboBox:focus, QSpinBox:focus {{ border-color: {PRIMARY}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
}}
QDialog {{ background: {BG}; }}
QDialogButtonBox QPushButton {{
    background: {CARD}; border: 1px solid #D1D5DB; border-radius: 6px;
    padding: 8px 18px;
}}
QDialogButtonBox QPushButton:hover {{ background: #F3F4F6; }}
"""
