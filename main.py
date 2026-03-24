"""
로또 6/45 당첨번호 예측 프로그램

사용법:
    python main.py                  # 기본 예측 (5세트)
    python main.py --sets 10        # 10세트 예측
    python main.py --update         # 데이터 업데이트만 수행
    python main.py --analysis       # 분석 리포트만 출력
    python main.py --backtest 50    # 최근 50회차 백테스트
    python main.py --chart          # 시각화 차트 표시
"""

import argparse
import sys
import io
from pathlib import Path

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from data.collector import LottoDataCollector
from data.storage import LottoStorage
from analysis.scorer import WeightedScorer
from prediction.generator import PredictionGenerator
from prediction.validator import PredictionValidator
from display.console import ConsoleDisplay


def load_data(display: ConsoleDisplay, force_update: bool = False) -> 'pd.DataFrame':
    """데이터를 로드하거나 수집

    1. 로컬 캐시 확인
    2. 캐시가 없으면 soledot에서 전체 수집
    3. 캐시가 있으면 새 회차만 추가 수집
    """
    import pandas as pd

    storage = LottoStorage()
    collector = LottoDataCollector()

    if storage.exists() and not force_update:
        df = storage.load()
        last_round = storage.get_last_round()
        print(f"  로컬 캐시 로드 완료 (마지막: {last_round}회, {len(df)}개 회차)")

        # 새 데이터 추가 수집
        print("  새 회차 확인 중...")
        new_df = collector.fetch_new_rounds(last_round)

        if not new_df.empty:
            new_count = len(new_df)
            df = storage.merge_and_save(new_df)
            print(f"  {new_count}개 새 회차 추가! 총 {len(df)}개 회차")
        else:
            print(f"  데이터가 최신 상태입니다 ({last_round}회)")
    else:
        print("  전체 데이터를 수집합니다 (최초 실행, 약 30초 소요)...")
        df = collector.fetch_all(
            progress_callback=lambda c, t: display.show_progress(c, t, "수집 ")
        )

        if df.empty:
            print("\n  [오류] 데이터 수집에 실패했습니다.")
            print("  인터넷 연결을 확인하거나, data/lotto_history.csv 파일을")
            print("  수동으로 배치해 주세요.")
            print()
            print("  CSV 형식: round,date,n1,n2,n3,n4,n5,n6,bonus,total_sales,winners,prize")
            sys.exit(1)

        storage.save(df)
        print(f"\n  {len(df)}개 회차 데이터 수집/저장 완료")

    return df


def run_prediction(df, display: ConsoleDisplay, num_sets: int = 5,
                   show_chart: bool = False):
    """예측 실행"""
    # 분석 및 점수 산출
    print("  분석 중...")
    scorer = WeightedScorer(df)
    report = scorer.generate_analysis_report()

    # 데이터 상태 표시
    display.show_data_status(report['total_rounds'], report['last_round'])

    # 분석 요약 표시
    display.show_analysis_summary(report)

    # 번호별 점수 순위 표시
    display.show_number_ranking(report['number_scores'])

    # 예측 생성
    print("  예측 번호 생성 중...")
    generator = PredictionGenerator(scorer)
    predictions = generator.generate_predictions(num_sets=num_sets)

    next_round = report['last_round'] + 1
    display.show_predictions(predictions, next_round)

    # 차트 표시
    if show_chart:
        show_charts(scorer, report)

    return predictions


def run_analysis(df, display: ConsoleDisplay, show_chart: bool = False):
    """분석 리포트만 출력"""
    print("  분석 중...")
    scorer = WeightedScorer(df)
    report = scorer.generate_analysis_report()

    display.show_data_status(report['total_rounds'], report['last_round'])
    display.show_analysis_summary(report)
    display.show_number_ranking(report['number_scores'])

    # 상세 통계
    print(f"{'─' * 56}")
    print(f"  상세 통계")
    print(f"{'─' * 56}")
    print()

    # 홀짝 분포
    print("  [홀짝 분포]")
    for ratio, pct in sorted(report['odd_even_dist'].items(),
                              key=lambda x: x[1], reverse=True):
        bar = '█' * int(pct / 2)
        print(f"    {ratio}: {pct:5.1f}% {bar}")
    print()

    # 고저 분포
    print("  [저:고 분포]")
    for ratio, pct in sorted(report['high_low_dist'].items(),
                              key=lambda x: x[1], reverse=True):
        bar = '█' * int(pct / 2)
        print(f"    {ratio}: {pct:5.1f}% {bar}")
    print()

    if show_chart:
        show_charts(scorer, report)


