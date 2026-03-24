"""예측 결과 저장 및 추첨 결과 비교 모듈"""

import json
import pandas as pd
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config

LOG_FILE = Path(__file__).parent.parent / "data" / "prediction_log.json"


def load_log() -> list[dict]:
    """저장된 예측 로그 로드"""
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_log(log: list[dict]):
    """예측 로그 저장"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def add_prediction(target_round: int, predictions: list[tuple[list[int], float]],
                    settings: dict = None) -> str:
    """예측 결과를 로그에 추가

    동일한 번호 세트가 이미 저장되어 있으면 중복 저장하지 않는다.

    Args:
        target_round: 예측 대상 회차
        predictions: [(번호 리스트, 적합도), ...]
        settings: 생성 설정 {'num_sets': N, 'temperature': T}

    Returns:
        생성된 entry의 id (중복이면 빈 문자열)
    """
    log = load_log()

    # 중복 체크: 같은 회차에 동일한 번호 조합이 이미 있는지
    new_sets = frozenset(tuple(sorted(nums)) for nums, _ in predictions)
    for existing in log:
        if existing['target_round'] == target_round:
            existing_sets = frozenset(tuple(sorted(s['numbers'])) for s in existing['sets'])
            if new_sets == existing_sets:
                return ''  # 중복, 저장 안 함

    # 고유 ID 생성 (회차_타임스탬프)
    entry_id = f"{target_round}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    entry = {
        'id': entry_id,
        'target_round': target_round,
        'predicted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'settings': settings or {},
        'sets': [
            {'numbers': nums, 'fitness': round(fitness, 1)}
            for nums, fitness in predictions
        ],
        'actual': None,
        'results': None,
    }
    log.append(entry)
    log.sort(key=lambda x: x['predicted_at'], reverse=True)
    save_log(log)
    return entry_id


def delete_prediction(entry_id: str):
    """예측 로그에서 특정 항목 삭제

    Args:
        entry_id: 삭제할 예측의 id
    """
    log = load_log()
    log = [e for e in log if e.get('id') != entry_id]
    save_log(log)


def delete_set_from_prediction(entry_id: str, set_index: int):
    """예측 항목에서 특정 세트만 삭제

    Args:
        entry_id: 예측 항목 id
        set_index: 삭제할 세트 인덱스 (0부터)
    """
    log = load_log()
    for entry in log:
        if entry.get('id') == entry_id:
            if 0 <= set_index < len(entry['sets']):
                entry['sets'].pop(set_index)
                if entry.get('results') and set_index < len(entry['results']):
                    entry['results'].pop(set_index)
            # 세트가 다 없어지면 항목 자체 삭제
            if not entry['sets']:
                log = [e for e in log if e.get('id') != entry_id]
            break
    save_log(log)


def update_actual_result(target_round: int, actual_numbers: list[int]):
    """실제 추첨 결과를 업데이트하고 적중 수 계산

    Args:
        target_round: 회차 번호
        actual_numbers: 실제 당첨번호 6개
    """
    log = load_log()
    actual_set = set(actual_numbers)

    for entry in log:
        if entry['target_round'] == target_round:
            entry['actual'] = sorted(actual_numbers)
            entry['results'] = []
            for s in entry['sets']:
                matched = sorted(set(s['numbers']) & actual_set)
                entry['results'].append({
                    'matched_count': len(matched),
                    'matched_numbers': matched,
                })
            break

    save_log(log)


def update_all_from_df(df: pd.DataFrame):
    """DataFrame의 실제 결과로 모든 미확인 예측 업데이트"""
    log = load_log()
    updated = False

    for entry in log:
        if entry['actual'] is not None:
            continue  # 이미 결과 있음

        round_no = entry['target_round']
        row = df[df['round'] == round_no]
        if row.empty:
            continue

        actual = sorted(row.iloc[0][config.NUMBER_COLUMNS].tolist())
        actual_set = set(actual)
        entry['actual'] = actual
        entry['results'] = []
        for s in entry['sets']:
            matched = sorted(set(s['numbers']) & actual_set)
            entry['results'].append({
                'matched_count': len(matched),
                'matched_numbers': matched,
            })
        updated = True

    if updated:
        save_log(log)

    return log


def get_stats(log: list[dict]) -> dict:
    """예측 로그에서 통계 산출"""
    confirmed = [e for e in log if e['results'] is not None]
    if not confirmed:
        return {'total_rounds': 0}

    all_matches = []
    best_per_round = []

    for entry in confirmed:
        round_best = 0
        for r in entry['results']:
            all_matches.append(r['matched_count'])
            round_best = max(round_best, r['matched_count'])
        best_per_round.append(round_best)

    import numpy as np
    return {
        'total_rounds': len(confirmed),
        'total_predictions': len(all_matches),
        'avg_match': float(np.mean(all_matches)) if all_matches else 0,
        'avg_best': float(np.mean(best_per_round)) if best_per_round else 0,
        'max_match': max(all_matches) if all_matches else 0,
        'match_distribution': {
            i: all_matches.count(i) for i in range(7)
        },
    }
