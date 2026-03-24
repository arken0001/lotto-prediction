"""로또 용지 마킹 PDF/이미지 생성 모듈

실제 로또 6/45 용지 규격에 맞춰 번호를 마킹한 PDF를 생성한다.
레이저 프린터 수동급지로 로또 용지에 직접 인쇄 가능.

용지 규격 (세로형):
- 전체: 약 62mm x 155mm
- 5개 게임 구역 (A~E) 세로 배치
- 번호 배치: 7열 x 7행 (오른쪽→왼쪽, 위→아래)
  1행: 1, 2, 3, 4, 5, 6, 7  (오른쪽부터)
  7행: 43, 44, 45 (3개만)

⚠️ 프린터마다 여백이 다르므로 OFFSET_X, OFFSET_Y로 미세 조정 필요
"""

from PIL import Image, ImageDraw, ImageFont
import io
from pathlib import Path

# ── 용지 규격 (mm 단위) ──
PAPER_W_MM = 62     # 용지 폭
PAPER_H_MM = 155    # 용지 높이

# ── DPI 설정 ──
DPI = 600  # 레이저 프린터 해상도

# ── mm → px 변환 ──
def mm(v): return int(v * DPI / 25.4)

# ── 게임 구역 A~E 설정 ──
# 각 구역의 상단 Y 위치 (mm, 용지 상단 기준)
# 사진 기준 추정치 - 실측 후 조정 필요
SECTION_TOP_MM = [28, 53.5, 79, 104.5, 130]  # A, B, C, D, E
SECTION_H_MM = 22      # 각 구역 높이

# ── 번호 그리드 설정 (각 구역 내 상대 좌표, mm) ──
# 번호 1이 우측 상단에 위치
GRID_RIGHT_MM = 57     # 1번 열(가장 오른쪽)의 X 위치 (용지 왼쪽 기준)
GRID_TOP_MM = 1.5      # 1번 행(가장 위)의 Y 위치 (구역 상단 기준)
COL_STEP_MM = 4.3      # 열 간격 (오른쪽→왼쪽이므로 빼기)
ROW_STEP_MM = 2.9      # 행 간격

# ── 마킹 설정 ──
MARK_SIZE_MM = 2.2     # 마킹 사각형/원 크기

# ── 프린터 보정값 (mm) ──
# 프린터마다 다름 - 테스트 인쇄 후 조정
OFFSET_X_MM = 0.0      # + → 오른쪽 이동
OFFSET_Y_MM = 0.0      # + → 아래로 이동


def number_to_pos(num: int, section_idx: int) -> tuple[float, float]:
    """번호(1~45)의 용지 상 절대 좌표(mm)를 반환

    Args:
        num: 로또 번호 (1~45)
        section_idx: 게임 구역 인덱스 (0=A, 1=B, ..., 4=E)

    Returns:
        (x_mm, y_mm) 용지 왼쪽 상단 기준 좌표
    """
    row = (num - 1) // 7     # 0~6
    col = (num - 1) % 7      # 0~6 (0=가장 오른쪽)

    section_top = SECTION_TOP_MM[section_idx]

    # X: 오른쪽에서 왼쪽으로 (1번이 오른쪽)
    x = GRID_RIGHT_MM - col * COL_STEP_MM + OFFSET_X_MM
    # Y: 위에서 아래로
    y = section_top + GRID_TOP_MM + row * ROW_STEP_MM + OFFSET_Y_MM

    return (x, y)


def create_marking_image(game_sets: list[list[int]]) -> Image.Image:
    """마킹만 있는 투명/흰색 이미지 생성 (용지 위에 겹쳐 인쇄)

    Args:
        game_sets: 최대 5세트 [[n1,...,n6], ...]

    Returns:
        PIL Image (용지 크기, 마킹만 포함)
    """
    w = mm(PAPER_W_MM)
    h = mm(PAPER_H_MM)

    # 흰색 배경 (실제 인쇄 시 마킹 부분만 토너 사용)
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)

    mark_r = mm(MARK_SIZE_MM) // 2

    for section_idx, numbers in enumerate(game_sets[:5]):
        for num in numbers:
            if not (1 <= num <= 45):
                continue

            x_mm, y_mm = number_to_pos(num, section_idx)
            cx = mm(x_mm)
            cy = mm(y_mm)

            # 검은 원으로 마킹 (OMR 인식용)
            draw.ellipse(
                [cx - mark_r, cy - mark_r, cx + mark_r, cy + mark_r],
                fill='black'
            )

    return img


