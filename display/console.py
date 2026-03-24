"""CLI 화면 출력을 담당하는 모듈"""

from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class ConsoleDisplay:
    """CLI 텍스트 기반 출력"""

    BALL_COLORS = {
        range(1, 11): '\033[93m',   # 노란색 (1-10)
        range(11, 21): '\033[94m',  # 파란색 (11-20)
        range(21, 31): '\033[91m',  # 빨간색 (21-30)
        range(31, 41): '\033[90m',  # 회색 (31-40)
        range(41, 46): '\033[92m',  # 초록색 (41-45)
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    def _colored_ball(self, num: int) -> str:
        """번호에 색상을 입힌 문자열"""
        for num_range, color in self.BALL_COLORS.items():
            if num in num_range:
                return f"{color}{self.BOLD}[{num:02d}]{self.RESET}"
        return f"[{num:02d}]"

    def show_banner(self):
        """프로그램 시작 배너"""
        print()
        print(f"{self.BOLD}{'=' * 56}{self.RESET}")
        print(f"{self.BOLD}{'로또 6/45 당첨번호 예측 프로그램':^46}{self.RESET}")
        print(f"{self.BOLD}{'=' * 56}{self.RESET}")
        print()

    def show_data_status(self, total_rounds: int, last_round: int):
        """데이터 상태 출력"""
        print(f"  분석 데이터: 1회 ~ {last_round}회 ({total_rounds}개 회차)")
        print(f"  분석일: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print()

    def show_predictions(self, predictions: list[tuple[list[int], float]],
                        next_round: int = None):
        """예측 결과 출력"""
        round_str = f" - 제{next_round}회" if next_round else ""
        print(f"{self.BOLD}{'─' * 56}{self.RESET}")
        print(f"{self.BOLD}  * 예측 번호{round_str} ({len(predictions)}세트){self.RESET}")
        print(f"{'─' * 56}")
        print()

        for i, (numbers, fitness) in enumerate(predictions, 1):
            balls = ' '.join(self._colored_ball(n) for n in numbers)
            print(f"  {i}순위  {balls}  {self.DIM}적합도: {fitness:.1f}{self.RESET}")

        print()

    def show_analysis_summary(self, report: dict):
        """분석 요약 출력"""
        print(f"{self.BOLD}{'─' * 56}{self.RESET}")
        print(f"{self.BOLD}  분석 요약{self.RESET}")
        print(f"{'─' * 56}")
        print()

        # HOT/COLD 번호
        hot = report['hot_numbers']
        cold = report['cold_numbers']
        overdue = report['overdue_numbers']

        if hot:
            hot_str = ', '.join(str(n) for n in hot[:10])
            print(f"  {self.BOLD}[HOT 번호]{self.RESET}  {hot_str}")
        if cold:
            cold_str = ', '.join(str(n) for n in cold[:10])
            print(f"  {self.BOLD}[COLD 번호]{self.RESET} {cold_str}")
        if overdue:
            overdue_str = ', '.join(str(n) for n in overdue[:10])
            print(f"  {self.BOLD}[OVERDUE]{self.RESET}   {overdue_str}")
        print()

        # 합계 범위
        stats = report['sum_stats']
        low, high = stats['optimal_range']
        print(f"  최적 합계 범위: {low} ~ {high} (평균: {stats['mean']:.0f})")

        # AC값 범위
        ac_low, ac_high = report['ac_range']
        print(f"  최적 AC값: {ac_low} ~ {ac_high}")

        # 홀짝 분포
        oe_dist = report['odd_even_dist']
        top_oe = sorted(oe_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        oe_str = ', '.join(f"{k}({v:.1f}%)" for k, v in top_oe)
        print(f"  홀짝 분포 TOP3: {oe_str}")
        print()

    def show_number_ranking(self, scores: dict[int, float], top_n: int = 15):
        """번호별 점수 순위표 (텍스트 막대그래프)"""
        print(f"{self.BOLD}{'─' * 56}{self.RESET}")
        print(f"{self.BOLD}  번호별 점수 TOP {top_n}{self.RESET}")
        print(f"{'─' * 56}")
        print()

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        max_score = sorted_scores[0][1] if sorted_scores else 100

        for num, score in sorted_scores[:top_n]:
            bar_len = int(score / max_score * 30)
            bar = '#' * bar_len
            ball = self._colored_ball(num)
            print(f"  {ball} {bar} {score:.1f}")

        print()

    def show_backtest_results(self, results: dict):
        """백테스트 결과 출력"""
        print()
        print(f"{self.BOLD}{'=' * 56}{self.RESET}")
        print(f"{self.BOLD}  백테스트 결과 (최근 {results['test_rounds']}회차){self.RESET}")
        print(f"{'=' * 56}")
        print()

        print(f"  예측 세트 수/회차: {results['num_sets_per_round']}세트")
        print(f"  총 예측 수: {results['total_predictions']}개")
        print()

        print(f"  {self.BOLD}평균 적중 번호 수: {results['avg_match']:.2f}개{self.RESET}")
        print(f"  최고 세트 평균 적중: {results['avg_best_match']:.2f}개")
        print(f"  최대 적중: {results['max_match']}개")
        print(f"  무작위 기대값: {results['random_expected']:.2f}개")

        improvement = results['improvement_pct']
        color = '\033[92m' if improvement > 0 else '\033[91m'
        print(f"  개선율: {color}{improvement:+.1f}%{self.RESET}")
        print()

        # 적중 분포
        print(f"  {self.BOLD}적중 분포:{self.RESET}")
        for match_count in range(7):
            info = results['match_distribution'].get(match_count, {'count': 0, 'pct': 0})
            count = info['count']
            pct = info['pct']
            bar = '#' * int(pct / 2)
            print(f"  {match_count}개 일치: {count:>5}회 ({pct:5.1f}%) {bar}")
        print()

    def show_progress(self, current: int, total: int, prefix: str = ""):
        """진행률 표시"""
        pct = current / total * 100
        bar_len = 30
        filled = int(bar_len * current / total)
        bar = '#' * filled + '-' * (bar_len - filled)
        try:
            print(f"\r  {prefix}[{bar}] {current}/{total} ({pct:.0f}%)", end='', flush=True)
        except UnicodeEncodeError:
            print(f"\r  {prefix}{current}/{total} ({pct:.0f}%)", end='', flush=True)
        if current == total:
            print()
