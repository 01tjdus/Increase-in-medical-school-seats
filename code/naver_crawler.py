"""Naver Blog crawler for medical school quota opinion analysis."""

# 전체 흐름:
# 1. 검색 결과에서 기간별 블로그 글 링크를 충분히 수집합니다.
# 2. 링크 체크포인트 CSV를 남겨 중간에 끊겨도 이어서 실행할 수 있게 합니다.
# 3. 각 글의 제목, 본문, 본문 좋아요 수, 댓글 수, 댓글 내용, 댓글 작성일,
#    댓글 좋아요 수를 추출합니다.
# 4. 최종 결과를 분석용 CSV로 저장합니다.
#
# 네이 버 화면 구조는 수시로 바뀔 수 있으므로 CSS 선택자는 여러 후보를 함께 둡니다.
# 대량 수집은 실패 링크가 생길 수 있어 target-count보다 더 많은 링크를 먼저 모읍니다.
import argparse
import html as html_lib
import json
import math
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException

# 최종 본문 데이터 목표 수입니다.
# 사용자가 요청한 10,000~20,000건 범위 안에서 기본값을 20,000건으로 둡니다.
TARGET_DATA_COUNT = 20000

# 설계서 기준 분석 기간입니다.
# 네이버 검색 결과는 날짜 범위가 길수록 누락되기 쉬워서 일자 단위로 쪼개 검색합니다.
PERIODS = [
    {"name": "1구간", "start": "20240101", "end": "20240331"},
    {"name": "2구간", "start": "20240401", "end": "20240630"},
    {"name": "3구간", "start": "20240701", "end": "20241231"},
    {"name": "4구간", "start": "20250101", "end": "20250630"},
]
# 본문과 댓글까지 파싱한 최종 결과 CSV입니다.
OUTPUT_FILE = "naver_blog_medical_quota.csv"


def get_daily_dates(start_str, end_str):
    """YYYYMMDD 형식의 시작일과 종료일 사이에 있는 모든 날짜를 YYYYMMDD 문자열 목록으로 반환합니다."""
    start = datetime.strptime(start_str, "%Y%m%d")
    end = datetime.strptime(end_str, "%Y%m%d")
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return dates


# 이번 과제에서는 다른 검색어를 섞지 않고 '의대 증원'만 수집합니다.
KEYWORDS = ["의대 증원"]
KEYWORD = KEYWORDS[0]

# 검색 링크만 따로 저장하는 체크포인트 파일입니다.
# 본문 파싱 전에 링크를 먼저 많이 모아두면 중간 실패 후에도 링크 수집부터 다시 하지 않아도 됩니다.
LINKS_OUTPUT_FILE = "naver_blog_medical_quota_links.csv"

# 최종 CSV에서 앞쪽에 고정할 컬럼 순서입니다.
# 기존 CSV에 없는 새 컬럼은 빈 값으로 만들어서 이전 결과와 새 결과가 함께 저장되게 합니다.
OUTPUT_COLUMNS = [
    "title",
    "content",
    "post_like_count",
    "like_count",
    "comment_count",
    "comments_text",
    "comment_times",
    "comment_like_counts",
    "comments_json",
    "url",
    "canonical_url",
    "keyword",
    "source",
    "section",
    "date",
    "search_date",
    "search_sort",
    "post_date",
    "writer",
]


def clean_text(value):
    """분석에 방해되는 제로폭 문자와 과도한 공백을 정리합니다."""
    if value is None:
        return ""
    text = str(value)
    text = html_lib.unescape(text)
    text = text.replace("\u200b", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_int(value, default=0):
    """'댓글 1,234개'처럼 숫자 외 문자가 섞인 문자열에서 정수만 추출합니다."""
    text = clean_text(value)
    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return default
    try:
        return int(digits)
    except ValueError:
        return default


def split_saved_comment_values(value):
    """CSV에 || 로 저장한 댓글 관련 값을 개별 값 목록으로 되돌립니다."""
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"\s*\|\|\s*", text) if part.strip()]


def has_complete_comment_meta(record, max_comments_per_post=50):
    """
    분석에 쓸 수 있는 완성 행인지 확인합니다.

    제목/본문/게시글 좋아요/댓글 수가 있고, 저장된 댓글마다 댓글 날짜와 댓글 좋아요 수가
    같은 개수로 붙어 있어야 완성 행으로 봅니다. 댓글 좋아요 0개는 정상 값입니다.
    """
    getter = record.get if hasattr(record, "get") else lambda key, default="": default

    if not clean_text(getter("title", "")) or not clean_text(getter("content", "")):
        return False

    post_like = parse_int(getter("post_like_count", ""), default=None)
    legacy_like = parse_int(getter("like_count", ""), default=None)
    if post_like is None and legacy_like is None:
        return False

    comment_count = parse_int(getter("comment_count", ""), default=0)
    if comment_count <= 0:
        return False

    comment_texts = split_saved_comment_values(getter("comments_text", ""))
    comment_times = split_saved_comment_values(getter("comment_times", ""))
    comment_likes = split_saved_comment_values(getter("comment_like_counts", ""))
    if not comment_texts:
        return False
    if len(comment_texts) != len(comment_times) or len(comment_texts) != len(comment_likes):
        return False
    if any(parse_int(value, default=None) is None for value in comment_likes):
        return False

    # max_comments_per_post는 저장 상한입니다. 상한보다 많은 댓글이 있는 글은 앞쪽 일부만 저장합니다.
    if max_comments_per_post > 0 and len(comment_texts) > max_comments_per_post:
        return False
    return True