def run_backtest(df, display: ConsoleDisplay, test_rounds: int = 50):
    """백테스트 실행"""
    print(f"  최근 {test_rounds}회차 백테스트 실행 중...")
    print("  (각 회차마다 분석/예측을 수행하므로 시간이 소요됩니다)")
    print()

    validator = PredictionValidator()
    results = validator.backtest(
        df, test_rounds=test_rounds, num_sets=5,
        progress_callback=lambda c, t: display.show_progress(c, t, "백테스트 ")
    )

    display.show_backtest_results(results)

    # 무작위 비교
    print("  무작위 선택과 비교 중...")
    random_results = validator.compare_with_random(df)
    print(f"  무작위 선택 평균 적중: {random_results['random_avg_match']:.2f}개")
    print(f"  무작위 선택 최대 적중: {random_results['random_max_match']}개")
    print()


def show_charts(scorer: WeightedScorer, report: dict):
    """시각화 차트 표시"""
    try:
        from display.visualizer import (
            plot_number_scores, plot_frequency_heatmap,
            plot_gap_analysis
        )

        # 번호별 점수 차트
        plot_number_scores(report['number_scores'])

        # 빈도 히트맵
        total_freq = scorer.freq_analyzer.total_frequency()
        plot_frequency_heatmap(total_freq)

        # 간격 분석 차트
        current_gaps = scorer.gap_analyzer.current_gap()
        average_gaps = scorer.gap_analyzer.average_gap()
        plot_gap_analysis(current_gaps, average_gaps)

    except ImportError:
        print("  [알림] matplotlib가 설치되지 않아 차트를 표시할 수 없습니다.")
        print("  설치: pip install matplotlib")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='로또 6/45 당첨번호 예측 프로그램',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py                  기본 예측 (5세트)
  python main.py --sets 10        10세트 예측
  python main.py --update         데이터 업데이트만
  python main.py --analysis       분석 리포트
  python main.py --backtest 50    최근 50회차 백테스트
  python main.py --chart          차트 포함 예측
        """
    )
    parser.add_argument('--sets', type=int, default=5,
                        help='생성할 예측 세트 수 (기본: 5)')
    parser.add_argument('--update', action='store_true',
                        help='데이터 업데이트만 수행')
    parser.add_argument('--analysis', action='store_true',
                        help='분석 리포트만 출력')
    parser.add_argument('--backtest', type=int, metavar='N',
                        help='최근 N회차 백테스트 실행')
    parser.add_argument('--chart', action='store_true',
                        help='시각화 차트 표시')
    parser.add_argument('--force-update', action='store_true',
                        help='캐시 무시하고 전체 재수집')

    args = parser.parse_args()
    display = ConsoleDisplay()

    # 배너 표시
    display.show_banner()

    # 데이터 로드
    df = load_data(display, force_update=args.force_update)
    print()

    if df.empty:
        print("  데이터가 없습니다. --update로 데이터를 수집해 주세요.")
        sys.exit(1)

    # 데이터 업데이트만
    if args.update:
        print("  데이터 업데이트 완료!")
        return

    # 백테스트
    if args.backtest:
        run_backtest(df, display, test_rounds=args.backtest)
        return

    # 분석 리포트
    if args.analysis:
        run_analysis(df, display, show_chart=args.chart)
        return

    # 기본: 예측 실행
    run_prediction(df, display, num_sets=args.sets, show_chart=args.chart)

    print(f"{'=' * 56}")
    print("  ※ 본 프로그램은 통계 분석 기반 참고용이며,")
    print("    실제 당첨을 보장하지 않습니다.")
    print(f"{'=' * 56}")
    print()


if __name__ == '__main__':
    main()
