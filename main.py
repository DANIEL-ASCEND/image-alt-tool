# -*- coding: utf-8 -*-
"""
独立站图片 SEO 自动化工具 v1.3
==============================
v1.3 相对 v1.2 的变化（界面做减法）：
- 去掉「行业分类」下拉：它与可编辑的策略表功能重复，属于摆设设置。
  策略表直接预填 3C 预设；其他行业预设收进同目录 presets.txt，需要时整段粘贴替换。
- 窗口加上 app.ico 图标（与本文件同目录，打包 exe 时自动带入）。
其余沿用 v1.2：真转码+压缩、长尾词逐张分发进 ALT、策略表可编辑、
自然排序、只复制不动原图、重名加 -v2、导出 alt_tags_mapping.csv。

依赖：PyQt6、Pillow
运行：python main.py
打包：pyinstaller --onefile --windowed --name SEO工具1.3 --icon app.ico main.py
"""

import sys
import os
import re
import csv

from PIL import Image, ImageOps

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QLineEdit, QTextEdit, QPushButton, QComboBox, QSpinBox,
        QFileDialog, QMessageBox
    )
    from PyQt6.QtGui import QIcon
    HAS_QT = True
except ImportError:
    HAS_QT = False


def app_icon_path():
    """app.ico 的位置：源码运行时在本文件旁，打包后在 PyInstaller 解包目录里。"""
    base = getattr(sys, '_MEIPASS',
                   os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, 'app.ico')
    return p if os.path.exists(p) else None

# ---------------------------------------------------------------- 预设策略表
# 每行： slug | 视角显示名 | ALT 侧重短语（英文，直接进 ALT）
PRESETS = {
    '3C数码 / 消费电子': """main-view | Main View | Product Overall View
detail-view-1 | Detail Close-up | Build Quality and Material Detail
scene-view-1 | In Use | In Use on Desk
feature-view-1 | Feature Highlight | Key Feature in Action
detail-view-2 | Interface Detail | Ports and Controls Detail
scene-view-2 | Lifestyle Scene | Everyday Use Scene
angle-view-1 | Side Angle | Side Profile View
package-view-1 | Package | Package and Accessories""",

    '服装鞋帽': """main-view | Front View | Front Full View
detail-view-1 | Fabric Detail | Fabric Texture Close-up
scene-view-1 | On Model | Worn Look on Model
feature-view-1 | Design Feature | Design Detail Highlight
detail-view-2 | Craft Detail | Stitching and Craftsmanship
scene-view-2 | Styling Scene | Outfit Pairing Scene
angle-view-1 | Back View | Back Full View
package-view-1 | Package | Package and Size Options""",

    '家居百货': """main-view | Main View | Product Overall View
detail-view-1 | Material Detail | Material and Finish Close-up
scene-view-1 | Home Scene | In a Home Setting
feature-view-1 | Feature Highlight | Practical Feature in Use
detail-view-2 | Size Detail | Dimensions and Capacity
scene-view-2 | Lifestyle Scene | Daily Life Scene
angle-view-1 | Side Angle | Side Profile View
package-view-1 | Package | Package Contents""",

    '通用类': """main-view | Main View | Product Overall View
detail-view-1 | Detail View | Product Detail Close-up
scene-view-1 | Scene View | Product In Use
feature-view-1 | Feature View | Key Feature Highlight
detail-view-2 | Detail View 2 | Design Detail
scene-view-2 | Scene View 2 | Usage Scene
angle-view-1 | Angle View | Another Angle
package-view-1 | Package View | Package and Contents""",
}

VALID_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')
ALT_MAX_LEN = 250  # ALT 过长对 SEO 无益，超限按词边界截断


# ---------------------------------------------------------------- 核心工具函数
def natural_key(name):
    """自然排序键：让 2 排在 10 前面。"""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r'(\d+)', name)]


def slugify(text):
    return re.sub(r'[^a-zA-Z0-9]+', '-', text.lower()).strip('-')


def parse_keywords(text):
    """长尾词按英文逗号 / 中文逗号 / 顿号 / 换行切分，去空去重保序。"""
    parts = re.split(r'[,，、\n]+', text or '')
    seen, out = set(), []
    for p in parts:
        p = p.strip()
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def parse_strategies(text):
    """解析可编辑策略表：每行 slug | 视角名 | 侧重短语 。"""
    strategies = []
    for line in (text or '').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        cells = [c.strip() for c in line.split('|')]
        if len(cells) == 3 and cells[0] and cells[2]:
            strategies.append({
                'type': slugify(cells[0]) or f'view-{len(strategies) + 1}',
                'name': cells[1],
                'focus': cells[2],
            })
    return strategies