def filter_complete_comment_rows(df, max_comments_per_post=50):
    """제목/본문만 있거나 댓글 메타가 빠진 행을 제거합니다."""
    if df.empty:
        return df

    mask = df.apply(
        lambda row: has_complete_comment_meta(row, max_comments_per_post=max_comments_per_post),
        axis=1,
    )
    removed = len(df) - int(mask.sum())
    if removed:
        print(f"댓글 본문/날짜/좋아요가 완성되지 않은 기존 행 제거: {removed:,}건")
    return df[mask].reset_index(drop=True)


def split_keywords(raw_keywords):
    """
    명령행에서 받은 검색어 문자열을 목록으로 바꿉니다.

    쉼표와 | 기호를 모두 구분자로 허용합니다.
    값이 비어 있으면 기본 검색어인 '의대 증원'을 사용합니다.
    """
    if isinstance(raw_keywords, (list, tuple)):
        keywords = raw_keywords
    else:
        keywords = re.split(r"[,|]", raw_keywords or "")

    cleaned = []
    for keyword in keywords:
        keyword = clean_text(keyword)
        if keyword and keyword not in cleaned:
            cleaned.append(keyword)
    return cleaned or KEYWORDS


def split_csv_values(raw_value, fallback=None):
    """쉼표 또는 | 로 구분된 옵션 값을 중복 없는 목록으로 정리합니다."""
    values = []
    for value in re.split(r"[,|]", raw_value or ""):
        value = clean_text(value)
        if value and value not in values:
            values.append(value)
    return values or list(fallback or [])


def canonical_post_url(raw_url):
    """네이버 블로그 글 URL을 중복 제거용 PC 표준 URL로 변환합니다."""
    if not raw_url:
        return None

    url = html_lib.unescape(str(raw_url)).replace("\\/", "/").strip()
    if url.startswith("//"):
        url = "https:" + url

    parsed = urlparse(url)
    if "blog.naver.com" not in parsed.netloc:
        return None

    # 네이버 블로그 URL은 /아이디/글번호 형태와 querystring 형태가 섞여 나옵니다.
    # 두 형태를 모두 https://blog.naver.com/{blog_id}/{log_no}로 통일해야 중복 제거가 가능합니다.
    query = parse_qs(parsed.query)
    blog_id = (query.get("blogId") or query.get("blogid") or [""])[0]
    log_no = (query.get("logNo") or query.get("logno") or [""])[0]
    if blog_id and log_no and log_no.isdigit():
        return f"https://blog.naver.com/{blog_id}/{log_no}"

    match = re.search(r"https?://(?:m\.)?blog\.naver\.com/([^/?#]+)/(\d+)", url)
    if not match:
        return None

    blog_id, log_no = match.group(1), match.group(2)
    # 글 본문이 아닌 블로그 목록/관리 페이지는 수집 대상에서 제외합니다.
    if blog_id.lower() in {"postview.naver", "postlist.naver", "myblog.naver"}:
        return None
    return f"https://blog.naver.com/{blog_id}/{log_no}"


def to_mobile_url(canonical_url):
    """표준 PC 블로그 URL을 모바일 URL로 변환합니다. 모바일 페이지가 댓글/본문 파싱에 더 안정적입니다."""
    canonical = canonical_post_url(canonical_url)
    if not canonical:
        return canonical_url
    return canonical.replace("https://blog.naver.com/", "https://m.blog.naver.com/")


def extract_blog_links_from_html(html):
    """
    네이버 검색 결과의 현재 Fender 구조와 스크립트 JSON 구조를 모두 훑어 글 링크를 찾습니다.
    핵심 셀렉터는 아직 .nblg가 맞지만, data-url/titleHref/contentHref까지 같이 봐야 안정적입니다.
    """
    if not html:
        return []

    decoded = html_lib.unescape(html).replace("\\/", "/")
    soup = BeautifulSoup(decoded, "html.parser")

    # 1차 추출: 실제 DOM에 들어 있는 링크성 속성을 전부 확인합니다.
    # 네이버 검색 결과는 href 대신 data-url 계열 속성에 원문 링크를 넣는 경우가 있습니다.
    candidates = []
    for tag in soup.find_all(True):
        for attr in ("href", "data-url", "data-href", "titleHref", "contentHref"):
            value = tag.get(attr)
            if value and "blog.naver.com" in value:
                candidates.append(value)

    patterns = [
        r"https?://(?:m\.)?blog\.naver\.com/[A-Za-z0-9_.%-]+/\d+",
        r'"(?:titleHref|contentHref|keepTriggerUrl)"\s*:\s*"(https?://(?:m\.)?blog\.naver\.com/[^"]+/\d+)"',
        r"data-url=[\"'](https?://(?:m\.)?blog\.naver\.com/[^\"']+/\d+)[\"']",
    ]
    # 2차 추출: 화면에 직접 노출되지 않고 스크립트 JSON 안에 숨어 있는 링크까지 정규식으로 찾습니다.
    for pattern in patterns:
        for match in re.findall(pattern, decoded):
            candidates.append(match)

    unique = []
    seen = set()
    for candidate in candidates:
        canonical = canonical_post_url(candidate)
        if canonical and canonical not in seen:
            seen.add(canonical)
            unique.append(canonical)
    return unique


def build_search_url(keyword, date, sort="r"):
    """
    네이버 블로그 검색 URL을 생성합니다.

    sort='r'은 관련도순, sort='dd'는 최신순입니다.
    날짜는 fromYYYYMMDDtoYYYYMMDD 형식으로 하루 단위 검색을 만듭니다.
    """
    params = {
        "ssc": "tab.blog.all",
        "query": keyword,
        "sm": "tab_opt",
        "nso": f"so:{sort},p:from{date}to{date}",
    }
    return "https://search.naver.com/search.naver?" + urlencode(params)


