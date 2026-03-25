"""로또 용지 마킹 이미지 생성 모듈

실측 규격: 82.5mm x 190mm (세로형, 프린터 급지 방향)
스캔 이미지 기반 좌표 보정 완료

마킹: 세로로 긴 사각형 (OMR 인식용)
"수동 선택" 체크박스 자동 마킹 포함
"""

from PIL import Image, ImageDraw, ImageFont
import io
from pathlib import Path

# ── 용지 규격 (mm, 세로형) ──
PAPER_W_MM = 82.5    # 폭
PAPER_H_MM = 190.0   # 높이

# ── DPI ──
DPI = 600

def mm2px(v): return int(v * DPI / 25.4)

# ── 스캔 실측 좌표 (mm, 용지 좌상단 기준) ──
# 스캔 이미지 분석으로 도출
A1_X_MM = 18.59      # 1번 칸 중심 X
A1_Y_MM = 22.01      # A구역 1번 행 중심 Y
COL_STEP_MM = 4.18   # 열 간격 (1→2→...→7, 좌→우)
ROW_STEP_MM = 2.64   # 행 간격 (1행→2행, 위→아래)

# 각 구역 1행 Y좌표 (mm)
SECTION_Y = [22.01, 53.07, 84.13, 115.19, 146.25]  # A~E

# 마킹 크기 (mm)
MARK_W_MM = 1.02     # 가로 (좁음)
MARK_H_MM = 1.72     # 세로 (긺)

# "수동 선택" 체크박스
CHECKBOX_X_MM = 7.28  # 체크박스 X
CHECKBOX_DY_MM = 19.50  # 1행에서 체크박스까지 Y 거리

# 보정값
OFFSET_X_MM = 0.0
OFFSET_Y_MM = 0.0

# ── 스캔 미리보기용 좌표 (축소 이미지 px) ──
_SCAN_A1_X = 395
_SCAN_A1_Y = 358
_SCAN_COL = 82
_SCAN_ROW = 40
_SCAN_SECTION_Y = [358, 828, 1298, 1768, 2238]
_SCAN_MW = 10   # 마킹 반폭
_SCAN_MH = 13   # 마킹 반높이
_SCAN_CHK_X = 173
_SCAN_CHK_DY = 295


def number_to_pos(num: int, section_idx: int) -> tuple[float, float]:
    """번호(1~45)의 인쇄 좌표 (mm)"""
    row = (num - 1) // 7
    col = (num - 1) % 7
    x = A1_X_MM + col * COL_STEP_MM + OFFSET_X_MM
    y = SECTION_Y[section_idx] + row * ROW_STEP_MM + OFFSET_Y_MM
    return (x, y)


def create_marking_image(game_sets: list[list[int]]) -> Image.Image:
    """인쇄용 이미지 (82.5mm x 190mm, 흰배경 + 검은 사각형 마킹)"""
    w = mm2px(PAPER_W_MM)
    h = mm2px(PAPER_H_MM)
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)

    mw = mm2px(MARK_W_MM) // 2
    mh = mm2px(MARK_H_MM) // 2

    for sec_idx, numbers in enumerate(game_sets[:5]):
        for num in numbers:
            if not (1 <= num <= 45):
                continue
            x_mm, y_mm = number_to_pos(num, sec_idx)
            cx, cy = mm2px(x_mm), mm2px(y_mm)
            draw.rectangle([cx-mw, cy-mh, cx+mw, cy+mh], fill='black')

        # 수동 선택 체크
        chk_x = mm2px(CHECKBOX_X_MM + OFFSET_X_MM)
        chk_y = mm2px(SECTION_Y[sec_idx] + CHECKBOX_DY_MM + OFFSET_Y_MM)
        draw.rectangle([chk_x-mw, chk_y-mh, chk_x+mw, chk_y+mh], fill='black')

    return img


