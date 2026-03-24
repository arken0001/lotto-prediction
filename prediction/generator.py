"""종합 점수 기반으로 예측 조합을 생성하는 모듈"""

import numpy as np
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from analysis.scorer import WeightedScorer


class PredictionGenerator:
    """가중 확률 샘플링 + 필터링으로 예측 조합 생성"""

    def __init__(self, scorer: WeightedScorer):
        self.scorer = scorer
        self.combo_analyzer = scorer.combo_analyzer
        self.pattern_constraints = scorer.pattern_analyzer.get_pattern_constraints()

    def generate_predictions(self, num_sets: int = None,
                             temperature: float = None) -> list[tuple[list[int], float]]:
        """예측 조합 생성

        Args:
            num_sets: 생성할 세트 수 (기본값: config.NUM_PREDICTION_SETS)
            temperature: softmax 온도 (기본값: config.SOFTMAX_TEMPERATURE)

        Returns:
            [(정렬된 번호 리스트, 적합도 점수), ...] 적합도 내림차순
        """
        num_sets = num_sets or config.NUM_PREDICTION_SETS
        temperature = temperature or config.SOFTMAX_TEMPERATURE

        # 번호별 점수 → 확률 분포 (softmax)
        scores = self.scorer.calculate_number_scores()
        numbers = list(range(config.MIN_NUMBER, config.MAX_NUMBER + 1))
        score_values = np.array([scores[n] for n in numbers])
        probabilities = self._softmax(score_values, temperature)

        # 유효 조합 수집
        predictions = []
        attempts = 0

        while len(predictions) < num_sets and attempts < config.MAX_GENERATION_ATTEMPTS:
            attempts += 1

            # 가중 확률 샘플링 (비복원)
            sampled_indices = np.random.choice(
                len(numbers), size=config.NUMBERS_PER_DRAW,
                replace=False, p=probabilities
            )
            sampled = sorted([numbers[i] for i in sampled_indices])

            # 유효성 검사
            if self._validate_set(sampled):
                # 중복 조합 체크
                if sampled not in [p[0] for p in predictions]:
                    fitness = self._calculate_fitness(sampled, scores)
                    predictions.append((sampled, fitness))

        # 적합도 내림차순 정렬
        predictions.sort(key=lambda x: x[1], reverse=True)
        return predictions

    def _softmax(self, scores: np.ndarray, temperature: float) -> np.ndarray:
        """점수를 확률 분포로 변환 (softmax with temperature)"""
        # 수치 안정성을 위해 최대값 빼기
        adjusted = (scores - np.max(scores)) / temperature
        exp_scores = np.exp(adjusted)
        return exp_scores / exp_scores.sum()

    def _validate_set(self, numbers: list[int]) -> bool:
        """생성된 조합의 종합 유효성 검사"""
        result = self.combo_analyzer.validate_combination(numbers)
        return result['overall']

    def _calculate_fitness(self, numbers: list[int],
                           scores: dict[int, float]) -> float:
        """조합의 적합도 점수 산출

        번호별 점수 평균 + 조합 특성 보너스
        """
        # 기본 점수: 선택된 번호들의 평균 점수
        avg_score = np.mean([scores[n] for n in numbers])

        # AC값 보너스 (높을수록 좋음)
        ac = self.combo_analyzer.calc_ac_value(numbers)
        ac_bonus = min(ac / 10 * 5, 5)  # 최대 5점

        # 합계 범위 적합도 보너스
        stats = self.combo_analyzer.sum_range_analysis()
        total = sum(numbers)
        mean = stats['mean']
        std = stats['std']
        # 평균에 가까울수록 높은 보너스
        sum_bonus = max(0, 5 - abs(total - mean) / std * 2)

        return avg_score + ac_bonus + sum_bonus
