
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 화면 설정
# --------------------------------------------------

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")
st.write("원하는 날짜의 KOBIS 일일 박스오피스를 조회해 보세요.")


# --------------------------------------------------
# 2. 한국 시간 기준 날짜 계산
# --------------------------------------------------

# 배포 서버의 시간이 한국 시간이 아닐 수 있으므로
# 한국 시간(Asia/Seoul)을 기준으로 날짜를 계산합니다.
KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

# 오늘 날짜
today = now_kst.date()

# 선택할 수 있는 가장 늦은 날짜 = 어제
yesterday = today - timedelta(days=1)


# --------------------------------------------------
# 3. 조회 날짜 선택
# --------------------------------------------------

st.subheader("📅 조회 날짜")

selected_date = st.date_input(
    "박스오피스를 확인할 날짜를 선택하세요.",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday
)

# KOBIS API에서 사용하는 날짜 형식으로 변환
# 예: 2026-09-06 → 20260906
target_date = selected_date.strftime("%Y%m%d")

# 화면에 표시할 날짜
display_date = selected_date.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 4. KOBIS API 호출 함수
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_box_office(target_dt):
    """
    선택한 날짜의 KOBIS 일일 박스오피스를 가져옵니다.

    ttl=3600은 1시간 동안 같은 날짜의 API 결과를
    기억한다는 뜻입니다.
    """

    # Streamlit Cloud Secrets에서 인증키를 가져옵니다.
    # 인증키를 코드에 직접 작성하지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]

    except Exception:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 "
                "Secrets를 열고 KOBIS_KEY가 등록되어 있는지 "
                "확인해 주세요."
            )
        }

    # KOBIS 일일 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API에 전달할 값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # KOBIS API 요청
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생하면 예외를 발생시킵니다.
        response.raise_for_status()

        # JSON 데이터로 변환합니다.
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                "다음 내용을 확인해 주세요.\n"
                "• 인터넷 연결 상태\n"
                "• KOBIS API 서버 상태\n"
                "• API 주소\n\n"
                f"오류 내용: {e}"
            )
        }

    except ValueError:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API에서 올바른 JSON 데이터를 "
                "받지 못했습니다.\n\n"
                "잠시 후 다시 시도해 주세요."
            )
        }

    # --------------------------------------------------
    # 5. KOBIS의 faultInfo 확인
    # --------------------------------------------------

    # KOBIS는 인증키가 틀려도 HTTP 상태코드가
    # 200으로 올 수 있습니다.
    # 따라서 faultInfo가 있는지 직접 확인해야 합니다.
    if "faultInfo" in data:

        fault_info = data["faultInfo"]

        fault_message = (
            fault_info.get("message")
            or fault_info.get("error")
            or str(fault_info)
        )

        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 내용: {fault_message}\n\n"
                "KOBIS_KEY가 정확한지 확인해 주세요."
            )
        }

    # --------------------------------------------------
    # 6. boxOfficeResult 확인
    # --------------------------------------------------

    box_office_result = data.get("boxOfficeResult")

    if not box_office_result:
        return {
            "success": False,
            "empty": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "KOBIS API 응답에 boxOfficeResult가 "
                "있는지 확인해 주세요."
            )
        }

    # 영화 목록 가져오기
    movie_list = box_office_result.get(
        "dailyBoxOfficeList",
        []
    )

    # --------------------------------------------------
    # 7. 영화 목록이 비어 있는 경우
    # --------------------------------------------------

    if not movie_list:
        return {
            "success": True,
            "empty": True,
            "message": "그날은 아직 집계 전입니다."
        }

    return {
        "success": True,
        "empty": False,
        "data": movie_list
    }


# --------------------------------------------------
# 8. 선택한 날짜의 데이터 가져오기
# --------------------------------------------------

result = get_box_office(target_date)


# --------------------------------------------------
# 9. API 오류 처리
# --------------------------------------------------

if not result["success"]:

    st.error("⚠️ 박스오피스 데이터를 가져오지 못했습니다.")

    st.warning(result["message"])

    st.stop()


