"""조합 수준의 통계적 필터링을 수행하는 모듈"""

from itertools import combinations
import numpy as np
import pandas as pd
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class CombinationAnalyzer:
    """조합 수준의 통계적 필터링"""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.draws = df[config.NUMBER_COLUMNS].values.tolist()
        self._sum_stats = None

    # === 합계 범위 분석 ===
    def sum_range_analysis(self) -> dict:
        """역대 당첨번호 합계 통계"""
        if self._sum_stats is None:
            sums = [sum(draw) for draw in self.draws]
            mean = np.mean(sums)
            std = np.std(sums)
            self._sum_stats = {
                'mean': float(mean),
                'std': float(std),
                'min': int(min(sums)),
                'max': int(max(sums)),
                'optimal_range': (
                    int(mean - config.SUM_RANGE_SIGMA * std),
                    int(mean + config.SUM_RANGE_SIGMA * std)
                ),
            }
        return self._sum_stats

    def is_sum_valid(self, numbers: list[int]) -> bool:
        """주어진 6개 번호의 합이 최적 범위 내인지 판단"""
        stats = self.sum_range_analysis()
        total = sum(numbers)
        low, high = stats['optimal_range']
        return low <= total <= high

    # === AC값 (Arithmetic Complexity) 분석 ===
    @staticmethod
    def calc_ac_value(numbers: list[int]) -> int:
        """AC값 계산

        6개 번호에서 2개씩 조합(C(6,2)=15쌍)의 차이값 중
        중복을 제거한 고유 차이값의 수 - (6-1)

        범위: 0 ~ 10
        """
        diffs = set()
        nums = sorted(numbers)
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                diffs.add(nums[j] - nums[i])

        return len(diffs) - (len(numbers) - 1)

    def ac_value_distribution(self) -> dict[int, float]:
        """역대 당첨번호의 AC값 분포 (%)"""
        ac_counts = Counter()
        for draw in self.draws:
            ac = self.calc_ac_value(draw)
            ac_counts[ac] += 1

        total = len(self.draws)
        return {ac: count / total * 100 for ac, count in sorted(ac_counts.items())}

    def optimal_ac_range(self) -> tuple[int, int]:
        """최적 AC값 범위 (보통 7~10)"""
        dist = self.ac_value_distribution()
        # 상위 80% 커버하는 범위
        sorted_ac = sorted(dist.items(), key=lambda x: x[1], reverse=True)
        cumulative = 0
        ac_values = []
        for ac, pct in sorted_ac:
            ac_values.append(ac)
            cumulative += pct
            if cumulative >= 80:
                break
        return (min(ac_values), max(ac_values))

    # === 소수/합성수 비율 ===
    def prime_composite_distribution(self) -> dict[str, float]:
        """소수:합성수(1 포함) 비율 분포 (%)"""
        dist = Counter()
        for draw in self.draws:
            prime_count = sum(1 for n in draw if n in config.PRIMES)
            composite_count = config.NUMBERS_PER_DRAW - prime_count
            dist[f"{prime_count}:{composite_count}"] += 1

        total = len(self.draws)
        return {k: v / total * 100 for k, v in sorted(dist.items())}

    def optimal_prime_range(self) -> list[int]:
        """가장 흔한 소수 개수 범위"""
        dist = self.prime_composite_distribution()
        sorted_dist = sorted(dist.items(), key=lambda x: x[1], reverse=True)
        # 상위 80% 커버
        cumulative = 0
        prime_counts = []
        for ratio_str, pct in sorted_dist:
            prime_count = int(ratio_str.split(':')[0])
            prime_counts.append(prime_count)
            cumulative += pct
            if cumulative >= 80:
                break
        return sorted(prime_counts)

    # === 종합 유효성 검사 ===
    def validate_combination(self, numbers: list[int]) -> dict[str, bool]:
        """조합의 종합 유효성 검사"""
        # 합계 검사
        sum_valid = self.is_sum_valid(numbers)

        # AC값 검사
        ac = self.calc_ac_value(numbers)
        ac_valid = ac >= config.MIN_AC_VALUE

        # 홀짝 검사
        odd = sum(1 for n in numbers if n % 2 == 1)
        even = config.NUMBERS_PER_DRAW - odd
        odd_even_valid = (odd, even) in config.ALLOWED_ODD_EVEN

        # 고저 검사
        low = sum(1 for n in numbers if config.LOW_RANGE[0] <= n <= config.LOW_RANGE[1])
        high = config.NUMBERS_PER_DRAW - low
        high_low_valid = (low, high) in config.ALLOWED_HIGH_LOW

        # 구간 집중도 검사
        section_valid = True
        for s_start, s_end in config.SECTIONS:
            cnt = sum(1 for n in numbers if s_start <= n <= s_end)
            if cnt > config.MAX_SAME_SECTION:
                section_valid = False
                break

        # 소수 비율 검사
        prime_count = sum(1 for n in numbers if n in config.PRIMES)
        prime_range = self.optimal_prime_range()
        prime_valid = prime_count in prime_range if prime_range else True

        overall = all([sum_valid, ac_valid, odd_even_valid,
                       high_low_valid, section_valid, prime_valid])

        return {
            'sum_valid': sum_valid,
            'ac_valid': ac_valid,
            'odd_even_valid': odd_even_valid,
            'high_low_valid': high_low_valid,
            'section_valid': section_valid,
            'prime_valid': prime_valid,
            'overall': overall,
            'ac_value': ac,
            'sum': sum(numbers),
        }