def setup_driver(headless=True, driver_path=None, use_webdriver_manager=False):
    """
    Selenium 크롬 드라이버를 초기화합니다.
    기본은 Selenium Manager를 사용합니다. webdriver_manager 다운로드는 오래 걸릴 수 있어 옵션일 때만 사용합니다.
    """
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")

    # 크롤링 안정성을 위한 기본 옵션입니다.
    # headless 환경에서도 동일한 화면 폭으로 결과가 뜨게 하고, 자동화 탐지 신호를 일부 줄입니다.
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    if driver_path:
        # 회사/학교 PC처럼 자동 다운로드가 막힌 환경에서는 직접 받은 chromedriver.exe 경로를 씁니다.
        print(f"ChromeDriver 경로 사용: {driver_path}")
        driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.implicitly_wait(3)
        driver.set_page_load_timeout(45)
        return driver

    print("ChromeDriver 초기화 중입니다. 처음 실행이면 Selenium Manager가 드라이버를 준비하느라 시간이 걸릴 수 있습니다.")
    try:
        # Selenium 4.6+는 Selenium Manager로 현재 크롬에 맞는 드라이버를 자동 준비할 수 있습니다.
        driver = webdriver.Chrome(options=chrome_options)
    except WebDriverException as exc:
        if not use_webdriver_manager:
            raise RuntimeError(
                "ChromeDriver 자동 초기화에 실패했습니다. 크롬이 설치되어 있는지 확인한 뒤 다시 실행하거나, "
                "--driver-path 옵션으로 chromedriver.exe 경로를 직접 지정하세요. "
                "webdriver_manager 다운로드를 시도하려면 --use-webdriver-manager 옵션을 추가하세요."
            ) from exc

        print("Selenium Manager가 실패해서 webdriver_manager로 드라이버를 내려받습니다. 네트워크 상태에 따라 오래 걸릴 수 있습니다.")
        from webdriver_manager.chrome import ChromeDriverManager

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.implicitly_wait(3)
    driver.set_page_load_timeout(45)
    return driver


def sleep_random(min_delay, max_delay):
    """요청 간격을 조금씩 흔들어 너무 기계적인 접속 패턴을 피합니다."""
    time.sleep(random.uniform(min_delay, max(max_delay, min_delay)))


def scroll_and_extract_links(driver, required_count, max_scrolls, min_delay, max_delay):
    """
    검색 결과 페이지를 아래로 스크롤하면서 블로그 글 링크를 모읍니다.

    같은 링크 수가 몇 번 반복되면 더 내려도 새 결과가 없다고 보고 중단합니다.
    """
    best_links = []
    stagnant_rounds = 0

    for attempt in range(max_scrolls + 1):
        links = extract_blog_links_from_html(driver.page_source)
        if len(links) > len(best_links):
            best_links = links
            stagnant_rounds = 0
        else:
            stagnant_rounds += 1

        if len(best_links) >= required_count:
            break
        if attempt >= max_scrolls or stagnant_rounds >= 3:
            break

        # 네이버 검색은 무한 스크롤 방식이라 스크롤을 내려야 다음 결과 묶음이 로드됩니다.
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep_random(min_delay, max_delay)

    return best_links[:required_count]


def collect_blog_links(
    driver,
    dates,
    required_per_day,
    section_name,
    keyword=KEYWORD,
    max_scrolls=12,
    sort="r",
    min_delay=1.0,
    max_delay=1.8,
):
    """
    특정 날짜 목록에 대해 네이버 블로그 검색 링크를 수집합니다.

    반환값은 본문 파싱에 바로 사용할 수 있도록 검색 구간, 검색일, 정렬 방식,
    원본 키워드, 표준 URL, 모바일 URL을 모두 담은 dict 목록입니다.
    """
    collected_links = []
    print(f"\n[{section_name}] '{keyword}' 블로그 검색 링크 수집 시작 (sort={sort})")

    for date in tqdm(dates, desc=f"{section_name} {keyword} {sort}"):
        search_url = build_search_url(keyword, date, sort=sort)
        try:
            driver.get(search_url)
            sleep_random(min_delay, max_delay)
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
        except Exception:
            # 검색 페이지 로딩이 일부 실패해도 현재 page_source에서 뽑을 수 있는 링크가 있을 수 있어 계속 진행합니다.
            pass

        links = scroll_and_extract_links(
            driver,
            required_per_day,
            max_scrolls=max_scrolls,
            min_delay=min_delay,
            max_delay=max_delay,
        )

        for canonical in links:
            collected_links.append(
                {
                    "section": section_name,
                    "date": date,
                    "search_date": date,
                    "search_sort": sort,
                    "keyword": keyword,
                    "canonical_url": canonical,
                    "url": to_mobile_url(canonical),
                }
            )

    return collected_links


def extract_first_text(soup, selectors):
    """여러 CSS 선택자 후보 중 처음으로 비어 있지 않은 텍스트를 반환합니다."""
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            text = clean_text(tag.get("content") if tag.name == "meta" else tag.get_text(" ", strip=True))
            if text:
                return text
    return ""


def extract_best_content(soup):
    """
    글 본문 후보 영역 중 가장 그럴듯한 본문 텍스트를 찾습니다.

    네이버 블로그는 스마트에디터 버전이나 스킨에 따라 본문 컨테이너가 다릅니다.
    그래서 여러 컨테이너 후보를 순서대로 검사하고, 충분한 길이의 텍스트가 나오면 본문으로 채택합니다.
    """
    selectors = [
        "div.se-main-container",
        "div#postViewArea",
        "div.post-view",
        "div.post_ct",
        "div#viewTypeSelector",
    ]

    for selector in selectors:
        best_for_selector = ""
        for area in soup.select(selector):
            # script/style/iframe은 실제 분석 본문이 아니므로 제거한 뒤 텍스트만 추출합니다.
            clone = BeautifulSoup(str(area), "html.parser")
            for junk in clone.select("script, style, iframe, noscript"):
                junk.decompose()
            text = clean_text(clone.get_text(" ", strip=True))
            if len(text) > len(best_for_selector):
                best_for_selector = text
        if len(best_for_selector) >= 20:
            return best_for_selector
    return ""