# --------------------------------------------------
# 10. 영화 목록이 없는 경우
# --------------------------------------------------

if result["empty"]:

    st.info(
        f"📅 {display_date} — 그날은 아직 집계 전입니다."
    )

    st.stop()


# --------------------------------------------------
# 11. 데이터를 데이터프레임으로 변환
# --------------------------------------------------

movies = result["data"]

df = pd.DataFrame(movies)


# --------------------------------------------------
# 12. 숫자 데이터를 실제 숫자로 변환
# --------------------------------------------------

# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 따라서 정렬과 그래프에 사용할 값은 숫자로 변환합니다.
numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in numeric_columns:

    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0)


# --------------------------------------------------
# 13. 순위 기준으로 정렬
# --------------------------------------------------

df = df.sort_values(
    "rank"
).reset_index(drop=True)


# --------------------------------------------------
# 14. 조회 날짜 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")


# --------------------------------------------------
# 15. 1위 영화 표시
# --------------------------------------------------

first_movie = df.iloc[0]

st.header(
    f"🥇 1위: {first_movie['movieNm']}"
)


# 1위 영화의 주요 정보를 크게 보여줍니다.
col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "당일 관객수",
        f"{int(first_movie['audiCnt']):,}명"
    )


with col2:

    st.metric(
        "누적 관객수",
        f"{int(first_movie['audiAcc']):,}명"
    )


with col3:

    st.metric(
        "스크린수",
        f"{int(first_movie['scrnCnt']):,}개"
    )


# --------------------------------------------------
# 16. 관객수 상위 5편 그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")


# 당일 관객수가 많은 순서로 정렬합니다.
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)


# 영화명을 그래프의 이름으로 사용합니다.
chart_data = top5.set_index("movieNm")[
    ["audiCnt"]
]


st.bar_chart(chart_data)


# --------------------------------------------------
# 17. 표에 표시할 데이터 만들기
# --------------------------------------------------

display_df = df[
    [
        "rank",
        "rankInten",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# --------------------------------------------------
# 18. 순위 증감 표시
# --------------------------------------------------

def make_rank_change(value):
    """
    전날 대비 순위 변화를 보기 쉽게 표시합니다.

    양수 → 빨간 위 화살표
    음수 → 파란 아래 화살표
    0 → 변화 없음
    """

    value = int(value)

    if value > 0:
        return f"🔴⬆️ {value}"

    elif value < 0:
        return f"🔵⬇️ {abs(value)}"

    else:
        return "—"


display_df["rankInten"] = (
    display_df["rankInten"]
    .apply(make_rank_change)
)


# --------------------------------------------------
# 19. 100만 관객 달성 영화에 트로피 추가
# --------------------------------------------------

def add_trophy(row):
    """
    누적 관객수가 100만 명을 넘으면
    영화명 뒤에 트로피 이모지를 붙입니다.
    """

    movie_name = row["movieNm"]
    accumulated_audience = int(row["audiAcc"])

    if accumulated_audience > 1_000_000:
        return f"{movie_name} 🏆"

    return movie_name


display_df["movieNm"] = df.apply(
    add_trophy,
    axis=1
)


# --------------------------------------------------
# 20. 표의 열 이름을 한국어로 변경
# --------------------------------------------------

display_df.columns = [
    "순위",
    "순위 변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# --------------------------------------------------
# 21. 박스오피스 표 출력
# --------------------------------------------------

st.subheader("🎥 전체 박스오피스")


st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={

        "순위": st.column_config.NumberColumn(
            format="%d위"
        ),

        "관객수": st.column_config.NumberColumn(
            format="%d명"
        ),

        "누적관객": st.column_config.NumberColumn(
            format="%d명"
        ),

        "스크린수": st.column_config.NumberColumn(
            format="%d개"
        )
    }
)


# --------------------------------------------------
# 22. 하단 안내
# --------------------------------------------------

st.caption(
    f"조회 기준일: {display_date} · "
    "한국시간 기준 · "
    "KOBIS 일일 박스오피스 API · "
    "동일 날짜 결과는 1시간 동안 캐시됩니다."
)
