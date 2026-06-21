"""主题样式表模块

提供深色和浅色主题的 QSS 样式表。
使用应用级样式 (QApplication.setStyleSheet) 以避免渲染竞态。
"""

DARK_THEME = """
    QMainWindow, QDialog { background-color: #1e1e2e; color: #cdd6f4; }
    QWidget { background-color: #1e1e2e; color: #cdd6f4; }
    QFrame#urlBar { background-color: #313244; border-radius: 8px; border: 1px solid #45475a; }
    QLineEdit { background-color: #45475a; color: #cdd6f4; border: 1px solid #585b70; border-radius: 6px; padding: 8px 12px; font-size: 13px; }
    QLineEdit:focus { border-color: #89b4fa; }
    QPushButton { background-color: #45475a; color: #cdd6f4; border: 1px solid #585b70; border-radius: 6px; padding: 6px 14px; font-size: 13px; }
    QPushButton:hover { background-color: #585b70; border-color: #89b4fa; }
    QPushButton:pressed { background-color: #313244; }
    QPushButton[default=\"true\"] { background-color: #89b4fa; color: #1e1e2e; border-color: #89b4fa; }
    QPushButton:disabled { background-color: #313244; color: #585b70; }
    QGroupBox { border: 1px solid #45475a; border-radius: 8px; margin-top: 12px; padding-top: 16px; font-size: 13px; font-weight: bold; }
    QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
    QTableWidget { background-color: #313244; alternate-background-color: #363a4f; border: 1px solid #45475a; border-radius: 6px; gridline-color: #45475a; font-size: 12px; }
    QTableWidget::item { padding: 4px 8px; }
    QHeaderView::section { background-color: #45475a; color: #cdd6f4; border: none; border-right: 1px solid #585b70; padding: 6px 8px; font-weight: bold; }
    QComboBox { background-color: #45475a; color: #cdd6f4; border: 1px solid #585b70; border-radius: 4px; padding: 4px 8px; font-size: 12px; }
    QComboBox:hover { border-color: #89b4fa; }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView { background-color: #45475a; color: #cdd6f4; selection-background-color: #89b4fa; selection-color: #1e1e2e; }
    QCheckBox { font-size: 13px; spacing: 6px; }
    QCheckBox::indicator { width: 18px; height: 18px; }
    QProgressBar { border: 1px solid #45475a; border-radius: 4px; text-align: center; font-size: 11px; background-color: #313244; }
    QProgressBar::chunk { background-color: #89b4fa; border-radius: 3px; }
    QStatusBar { background-color: #313244; color: #a6adc8; border-top: 1px solid #45475a; }
    QMenuBar { background-color: #313244; color: #cdd6f4; border-bottom: 1px solid #45475a; }
    QMenuBar::item:selected { background-color: #45475a; }
    QMenu { background-color: #45475a; color: #cdd6f4; border: 1px solid #585b70; }
    QMenu::item:selected { background-color: #89b4fa; color: #1e1e2e; }
    QScrollBar:vertical { background: #313244; width: 10px; border-radius: 5px; }
    QScrollBar::handle:vertical { background: #585b70; border-radius: 5px; min-height: 30px; }
    QScrollBar::handle:vertical:hover { background: #89b4fa; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QFrame#videoInfoCard { background-color: #313244; border-radius: 8px; border: 1px solid #45475a; }
    QTabWidget::pane { border: 1px solid #45475a; border-radius: 6px; background-color: #1e1e2e; }
    QTabBar::tab { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; padding: 8px 16px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
    QTabBar::tab:selected { background-color: #45475a; border-bottom-color: #1e1e2e; }
    QTabBar::tab:hover { background-color: #585b70; }
    QSpinBox { background-color: #45475a; color: #cdd6f4; border: 1px solid #585b70; border-radius: 4px; padding: 4px; }
    QLabel { background: transparent; }
"""

LIGHT_THEME = """
    QMainWindow, QDialog { background-color: #f5f5f5; color: #333333; }
    QWidget { background-color: #f5f5f5; color: #333333; }
    QFrame#urlBar { background-color: #ffffff; border-radius: 8px; border: 1px solid #e0e0e0; }
    QLineEdit { background-color: #ffffff; color: #333333; border: 1px solid #d0d0d0; border-radius: 6px; padding: 8px 12px; font-size: 13px; }
    QLineEdit:focus { border-color: #1976D2; }
    QPushButton { background-color: #ffffff; color: #333333; border: 1px solid #d0d0d0; border-radius: 6px; padding: 6px 14px; font-size: 13px; }
    QPushButton:hover { background-color: #e3f2fd; border-color: #1976D2; }
    QPushButton:pressed { background-color: #bbdefb; }
    QPushButton[default=\"true\"] { background-color: #1976D2; color: white; border-color: #1976D2; }
    QPushButton:disabled { background-color: #f0f0f0; color: #b0b0b0; }
    QGroupBox { border: 1px solid #e0e0e0; border-radius: 8px; margin-top: 12px; padding-top: 16px; font-size: 13px; font-weight: bold; background-color: #ffffff; }
    QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
    QTableWidget { background-color: #ffffff; alternate-background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; gridline-color: #e0e0e0; font-size: 12px; }
    QTableWidget::item { padding: 4px 8px; }
    QHeaderView::section { background-color: #f0f0f0; color: #333333; border: none; border-right: 1px solid #e0e0e0; padding: 6px 8px; font-weight: bold; }
    QComboBox { background-color: #ffffff; color: #333333; border: 1px solid #d0d0d0; border-radius: 4px; padding: 4px 8px; font-size: 12px; }
    QComboBox:hover { border-color: #1976D2; }
    QComboBox QAbstractItemView { background-color: #ffffff; color: #333333; selection-background-color: #1976D2; selection-color: white; }
    QCheckBox { font-size: 13px; spacing: 6px; background-color: transparent; }
    QProgressBar { border: 1px solid #e0e0e0; border-radius: 4px; text-align: center; font-size: 11px; background-color: #f0f0f0; }
    QProgressBar::chunk { background-color: #1976D2; border-radius: 3px; }
    QStatusBar { background-color: #ffffff; color: #666666; border-top: 1px solid #e0e0e0; }
    QMenuBar { background-color: #ffffff; color: #333333; border-bottom: 1px solid #e0e0e0; }
    QMenuBar::item:selected { background-color: #e3f2fd; }
    QMenu { background-color: #ffffff; color: #333333; border: 1px solid #e0e0e0; }
    QMenu::item:selected { background-color: #1976D2; color: white; }
    QFrame#videoInfoCard { background-color: #ffffff; border-radius: 8px; border: 1px solid #e0e0e0; }
    QTabWidget::pane { border: 1px solid #e0e0e0; background-color: #ffffff; }
    QTabBar::tab { background-color: #f0f0f0; color: #333333; border: 1px solid #e0e0e0; padding: 8px 16px; margin-right: 2px; }
    QTabBar::tab:selected { background-color: #ffffff; border-bottom-color: #ffffff; }
    QTabBar::tab:hover { background-color: #e3f2fd; }
    QSpinBox { background-color: #ffffff; color: #333333; border: 1px solid #d0d0d0; border-radius: 4px; padding: 4px; }
    QLabel { background: transparent; }
"""


def get_theme_stylesheet(is_dark: bool) -> str:
    """获取指定主题的 QSS 样式表

    Args:
        is_dark: True 返回深色主题，False 返回浅色主题

    Returns:
        QSS 样式表字符串
    """
    return DARK_THEME if is_dark else LIGHT_THEME
