"""번호별 출현 빈도를 분석하는 모듈"""

import numpy as np
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class FrequencyAnalyzer:
    """번호별 출현 빈도 분석"""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.all_numbers = self._extract_all_numbers(df)
        self.total_rounds = len(df)

    def _extract_all_numbers(self, df: pd.DataFrame) -> list[int]:
        """DataFrame에서 모든 당첨번호를 1차원 리스트로 추출"""
        nums = []
        for col in config.NUMBER_COLUMNS:
            nums.extend(df[col].tolist())
        return nums

    def total_frequency(self) -> dict[int, int]:
        """1~45 각 번호의 전체 기간 출현 횟수"""
        freq = {n: 0 for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1)}
        for n in self.all_numbers:
            freq[n] += 1
        return freq

    def recent_frequency(self, n: int = None) -> dict[int, int]:
        """최근 N회차 출현 빈도

        Args:
            n: 최근 회차 수 (기본값: config.RECENT_N)
        """
        n = n or config.RECENT_N
        recent_df = self.df.tail(n)
        recent_nums = self._extract_all_numbers(recent_df)

        freq = {num: 0 for num in range(config.MIN_NUMBER, config.MAX_NUMBER + 1)}
        for num in recent_nums:
            freq[num] += 1
        return freq

    def moving_average_trend(self, window: int = None) -> dict[int, float]:
        """이동 평균 기반 번호별 트렌드 점수

        최근 window 기간의 출현율과 전체 기간 출현율을 비교하여
        상승/하락 트렌드를 점수화한다.

        Returns:
            번호별 트렌드 점수 (-1.0 ~ 1.0). 양수=상승 추세, 음수=하락 추세
        """
        window = window or config.MOVING_AVG_WINDOW

        # 전체 기간 기대 출현율 (6개/45개 = 약 0.133)
        expected_rate = config.NUMBERS_PER_DRAW / config.MAX_NUMBER

        # 최근 window 회차에서의 출현율
        recent_df = self.df.tail(window)
        recent_freq = self._extract_all_numbers(recent_df)

        trend = {}
        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            recent_count = recent_freq.count(n) if isinstance(recent_freq, list) else 0
            recent_rate = recent_count / window if window > 0 else 0

            # 트렌드: 최근 출현율 - 기대 출현율 (정규화)
            trend[n] = (recent_rate - expected_rate) / expected_rate if expected_rate > 0 else 0

        return trend

    def hot_cold_classification(self, recent_n: int = None) -> dict[int, str]:
        """각 번호를 'hot', 'warm', 'cold'로 분류"""
        recent_n = recent_n or config.RECENT_N
        recent_freq = self.recent_frequency(recent_n)

        # 기대 출현 횟수: recent_n * 6 / 45
        expected = recent_n * config.NUMBERS_PER_DRAW / config.MAX_NUMBER

        classification = {}
        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            count = recent_freq[n]
            if count >= expected * config.HOT_THRESHOLD:
                classification[n] = 'hot'
            elif count <= expected * config.COLD_THRESHOLD:
                classification[n] = 'cold'
            else:
                classification[n] = 'warm'

        return classification

    def get_scores(self) -> dict[int, float]:
        """빈도 분석 기반 1~45 번호별 점수 (0~100)

        점수 구성:
        - 전체 빈도 점수 (30%)
        - 최근 빈도 점수 (40%)
        - 트렌드 점수 (30%)
        """
        total_freq = self.total_frequency()
        recent_freq = self.recent_frequency()
        trend = self.moving_average_trend()

        # 각 지표를 0~100으로 정규화
        total_scores = self._normalize(total_freq)
        recent_scores = self._normalize(recent_freq)
        trend_scores = self._normalize_trend(trend)

        # 가중 합산
        scores = {}
        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            scores[n] = (
                0.30 * total_scores[n] +
                0.40 * recent_scores[n] +
                0.30 * trend_scores[n]
            )

        return scores

    def _normalize(self, values: dict[int, int | float]) -> dict[int, float]:
        """값들을 0~100 범위로 정규화"""
        vals = list(values.values())
        min_v, max_v = min(vals), max(vals)
        rng = max_v - min_v if max_v != min_v else 1

        return {k: (v - min_v) / rng * 100 for k, v in values.items()}

    def _normalize_trend(self, trend: dict[int, float]) -> dict[int, float]:
        """트렌드 값(-1~1)을 0~100 범위로 변환"""
        vals = list(trend.values())
        min_v, max_v = min(vals), max(vals)
        rng = max_v - min_v if max_v != min_v else 1

        return {k: (v - min_v) / rng * 100 for k, v in trend.items()}
