"""각 번호의 미출현 간격을 분석하는 모듈"""

import numpy as np
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class GapAnalyzer:
    """각 번호의 미출현 간격 분석"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.sort_values('round').reset_index(drop=True)
        self.total_rounds = len(df)
        # 각 번호가 출현한 회차 인덱스 목록을 미리 계산
        self._appearance_indices = self._build_appearance_map()

    def _build_appearance_map(self) -> dict[int, list[int]]:
        """각 번호가 출현한 회차의 인덱스 목록"""
        appearances = {n: [] for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1)}

        for idx, row in self.df.iterrows():
            for col in config.NUMBER_COLUMNS:
                num = int(row[col])
                appearances[num].append(idx)

        return appearances

    def current_gap(self) -> dict[int, int]:
        """각 번호의 현재 미출현 기간 (마지막 출현 이후 경과 회차 수)"""
        last_idx = self.total_rounds - 1
        gaps = {}

        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            indices = self._appearance_indices[n]
            if indices:
                gaps[n] = last_idx - indices[-1]
            else:
                gaps[n] = self.total_rounds  # 한 번도 안 나온 번호

        return gaps

    def average_gap(self) -> dict[int, float]:
        """각 번호의 평균 출현 간격"""
        avg_gaps = {}

        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            indices = self._appearance_indices[n]
            if len(indices) < 2:
                # 기대 간격: 45/6 ≈ 7.5
                avg_gaps[n] = config.MAX_NUMBER / config.NUMBERS_PER_DRAW
                continue

            # 연속 출현 간의 간격 계산
            gaps = [indices[i+1] - indices[i] for i in range(len(indices) - 1)]
            avg_gaps[n] = np.mean(gaps)

        return avg_gaps

    def max_gap(self) -> dict[int, int]:
        """각 번호의 역대 최대 미출현 기간"""
        max_gaps = {}

        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            indices = self._appearance_indices[n]
            if len(indices) < 2:
                max_gaps[n] = self.total_rounds
                continue

            gaps = [indices[i+1] - indices[i] for i in range(len(indices) - 1)]
            max_gaps[n] = max(gaps)

        return max_gaps

    def overdue_ratio(self) -> dict[int, float]:
        """미출현 비율 = 현재 미출현 기간 / 평균 출현 간격

        1.0 이상: 평균보다 오래 미출현 (overdue)
        2.0 이상: 강한 overdue 상태
        """
        cur_gaps = self.current_gap()
        avg_gaps = self.average_gap()

        ratios = {}
        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            avg = avg_gaps[n]
            if avg > 0:
                ratios[n] = cur_gaps[n] / avg
            else:
                ratios[n] = 0.0

        return ratios

    def get_scores(self) -> dict[int, float]:
        """간격 분석 기반 1~45 번호별 점수 (0~100)

        overdue_ratio 기반 종 모양(bell curve) 점수 분포:
        - 최적 구간: 1.2 ~ 2.0 (가장 높은 점수)
        - 너무 최근(0~0.3): 낮은 점수
        - 극단적 미출현(3.0+): 점수 감소
        """
        ratios = self.overdue_ratio()

        scores = {}
        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            r = ratios[n]
            # 가우시안 형태: 최적점 1.5에서 최대, σ=0.8
            optimal = 1.5
            sigma = 0.8
            score = np.exp(-0.5 * ((r - optimal) / sigma) ** 2) * 100
            scores[n] = score

        return scores

    def get_overdue_numbers(self, threshold: float = 1.5) -> list[tuple[int, float]]:
        """overdue 상태인 번호 목록 반환

        Args:
            threshold: overdue 기준 비율

        Returns:
            [(번호, overdue_ratio)] 내림차순 정렬
        """
        ratios = self.overdue_ratio()
        overdue = [(n, r) for n, r in ratios.items() if r >= threshold]
        return sorted(overdue, key=lambda x: x[1], reverse=True)