def create_preview_on_scan(game_sets: list[list[int]]) -> Image.Image:
    """스캔 이미지 위에 마킹 오버레이 (미리보기)"""
    bg_path = Path(__file__).parent.parent / "data" / "lotto_paper_bg.png"
    if not bg_path.exists():
        return create_preview_simple(game_sets)

    bg = Image.open(bg_path).convert("RGBA")
    overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for sec_idx, numbers in enumerate(game_sets[:5]):
        for num in numbers:
            if not (1 <= num <= 45):
                continue
            row = (num - 1) // 7
            col = (num - 1) % 7
            x = _SCAN_A1_X + col * _SCAN_COL
            y = _SCAN_SECTION_Y[sec_idx] + row * _SCAN_ROW
            draw.rectangle([x-_SCAN_MW, y-_SCAN_MH, x+_SCAN_MW, y+_SCAN_MH],
                          fill=(0, 0, 0, 220))

        # 수동 선택 체크
        chk_y = _SCAN_SECTION_Y[sec_idx] + _SCAN_CHK_DY
        draw.rectangle([_SCAN_CHK_X-_SCAN_MW, chk_y-_SCAN_MH,
                        _SCAN_CHK_X+_SCAN_MW, chk_y+_SCAN_MH],
                       fill=(0, 0, 0, 220))

    result = Image.alpha_composite(bg, overlay)
    # 가로형으로 회전 (화면 표시용)
    rotated = result.convert("RGB").transpose(Image.ROTATE_270)
    return rotated


def create_preview_simple(game_sets: list[list[int]]) -> Image.Image:
    """스캔 없을 때 간단 미리보기"""
    pdpi = 150
    def pmm(v): return int(v * pdpi / 25.4)

    w, h = pmm(PAPER_W_MM), pmm(PAPER_H_MM)
    img = Image.new('RGB', (w, h), '#fefefe')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", pmm(2.0))
        lfont = ImageFont.truetype("arialbd.ttf", pmm(4.0))
    except Exception:
        font = ImageFont.load_default()
        lfont = font

    draw.rectangle([1, 1, w-2, h-2], outline='#ccc', width=2)

    sel = set()
    for si, nums in enumerate(game_sets[:5]):
        for n in nums:
            sel.add((si, n))

    cw = pmm(COL_STEP_MM)
    ch = pmm(ROW_STEP_MM)

    for si in range(5):
        label = chr(65+si)
        sy = pmm(SECTION_Y[si])
        sx = pmm(A1_X_MM)

        gl = sx - pmm(1)
        gr = sx + pmm(COL_STEP_MM*6 + 1)
        gt = sy - pmm(1)
        gb = sy + pmm(ROW_STEP_MM*6 + 1)
        draw.rectangle([gl, gt, gr, gb], outline='#e88', width=1)

        bbox = draw.textbbox((0,0), label, font=lfont)
        tw = bbox[2]-bbox[0]
        draw.text((gr-tw-pmm(1), gt-pmm(5)), label, fill='#e44', font=lfont)

        for num in range(1, 46):
            r = (num-1)//7
            c = (num-1)%7
            cx = pmm(A1_X_MM + c*COL_STEP_MM)
            cy = pmm(SECTION_Y[si] + r*ROW_STEP_MM)

            if (si, num) in sel:
                draw.rectangle([cx-cw//2+1, cy-ch//2+1, cx+cw//2-1, cy+ch//2-1], fill='#222')
                tc = 'white'
            else:
                draw.rectangle([cx-cw//2+1, cy-ch//2+1, cx+cw//2-1, cy+ch//2-1], outline='#bbb', width=1)
                tc = '#888'
            text = str(num)
            bbox = draw.textbbox((0,0), text, font=font)
            draw.text((cx-(bbox[2]-bbox[0])//2, cy-(bbox[3]-bbox[1])//2), text, fill=tc, font=font)

    rotated = img.transpose(Image.ROTATE_270)
    return rotated


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
