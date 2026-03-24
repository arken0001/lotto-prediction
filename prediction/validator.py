"""과거 데이터를 사용한 예측 성능 백테스트 모듈"""

import numpy as np
import pandas as pd
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from analysis.scorer import WeightedScorer
from prediction.generator import PredictionGenerator


class PredictionValidator:
    """과거 데이터 기반 예측 성능 백테스트"""

    def backtest(self, df: pd.DataFrame, test_rounds: int = 50,
                 num_sets: int = 5, progress_callback=None) -> dict:
        """마지막 N회차에 대한 백테스트

        각 회차에 대해:
        1. 해당 회차 이전 데이터만으로 분석/예측
        2. 실제 당첨번호와 비교
        3. 적중 개수 기록

        Args:
            df: 전체 데이터 DataFrame
            test_rounds: 테스트할 회차 수
            num_sets: 각 회차당 예측 세트 수
            progress_callback: 진행상황 콜백 (current, total)

        Returns:
            백테스트 결과 딕셔너리
        """
        total = len(df)
        if test_rounds >= total:
            test_rounds = total - 100  # 최소 100회 학습 데이터 확보

        match_counts = []  # 각 회차별 최대 적중 수
        all_match_details = []  # 모든 세트의 적중 수

        for i in range(test_rounds):
            idx = total - test_rounds + i

            # 학습 데이터: 해당 회차 이전까지
            train_df = df.iloc[:idx].copy()
            if len(train_df) < 50:
                continue

            # 실제 당첨번호
            actual = sorted(df.iloc[idx][config.NUMBER_COLUMNS].tolist())

            # 예측 생성
            scorer = WeightedScorer(train_df)
            generator = PredictionGenerator(scorer)
            predictions = generator.generate_predictions(num_sets=num_sets)

            # 적중 수 계산
            best_match = 0
            for pred_numbers, _ in predictions:
                matches = len(set(pred_numbers) & set(actual))
                all_match_details.append(matches)
                best_match = max(best_match, matches)

            match_counts.append(best_match)

            if progress_callback:
                progress_callback(i + 1, test_rounds)

        if not match_counts:
            return {'error': '백테스트 데이터 부족'}

        # 적중 분포 계산
        match_dist = Counter(all_match_details)
        total_predictions = len(all_match_details)

        # 무작위 기대값 계산 (초기하분포)
        # E(적중) = 6 * 6 / 45 ≈ 0.8
        random_expected = (config.NUMBERS_PER_DRAW ** 2) / config.MAX_NUMBER

        avg_match = np.mean(all_match_details)
        avg_best_match = np.mean(match_counts)

        return {
            'test_rounds': test_rounds,
            'num_sets_per_round': num_sets,
            'total_predictions': total_predictions,
            'avg_match': float(avg_match),
            'avg_best_match': float(avg_best_match),
            'max_match': int(max(match_counts)),
            'random_expected': float(random_expected),
            'improvement_pct': float((avg_match - random_expected) / random_expected * 100),
            'match_distribution': {
                k: {'count': v, 'pct': v / total_predictions * 100}
                for k, v in sorted(match_dist.items())
            },
            'best_match_distribution': dict(Counter(match_counts)),
        }

    def compare_with_random(self, df: pd.DataFrame,
                            n_simulations: int = 1000) -> dict:
        """무작위 선택 대비 성능 비교

        Args:
            df: 전체 데이터
            n_simulations: 무작위 시뮬레이션 횟수

        Returns:
            비교 결과
        """
        # 마지막 50회차로 테스트
        test_rounds = min(50, len(df) - 100)
        total = len(df)

        random_matches = []
        for _ in range(n_simulations):
            idx = np.random.randint(100, total)
            actual = set(df.iloc[idx][config.NUMBER_COLUMNS].tolist())

            # 무작위로 6개 번호 선택
            random_pick = set(np.random.choice(
                range(config.MIN_NUMBER, config.MAX_NUMBER + 1),
                size=config.NUMBERS_PER_DRAW, replace=False
            ))
            random_matches.append(len(random_pick & actual))

        return {
            'random_avg_match': float(np.mean(random_matches)),
            'random_max_match': int(max(random_matches)),
            'random_distribution': dict(Counter(random_matches)),
        }
