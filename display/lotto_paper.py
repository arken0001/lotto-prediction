"""로또 용지 마킹 이미지 생성 모듈

로또 6/45 용지에 예측 번호를 마킹한 이미지를 생성한다.
X-Printer 또는 일반 프린터로 출력할 수 있는 이미지/PDF 형태.

용지 규격 (실측 기준):
- 전체 용지: 약 190mm x 95mm
- 게임 구역: A~E 5개 (각 약 32mm 폭)
- 번호 배치: 7열 x 7행 (마지막 행은 43,44,45 3개만)
- 번호 간격: 약 4mm
- 마킹 원 크기: 약 3mm 직경
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import io

# ── 용지 규격 (픽셀 단위, 300DPI 기준) ──
DPI = 300
MM_TO_PX = DPI / 25.4  # 1mm = 약 11.81px

# 전체 용지 크기
PAPER_W = int(190 * MM_TO_PX)  # ~2244px
PAPER_H = int(95 * MM_TO_PX)   # ~1122px

# 게임 구역 설정 (A~E, 5개)
# 각 구역의 X 시작 위치 (mm)
GAME_X_STARTS_MM = [19, 52, 86, 120, 153]
GAME_W_MM = 30  # 각 게임 구역 폭

# 번호 그리드 시작 Y 위치 (mm) - 구역 내 상대적
GRID_START_Y_MM = 8    # 첫 번째 행 Y
GRID_STEP_X_MM = 4.2   # 열 간격
GRID_STEP_Y_MM = 4.2   # 행 간격
GRID_START_X_MM = 1.5   # 구역 내 첫 번째 열 X

# 마킹 크기
MARK_RADIUS_MM = 1.5

# 번호 → 그리드 위치 (행, 열) 매핑
# 로또 용지는 7열 x 7행 배치
# 1행: 1,2,3,4,5,6,7
# 2행: 8,9,10,11,12,13,14
# ...
# 7행: 43,44,45 (3개만)
def number_to_grid(num: int) -> tuple[int, int]:
    """번호(1~45)를 (행, 열) 인덱스로 변환 (0-based)"""
    row = (num - 1) // 7
    col = (num - 1) % 7
    return (row, col)


def create_marked_paper(game_sets: list[list[int]],
                        mark_color: str = 'black',
                        paper_bg: str = 'white') -> Image.Image:
    """예측 번호가 마킹된 로또 용지 이미지 생성

    Args:
        game_sets: 최대 5세트의 번호 리스트 [[n1,n2,...,n6], ...]
        mark_color: 마킹 색상
        paper_bg: 배경색

    Returns:
        PIL Image 객체
    """
    # 빈 용지 생성
    img = Image.new('RGB', (PAPER_W, PAPER_H), paper_bg)
    draw = ImageDraw.Draw(img)

    # 구역 경계선 그리기 (가이드)
    for i, x_mm in enumerate(GAME_X_STARTS_MM):
        x = int(x_mm * MM_TO_PX)
        w = int(GAME_W_MM * MM_TO_PX)

        # 구역 테두리
        draw.rectangle(
            [x, int(3 * MM_TO_PX), x + w, int(90 * MM_TO_PX)],
            outline='#ccc', width=1
        )

        # 구역 라벨
        label = chr(ord('A') + i)
        try:
            font = ImageFont.truetype("arial.ttf", int(3 * MM_TO_PX))
        except Exception:
            font = ImageFont.load_default()
        draw.text((x + int(1 * MM_TO_PX), int(1 * MM_TO_PX)),
                  label, fill='#999', font=font)

        # 번호 그리드 가이드 (작은 원)
        for num in range(1, 46):
            row, col = number_to_grid(num)
            cx = x + int((GRID_START_X_MM + col * GRID_STEP_X_MM) * MM_TO_PX)
            cy = int((GRID_START_Y_MM + row * GRID_STEP_Y_MM) * MM_TO_PX)
            r = int(MARK_RADIUS_MM * MM_TO_PX * 0.8)

            # 빈 원 (가이드)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                        outline='#ddd', width=1)

            # 번호 텍스트 (작게)
            try:
                small_font = ImageFont.truetype("arial.ttf", int(1.8 * MM_TO_PX))
            except Exception:
                small_font = ImageFont.load_default()
            text = str(num)
            bbox = draw.textbbox((0, 0), text, font=small_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((cx - tw // 2, cy - th // 2), text,
                     fill='#bbb', font=small_font)

    # 선택된 번호 마킹
    for game_idx, numbers in enumerate(game_sets[:5]):
        if game_idx >= len(GAME_X_STARTS_MM):
            break

        base_x = int(GAME_X_STARTS_MM[game_idx] * MM_TO_PX)

        for num in numbers:
            if not (1 <= num <= 45):
                continue

            row, col = number_to_grid(num)
            cx = base_x + int((GRID_START_X_MM + col * GRID_STEP_X_MM) * MM_TO_PX)
            cy = int((GRID_START_Y_MM + row * GRID_STEP_Y_MM) * MM_TO_PX)
            r = int(MARK_RADIUS_MM * MM_TO_PX)

            # 진한 마킹
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                        fill=mark_color)

    return img


def image_to_bytes(img: Image.Image, format: str = 'PNG') -> bytes:
    """PIL Image를 바이트로 변환"""
    buf = io.BytesIO()
    img.save(buf, format=format, dpi=(DPI, DPI))
    buf.seek(0)
    return buf.getvalue()


def generate_lotto_paper(predictions: list[list[int]]) -> bytes:
    """예측 번호로 로또 용지 마킹 이미지 생성 (PNG 바이트)

    Args:
        predictions: [[n1,n2,...,n6], ...] 최대 5세트

    Returns:
        PNG 이미지 바이트
    """
    img = create_marked_paper(predictions)
    return image_to_bytes(img)


# ── ESC/POS 프린터 직접 출력 (X-Printer 등) ──
def generate_escpos_data(predictions: list[list[int]],
                         round_no: int = None) -> bytes:
    """ESC/POS 형식의 영수증 출력 데이터 생성

    Args:
        predictions: 예측 번호 세트들
        round_no: 대상 회차

    Returns:
        ESC/POS 바이트 데이터
    """
    ESC = b'\x1b'
    GS = b'\x1d'

    data = b''
    # 초기화
    data += ESC + b'@'
    # 중앙 정렬
    data += ESC + b'a\x01'
    # 굵게
    data += ESC + b'E\x01'
    data += b'=== LOTTO 6/45 ===\n'
    data += ESC + b'E\x00'

    if round_no:
        data += f'제{round_no}회 예측\n'.encode('euc-kr', errors='replace')

    data += b'------------------------\n'
    # 왼쪽 정렬
    data += ESC + b'a\x00'

    for i, nums in enumerate(predictions[:5], 1):
        game_label = chr(ord('A') + i - 1)
        nums_str = ' '.join(f'{n:02d}' for n in sorted(nums))
        line = f' {game_label}: {nums_str}\n'
        data += line.encode('euc-kr', errors='replace')

    data += b'------------------------\n'
    data += ESC + b'a\x01'

    from datetime import datetime
    data += datetime.now().strftime('%Y-%m-%d %H:%M\n').encode()
    data += b'\n\n\n'

    # 용지 컷
    data += GS + b'V\x00'

    return data
