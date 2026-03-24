"""모든 분석 결과를 종합하여 번호별 최종 점수를 산출하는 모듈"""

import numpy as np
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from analysis.frequency import FrequencyAnalyzer
from analysis.gap import GapAnalyzer
from analysis.pattern import PatternAnalyzer
from analysis.combination import CombinationAnalyzer


class WeightedScorer:
    """모든 분석 결과를 가중치로 종합하여 번호별 최종 점수 산출"""

    def __init__(self, df: pd.DataFrame, weights: dict = None):
        self.df = df
        self.weights = weights or config.SCORING_WEIGHTS

        # 각 분석기 초기화
        self.freq_analyzer = FrequencyAnalyzer(df)
        self.gap_analyzer = GapAnalyzer(df)
        self.pattern_analyzer = PatternAnalyzer(df)
        self.combo_analyzer = CombinationAnalyzer(df)

    def calculate_number_scores(self) -> dict[int, float]:
        """1~45 각 번호의 가중 종합 점수 계산

        각 분석기에서 0~100 정규화 점수를 받아 가중 합산 후
        최종 점수를 0~100으로 재정규화한다.
        """
        # 각 분석기의 점수 (모두 0~100 범위)
        freq_scores = self.freq_analyzer.get_scores()
        gap_scores = self.gap_analyzer.get_scores()
        pattern_scores = self.pattern_analyzer.get_scores()

        # 트렌드 점수 (frequency 내부의 이동평균 기반)
        trend_raw = self.freq_analyzer.moving_average_trend()
        trend_scores = self.freq_analyzer._normalize_trend(trend_raw)

        # Overdue 보너스 (gap의 overdue_ratio 기반 추가 점수)
        overdue_ratios = self.gap_analyzer.overdue_ratio()
        overdue_scores = {}
        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            r = overdue_ratios[n]
            # 1.0~2.5 범위에서 보너스, 가우시안 피크 1.8
            overdue_scores[n] = np.exp(-0.5 * ((r - 1.8) / 0.7) ** 2) * 100

        # 가중 합산
        scores = {}
        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            scores[n] = (
                self.weights['frequency'] * freq_scores[n] +
                self.weights['gap'] * gap_scores[n] +
                self.weights['trend'] * trend_scores[n] +
                self.weights['pattern_bonus'] * pattern_scores[n] +
                self.weights['overdue_bonus'] * overdue_scores[n]
            )

        # 최종 0~100 정규화
        vals = list(scores.values())
        min_v, max_v = min(vals), max(vals)
        rng = max_v - min_v if max_v != min_v else 1
        return {k: (v - min_v) / rng * 100 for k, v in scores.items()}

    def get_top_numbers(self, n: int = 15) -> list[tuple[int, float]]:
        """상위 N개 번호와 점수를 반환 (내림차순)"""
        scores = self.calculate_number_scores()
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:n]

    def generate_analysis_report(self) -> dict:
        """전체 분석 리포트 생성"""
        scores = self.calculate_number_scores()
        top_numbers = self.get_top_numbers(15)
        classification = self.freq_analyzer.hot_cold_classification()
        overdue = self.gap_analyzer.get_overdue_numbers(1.5)
        sum_stats = self.combo_analyzer.sum_range_analysis()
        ac_range = self.combo_analyzer.optimal_ac_range()
        pattern_constraints = self.pattern_analyzer.get_pattern_constraints()

        # hot/cold 번호 추출
        hot_numbers = [n for n, c in classification.items() if c == 'hot']
        cold_numbers = [n for n, c in classification.items() if c == 'cold']
        overdue_numbers = [n for n, r in overdue[:10]]

        return {
            'total_rounds': self.freq_analyzer.total_rounds,
            'last_round': int(self.df['round'].max()),
            'number_scores': scores,
            'top_numbers': top_numbers,
            'hot_numbers': sorted(hot_numbers),
            'cold_numbers': sorted(cold_numbers),
            'overdue_numbers': sorted(overdue_numbers),
            'sum_stats': sum_stats,
            'ac_range': ac_range,
            'pattern_constraints': pattern_constraints,
            'odd_even_dist': self.pattern_analyzer.odd_even_distribution(),
            'high_low_dist': self.pattern_analyzer.high_low_distribution(),
        }