def create_preview_image(game_sets: list[list[int]]) -> Image.Image:
    """미리보기용 이미지 (번호 그리드 + 마킹 표시)

    Args:
        game_sets: 최대 5세트

    Returns:
        PIL Image (미리보기용, 그리드 포함)
    """
    w = mm(PAPER_W_MM)
    h = mm(PAPER_H_MM)

    img = Image.new('RGB', (w, h), '#fafafa')
    draw = ImageDraw.Draw(img)

    mark_r = mm(MARK_SIZE_MM) // 2
    dot_r = mm(0.5)

    try:
        font = ImageFont.truetype("arial.ttf", mm(1.5))
        label_font = ImageFont.truetype("arial.ttf", mm(2.5))
    except Exception:
        font = ImageFont.load_default()
        label_font = font

    # 각 구역 그리기
    for sec_idx in range(5):
        sec_top = mm(SECTION_TOP_MM[sec_idx])
        sec_label = chr(ord('A') + sec_idx)

        # 구역 테두리
        draw.rectangle(
            [mm(2), sec_top - mm(1), mm(PAPER_W_MM - 2), sec_top + mm(SECTION_H_MM)],
            outline='#ccc', width=2
        )
        # 구역 라벨
        draw.text((mm(PAPER_W_MM - 5), sec_top - mm(0.5)),
                  sec_label, fill='#e44', font=label_font)

        # 번호 그리드
        for num in range(1, 46):
            x_mm, y_mm = number_to_pos(num, sec_idx)
            cx = mm(x_mm)
            cy = mm(y_mm)

            # 빈 원
            draw.ellipse(
                [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
                outline='#ccc', width=1
            )
            # 번호 텍스트
            text = str(num)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((cx - tw // 2, cy + dot_r + mm(0.2)),
                     text, fill='#aaa', font=font)

    # 선택된 번호 마킹
    for sec_idx, numbers in enumerate(game_sets[:5]):
        for num in numbers:
            if not (1 <= num <= 45):
                continue
            x_mm, y_mm = number_to_pos(num, sec_idx)
            cx = mm(x_mm)
            cy = mm(y_mm)
            draw.ellipse(
                [cx - mark_r, cy - mark_r, cx + mark_r, cy + mark_r],
                fill='black'
            )

    return img


def image_to_bytes(img: Image.Image, fmt: str = 'PNG') -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, dpi=(DPI, DPI))
    buf.seek(0)
    return buf.getvalue()


def generate_lotto_paper(predictions: list[list[int]], preview: bool = True) -> bytes:
    """로또 용지 마킹 이미지 생성

    Args:
        predictions: [[n1,...,n6], ...] 최대 5세트
        preview: True=미리보기(그리드 포함), False=인쇄용(마킹만)

    Returns:
        PNG 이미지 바이트
    """
    if preview:
        img = create_preview_image(predictions)
    else:
        img = create_marking_image(predictions)
    return image_to_bytes(img)


# ── ESC/POS 영수증 출력 ──
def generate_escpos_data(predictions: list[list[int]],
                         round_no: int = None) -> bytes:
    """XP-DT108B ESC/POS 영수증 출력 데이터"""
    ESC = b'\x1b'
    GS = b'\x1d'

    data = b''
    data += ESC + b'@'           # 초기화
    data += ESC + b'a\x01'       # 중앙 정렬
    data += ESC + b'E\x01'       # 굵게
    data += b'=== LOTTO 6/45 ===\n'
    data += ESC + b'E\x00'

    if round_no:
        line = f'제{round_no}회 예측\n'
        data += line.encode('euc-kr', errors='replace')

    data += b'------------------------\n'
    data += ESC + b'a\x00'       # 왼쪽 정렬

    for i, nums in enumerate(predictions[:5], 1):
        label = chr(ord('A') + i - 1)
        nums_str = ' '.join(f'{n:02d}' for n in sorted(nums))
        data += f' {label}: {nums_str}\n'.encode('euc-kr', errors='replace')

    data += b'------------------------\n'
    data += ESC + b'a\x01'

    from datetime import datetime
    data += datetime.now().strftime('%Y-%m-%d %H:%M\n').encode()
    data += b'\n\n\n'
    data += GS + b'V\x00'       # 용지 컷

    return data
