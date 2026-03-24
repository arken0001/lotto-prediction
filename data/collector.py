"""로또 당첨번호 데이터를 수집하는 모듈

데이터 소스: data.soledot.com (엑셀 다운로드)
Fallback: 동행복권 API
"""

import time
import requests
import pandas as pd
from io import BytesIO
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


# soledot 엑셀 컬럼 매핑 (한글 깨짐 대비, 위치 기반)
SOLEDOT_COLUMNS = {
    0: 'round',
    1: 'n1',
    2: 'n2',
    3: 'n3',
    4: 'n4',
    5: 'n5',
    6: 'n6',
    7: 'bonus',
    8: 'winners',
    9: 'prize',
    10: 'total_sales',
    11: 'date',
}


class LottoDataCollector:
    """로또 6/45 당첨번호를 수집하는 클래스

    1차: data.soledot.com 엑셀 다운로드 (페이지별 20건)
    2차: 동행복권 API (fallback)
    """

    SOLEDOT_URL = "https://data.soledot.com/lottowinnumber/fo/lottowinnumberexceldown.sd"
    DHLOTTERY_API = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
        })

    def _parse_soledot_excel(self, content: bytes) -> pd.DataFrame:
        """soledot 엑셀 바이트를 DataFrame으로 변환"""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_excel(BytesIO(content))

        if df.empty:
            return pd.DataFrame()

        # 컬럼명을 위치 기반으로 매핑 (한글 인코딩 문제 회피)
        cols = list(df.columns)
        rename_map = {}
        for idx, new_name in SOLEDOT_COLUMNS.items():
            if idx < len(cols):
                rename_map[cols[idx]] = new_name

        df = df.rename(columns=rename_map)

        # 필요한 컬럼만 선택
        needed = ['round', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6',
                  'bonus', 'winners', 'prize', 'total_sales', 'date']
        available = [c for c in needed if c in df.columns]
        df = df[available]

        # 타입 변환
        for col in ['round', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'bonus']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')

        return df

    def fetch_from_soledot(self, page: int = 1) -> pd.DataFrame:
        """soledot에서 한 페이지(20건) 엑셀 다운로드

        Args:
            page: 페이지 번호 (1=최신, 클수록 과거)

        Returns:
            당첨번호 DataFrame
        """
        try:
            resp = self.session.get(
                self.SOLEDOT_URL,
                params={'s_pagenum': page},
                timeout=15,
            )
            resp.raise_for_status()

            if 'spreadsheet' not in resp.headers.get('Content-Type', ''):
                return pd.DataFrame()

            return self._parse_soledot_excel(resp.content)
        except Exception as e:
            print(f"  [경고] soledot 페이지 {page} 다운로드 실패: {e}")
            return pd.DataFrame()

    def fetch_all_from_soledot(self, progress_callback=None) -> pd.DataFrame:
        """soledot에서 전체 데이터 수집 (페이지별 20건씩)

        Args:
            progress_callback: 진행상황 콜백 (current, total)

        Returns:
            전체 당첨번호 DataFrame
        """
        # 1페이지를 먼저 가져와서 최신 회차 확인
        first_page = self.fetch_from_soledot(1)
        if first_page.empty:
            return pd.DataFrame()

        latest_round = int(first_page['round'].max())
        total_pages = (latest_round + 19) // 20  # 올림 나눗셈

        print(f"  최신 회차: {latest_round}회, 총 {total_pages}페이지")

        all_dfs = [first_page]

        for page in range(2, total_pages + 1):
            df = self.fetch_from_soledot(page)
            if not df.empty:
                all_dfs.append(df)

            if progress_callback:
                progress_callback(page, total_pages)

            # API 부하 방지
            time.sleep(0.3)

        result = pd.concat(all_dfs, ignore_index=True)
        result = result.drop_duplicates(subset=['round'])
        result = result.sort_values('round').reset_index(drop=True)
        return result

    def fetch_single_dhlottery(self, draw_no: int) -> dict | None:
        """동행복권 API에서 단일 회차 데이터 수집 (fallback)"""
        url = self.DHLOTTERY_API.format(draw_no)

        for attempt in range(config.MAX_RETRIES):
            try:
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                if data.get('returnValue') == 'fail':
                    return None

                return {
                    'round': data['drwNo'],
                    'date': data['drwNoDate'],
                    'n1': data['drwtNo1'],
                    'n2': data['drwtNo2'],
                    'n3': data['drwtNo3'],
                    'n4': data['drwtNo4'],
                    'n5': data['drwtNo5'],
                    'n6': data['drwtNo6'],
                    'bonus': data['bnusNo'],
                    'total_sales': data.get('totSellamnt', 0),
                    'winners': data.get('firstPrzwnerCo', 0),
                    'prize': data.get('firstWinamnt', 0),
                }
            except (requests.RequestException, ValueError, KeyError) as e:
                if attempt < config.MAX_RETRIES - 1:
                    time.sleep(config.API_DELAY * (attempt + 1))
                    continue
                return None

        return None

    def fetch_all(self, progress_callback=None) -> pd.DataFrame:
        """전체 데이터 수집 (soledot 우선, 실패 시 동행복권 API)"""
        print("  data.soledot.com에서 데이터를 수집합니다...")
        df = self.fetch_all_from_soledot(progress_callback)

        if not df.empty:
            print(f"  {len(df)}개 회차 수집 완료!")
            return df

        print("  soledot 수집 실패. 동행복권 API를 시도합니다...")
        # 동행복권 API fallback (시간이 오래 걸림)
        from datetime import datetime
        weeks = (datetime.now() - datetime(2002, 12, 7)).days // 7
        latest = weeks + 1

        records = []
        for draw_no in range(1, latest + 1):
            data = self.fetch_single_dhlottery(draw_no)
            if data:
                records.append(data)
            if progress_callback:
                progress_callback(draw_no, latest)
            time.sleep(config.API_DELAY)

        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records).sort_values('round').reset_index(drop=True)

    def fetch_new_rounds(self, last_round: int,
                         progress_callback=None) -> pd.DataFrame:
        """마지막 캐시 이후 새 회차만 수집

        Args:
            last_round: 캐시에 저장된 마지막 회차

        Returns:
            새 회차 데이터 DataFrame
        """
        # 최신 1페이지만 가져와서 확인
        first_page = self.fetch_from_soledot(1)
        if first_page.empty:
            return pd.DataFrame()

        # 캐시 이후 회차만 필터링
        new_data = first_page[first_page['round'] > last_round]

        if new_data.empty:
            return pd.DataFrame()

        # 1페이지(20건)에 다 안 들어오면 추가 페이지 수집
        if int(new_data['round'].min()) > last_round + 1:
            page = 2
            while True:
                df = self.fetch_from_soledot(page)
                if df.empty:
                    break
                page_new = df[df['round'] > last_round]
                if page_new.empty:
                    break
                new_data = pd.concat([new_data, page_new], ignore_index=True)
                if int(df['round'].min()) <= last_round:
                    break
                page += 1
                time.sleep(0.3)

        new_data = new_data.drop_duplicates(subset=['round'])
        new_data = new_data.sort_values('round').reset_index(drop=True)
        return new_data
