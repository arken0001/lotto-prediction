"""Supabase 기반 예측 저장소 모듈"""

import json
from datetime import datetime
from pathlib import Path
from supabase import create_client, Client

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config

# Supabase 설정 (Streamlit secrets 또는 환경변수에서 로드)
def get_supabase() -> Client:
    """Supabase 클라이언트 생성"""
    try:
        import streamlit as st
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
    except Exception:
        url = ""
        key = ""

    if not url or not key:
        import os
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        return None

    return create_client(url, key)


def load_log() -> list[dict]:
    """Supabase에서 예측 로그 로드"""
    client = get_supabase()
    if not client:
        return _load_local()

    try:
        resp = client.table('predictions').select('*').order('predicted_at', desc=True).execute()
        log = []
        for row in resp.data:
            log.append({
                'id': row['id'],
                'target_round': row['target_round'],
                'predicted_at': row['predicted_at'],
                'settings': row.get('settings') or {},
                'sets': row.get('sets') or [],
                'actual': row.get('actual'),
                'results': row.get('results'),
            })
        return log
    except Exception as e:
        print(f"[Supabase 로드 실패] {e}")
        return _load_local()


def save_entry(entry: dict):
    """Supabase에 단일 항목 저장"""
    client = get_supabase()
    if not client:
        return

    try:
        client.table('predictions').upsert({
            'id': entry['id'],
            'target_round': entry['target_round'],
            'predicted_at': entry['predicted_at'],
            'settings': entry.get('settings', {}),
            'sets': entry['sets'],
            'actual': entry.get('actual'),
            'results': entry.get('results'),
        }).execute()
    except Exception as e:
        print(f"[Supabase 저장 실패] {e}")


def add_prediction(target_round: int, predictions: list[tuple[list[int], float]],
                    settings: dict = None) -> str:
    """예측 결과를 Supabase에 추가 (중복 방지)"""
    log = load_log()

    # 중복 체크
    new_sets = frozenset(tuple(sorted(nums)) for nums, _ in predictions)
    for existing in log:
        if existing['target_round'] == target_round:
            existing_sets = frozenset(tuple(sorted(s['numbers'])) for s in existing['sets'])
            if new_sets == existing_sets:
                return ''

    entry_id = f"{target_round}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    entry = {
        'id': entry_id,
        'target_round': target_round,
        'predicted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'settings': settings or {},
        'sets': [{'numbers': nums, 'fitness': round(fitness, 1)} for nums, fitness in predictions],
        'actual': None,
        'results': None,
    }

    client = get_supabase()
    if client:
        save_entry(entry)
    else:
        # 로컬 fallback
        from data.prediction_log import add_prediction as local_add
        return local_add(target_round, predictions, settings)

    return entry_id


def delete_prediction(entry_id: str):
    """예측 항목 삭제"""
    client = get_supabase()
    if client:
        try:
            client.table('predictions').delete().eq('id', entry_id).execute()
        except Exception as e:
            print(f"[Supabase 삭제 실패] {e}")
    else:
        from data.prediction_log import delete_prediction as local_del
        local_del(entry_id)


def delete_set_from_prediction(entry_id: str, set_index: int):
    """특정 세트만 삭제"""
    client = get_supabase()
    if not client:
        from data.prediction_log import delete_set_from_prediction as local_ds
        local_ds(entry_id, set_index)
        return

    try:
        resp = client.table('predictions').select('*').eq('id', entry_id).execute()
        if not resp.data:
            return

        entry = resp.data[0]
        sets = entry.get('sets', [])
        results = entry.get('results')

        if 0 <= set_index < len(sets):
            sets.pop(set_index)
            if results and set_index < len(results):
                results.pop(set_index)

        if not sets:
            client.table('predictions').delete().eq('id', entry_id).execute()
        else:
            client.table('predictions').update({
                'sets': sets,
                'results': results,
            }).eq('id', entry_id).execute()
    except Exception as e:
        print(f"[Supabase 세트 삭제 실패] {e}")


def update_all_from_df(df) -> list[dict]:
    """미확인 예측에 실제 결과 업데이트"""
    log = load_log()
    client = get_supabase()
    updated = False

    for entry in log:
        if entry.get('actual') is not None:
            continue

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

        if client:
            try:
                client.table('predictions').update({
                    'actual': entry['actual'],
                    'results': entry['results'],
                }).eq('id', entry['id']).execute()
            except Exception:
                pass
        updated = True

    return log


def get_stats(log: list[dict]) -> dict:
    """예측 로그에서 통계 산출"""
    confirmed = [e for e in log if e.get('results') is not None]
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
        'match_distribution': {i: all_matches.count(i) for i in range(7)},
    }


# ── 로컬 JSON fallback ──
_LOCAL_LOG = Path(__file__).parent.parent / "data" / "prediction_log.json"

def _load_local() -> list[dict]:
    if not _LOCAL_LOG.exists():
        return []
    try:
        with open(_LOCAL_LOG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []
