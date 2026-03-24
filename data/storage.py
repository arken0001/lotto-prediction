"""로또 데이터의 로컬 저장/로드를 관리하는 모듈"""

import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class LottoStorage:
    """로또 데이터의 CSV 기반 로컬 캐시 관리"""

    def __init__(self, csv_path: str = None):
        self.csv_path = Path(csv_path or config.CACHE_FILE)
        # 프로젝트 루트 기준 절대 경로
        if not self.csv_path.is_absolute():
            self.csv_path = Path(__file__).parent.parent / self.csv_path

    def exists(self) -> bool:
        """캐시 파일이 존재하는지 확인"""
        return self.csv_path.exists() and self.csv_path.stat().st_size > 0

    def save(self, df: pd.DataFrame) -> None:
        """DataFrame을 CSV로 저장"""
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.csv_path, index=False, encoding='utf-8-sig')

    def load(self) -> pd.DataFrame:
        """CSV에서 DataFrame 로드

        Returns:
            당첨번호 DataFrame. 파일이 없으면 빈 DataFrame 반환.
        """
        if not self.exists():
            return pd.DataFrame()

        df = pd.read_csv(self.csv_path, encoding='utf-8-sig')
        df = df.sort_values('round').reset_index(drop=True)
        return df

    def get_last_round(self) -> int:
        """저장된 마지막 회차 번호 반환. 데이터 없으면 0."""
        df = self.load()
        if df.empty:
            return 0
        return int(df['round'].max())

    def merge_and_save(self, new_df: pd.DataFrame) -> pd.DataFrame:
        """기존 데이터와 새 데이터를 병합하여 저장

        Args:
            new_df: 새로 수집된 데이터

        Returns:
            병합된 전체 DataFrame
        """
        existing = self.load()

        if existing.empty:
            merged = new_df
        elif new_df.empty:
            merged = existing
        else:
            merged = pd.concat([existing, new_df], ignore_index=True)
            merged = merged.drop_duplicates(subset=['round'], keep='last')

        merged = merged.sort_values('round').reset_index(drop=True)
        self.save(merged)
        return merged

    def get_all_numbers(self, df: pd.DataFrame = None) -> list[list[int]]:
        """모든 회차의 당첨번호를 리스트로 반환

        Returns:
            [[n1, n2, n3, n4, n5, n6], ...] 형태
        """
        if df is None:
            df = self.load()
        if df.empty:
            return []

        return df[config.NUMBER_COLUMNS].values.tolist()
