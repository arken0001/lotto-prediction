"""로또 용지 마킹 이미지 생성 모듈

실측 규격: 190mm x 82.5mm (가로형)
스캔 이미지 기반 좌표 보정 완료

마킹: 세로로 긴 사각형 (OMR 인식용)
"수동 선택" 체크박스 자동 마킹 포함
"""

from PIL import Image, ImageDraw, ImageFont
import io
from pathlib import Path

# ── 용지 규격 (mm) ──
PAPER_W_MM = 190.0
PAPER_H_MM = 82.5

# ── DPI ──
DPI = 600

def mm(v): return int(v * DPI / 25.4)

# ── 스캔 실측 좌표 (축소 이미지 1700x2940 기준) ──
# 세로형 스캔: 190mm=세로방향, 82.5mm=가로방향
# 축소 이미지: 가로 1700px = 약 108mm, 세로 2940px = 약 187mm
# 실제 인쇄용 좌표는 mm로 변환 필요

# 스캔 px → mm 변환 계수 (세로형 스캔 기준)
# 가로(X): 1700px ≈ 82.5mm → 1px = 0.04853mm  (용지 높이 방향)
# 세로(Y): 2940px ≈ 190mm → 1px = 0.06463mm   (용지 폭 방향)
_SCAN_X_TO_MM = 82.5 / 1700   # 스캔X → 용지Y(높이)
_SCAN_Y_TO_MM = 190.0 / 2940  # 스캔Y → 용지X(폭)

# ── 스캔 기반 좌표 (세로 스캔 px) ──
_SCAN_A1_X = 395     # A구역 1번 열 중심 X
_SCAN_COL_STEP = 82  # 열 간격 px
_SCAN_ROW_STEP = 40  # 행 간격 px
_SCAN_SECTION_Y = [358, 828, 1298, 1768, 2238]  # A~E 1행 Y
_SCAN_MARK_W = 10    # 마킹 반폭 px
_SCAN_MARK_H = 13    # 마킹 반높이 px
_SCAN_CHECKBOX_X = 173  # "수동 선택" 체크 X
_SCAN_CHECKBOX_DY = 295 # 1행 Y에서 체크박스까지 거리

# ── mm 변환 (가로형 인쇄용) ──
# 스캔(세로) → 인쇄(가로) 변환: 스캔X→인쇄Y, 스캔Y→인쇄X
SECTION_X_START = [y * _SCAN_Y_TO_MM for y in _SCAN_SECTION_Y]  # A~E 인쇄X
GRID_Y_START = _SCAN_A1_X * _SCAN_X_TO_MM  # 1번행 인쇄Y
COL_STEP_MM = _SCAN_ROW_STEP * _SCAN_Y_TO_MM  # 행간격→인쇄열간격
ROW_STEP_MM = _SCAN_COL_STEP * _SCAN_X_TO_MM  # 열간격→인쇄행간격
MARK_W_MM = _SCAN_MARK_H * _SCAN_Y_TO_MM * 2  # 마킹 폭 (인쇄 가로)
MARK_H_MM = _SCAN_MARK_W * _SCAN_X_TO_MM * 2  # 마킹 높이 (인쇄 세로)
CHECKBOX_Y = _SCAN_CHECKBOX_X * _SCAN_X_TO_MM  # 체크박스 인쇄Y
CHECKBOX_DX = _SCAN_CHECKBOX_DY * _SCAN_Y_TO_MM  # 체크박스 인쇄X 오프셋

# ── 보정값 ──
OFFSET_X_MM = 0.0
OFFSET_Y_MM = 0.0
SECTION_Y_START = GRID_Y_START  # alias


def number_to_pos_print(num: int, section_idx: int) -> tuple[float, float]:
    """번호의 인쇄용 절대 좌표 (mm, 가로형)"""
    row = (num - 1) // 7
    col = (num - 1) % 7
    x = SECTION_X_START[section_idx] + col * COL_STEP_MM + OFFSET_X_MM
    y = GRID_Y_START + row * ROW_STEP_MM + OFFSET_Y_MM
    return (x, y)


def number_to_pos_scan(num: int, section_idx: int) -> tuple[int, int]:
    """번호의 스캔 이미지 좌표 (px, 세로형)"""
    row = (num - 1) // 7
    col = (num - 1) % 7
    x = _SCAN_A1_X + col * _SCAN_COL_STEP
    y = _SCAN_SECTION_Y[section_idx] + row * _SCAN_ROW_STEP
    return (x, y)


def create_marking_image(game_sets: list[list[int]]) -> Image.Image:
    """인쇄용 이미지 (흰 배경 + 검은 사각형 마킹, 가로형)"""
    w, h = mm(PAPER_W_MM), mm(PAPER_H_MM)
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)

    mw = mm(MARK_W_MM) // 2
    mh = mm(MARK_H_MM) // 2

    for sec_idx, numbers in enumerate(game_sets[:5]):
        # 번호 마킹
        for num in numbers:
            if not (1 <= num <= 45):
                continue
            x_mm, y_mm = number_to_pos_print(num, sec_idx)
            cx, cy = mm(x_mm), mm(y_mm)
            draw.rectangle([cx-mw, cy-mh, cx+mw, cy+mh], fill='black')

        # "수동 선택" 체크
        chk_x = mm(SECTION_X_START[sec_idx] + CHECKBOX_DX + OFFSET_X_MM)
        chk_y = mm(CHECKBOX_Y + OFFSET_Y_MM)
        draw.rectangle([chk_x-mw, chk_y-mh, chk_x+mw, chk_y+mh], fill='black')

    return img