def extract_like_count(soup):
    """본문에 달린 공감/좋아요 수를 여러 네이버 블로그 UI 후보에서 추출합니다."""
    selectors = [
        "li.u_likeit_list.like span.u_likeit_list_count",
        "a[data-type='like'] span.u_likeit_list_count",
        "span.u_likeit_text._count.num",
        "em.u_cnt._count",
        ".btn_sympathy ._count",
    ]
    for selector in selectors:
        for tag in soup.select(selector):
            value = parse_int(tag.get_text(" ", strip=True), default=None)
            if value is not None:
                return value
    return 0


def extract_comment_count(soup, html):
    """
    게시글의 전체 댓글 수를 추출합니다.

    댓글 목록을 전부 열지 않아도 페이지 속성이나 스크립트에 commentCount가 들어 있는 경우가 많습니다.
    우선 숨은 속성/스크립트를 보고, 없으면 화면에 보이는 댓글 버튼 텍스트를 확인합니다.
    """
    prop = soup.select_one("#_post_property")
    if prop and prop.get("commentcount") is not None:
        return parse_int(prop.get("commentcount"))

    for pattern in (r'"commentCount"\s*:\s*(\d+)', r"commentCount\s*[:=]\s*['\"]?(\d+)"):
        match = re.search(pattern, html)
        if match:
            return parse_int(match.group(1))

    selectors = [
        "button[class*='comment_btn'] span[class*='num']",
        "h2[class*='title'] span[class*='num']",
        "a.btn_reply",
    ]
    for selector in selectors:
        for tag in soup.select(selector):
            value = parse_int(tag.get_text(" ", strip=True), default=None)
            if value is not None:
                return value
    return 0


def extract_post_property(soup):
    """네이버가 페이지에 심어 둔 속성에서 본문 작성일과 작성자 닉네임을 추출합니다."""
    prop = soup.select_one("#_post_property")
    post_date = ""
    if prop and prop.get("adddate"):
        try:
            # adddate는 밀리초 단위 Unix timestamp로 들어오는 경우가 많아 YYYYMMDD로 변환합니다.
            post_date = datetime.fromtimestamp(int(prop.get("adddate")) / 1000).strftime("%Y%m%d")
        except (TypeError, ValueError, OSError):
            post_date = ""

    writer = extract_first_text(
        soup,
        [
            "meta[property='naverblog:nickname']",
            "meta[property='og:article:author']",
            "strong.ell",
        ],
    )
    return post_date, writer


def find_direct_child_by_class(tag, class_name):
    """댓글 박스 안에서 바로 아래 자식 중 특정 class를 가진 태그만 찾습니다."""
    for child in tag.find_all(recursive=False):
        classes = child.get("class") or []
        if class_name in classes:
            return child
    return None


def extract_comment_like_count(comment_box):
    """
    댓글 하나에 달린 공감 수를 추출합니다.

    네이버 댓글은 추천 버튼이 숨겨진 상태로 중복 렌더링되는 경우가 있어,
    먼저 화면에 보이는 버튼을 우선하고 없으면 fallback 후보를 사용합니다.
    """
    if not comment_box:
        return 0

    visible_candidates = []
    fallback_candidates = []
    for button in comment_box.select("a.u_cbox_btn_recomm"):
        count_tag = button.select_one("em.u_cbox_cnt_recomm")
        if not count_tag:
            continue
        fallback_candidates.append(count_tag)
        style = (button.get("style") or "").replace(" ", "").lower()
        if "display:none" not in style:
            visible_candidates.append(count_tag)

    candidates = visible_candidates or fallback_candidates
    if not candidates:
        return 0
    return parse_int(candidates[0].get_text(" ", strip=True))


def extract_comments_from_soup(soup, max_comments):
    """
    현재 HTML에 로드된 댓글 목록에서 댓글 내용, 작성 시간, 댓글 공감 수를 추출합니다.

    댓글이 너무 많은 글에서 CSV가 과도하게 커지지 않도록 max_comments까지만 저장합니다.
    """
    comments = []
    for comment in soup.select("li.u_cbox_comment"):
        comment_box = find_direct_child_by_class(comment, "u_cbox_comment_box")
        if not comment_box:
            continue

        text_tag = comment_box.select_one("span.u_cbox_contents")
        text = clean_text(text_tag.get_text(" ", strip=True)) if text_tag else ""
        if text:
            date_tag = comment_box.select_one("span.u_cbox_date")
            # data-value가 있으면 원본 시간값을 우선 사용하고, 없으면 화면 표시 텍스트를 사용합니다.
            comment_time = clean_text(date_tag.get("data-value") if date_tag else "")
            if not comment_time and date_tag:
                comment_time = clean_text(date_tag.get_text(" ", strip=True))

            comments.append(
                {
                    "text": text,
                    "time": comment_time,
                    "like_count": extract_comment_like_count(comment_box),
                }
            )
        if len(comments) >= max_comments:
            break
    return comments


