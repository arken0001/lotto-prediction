"""당첨번호 패턴을 분석하는 모듈"""

from collections import Counter
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class PatternAnalyzer:
    """당첨번호 패턴 분석 (홀짝, 고저, 구간, 연속번호, 끝수)"""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.total_rounds = len(df)
        # 각 회차의 당첨번호 리스트
        self.draws = df[config.NUMBER_COLUMNS].values.tolist()

    # === 연속번호 분석 ===
    def consecutive_pair_frequency(self) -> dict[tuple, int]:
        """연속번호 쌍의 역대 출현 빈도"""
        pair_count = Counter()
        for draw in self.draws:
            nums = sorted(draw)
            for i in range(len(nums) - 1):
                if nums[i + 1] - nums[i] == 1:
                    pair_count[(nums[i], nums[i + 1])] += 1
        return dict(pair_count)

    def consecutive_probability(self) -> float:
        """당첨번호에 연속번호 쌍이 1개 이상 포함될 확률"""
        count = 0
        for draw in self.draws:
            nums = sorted(draw)
            has_consecutive = any(
                nums[i + 1] - nums[i] == 1 for i in range(len(nums) - 1)
            )
            if has_consecutive:
                count += 1
        return count / self.total_rounds if self.total_rounds > 0 else 0

    # === 홀짝 비율 분석 ===
    def odd_even_distribution(self) -> dict[str, float]:
        """역대 홀짝 비율 분포 (예: '3:3' -> 33%)"""
        dist = Counter()
        for draw in self.draws:
            odd = sum(1 for n in draw if n % 2 == 1)
            even = config.NUMBERS_PER_DRAW - odd
            dist[f"{odd}:{even}"] += 1

        return {k: v / self.total_rounds * 100 for k, v in dist.items()}

    def optimal_odd_even_ratio(self) -> tuple[int, int]:
        """가장 빈번한 홀짝 비율"""
        dist = self.odd_even_distribution()
        best = max(dist, key=dist.get)
        odd, even = map(int, best.split(':'))
        return (odd, even)

    # === 고저 비율 분석 ===
    def high_low_distribution(self) -> dict[str, float]:
        """저(1-22):고(23-45) 비율 분포"""
        dist = Counter()
        for draw in self.draws:
            low = sum(1 for n in draw if config.LOW_RANGE[0] <= n <= config.LOW_RANGE[1])
            high = config.NUMBERS_PER_DRAW - low
            dist[f"{low}:{high}"] += 1

        return {k: v / self.total_rounds * 100 for k, v in dist.items()}

    def optimal_high_low_ratio(self) -> tuple[int, int]:
        """가장 빈번한 고저 비율 (저:고)"""
        dist = self.high_low_distribution()
        best = max(dist, key=dist.get)
        low, high = map(int, best.split(':'))
        return (low, high)

    # === 끝수 분석 ===
    def last_digit_distribution(self) -> dict[int, float]:
        """끝수(0~9)별 출현 비율 (%)"""
        digit_count = Counter()
        total = 0
        for draw in self.draws:
            for n in draw:
                digit_count[n % 10] += 1
                total += 1

        return {d: digit_count.get(d, 0) / total * 100 for d in range(10)}

    def same_last_digit_frequency(self) -> float:
        """같은 끝수 번호가 2개 이상 포함된 회차의 비율 (%)"""
        count = 0
        for draw in self.draws:
            digits = [n % 10 for n in draw]
            if len(digits) != len(set(digits)):  # 중복 끝수 존재
                count += 1
        return count / self.total_rounds * 100 if self.total_rounds > 0 else 0

    # === 구간별 분포 ===
    def section_distribution(self) -> dict[str, float]:
        """5개 구간별 번호 배분 분포"""
        dist = Counter()
        for draw in self.draws:
            pattern = []
            for s_start, s_end in config.SECTIONS:
                cnt = sum(1 for n in draw if s_start <= n <= s_end)
                pattern.append(cnt)
            dist[tuple(pattern)] += 1

        return {
            str(k): v / self.total_rounds * 100
            for k, v in dist.most_common(20)
        }

    def optimal_section_pattern(self) -> list[int]:
        """가장 빈번한 구간별 분포 패턴"""
        dist = Counter()
        for draw in self.draws:
            pattern = []
            for s_start, s_end in config.SECTIONS:
                cnt = sum(1 for n in draw if s_start <= n <= s_end)
                pattern.append(cnt)
            dist[tuple(pattern)] += 1

        best = dist.most_common(1)[0][0]
        return list(best)

    # === 종합 제약 조건 ===
    def get_pattern_constraints(self) -> dict:
        """조합 생성 시 적용할 패턴 제약 조건들"""
        # 상위 빈도 홀짝 비율들 (전체의 70% 이상 커버하는 비율들)
        oe_dist = self.odd_even_distribution()
        sorted_oe = sorted(oe_dist.items(), key=lambda x: x[1], reverse=True)
        allowed_oe = []
        cumulative = 0
        for ratio_str, pct in sorted_oe:
            odd, even = map(int, ratio_str.split(':'))
            allowed_oe.append((odd, even))
            cumulative += pct
            if cumulative >= 80:
                break

        # 상위 빈도 고저 비율들
        hl_dist = self.high_low_distribution()
        sorted_hl = sorted(hl_dist.items(), key=lambda x: x[1], reverse=True)
        allowed_hl = []
        cumulative = 0
        for ratio_str, pct in sorted_hl:
            low, high = map(int, ratio_str.split(':'))
            allowed_hl.append((low, high))
            cumulative += pct
            if cumulative >= 80:
                break

        return {
            'odd_even_range': allowed_oe,
            'high_low_range': allowed_hl,
            'consecutive_prob': self.consecutive_probability(),
            'section_pattern': self.optimal_section_pattern(),
        }

    def get_scores(self) -> dict[int, float]:
        """패턴 분석 기반 1~45 번호별 보너스 점수 (0~100)

        최근 패턴 트렌드에 부합하는 번호에 보너스 부여
        """
        scores = {n: 50.0 for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1)}

        # 홀짝 최적 비율 기반 보너스
        opt_odd, opt_even = self.optimal_odd_even_ratio()
        odd_ratio = opt_odd / config.NUMBERS_PER_DRAW
        for n in range(config.MIN_NUMBER, config.MAX_NUMBER + 1):
            if n % 2 == 1:
                scores[n] += (odd_ratio - 0.5) * 40  # 홀수 비율이 높으면 홀수 가산
            else:
                scores[n] += (0.5 - odd_ratio) * 40  # 짝수 비율이 높으면 짝수 가산

        # 구간 분포 기반 보너스
        section_pattern = self.optimal_section_pattern()
        for i, (s_start, s_end) in enumerate(config.SECTIONS):
            section_size = s_end - s_start + 1
            expected_density = section_pattern[i] / section_size
            for n in range(s_start, s_end + 1):
                scores[n] += expected_density * 30  # 밀도 높은 구간 번호 가산

        # 연속번호 쌍 빈도 반영
        pair_freq = self.consecutive_pair_frequency()
        if pair_freq:
            max_freq = max(pair_freq.values())
            for (a, b), freq in pair_freq.items():
                bonus = (freq / max_freq) * 10
                scores[a] = scores.get(a, 50) + bonus
                scores[b] = scores.get(b, 50) + bonus

        # 0~100 정규화
        vals = list(scores.values())
        min_v, max_v = min(vals), max(vals)
        rng = max_v - min_v if max_v != min_v else 1
        return {k: (v - min_v) / rng * 100 for k, v in scores.items()}