def build_alt(brand, product_name, strategy, keyword):
    """ALT = 品牌 产品名 - 侧重短语, 长尾词（长尾词已在侧重里出现则不重复加）。"""
    head = f"{brand} {product_name}".strip()
    desc = strategy['focus']
    if keyword and keyword.lower() not in desc.lower() \
            and keyword.lower() not in head.lower():
        desc = f"{desc}, {keyword}"
    alt = f"{head} - {desc}"
    if len(alt) > ALT_MAX_LEN:
        alt = alt[:ALT_MAX_LEN].rsplit(' ', 1)[0]
    return alt


def convert_image(src_path, out_path, out_format, quality, max_width):
    """真转码：处理方向/透明底/尺寸后，以目标格式真实编码保存。"""
    with Image.open(src_path) as im:
        im = ImageOps.exif_transpose(im)
        if max_width and im.width > max_width:
            new_h = round(im.height * max_width / im.width)
            im = im.resize((max_width, new_h), Image.LANCZOS)
        if out_format == 'jpg':
            if im.mode in ('RGBA', 'LA', 'P'):
                im = im.convert('RGBA')
                bg = Image.new('RGB', im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            elif im.mode != 'RGB':
                im = im.convert('RGB')
            im.save(out_path, 'JPEG', quality=quality, optimize=True,
                    progressive=True)
        else:  # webp
            if im.mode not in ('RGB', 'RGBA'):
                im = im.convert('RGBA' if 'transparency' in im.info else 'RGB')
            im.save(out_path, 'WEBP', quality=quality, method=6)


def unique_path(out_dir, filename):
    """输出重名时自动加 -v2 / -v3，绝不静默覆盖已有文件。"""
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(out_dir, filename)
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(out_dir, f"{base}-v{n}{ext}")
        n += 1
    return candidate


def process_images_core(src_dir, out_dir, brand, product_name, keywords,
                        strategies, out_format='jpg', quality=85,
                        max_width=2000, log=print):
    """核心处理（与界面无关，可单独测试）。返回映射行列表。"""
    if not strategies:
        raise ValueError('视角策略表为空：请至少保留一行 slug | 视角名 | 侧重短语')
    os.makedirs(out_dir, exist_ok=True)

    img_files = sorted(
        [f for f in os.listdir(src_dir)
         if f.lower().endswith(VALID_EXTS)
         and os.path.isfile(os.path.join(src_dir, f))],
        key=natural_key)
    if not img_files:
        raise ValueError('源文件夹内没有找到图片文件')

    product_slug = slugify(product_name)
    ext = '.jpg' if out_format == 'jpg' else '.webp'
    rows = []

    for idx, file_name in enumerate(img_files):
        cycle = idx // len(strategies)
        strategy = strategies[idx % len(strategies)]
        view_slug = strategy['type'] + (f"-{cycle + 1}" if cycle else '')
        keyword = keywords[idx % len(keywords)] if keywords else ''

        new_filename = f"{product_slug}-{view_slug}{ext}"
        out_path = unique_path(out_dir, new_filename)
        new_filename = os.path.basename(out_path)

        convert_image(os.path.join(src_dir, file_name), out_path,
                      out_format, quality, max_width)
        alt_text = build_alt(brand, product_name, strategy, keyword)

        rows.append({
            'Original_Filename': file_name,
            'New_Filename': new_filename,
            'ALT_Text': alt_text,
            'Keyword': keyword,
            'Out_Size_KB': round(os.path.getsize(out_path) / 1024, 1),
        })
        log(f"✅ [{idx + 1}/{len(img_files)}] {file_name} → {new_filename}\n"
        f"   ALT: {alt_text}")

    csv_path = os.path.join(out_dir, 'alt_tags_mapping.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    log(f"🎉 处理完成！映射表已保存至: {csv_path}")
    return rows


# ---------------------------------------------------------------- 界面
if HAS_QT:
    class ImageSEOApp(QWidget):
        def __init__(self):
            super().__init__()
            self.initUI()

        def initUI(self):
            self.setWindowTitle('独立站图片 SEO 自动化工具 v1.3')
            icon = app_icon_path()
            if icon:
                self.setWindowIcon(QIcon(icon))
            self.resize(780, 700)
            layout = QVBoxLayout()

            h1 = QHBoxLayout()
            h1.addWidget(QLabel('源图片文件夹:'))
            self.src_dir_input = QLineEdit()
            h1.addWidget(self.src_dir_input)
            btn = QPushButton('选择文件夹')
            btn.clicked.connect(lambda: self._pick(self.src_dir_input))
            h1.addWidget(btn)
            layout.addLayout(h1)

            h2 = QHBoxLayout()
            h2.addWidget(QLabel('输出保存文件夹:'))
            self.out_dir_input = QLineEdit()
            h2.addWidget(self.out_dir_input)
            btn = QPushButton('选择文件夹')
            btn.clicked.connect(lambda: self._pick(self.out_dir_input))
            h2.addWidget(btn)
            layout.addLayout(h2)

            h4 = QHBoxLayout()
            h4.addWidget(QLabel('品牌名称 (Brand):'))
            self.brand_input = QLineEdit()
            self.brand_input.setPlaceholderText('例如: DEVIA')
            h4.addWidget(self.brand_input)
            layout.addLayout(h4)

            h5 = QHBoxLayout()
            h5.addWidget(QLabel('核心产品名 (Product Name):'))
            self.product_name_input = QLineEdit()
            self.product_name_input.setPlaceholderText(
                '例如: Smart Series 3 In 1 Magnetic Wireless Charger')
            h5.addWidget(self.product_name_input)
            layout.addLayout(h5)

            layout.addWidget(QLabel(
                '核心卖点词/长尾词（逗号或换行分隔，会逐张分发进 ALT）:'))
            self.param_text = QTextEdit()
            self.param_text.setPlaceholderText(
                '例如: 15W Fast Wireless Charging, Magnetic Rotation Bracket, '
                'For iPhone and Apple Watch, Foldable Travel Design')
            self.param_text.setMaximumHeight(70)
            layout.addWidget(self.param_text)

            layout.addWidget(QLabel(
                '视角策略表（可编辑，每行: 文件名后缀 | 视角名 | ALT侧重短语；'
                '按图片顺序逐行分配；其他行业预设见同目录 presets.txt）:'))
            self.strategy_text = QTextEdit()
            self.strategy_text.setPlainText(PRESETS['3C数码 / 消费电子'])
            self.strategy_text.setMaximumHeight(150)
            layout.addWidget(self.strategy_text)

            h6 = QHBoxLayout()
            h6.addWidget(QLabel('输出格式:'))
            self.fmt_combo = QComboBox()
            self.fmt_combo.addItems(['jpg', 'webp'])
            h6.addWidget(self.fmt_combo)
            h6.addWidget(QLabel('质量(1-100):'))
            self.quality_spin = QSpinBox()
            self.quality_spin.setRange(1, 100)
            self.quality_spin.setValue(85)
            h6.addWidget(self.quality_spin)
            h6.addWidget(QLabel('最大宽度 px（0=不缩放）:'))
            self.width_input = QLineEdit('2000')
            self.width_input.setMaximumWidth(70)
            h6.addWidget(self.width_input)
            h6.addStretch()
            layout.addLayout(h6)

            self.btn_process = QPushButton('🚀 一键优化并打包（真转码 + ALT 分发）')
            self.btn_process.setStyleSheet(
                'background-color: #4CAF50; color: white; font-weight: bold;'
                'font-size: 14px; padding: 8px;')
            self.btn_process.clicked.connect(self.process_images)
            layout.addWidget(self.btn_process)

            self.log_area = QTextEdit()
            self.log_area.setReadOnly(True)
            layout.addWidget(self.log_area)
            self.setLayout(layout)

        def _pick(self, target_input):
            dir_path = QFileDialog.getExistingDirectory(self, '选择文件夹')
            if dir_path:
                target_input.setText(dir_path)

        def process_images(self):
            src_dir = self.src_dir_input.text().strip()
            out_dir = self.out_dir_input.text().strip()
            brand = self.brand_input.text().strip()
            product_name = self.product_name_input.text().strip()

            if not os.path.exists(src_dir) or not out_dir or not product_name:
                QMessageBox.warning(
                    self, '警告',
                    '请填满必填项（源路径、保存路径、产品名称）！')
                return
            try:
                max_width = int(self.width_input.text().strip() or 0)
            except ValueError:
                QMessageBox.warning(self, '警告', '最大宽度请填数字（0 表示不缩放）')
                return

            self.log_area.clear()
            try:
                process_images_core(
                    src_dir, out_dir, brand, product_name,
                    keywords=parse_keywords(self.param_text.toPlainText()),
                    strategies=parse_strategies(
                        self.strategy_text.toPlainText()),
                    out_format=self.fmt_combo.currentText(),
                    quality=self.quality_spin.value(),
                    max_width=max_width,
                    log=self.log_area.append)
            except Exception as e:
                QMessageBox.warning(self, '处理失败', str(e))
                return
            QMessageBox.information(self, '成功', '处理完毕！请查看输出文件夹。')


if __name__ == '__main__':
    if not HAS_QT:
        print('未安装 PyQt6，请先执行: pip install PyQt6 Pillow')
        sys.exit(1)
    app = QApplication(sys.argv)
    _icon = app_icon_path()
    if _icon:
        app.setWindowIcon(QIcon(_icon))
    ex = ImageSEOApp()
    ex.show()
    sys.exit(app.exec())