def parse_blog_html(html, url="", max_comments=50):
    """
    블로그 글 HTML 하나를 분석해서 최종 CSV 한 행에 들어갈 본문/댓글 데이터를 만듭니다.

    comments_json에는 댓글별 text/time/like_count를 구조화해서 저장하고,
    comments_text/comment_times/comment_like_counts에는 엑셀에서 보기 쉽게 || 구분 문자열을 저장합니다.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    title = extract_first_text(
        soup,
        [
            "meta[property='og:title']",
            "span.se-title-text",
            "div.se-title-text",
            ".se-title-text",
            "h3",
        ],
    )
    title = re.sub(r"\s*:\s*네이버 블로그\s*$", "", title).strip()

    post_date, writer = extract_post_property(soup)
    comments = extract_comments_from_soup(soup, max_comments)
    comment_texts = [comment["text"] for comment in comments]
    comment_times = [comment["time"] for comment in comments]
    comment_like_counts = [str(comment["like_count"]) for comment in comments]
    post_like_count = extract_like_count(soup)

    return {
        "title": title,
        "content": extract_best_content(soup),
        "post_like_count": post_like_count,
        "like_count": post_like_count,
        "comment_count": extract_comment_count(soup, html or ""),
        "comments_text": " || ".join(comment_texts),
        "comment_times": " || ".join(comment_times),
        "comment_like_counts": " || ".join(comment_like_counts),
        "comments_json": json.dumps(comments, ensure_ascii=False),
        "post_date": post_date,
        "writer": writer,
        "source": "네이버 블로그",
    }


def open_comment_layer(driver, max_comments=50):
    """
    모바일 블로그 글에서 댓글 영역을 열고, 필요한 만큼 '더보기'를 눌러 댓글을 로드합니다.

    parse_blog_html은 현재 page_source에 들어온 댓글만 읽을 수 있으므로,
    댓글이 있는 글은 먼저 버튼을 눌러 댓글 레이어를 열어야 합니다.
    """
    selectors = [
        "button.comment_btn__TUucZ",
        "button[class*='comment_btn']",
        "a.btn_reply",
    ]

    clicked = False
    for selector in selectors:
        for button in driver.find_elements(By.CSS_SELECTOR, selector):
            try:
                # 화면 밖에 있거나 일반 click이 막힌 요소도 JS 클릭으로 열 수 있는 경우가 많습니다.
                driver.execute_script("arguments[0].click();", button)
                clicked = True
                break
            except Exception:
                continue
        if clicked:
            break

    if not clicked:
        return

    try:
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#naverComment, span.u_cbox_contents, span.u_cbox_secret_contents")
            )
        )
    except TimeoutException:
        # 댓글 버튼은 눌렸지만 로딩이 안 되는 글이 있어, 해당 글은 댓글 없이 계속 진행합니다.
        return

    max_more_clicks = max(0, math.ceil(max_comments / 20))
    for _ in range(max_more_clicks):
        current_count = len(driver.find_elements(By.CSS_SELECTOR, "span.u_cbox_contents"))
        if current_count >= max_comments:
            break

        more_buttons = driver.find_elements(By.CSS_SELECTOR, "a.u_cbox_btn_more")
        visible_more = [btn for btn in more_buttons if btn.is_displayed()]
        if not visible_more:
            break

        try:
            # 댓글 더보기는 보통 20개 단위로 추가 로드됩니다.
            driver.execute_script("arguments[0].click();", visible_more[-1])
            time.sleep(1.0)
        except Exception:
            break


def parse_blog_content(
    driver,
    url,
    collect_comments=True,
    max_comments=50,
    article_min_delay=1.0,
    article_max_delay=2.0,
):
    """
    블로그 글 하나에 접속해 제목/본문/좋아요/댓글 정보를 추출합니다.

    1차로 본문 HTML을 파싱한 뒤 댓글 수가 1개 이상이면 댓글 레이어를 열고 다시 파싱합니다.
    이렇게 해야 본문 메타와 동적 댓글 데이터를 한 행에 함께 담을 수 있습니다.
    """
    mobile_url = to_mobile_url(url)
    driver.get(mobile_url)
    sleep_random(article_min_delay, article_max_delay)

    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
    except TimeoutException:
        pass

    result = parse_blog_html(driver.page_source, mobile_url, max_comments=max_comments)
    if collect_comments and result["comment_count"] > 0 and max_comments > 0:
        # 댓글은 초기 HTML에 없고 버튼 클릭 후 로드되는 경우가 많아 한 번 더 파싱합니다.
        open_comment_layer(driver, max_comments=max_comments)
        result = parse_blog_html(driver.page_source, mobile_url, max_comments=max_comments)
    return result


def save_dataframe(df, path):
    """
    DataFrame을 UTF-8 BOM CSV로 저장합니다.

    utf-8-sig를 쓰면 Windows Excel에서 한글이 깨지지 않고 열립니다.
    OUTPUT_COLUMNS를 앞쪽에 강제로 배치해 실행할 때마다 컬럼 순서가 흔들리지 않게 합니다.
    """
    df = df.copy()
    for column in OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    front = [column for column in OUTPUT_COLUMNS if column in df.columns]
    rest = [column for column in df.columns if column not in front]
    df[front + rest].to_csv(path, index=False, encoding="utf-8-sig")


def load_csv(path):
    """CSV가 있으면 읽고, 없거나 비어 있거나 깨진 파일이면 빈 DataFrame을 반환합니다."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def normalize_existing_results(df):
    """
    이전 실행 결과 CSV를 현재 코드의 컬럼 구조에 맞게 보정합니다.

    예전 버전에는 canonical_url, post_like_count, comment_times 같은 컬럼이 없을 수 있으므로
    이어받기 전에 필요한 컬럼을 만들어 줍니다.
    """
    if df.empty:
        return df
    df = df.copy()
    if "canonical_url" not in df.columns:
        # URL 표준화 컬럼이 없던 기존 결과도 중복 제거가 가능하도록 보강합니다.
        df["canonical_url"] = df["url"].map(canonical_post_url) if "url" in df.columns else ""
    if "post_like_count" not in df.columns and "like_count" in df.columns:
        df["post_like_count"] = df["like_count"]
    if "like_count" not in df.columns and "post_like_count" in df.columns:
        df["like_count"] = df["post_like_count"]
    if "search_date" not in df.columns and "date" in df.columns:
        df["search_date"] = df["date"]
    for column in OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df["source"] = df["source"].replace("", "네이버 블로그").fillna("네이버 블로그")
    return df