def create_preview_on_scan(game_sets: list[list[int]]) -> Image.Image:
    """스캔 이미지 위에 마킹 오버레이 (미리보기용)"""
    bg_path = Path(__file__).parent.parent / "data" / "lotto_paper_bg.png"
    if not bg_path.exists():
        return create_preview_simple(game_sets)

    bg = Image.open(bg_path).convert("RGBA")
    overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    mw = _SCAN_MARK_W
    mh = _SCAN_MARK_H

    for sec_idx, numbers in enumerate(game_sets[:5]):
        base_y = _SCAN_SECTION_Y[sec_idx]

        for num in numbers:
            if not (1 <= num <= 45):
                continue
            x, y = number_to_pos_scan(num, sec_idx)
            draw.rectangle([x-mw, y-mh, x+mw, y+mh], fill=(0, 0, 0, 220))

        # "수동 선택" 체크
        chk_x = _SCAN_CHECKBOX_X
        chk_y = base_y + _SCAN_CHECKBOX_DY
        draw.rectangle([chk_x-mw, chk_y-mh, chk_x+mw, chk_y+mh], fill=(0, 0, 0, 220))

    result = Image.alpha_composite(bg, overlay)
    return result.convert("RGB")


def create_preview_simple(game_sets: list[list[int]]) -> Image.Image:
    """스캔 없을 때 간단한 미리보기 (흰 배경 + 격자)"""
    preview_dpi = 250
    def pmm(v): return int(v * preview_dpi / 25.4)

    w, h = pmm(PAPER_W_MM), pmm(PAPER_H_MM)
    img = Image.new('RGB', (w, h), '#fefefe')
    draw = ImageDraw.Draw(img)

    try:
        num_font = ImageFont.truetype("arial.ttf", pmm(2.0))
        label_font = ImageFont.truetype("arialbd.ttf", pmm(4.5))
    except Exception:
        num_font = ImageFont.load_default()
        label_font = num_font

    draw.rectangle([1, 1, w-2, h-2], outline='#ccc', width=2)

    selected = {}
    for si, nums in enumerate(game_sets[:5]):
        for n in nums:
            selected[(si, n)] = True

    cell_w = pmm(COL_STEP_MM)
    cell_h = pmm(ROW_STEP_MM)
    pad = pmm(0.3)

    for sec_idx in range(5):
        sx = pmm(SECTION_X_START[sec_idx])
        sy = pmm(GRID_Y_START)
        label = chr(65 + sec_idx)

        grid_l = sx - pmm(1.5)
        grid_r = sx + pmm(COL_STEP_MM * 6 + 1.5)
        grid_t = sy - pmm(1.5)
        grid_b = sy + pmm(ROW_STEP_MM * 6 + 1.5)
        draw.rectangle([grid_l, grid_t, grid_r, grid_b], outline='#e88', width=2)
        draw.rectangle([grid_r-pmm(8), grid_t-pmm(6), grid_r, grid_t], fill='#e44')
        bbox = draw.textbbox((0, 0), label, font=label_font)
        tw = bbox[2] - bbox[0]
        draw.text((grid_r - pmm(4) - tw//2, grid_t - pmm(5.5)), label, fill='white', font=label_font)

        for num in range(1, 46):
            row = (num - 1) // 7
            col = (num - 1) % 7
            cx = pmm(SECTION_X_START[sec_idx] + col * COL_STEP_MM)
            cy = pmm(GRID_Y_START + row * ROW_STEP_MM)
            bx1 = cx - cell_w//2 + pad
            by1 = cy - cell_h//2 + pad
            bx2 = cx + cell_w//2 - pad
            by2 = cy + cell_h//2 - pad

            if (sec_idx, num) in selected:
                draw.rectangle([bx1, by1, bx2, by2], fill='#222')
                tc = 'white'
            else:
                draw.rectangle([bx1, by1, bx2, by2], outline='#bbb', width=1)
                tc = '#888'

            text = str(num)
            bbox = draw.textbbox((0, 0), text, font=num_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((cx - tw//2, cy - th//2), text, fill=tc, font=num_font)

    return img


def image_to_bytes(img: Image.Image, fmt: str = 'PNG') -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, dpi=(DPI, DPI))
    buf.seek(0)
    return buf.getvalue()


def generate_escpos_data(predictions: list[list[int]], round_no: int = None) -> bytes:
    """ESC/POS 영수증 출력 데이터"""
    ESC, GS = b'\x1b', b'\x1d'
    data = ESC + b'@' + ESC + b'a\x01' + ESC + b'E\x01'
    data += b'=== LOTTO 6/45 ===\n' + ESC + b'E\x00'
    if round_no:
        data += f'  #{round_no}\n'.encode('euc-kr', errors='replace')
    data += b'------------------------\n' + ESC + b'a\x00'
    for i, nums in enumerate(predictions[:5], 1):
        label = chr(64 + i)
        nums_str = ' '.join(f'{n:02d}' for n in sorted(nums))
        data += f' {label}: {nums_str}\n'.encode('euc-kr', errors='replace')
    data += b'------------------------\n' + ESC + b'a\x01'
    from datetime import datetime
    data += datetime.now().strftime('%Y-%m-%d %H:%M\n').encode()
    data += b'\n\n\n' + GS + b'V\x00'
    return data
