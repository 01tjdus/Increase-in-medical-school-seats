"""네이버 카페 '의대 증원' 게시글 수집 스크립트.

네이버 검색 결과에서 날짜를 하루 단위로 나누어 카페 글을 찾고, 각 글의
제목·본문·게시일·공감 수·댓글 정보를 JSON으로 저장한다. 이후
`notebooks/01_preprocess/cafe_preprocess_pipeline.ipynb`에서 이 JSON을
표 형태로 바꾸고 형태소 분석을 진행한다.
"""

from playwright.async_api import async_playwright, expect
import asyncio
import datetime
import pandas as pd
import nest_asyncio
import os
import json
from pathlib import Path

nest_asyncio.apply()

# 프로젝트 `data/cafe_only/`에 카페 단독 수집 결과를 저장한다.
# 스크립트가 어디서 실행되더라도 루트는 project_paths.py 기준으로 찾는다.
def _project_root() -> Path:
    here = Path(__file__).resolve()
    for d in [here, *here.parents]:
        if (d / "project_paths.py").is_file():
            return d
    raise RuntimeError(f"project_paths.py를 찾지 못했습니다. 시작 경로: {here}")


_ROOT = _project_root()
OUTPUT_JSON = str(_ROOT / "data" / "cafe_only" / "의대증원_카페_v2.json")


def get_url(keyword, fromtime, totime):
    """네이버 카페 검색 URL을 생성한다. 기간은 YYYYMMDD 문자열로 넣는다."""
    return f"https://search.naver.com/search.naver?ssc=tab.cafe.all&query={keyword}&sm=tab_opt&st=rel&nso=so%3Add%2Cp%3Afrom{fromtime}to{totime}"


async def post_like_text_from_frame(frame):
    """댓글 목록(.comment_list) 밖에 있는 첫 em.u_cnt._count만 글 공감으로 간주"""
    ems = frame.locator('em.u_cnt._count')
    n = await ems.count()
    for i in range(n):
        em = ems.nth(i)
        in_comment = await em.evaluate(
            """el => !!el.closest('ul.comment_list') || !!el.closest('.comment_list')"""
        )
        if not in_comment:
            t = await em.text_content()
            return (t or '').strip() if t else None
    return None


MAX_PAGE = 18
MAX_ARTICLES = 30000
KEYWORD = "의대 증원"
SKIP_DAYS = 1
CURRENT_TIME = datetime.datetime(2025, 6, 30)
MIN_TIME = datetime.datetime(2024, 1, 1)
TIMEOUT = 5000
BLACKLIST = [
    "joonggonara",
]

expect.set_options(timeout=TIMEOUT)