def dedupe_links(df):
    """링크 체크포인트에서 표준 URL 기준으로 중복 글을 제거합니다."""
    if df.empty:
        return df
    df = df.copy()
    if "canonical_url" not in df.columns:
        df["canonical_url"] = df["url"].map(canonical_post_url)
    df = df[df["canonical_url"].notna() & (df["canonical_url"] != "")]
    return df.drop_duplicates(subset=["canonical_url"]).reset_index(drop=True)


def filter_links_for_keywords(df, keywords):
    """기존 링크 체크포인트에 다른 검색어가 섞여 있으면 현재 검색어에 맞는 링크만 남깁니다."""
    if df.empty or "keyword" not in df.columns:
        return df
    allowed = set(keywords)
    return df[df["keyword"].isin(allowed)].reset_index(drop=True)


def reparse_existing_comment_meta(driver, args, existing_df, output_path):
    """
    이미 수집한 결과 중 댓글 시간/댓글 공감 수가 비어 있는 행만 다시 열어 보강합니다.

    이전 버전으로 모은 CSV를 버리지 않고, 부족한 댓글 메타데이터만 추가할 때 사용합니다.
    """
    if not args.reparse_existing_comment_meta or existing_df.empty:
        return existing_df

    df = normalize_existing_results(existing_df).copy()
    for column in OUTPUT_COLUMNS:
        if column in df.columns:
            df[column] = df[column].astype("object")

    comment_counts = pd.to_numeric(df["comment_count"], errors="coerce").fillna(0)
    if args.require_complete_comment_meta:
        incomplete_meta = ~df.apply(
            lambda row: has_complete_comment_meta(
                row,
                max_comments_per_post=args.max_comments_per_post,
            ),
            axis=1,
        )
        # 댓글 수가 0인 글은 완성 댓글 행으로 만들 수 없으므로 보강 대상에서도 제외합니다.
        targets = df[incomplete_meta & (comment_counts > 0)]
    else:
        missing_meta = (
            df["comment_times"].fillna("").astype(str).str.strip().eq("")
            | df["comment_like_counts"].fillna("").astype(str).str.strip().eq("")
        )
        # 댓글 수가 0인 글은 보강할 댓글 메타가 없으므로 제외합니다.
        targets = df[missing_meta & (comment_counts > 0)]
    if args.reparse_limit:
        targets = targets.head(args.reparse_limit)

    print(f"기존 댓글 시간/공감 수 보강 대상: {len(targets):,}건")
    if targets.empty:
        return df

    try:
        iterator = tqdm(targets.iterrows(), total=len(targets), desc="기존 댓글 메타 보강")
        for done, (idx, row) in enumerate(iterator, start=1):
            try:
                data = parse_blog_content(
                    driver,
                    row["url"],
                    collect_comments=not args.no_comments,
                    max_comments=args.max_comments_per_post,
                    article_min_delay=args.article_min_delay,
                    article_max_delay=args.article_max_delay,
                )
            except Exception:
                # 특정 글 하나가 실패해도 전체 보강 작업은 계속 진행합니다.
                continue

            for key in (
                "post_like_count",
                "like_count",
                "comment_count",
                "comments_text",
                "comment_times",
                "comment_like_counts",
                "comments_json",
                "post_date",
                "writer",
            ):
                df.loc[idx, key] = data.get(key, "")

            if done % args.save_interval == 0:
                # 대량 보강 중 중단되어도 손실을 줄이기 위해 주기적으로 저장합니다.
                save_dataframe(df, output_path)
    except KeyboardInterrupt:
        print("\n중단 요청을 받아 기존 댓글 메타 보강 결과를 현재까지 저장합니다.")
        save_dataframe(df, output_path)
        raise

    save_dataframe(df, output_path)
    return df


