"""matplotlib 기반 시각화 모듈"""

import numpy as np
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def plot_number_scores(scores: dict[int, float], title: str = "번호별 종합 점수"):
    """번호별 점수 막대그래프"""
    import matplotlib.pyplot as plt
    import matplotlib

    # 한글 폰트 설정
    matplotlib.rcParams['font.family'] = 'Malgun Gothic'
    matplotlib.rcParams['axes.unicode_minus'] = False

    numbers = sorted(scores.keys())
    values = [scores[n] for n in numbers]

    # 구간별 색상
    colors = []
    color_map = {
        (1, 10): '#FBC400',    # 노란색
        (11, 20): '#69C8F2',   # 파란색
        (21, 30): '#FF7272',   # 빨간색
        (31, 40): '#AAAAAA',   # 회색
        (41, 45): '#B0D840',   # 초록색
    }
    for n in numbers:
        for (s, e), color in color_map.items():
            if s <= n <= e:
                colors.append(color)
                break

    fig, ax = plt.subplots(figsize=(14, 6))
    bars = ax.bar(numbers, values, color=colors, edgecolor='white', linewidth=0.5)

    # 상위 6개 번호 강조
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top6 = {n for n, _ in sorted_scores[:6]}
    for bar, n in zip(bars, numbers):
        if n in top6:
            bar.set_edgecolor('red')
            bar.set_linewidth(2)

    ax.set_xlabel('번호')
    ax.set_ylabel('점수')
    ax.set_title(title)
    ax.set_xticks(numbers)
    ax.set_xticklabels(numbers, fontsize=7)
    ax.set_ylim(0, 105)
    plt.tight_layout()
    plt.show()


def plot_frequency_heatmap(freq_data: dict[int, int], title: str = "번호 출현 빈도"):
    """번호 출현 빈도 히트맵 (5x9 격자)"""
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.rcParams['font.family'] = 'Malgun Gothic'
    matplotlib.rcParams['axes.unicode_minus'] = False

    # 5행 9열 격자로 배치 (1~45)
    grid = np.zeros((5, 9))
    labels = np.zeros((5, 9), dtype=int)
    mask = np.ones((5, 9), dtype=bool)

    for n in range(1, 46):
        row = (n - 1) // 9
        col = (n - 1) % 9
        grid[row, col] = freq_data.get(n, 0)
        labels[row, col] = n
        mask[row, col] = False

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(np.ma.array(grid, mask=mask), cmap='YlOrRd', aspect='auto')

    # 셀에 번호와 빈도 표시
    for i in range(5):
        for j in range(9):
            if not mask[i, j]:
                num = labels[i, j]
                freq = int(grid[i, j])
                ax.text(j, i, f"{num}\n({freq})",
                       ha='center', va='center', fontsize=8,
                       fontweight='bold')

    ax.set_title(title)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, label='출현 횟수')
    plt.tight_layout()
    plt.show()


def plot_section_pie(section_data: dict[str, float],
                     title: str = "구간별 분포 TOP 10"):
    """구간 분포 파이차트"""
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.rcParams['font.family'] = 'Malgun Gothic'
    matplotlib.rcParams['axes.unicode_minus'] = False

    # 상위 10개 패턴만 표시
    sorted_data = sorted(section_data.items(), key=lambda x: x[1], reverse=True)[:10]
    labels = [k for k, _ in sorted_data]
    values = [v for _, v in sorted_data]

    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct='%1.1f%%',
        startangle=90, textprops={'fontsize': 9}
    )

    ax.set_title(title)
    plt.tight_layout()
    plt.show()


def plot_gap_analysis(current_gaps: dict[int, int],
                      average_gaps: dict[int, float],
                      title: str = "번호별 미출현 간격 분석"):
    """현재 미출현 기간 vs 평균 간격 비교 차트"""
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.rcParams['font.family'] = 'Malgun Gothic'
    matplotlib.rcParams['axes.unicode_minus'] = False

    numbers = sorted(current_gaps.keys())
    cur = [current_gaps[n] for n in numbers]
    avg = [average_gaps[n] for n in numbers]

    fig, ax = plt.subplots(figsize=(14, 6))
    x = np.arange(len(numbers))
    width = 0.35

    bars1 = ax.bar(x - width/2, cur, width, label='현재 미출현', color='#FF7272', alpha=0.8)
    bars2 = ax.bar(x + width/2, avg, width, label='평균 간격', color='#69C8F2', alpha=0.8)

    # overdue 번호 강조
    for i, n in enumerate(numbers):
        if avg[i] > 0 and cur[i] / avg[i] >= 1.5:
            bars1[i].set_edgecolor('red')
            bars1[i].set_linewidth(2)

    ax.set_xlabel('번호')
    ax.set_ylabel('회차 수')
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(numbers, fontsize=7)
    ax.legend()
    plt.tight_layout()
    plt.show()
