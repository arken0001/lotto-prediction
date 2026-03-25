"""로또 용지 마킹 이미지 생성 모듈

실측 규격: 190mm x 82.5mm (가로형)
A~E 5구역이 좌→우로 나란히 배치
각 구역: 7열 x 7행 번호 격자 (마지막 행 43,44,45만)
번호 배열: 좌→우 = 1,2,3,4,5,6,7 / 위→아래

⚠️ 프린터마다 여백이 다르므로 보정값으로 미세 조정
"""

from PIL import Image, ImageDraw, ImageFont
import io

# ── 용지 규격 (mm) ──
PAPER_W_MM = 190.0
PAPER_H_MM = 82.5

# ── DPI ──
DPI = 600

def mm(v): return int(v * DPI / 25.4)

# ── 5개 구역 (A~E) 좌→우 배치 ──
# 각 구역의 번호 그리드 1번(좌상단) 중심 좌표 (용지 좌상단 기준, mm)
# 첫번째 사진 참고: A가 가장 왼쪽, E가 오른쪽
SECTION_X_START = [43.0, 75.0, 107.0, 139.0, 171.0]  # 각 구역 1열(1번) 중심 X
SECTION_Y_START = 18.0   # 1행 중심 Y (모든 구역 동일)

# ── 번호 그리드 간격 ──
COL_STEP_MM = 4.0     # 열 간격 (좌→우)
ROW_STEP_MM = 4.0     # 행 간격 (위→아래)

# ── 마킹 설정 ──
MARK_SIZE_MM = 2.8    # 마킹 직경
MARK_SHAPE = 'circle'

# ── 보정값 (mm) ──
OFFSET_X_MM = 0.0
OFFSET_Y_MM = 0.0


def number_to_pos(num: int, section_idx: int) -> tuple[float, float]:
    """번호(1~45)의 용지 상 절대 좌표(mm)"""
    row = (num - 1) // 7     # 0~6
    col = (num - 1) % 7      # 0~6

    x = SECTION_X_START[section_idx] + col * COL_STEP_MM + OFFSET_X_MM
    y = SECTION_Y_START + row * ROW_STEP_MM + OFFSET_Y_MM
    return (x, y)


def create_marking_image(game_sets: list[list[int]]) -> Image.Image:
    """인쇄용 이미지 (흰 배경 + 검은 마킹만)"""
    w, h = mm(PAPER_W_MM), mm(PAPER_H_MM)
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)
    mark_r = mm(MARK_SIZE_MM) // 2

    for sec_idx, numbers in enumerate(game_sets[:5]):
        for num in numbers:
            if not (1 <= num <= 45):
                continue
            x_mm, y_mm = number_to_pos(num, sec_idx)
            cx, cy = mm(x_mm), mm(y_mm)
            if MARK_SHAPE == 'rect':
                draw.rectangle([cx-mark_r, cy-mark_r, cx+mark_r, cy+mark_r], fill='black')
            else:
                draw.ellipse([cx-mark_r, cy-mark_r, cx+mark_r, cy+mark_r], fill='black')
    return img


def create_preview_image(game_sets: list[list[int]]) -> Image.Image:
    """미리보기용 이미지 (다크 배경, 컬러 마킹)"""
    preview_dpi = 200
    def pmm(v): return int(v * preview_dpi / 25.4)

    w, h = pmm(PAPER_W_MM), pmm(PAPER_H_MM)
    img = Image.new('RGB', (w, h), '#1a1a2e')
    draw = ImageDraw.Draw(img)
    mark_r = pmm(MARK_SIZE_MM) // 2
    dot_r = pmm(1.5)

    try:
        font = ImageFont.truetype("arial.ttf", pmm(2.2))
        label_font = ImageFont.truetype("arial.ttf", pmm(4.0))
    except Exception:
        font = ImageFont.load_default()
        label_font = font

    # 5개 구역 그리기
    for sec_idx in range(5):
        sec_label = chr(65 + sec_idx)
        sx = pmm(SECTION_X_START[sec_idx])

        # 구역 배경
        grid_w = pmm(COL_STEP_MM * 6 + 6)
        grid_h = pmm(ROW_STEP_MM * 6 + 6)
        sec_top = pmm(SECTION_Y_START) - pmm(3)
        draw.rectangle([sx - pmm(3), sec_top, sx + grid_w, sec_top + grid_h],
                       fill='#16213e', outline='#334')

        # 라벨
        draw.text((sx + grid_w // 2 - pmm(2), sec_top - pmm(5)),
                  sec_label, fill='#e44', font=label_font)

        # 45개 번호 그리드
        for num in range(1, 46):
            row = (num - 1) // 7
            col = (num - 1) % 7
            x = pmm(SECTION_X_START[sec_idx] + col * COL_STEP_MM + OFFSET_X_MM)
            y = pmm(SECTION_Y_START + row * ROW_STEP_MM + OFFSET_Y_MM)

            draw.ellipse([x-dot_r, y-dot_r, x+dot_r, y+dot_r], outline='#335', width=1)
            text = str(num)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((x - tw//2, y - th//2), text, fill='#445', font=font)

    # 선택된 번호 마킹
    for sec_idx, numbers in enumerate(game_sets[:5]):
        for num in numbers:
            if not (1 <= num <= 45):
                continue
            row = (num - 1) // 7
            col = (num - 1) % 7
            x = pmm(SECTION_X_START[sec_idx] + col * COL_STEP_MM + OFFSET_X_MM)
            y = pmm(SECTION_Y_START + row * ROW_STEP_MM + OFFSET_Y_MM)

            if num <= 10: color = '#FBC400'
            elif num <= 20: color = '#69C8F2'
            elif num <= 30: color = '#FF7272'
            elif num <= 40: color = '#AAAAAA'
            else: color = '#B0D840'

            draw.ellipse([x-mark_r, y-mark_r, x+mark_r, y+mark_r], fill=color)
            text = str(num)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((x - tw//2, y - th//2), text, fill='white', font=font)

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