def parse_args():
    """명령행 옵션을 정의합니다. 기본값은 대량 수집 실행에 맞춰져 있습니다."""
    parser = argparse.ArgumentParser(description="네이버 블로그 '의대 증원' 대량 크롤러")
    parser.add_argument("--keywords", default=",".join(KEYWORDS), help="쉼표로 구분한 검색어")
    parser.add_argument("--target-count", type=int, default=TARGET_DATA_COUNT, help="최종 본문 수집 목표")
    parser.add_argument("--output", default=OUTPUT_FILE, help="본문 CSV 저장 경로")
    parser.add_argument("--links-output", default=LINKS_OUTPUT_FILE, help="링크 체크포인트 CSV")
    parser.add_argument("--link-multiplier", type=float, default=2.5, help="본문 실패 대비 링크 여유 배율")
    parser.add_argument("--max-scrolls", type=int, default=30, help="검색 결과 일자별 최대 스크롤 수")
    parser.add_argument("--min-links-per-query", type=int, default=40, help="날짜/검색어/정렬 조합마다 최소 수집할 링크 수")
    parser.add_argument("--sort", default="r", choices=["r", "dd"], help="네이버 검색 정렬: r=관련도, dd=최신순")
    parser.add_argument("--sorts", default="r,dd", help="쉼표로 구분한 정렬 목록. 예: r,dd")
    parser.add_argument("--show-browser", action="store_true", help="브라우저 창을 보이게 실행")
    parser.add_argument("--driver-path", default="", help="chromedriver.exe 경로를 직접 지정")
    parser.add_argument("--use-webdriver-manager", action="store_true", help="Selenium Manager 실패 시 webdriver_manager 다운로드 사용")
    parser.add_argument("--link-only", action="store_true", help="본문 수집 없이 링크만 수집")
    parser.add_argument("--refresh-links", action="store_true", help="기존 링크 체크포인트를 무시하고 다시 수집")
    parser.add_argument("--no-resume", action="store_true", help="기존 결과 CSV 이어받기 비활성화")
    parser.add_argument("--keep-existing-other-keywords", action="store_true", help="기존 CSV에 섞인 다른 검색어 결과도 유지")
    parser.add_argument("--reparse-existing-comment-meta", action="store_true", help="기존 CSV 중 댓글 시간/공감 수가 비어 있는 글을 다시 열어 보강")
    parser.add_argument("--reparse-limit", type=int, default=0, help="기존 댓글 메타 보강 개수 제한. 0이면 제한 없음")
    parser.add_argument("--require-complete-comment-meta", action="store_true", help="댓글 본문/날짜/댓글 좋아요가 모두 있는 행만 최종 CSV에 저장")
    parser.add_argument("--no-comments", action="store_true", help="댓글 본문 수집 비활성화")
    parser.add_argument("--max-comments-per-post", type=int, default=50, help="게시글당 저장할 댓글 최대 개수")
    parser.add_argument("--save-interval", type=int, default=50, help="본문 수집 중간 저장 간격")
    parser.add_argument("--max-days", type=int, default=0, help="테스트용: 앞에서부터 N일만 수집")
    parser.add_argument("--limit-links", type=int, default=0, help="테스트용: 본문 파싱 링크 개수 제한")
    parser.add_argument("--search-min-delay", type=float, default=1.0)
    parser.add_argument("--search-max-delay", type=float, default=1.8)
    parser.add_argument("--article-min-delay", type=float, default=1.0)
    parser.add_argument("--article-max-delay", type=float, default=2.0)
    return parser.parse_args()


def build_period_rows(max_days=0):
    """
    PERIODS에 정의된 전체 기간을 일자별 작업 목록으로 펼칩니다.

    max_days는 실제 크롤링 전 빠른 테스트를 위해 앞에서부터 N일만 실행하는 옵션입니다.
    """
    rows = []
    for period in PERIODS:
        for date in get_daily_dates(period["start"], period["end"]):
            rows.append({"section": period["name"], "date": date})
            if max_days and len(rows) >= max_days:
                return rows
    return rows


def collect_all_links(driver, args, keywords, period_rows):
    """
    목표 본문 수보다 넉넉한 링크를 먼저 수집합니다.

    본문 삭제, 비공개, 로딩 실패, 댓글 로딩 실패가 발생할 수 있으므로
    target-count에 link-multiplier를 곱한 만큼 링크를 확보합니다.
    """
    target_link_count = math.ceil(args.target_count * args.link_multiplier)
    sorts = split_csv_values(args.sorts, fallback=[args.sort])
    daily_per_keyword = max(
        args.min_links_per_query,
        math.ceil(target_link_count / max(1, len(period_rows) * len(keywords) * len(sorts))),
    )

    print(f"목표 본문 수: {args.target_count:,}건")
    print(f"목표 링크 수(여유분): {target_link_count:,}개")
    print(f"검색어: {', '.join(keywords)}")
    print(f"검색 정렬: {', '.join(sorts)}")
    print(f"검색 일수: {len(period_rows):,}일, 검색어/정렬별 하루 목표: {daily_per_keyword}개")

    link_path = Path(args.links_output)
    if args.refresh_links:
        # 사용자가 명시적으로 새로 수집하겠다고 한 경우 기존 체크포인트를 무시합니다.
        link_df = pd.DataFrame()
    else:
        # 기존 체크포인트가 있으면 이어받되, 현재 검색어가 아닌 링크는 제외합니다.
        link_df = filter_links_for_keywords(dedupe_links(load_csv(link_path)), keywords)

    if len(link_df) >= target_link_count:
        print(f"기존 링크 체크포인트 사용: {len(link_df):,}개")
        return link_df

    all_records = link_df.to_dict("records") if not link_df.empty else []

    for row in tqdm(period_rows, desc="전체 날짜 링크 수집"):
        for keyword in keywords:
            for sort in sorts:
                records = collect_blog_links(
                    driver,
                    [row["date"]],
                    daily_per_keyword,
                    row["section"],
                    keyword=keyword,
                    max_scrolls=args.max_scrolls,
                    sort=sort,
                    min_delay=args.search_min_delay,
                    max_delay=args.search_max_delay,
                )
                all_records.extend(records)

        checkpoint = dedupe_links(pd.DataFrame(all_records))
        # 날짜 하나가 끝날 때마다 링크 체크포인트를 저장합니다.
        # 링크 수집 단계에서 중단되어도 다음 실행에서 이어받을 수 있습니다.
        checkpoint.to_csv(link_path, index=False, encoding="utf-8-sig")
        if len(checkpoint) >= target_link_count:
            print(f"목표 링크 수를 채워 링크 수집을 조기 종료합니다: {len(checkpoint):,}개")
            return checkpoint

    return dedupe_links(pd.DataFrame(all_records))


