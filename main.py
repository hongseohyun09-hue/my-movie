
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.write("한국시간 기준 어제의 일일 박스오피스를 보여줍니다.")


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# --------------------------------------------------

# 배포 서버가 한국 시간이 아닐 수 있으므로
# 서버의 현재 시간을 그대로 사용하지 않습니다.
KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

# 한국 시간 기준 어제
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여줄 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 3. KOBIS API 호출 함수
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_box_office(target_dt):
    """
    KOBIS 일일 박스오피스 API를 호출합니다.

    ttl=3600:
    같은 날짜의 결과를 약 1시간 동안 기억하여
    API를 계속 호출하지 않도록 합니다.
    """

    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키는 코드에 작성하지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 "
                "Secrets에 KOBIS_KEY가 등록되어 있는지 확인하세요."
            )
        }

    # KOBIS 일일 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API에 보낼 요청값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # API 요청
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있는 경우 예외 발생
        response.raise_for_status()

        # JSON으로 변환
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                "다음 내용을 확인해 주세요.\n"
                "• 인터넷 연결 상태\n"
                "• KOBIS API 주소\n"
                "• KOBIS API 서버 상태\n"
                f"• 오류 내용: {e}"
            )
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API에서 올바른 JSON 데이터를 받지 못했습니다.\n\n"
                "잠시 후 다시 실행해 보세요."
            )
        }

    # --------------------------------------------------
    # 4. 인증키 오류 확인
    # --------------------------------------------------

    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        # 오류 메시지가 있으면 가져옵니다.
        fault_message = (
            fault_info.get("message")
            or fault_info.get("error")
            or str(fault_info)
        )

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 내용: {fault_message}\n\n"
                "KOBIS_KEY가 정확한지 확인해 주세요."
            )
        }

    # --------------------------------------------------
    # 5. 박스오피스 결과 확인
    # --------------------------------------------------

    box_office_result = data.get("boxOfficeResult")

    if not box_office_result:
        return {
            "success": False,
            "message": (
                "박스오피스 결과가 없습니다.\n\n"
                "KOBIS API 응답에 boxOfficeResult가 있는지 "
                "확인해 주세요."
            )
        }

    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_dt} 날짜의 영화 목록이 없습니다.\n\n"
                "다음 내용을 확인해 주세요.\n"
                "• 조회 날짜가 올바른지\n"
                "• KOBIS에서 해당 날짜의 박스오피스가 집계되었는지\n"
                "• API 응답에 dailyBoxOfficeList가 있는지"
            )
        }

    return {
        "success": True,
        "data": movie_list
    }


# --------------------------------------------------
# 6. API에서 데이터 가져오기
# --------------------------------------------------

result = get_box_office(target_date)


# --------------------------------------------------
# 7. API 오류가 발생한 경우 안내
# --------------------------------------------------

if not result["success"]:
    st.error("⚠️ 박스오피스 데이터를 가져오지 못했습니다.")

    # 오류 메시지를 줄바꿈해서 보여주기
    st.warning(result["message"])

    st.stop()


# --------------------------------------------------
# 8. 영화 목록을 데이터프레임으로 변환
# --------------------------------------------------

movies = result["data"]

df = pd.DataFrame(movies)


# --------------------------------------------------
# 9. 숫자로 사용할 열을 숫자형으로 변환
# --------------------------------------------------

# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 그래프와 정렬을 제대로 하기 위해 숫자로 변환합니다.
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
# 10. 순위 기준으로 정렬
# --------------------------------------------------

df = df.sort_values("rank").reset_index(drop=True)


# --------------------------------------------------
# 11. 조회 날짜 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")


# --------------------------------------------------
# 12. 1위 영화 확인
# --------------------------------------------------

if len(df) > 0:
    first_movie = df.iloc[0]

    st.header(f"🥇 1위: {first_movie['movieNm']}")

    # 지표 카드 3개
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
# 13. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬한 뒤 5편만 선택
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 영화명을 그래프의 인덱스로 사용
chart_data = top5.set_index("movieNm")[["audiCnt"]]

# Streamlit 기본 막대그래프
st.bar_chart(chart_data)


# --------------------------------------------------
# 14. 전체 영화 목록 표
# --------------------------------------------------

st.subheader("🎥 전체 박스오피스")

# 사용자에게 보여줄 열만 선택
display_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 열 이름을 한국어로 변경
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 표에 숫자를 보기 좋게 표시
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
# 15. 데이터 업데이트 안내
# --------------------------------------------------

st.caption(
    f"조회 기준일: {display_date} · "
    "한국시간 기준 · "
    "KOBIS 일일 박스오피스 API"
)

