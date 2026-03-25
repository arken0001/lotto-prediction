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
SECTION_X_START = [33.0, 65.0, 97.0, 129.0, 161.0]  # 각 구역 1열(1번) 중심 X
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
    """미리보기용 이미지 (실제 로또 용지 스타일)"""
    preview_dpi = 250
    def pmm(v): return int(v * preview_dpi / 25.4)

    w, h = pmm(PAPER_W_MM), pmm(PAPER_H_MM)
    img = Image.new('RGB', (w, h), '#fefefe')
    draw = ImageDraw.Draw(img)
    mark_r = pmm(MARK_SIZE_MM) // 2

    # 글꼴
    try:
        num_font = ImageFont.truetype("arial.ttf", pmm(2.0))
        label_font = ImageFont.truetype("arialbd.ttf", pmm(4.5))
        title_font = ImageFont.truetype("arialbd.ttf", pmm(3.0))
    except Exception:
        num_font = ImageFont.load_default()
        label_font = num_font
        title_font = num_font

    # 용지 테두리
    draw.rectangle([1, 1, w-2, h-2], outline='#ccc', width=2)

    # 상단 타이틀
    draw.text((pmm(5), pmm(2)), "Lotto 6/45", fill='#e44', font=title_font)

    # 셀 크기
    cell_w = pmm(COL_STEP_MM)
    cell_h = pmm(ROW_STEP_MM)
    bracket_pad = pmm(0.3)

    # 선택된 번호 세트 (빠른 조회용)
    selected = {}
    for sec_idx, numbers in enumerate(game_sets[:5]):
        for num in numbers:
            selected[(sec_idx, num)] = True

    # 5개 구역
    for sec_idx in range(5):
        sec_label = chr(65 + sec_idx)
        sx = pmm(SECTION_X_START[sec_idx])
        sy = pmm(SECTION_Y_START)

        # 구역 외곽선 (빨간)
        grid_left = sx - pmm(1.5)
        grid_right = sx + pmm(COL_STEP_MM * 6 + 1.5)
        grid_top = sy - pmm(1.5)
        grid_bot = sy + pmm(ROW_STEP_MM * 6 + 1.5)
        draw.rectangle([grid_left, grid_top, grid_right, grid_bot],
                       outline='#e88', width=2)

        # 구역 라벨 + 1,000원
        label_x = grid_right - pmm(7)
        draw.rectangle([grid_right - pmm(8), grid_top - pmm(6),
                        grid_right, grid_top],
                       fill='#e44')
        bbox = draw.textbbox((0, 0), sec_label, font=label_font)
        tw = bbox[2] - bbox[0]
        draw.text((grid_right - pmm(4) - tw//2, grid_top - pmm(5.5)),
                  sec_label, fill='white', font=label_font)

        # 45개 번호
        for num in range(1, 46):
            row = (num - 1) // 7
            col = (num - 1) % 7
            cx = pmm(SECTION_X_START[sec_idx] + col * COL_STEP_MM + OFFSET_X_MM)
            cy = pmm(SECTION_Y_START + row * ROW_STEP_MM + OFFSET_Y_MM)

            is_selected = (sec_idx, num) in selected

            # 사각 괄호 [ ] 그리기
            bx1 = cx - cell_w // 2 + bracket_pad
            by1 = cy - cell_h // 2 + bracket_pad
            bx2 = cx + cell_w // 2 - bracket_pad
            by2 = cy + cell_h // 2 - bracket_pad

            if is_selected:
                # 선택됨: 검은 채움 (실제 마킹)
                draw.rectangle([bx1, by1, bx2, by2], fill='#222')
                text_color = 'white'
            else:
                # 미선택: 연회색 괄호
                draw.rectangle([bx1, by1, bx2, by2], outline='#bbb', width=1)
                text_color = '#888'

            # 번호 텍스트
            text = str(num)
            bbox = draw.textbbox((0, 0), text, font=num_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((cx - tw//2, cy - th//2), text, fill=text_color, font=num_font)

    # 하단 안내문
    draw.text((pmm(20), pmm(PAPER_H_MM - 6)),
              "- 발행기관: 복권위원회                         - 한 복권당 가격은 1,000원입니다.",
              fill='#999', font=num_font)

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
