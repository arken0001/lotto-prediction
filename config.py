"""로또 6/45 예측 프로그램 설정"""

# === 데이터 수집 설정 ===
API_BASE_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}"
DATA_DIR = "data"
CACHE_FILE = "data/lotto_history.csv"
API_DELAY = 0.5  # API 호출 간격 (초)
MAX_RETRIES = 3

# === 분석 설정 ===
RECENT_N = 20              # '최근' 기준 회차 수
MOVING_AVG_WINDOW = 10     # 이동평균 윈도우
HOT_THRESHOLD = 1.5        # hot number 기준 (기대값 대비 배수)
COLD_THRESHOLD = 0.5       # cold number 기준

# === 번호 범위 상수 ===
MIN_NUMBER = 1
MAX_NUMBER = 45
NUMBERS_PER_DRAW = 6
LOW_RANGE = (1, 22)
HIGH_RANGE = (23, 45)
SECTIONS = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 45)]
PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43}

# === 가중치 설정 ===
SCORING_WEIGHTS = {
    'frequency': 0.25,
    'gap': 0.25,
    'trend': 0.20,
    'pattern_bonus': 0.15,
    'overdue_bonus': 0.15,
}

# === 조합 필터링 설정 ===
SUM_RANGE_SIGMA = 1.5      # 합계 범위: 평균 ± N*표준편차
MIN_AC_VALUE = 6            # 최소 AC값
ALLOWED_ODD_EVEN = [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)]  # 허용 홀짝 비율
ALLOWED_HIGH_LOW = [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)]  # 허용 고저 비율
MAX_SAME_SECTION = 3        # 한 구간 최대 번호 수

# === 예측 설정 ===
NUM_PREDICTION_SETS = 5     # 생성할 예측 세트 수
MAX_GENERATION_ATTEMPTS = 10000  # 조합 생성 최대 시도
SOFTMAX_TEMPERATURE = 2.0   # 점수→확률 변환 온도 (높을수록 다양한 조합)

# === 번호 컬럼명 ===
NUMBER_COLUMNS = ['n1', 'n2', 'n3', 'n4', 'n5', 'n6']