def filter_existing_results_for_keywords(df, keywords, keep_other_keywords=False):
    """
    기존 결과 CSV에서 현재 실행 검색어에 해당하는 행만 남깁니다.

    keep_existing_other_keywords 옵션을 켜면 예전 검색어 결과도 그대로 유지합니다.
    """
    if keep_other_keywords or df.empty or "keyword" not in df.columns:
        return df

    keyword_series = df["keyword"].fillna("").astype(str).str.strip()
    allowed = set(keywords)
    filtered = df[(keyword_series == "") | keyword_series.isin(allowed)].copy()
    removed = len(df) - len(filtered)
    if removed:
        print(f"기존 결과 중 요청 검색어가 아닌 행 {removed:,}건은 이번 출력에서 제외합니다.")
    return filtered.reset_index(drop=True)


def crawl_articles(driver, args, link_df, keywords):
    """
    링크 목록을 순회하며 실제 블로그 본문과 댓글 데이터를 수집합니다.

    기존 CSV가 있으면 이어받고, 이미 처리한 canonical_url은 건너뜁니다.
    target-count를 채우면 남은 링크가 있어도 조기 종료합니다.
    """
    resume = not args.no_resume
    output_path = Path(args.output)
    existing_df = normalize_existing_results(load_csv(output_path)) if resume else pd.DataFrame()
    existing_df = filter_existing_results_for_keywords(
        existing_df,
        keywords,
        keep_other_keywords=args.keep_existing_other_keywords,
    )
    existing_urls_before_filter = (
        set(existing_df["canonical_url"].dropna()) if not existing_df.empty else set()
    )
    existing_df = reparse_existing_comment_meta(driver, args, existing_df, output_path)
    if args.require_complete_comment_meta:
        existing_df = filter_complete_comment_rows(
            existing_df,
            max_comments_per_post=args.max_comments_per_post,
        )
        existing_urls = existing_urls_before_filter
    else:
        existing_urls = set(existing_df["canonical_url"].dropna()) if not existing_df.empty else set()
    results = existing_df.to_dict("records") if not existing_df.empty else []

    # 이미 저장된 글은 다시 열지 않습니다. 긴 크롤링을 여러 번 나눠 실행할 때 시간을 크게 줄입니다.
    candidates = link_df[~link_df["canonical_url"].isin(existing_urls)].copy()
    if args.limit_links:
        candidates = candidates.head(args.limit_links)

    print(f"기존 본문 결과: {len(results):,}건")
    print(f"이번 실행 파싱 후보: {len(candidates):,}개")

    try:
        iterator = tqdm(candidates.iterrows(), total=len(candidates), desc="본문 크롤링")
        for idx, row in iterator:
            if len(results) >= args.target_count:
                break

            try:
                data = parse_blog_content(
                    driver,
                    row["url"],
                    collect_comments=not args.no_comments,
                    max_comments=args.max_comments_per_post,
                    article_min_delay=args.article_min_delay,
                    article_max_delay=args.article_max_delay,
                )
            except Exception:
                # 삭제/비공개/접속 실패 글은 건너뛰고 다음 링크를 처리합니다.
                continue

            if not data.get("title") and not data.get("content"):
                continue
            if args.require_complete_comment_meta and not has_complete_comment_meta(
                data,
                max_comments_per_post=args.max_comments_per_post,
            ):
                continue

            # 본문 파서가 만든 데이터에 검색 당시 메타데이터를 붙여 CSV 한 행을 완성합니다.
            data.update(
                {
                    "url": row["url"],
                    "canonical_url": row["canonical_url"],
                    "keyword": row.get("keyword", ""),
                    "source": "네이버 블로그",
                    "section": row.get("section", ""),
                    "date": row.get("date", ""),
                    "search_date": row.get("search_date", row.get("date", "")),
                    "search_sort": row.get("search_sort", ""),
                }
            )
            results.append(data)

            if len(results) % args.save_interval == 0:
                # 긴 실행 도중 Ctrl+C나 네트워크 문제로 끊겨도 현재까지의 결과를 보존합니다.
                save_dataframe(pd.DataFrame(results), output_path)
    except KeyboardInterrupt:
        print("\n중단 요청을 받아 본문 크롤링 결과를 현재까지 저장합니다.")
        save_dataframe(pd.DataFrame(results), output_path)
        raise

    final_df = pd.DataFrame(results)
    save_dataframe(final_df, output_path)
    return final_df


def main():
    """크롤러 전체 실행 순서를 제어하는 진입점입니다."""
    args = parse_args()
    keywords = split_keywords(args.keywords)
    period_rows = build_period_rows(args.max_days)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 네이버 블로그 크롤러 시작")
    driver = None

    try:
        # 1단계: 브라우저 드라이버 준비
        driver = setup_driver(
            headless=not args.show_browser,
            driver_path=args.driver_path or None,
            use_webdriver_manager=args.use_webdriver_manager,
        )
        # 2단계: 검색 결과에서 블로그 글 링크를 충분히 확보
        link_df = collect_all_links(driver, args, keywords, period_rows)
        print(f"\n고유 블로그 링크: {len(link_df):,}개")
        link_df.to_csv(args.links_output, index=False, encoding="utf-8-sig")

        if args.link_only:
            print(f"링크만 저장하고 종료: {args.links_output}")
            return

        # 3단계: 확보한 링크를 열어 본문/댓글/좋아요 데이터를 수집
        final_df = crawl_articles(driver, args, link_df, keywords)
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 크롤링 종료")
        print(f"최종 저장 파일: {args.output} ({len(final_df):,}건)")
        if len(final_df) < args.target_count:
            print("목표보다 적게 모였습니다. --refresh-links 또는 --max-scrolls 값을 키워 추가 수집해보세요.")
    except KeyboardInterrupt:
        print("\n사용자 중단(Ctrl+C)을 감지했습니다. 이미 저장된 CSV와 링크 체크포인트는 유지됩니다.")
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()