async def main():
    """검색 결과를 순회하며 카페 게시글과 댓글 정보를 누적 저장한다."""
    dataset = []
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, 'r', encoding='utf8') as f:
            dataset = json.loads(f.read())

    titles = []
    current_time = CURRENT_TIME
    done_counter = [0]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, timeout=TIMEOUT)
        context = await browser.new_context()
        page = await context.new_page()
        tab_sem = asyncio.Semaphore(MAX_PAGE)
        count = 0

        # 최근 날짜에서 과거 날짜로 하루씩 이동하며 검색 누락을 줄인다.
        while True:
            if count >= MAX_ARTICLES:
                break

            keyword = KEYWORD
            current_time += datetime.timedelta(days=-SKIP_DAYS)

            if current_time < MIN_TIME:
                print("최소 설정 날짜에 도달하여 크롤링을 종료합니다.")
                break

            url = get_url(
                keyword,
                (current_time - datetime.timedelta(days=-1)).strftime('%Y%m%d'),
                current_time.strftime('%Y%m%d'),
            )

            skip = False
            for block in BLACKLIST:
                if block in url:
                    print(f"블랙리스트에 포함된 URL 건너뛰기: {url}")
                    skip = True
                    break
            if skip:
                continue

            await page.goto(url)

            while True:
                lists = await page.query_selector('.lst_view')
                if lists is None:
                    print("게시글 목록을 찾을 수 없습니다. 다음 날짜로 넘어갑니다.")
                    break

                articles = await lists.query_selector_all('.bx')
                if len(articles) < 5:
                    break

                query_from = (current_time - datetime.timedelta(days=-1)).strftime('%Y%m%d')
                query_to = current_time.strftime('%Y%m%d')

                day_tasks = []

                async def process_article(query_from, query_to, href, title_search):
                    """검색 결과 한 건을 열어 본문·댓글·공감 수를 추출한다."""
                    async with tab_sem:
                        cafe = await context.new_page()
                        try:
                            await cafe.goto(href)
                            frame = cafe.frame_locator('#cafe_main').first

                            article_body = None
                            body_loc = frame.locator('.se-main-container,.article_viewer').first
                            if await body_loc.count() > 0:
                                raw_body = await body_loc.text_content(timeout=TIMEOUT)
                                if raw_body is not None:
                                    article_body = raw_body.strip()

                            title_final = (title_search or '').strip()
                            title_loc = frame.locator('div.title_area h3.title_text')
                            if await title_loc.count() > 0:
                                t = await title_loc.first.text_content(timeout=TIMEOUT)
                                if t is not None and str(t).strip():
                                    title_final = str(t).strip()

                            posted_time = None
                            for sel in ('.article_info span.date', '.article_info > .date', '.article_info .date'):
                                dl = frame.locator(sel)
                                if await dl.count() > 0:
                                    raw_time = await dl.first.text_content(timeout=TIMEOUT)
                                    if raw_time is not None:
                                        posted_time = raw_time.strip()
                                    break

                            like_text = await post_like_text_from_frame(frame)

                            comment_cnt_text = None
                            num_loc = frame.locator('.button_comment strong.num')
                            if await num_loc.count() > 0:
                                comment_cnt_text = await num_loc.first.text_content(timeout=TIMEOUT)
                            else:
                                btn = frame.locator('.button_comment').first
                                if await btn.count() > 0:
                                    comment_cnt_text = await btn.text_content(timeout=TIMEOUT)

                            comments = []
                            list_loc = frame.locator('ul.comment_list, .comment_list').first
                            if await list_loc.count() > 0:
                                comment_elements = await list_loc.locator('.comment_area').all()
                                for c in comment_elements:
                                    raw_comment = None
                                    if await c.locator('span.text_comment').count() > 0:
                                        raw_comment = await c.locator('span.text_comment').first.text_content(timeout=TIMEOUT)
                                    if (raw_comment is None or not str(raw_comment).strip()) and await c.locator('p.comment_text_view').count() > 0:
                                        raw_comment = await c.locator('p.comment_text_view').first.text_content(timeout=TIMEOUT)
                                    comment_body = raw_comment.strip() if raw_comment is not None else None

                                    comment_date = None
                                    if await c.locator('span.comment_info_date').count() > 0:
                                        rd = await c.locator('span.comment_info_date').first.text_content(timeout=TIMEOUT)
                                        if rd is not None:
                                            comment_date = rd.strip()

                                    comment_like = 0
                                    if await c.locator('em.u_cnt._count').count() > 0:
                                        rl = await c.locator('em.u_cnt._count').first.text_content(timeout=TIMEOUT)
                                        if rl and str(rl).strip():
                                            try:
                                                comment_like = int(str(rl).strip())
                                            except ValueError:
                                                comment_like = 0

                                    comments.append(dict(
                                        content=comment_body,
                                        comment_date=comment_date,
                                        like=comment_like,
                                    ))

                            img_cnt = await frame.locator('.se-main-container img, .article_viewer img').count()
                            div_cnt = await frame.locator(
                                '.se-main-container iframe, .article_viewer iframe, .se-main-container video, .article_viewer video'
                            ).count()

                            dataset.append(dict(
                                title=title_final,
                                doc=article_body,
                                like=like_text,
                                comment_cnt=comment_cnt_text,
                                comment_list=comments,
                                img=img_cnt,
                                div=div_cnt,
                                ch='naver',
                                ch2='cafe',
                                time=posted_time,
                                query_from=query_from,
                                query_to=query_to,
                            ))
                            done_counter[0] += 1
                            print(f"[완료 {done_counter[0]}] {title_final}")
                        except Exception as e:
                            print(f"에러 발생: {e}")
                        finally:
                            await cafe.close()

                for article in articles:
                    if count >= MAX_ARTICLES:
                        break

                    title_el = await article.query_selector('.title_link')
                    if title_el is None:
                        continue
                    title_text = await title_el.text_content()
                    if title_text is None:
                        continue
                    title_text = title_text.strip()
                    if not title_text:
                        continue

                    if title_text in titles:
                        continue
                    titles.append(title_text)

                    href = await title_el.get_attribute('href')
                    if not href:
                        continue

                    count += 1
                    day_tasks.append(asyncio.create_task(
                        process_article(query_from, query_to, href, title_text)
                    ))
                    await asyncio.sleep(0.5)

                if day_tasks:
                    await asyncio.gather(*day_tasks, return_exceptions=True)

                df = pd.DataFrame(dataset)
                df.to_json(OUTPUT_JSON, force_ascii=False, indent=2, orient='records')
                break

    print(f"종료: 누적 저장 {len(dataset)}건, 상세 성공 {done_counter[0]}건")


asyncio.run(main())
