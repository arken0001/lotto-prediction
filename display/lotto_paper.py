"""로또 용지 마킹 이미지 생성 모듈

용지: 190mm x 82.5mm (가로형, 1200DPI 실측)
A~E 5구역 좌→우 배치
마킹: 세로 직사각형 (0.95mm x 1.52mm)
"""

from PIL import Image, ImageDraw, ImageFont
import io
from pathlib import Path

# ── 용지 규격 (mm, 가로형) ──
PAPER_W_MM = 190.0
PAPER_H_MM = 82.5

# ── DPI ──
DPI = 1200  # 원본 이미지와 동일

def mm2px(v): return int(v * DPI / 25.4)

# ── 좌표 (mm, 가로형 용지 좌상단 기준) ──
# workspace/lotto.jpg 실측 (1200DPI 가로형)
SECTION_X = [26.37, 55.36, 84.35, 113.34, 142.33]  # A~E 1번열 X (좌 1mm 보정)
NUM1_Y = 18.30     # 1행 Y (하 1mm 보정)
COL_MM = 3.30      # 열 간격 (1→2→...→7)
ROW_MM = 3.65      # 행 간격

# 마킹 크기 (2배)
MARK_W_MM = 1.90   # 가로
MARK_H_MM = 3.04   # 세로

# 수동선택 체크박스
CHK_DX_MM = -2.0   # 1번열 X에서 좌측 오프셋
CHK_Y_MM = 69.43   # 체크박스 Y (하 1mm 보정)

# 보정값
OFFSET_X_MM = 0.0
OFFSET_Y_MM = 0.0

# ── 미리보기용 축소 좌표 (2000x868 이미지 기준) ──
_BG_W = 2000
_BG_H = 868
_BG_SCALE = _BG_W / (PAPER_W_MM * DPI / 25.4)  # 2000 / 8976 = 0.2228
_BG_PX_PER_MM = _BG_W / PAPER_W_MM  # 10.526


def number_to_pos(num: int, section_idx: int) -> tuple[float, float]:
    """번호(1~45)의 인쇄 좌표 (mm)"""
    row = (num - 1) // 7
    col = (num - 1) % 7
    x = SECTION_X[section_idx] + col * COL_MM + OFFSET_X_MM
    y = NUM1_Y + row * ROW_MM + OFFSET_Y_MM
    return (x, y)


def create_marking_image(game_sets: list[list[int]]) -> Image.Image:
    """인쇄용 이미지 (190x82.5mm 가로형, 흰배경 + 검은 마킹)"""
    w = mm2px(PAPER_W_MM)
    h = mm2px(PAPER_H_MM)
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)

    mw = mm2px(MARK_W_MM) // 2
    mh = mm2px(MARK_H_MM) // 2

    for si, numbers in enumerate(game_sets[:5]):
        for num in numbers:
            if not (1 <= num <= 45):
                continue
            x_mm, y_mm = number_to_pos(num, si)
            cx, cy = mm2px(x_mm), mm2px(y_mm)
            draw.rectangle([cx-mw, cy-mh, cx+mw, cy+mh], fill='black')

        # 수동선택 체크
        chk_x = mm2px(SECTION_X[si] + CHK_DX_MM + OFFSET_X_MM)
        chk_y = mm2px(CHK_Y_MM + OFFSET_Y_MM)
        draw.rectangle([chk_x-mw, chk_y-mh, chk_x+mw, chk_y+mh], fill='black')

    return img


def create_preview_on_scan(game_sets: list[list[int]]) -> Image.Image:
    """배경 이미지 위에 마킹 오버레이 (가로형 미리보기)"""
    bg_path = Path(__file__).parent.parent / "data" / "lotto_paper_bg.png"
    if not bg_path.exists():
        return create_preview_simple(game_sets)

    bg = Image.open(bg_path).convert("RGBA")
    overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    ppm = _BG_PX_PER_MM  # px per mm
    mw = int(MARK_W_MM * ppm / 2)
    mh = int(MARK_H_MM * ppm / 2)

    for si, numbers in enumerate(game_sets[:5]):
        for num in numbers:
            if not (1 <= num <= 45):
                continue
            x_mm, y_mm = number_to_pos(num, si)
            cx = int(x_mm * ppm)
            cy = int(y_mm * ppm)
            draw.rectangle([cx-mw, cy-mh, cx+mw, cy+mh], fill=(0, 0, 0, 220))

        # 수동선택 체크
        chk_x = int((SECTION_X[si] + CHK_DX_MM + OFFSET_X_MM) * ppm)
        chk_y = int((CHK_Y_MM + OFFSET_Y_MM) * ppm)
        draw.rectangle([chk_x-mw, chk_y-mh, chk_x+mw, chk_y+mh], fill=(0, 0, 0, 220))

    result = Image.alpha_composite(bg, overlay)
    return result.convert("RGB")


def create_preview_simple(game_sets: list[list[int]]) -> Image.Image:
    """배경 없을 때 간단 미리보기"""
    pw, ph = 1200, 520
    img = Image.new('RGB', (pw, ph), '#fefefe')
    draw = ImageDraw.Draw(img)
    draw.rectangle([1, 1, pw-2, ph-2], outline='#ccc', width=2)

    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        font = ImageFont.load_default()

    ppm = pw / PAPER_W_MM
    sel = set()
    for si, nums in enumerate(game_sets[:5]):
        for n in nums:
            sel.add((si, n))

    cw = int(COL_MM * ppm)
    ch = int(ROW_MM * ppm)

    for si in range(5):
        for num in range(1, 46):
            r = (num-1)//7
            c = (num-1)%7
            cx = int((SECTION_X[si] + c*COL_MM) * ppm)
            cy = int((NUM1_Y + r*ROW_MM) * ppm)

            if (si, num) in sel:
                draw.rectangle([cx-cw//2+1, cy-ch//2+1, cx+cw//2-1, cy+ch//2-1], fill='#222')
                tc = 'white'
            else:
                draw.rectangle([cx-cw//2+1, cy-ch//2+1, cx+cw//2-1, cy+ch//2-1], outline='#bbb')
                tc = '#888'
            t = str(num)
            bb = draw.textbbox((0,0), t, font=font)
            draw.text((cx-(bb[2]-bb[0])//2, cy-(bb[3]-bb[1])//2), t, fill=tc, font=font)

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
        data += f' {chr(64+i)}: {" ".join(f"{n:02d}" for n in sorted(nums))}\n'.encode('euc-kr', errors='replace')
    data += b'------------------------\n' + ESC + b'a\x01'
    from datetime import datetime
    data += datetime.now().strftime('%Y-%m-%d %H:%M\n').encode()
    data += b'\n\n\n' + GS + b'V\x00'
    return data
