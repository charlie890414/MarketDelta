# Market Changes Engine — Product Requirements Document



## 1. 產品概要



### Product Name



Market Changes Engine



### 一句話描述



自動追蹤使用者關注股票與持倉的市場、基本面、預期、籌碼、事件與新聞變化，並將大量資料轉換成：



**What changed → Why it matters → What to watch next**



### 核心問題



目前投資研究最大的問題通常不是缺資料，而是：



* 資料散落在不同來源

* 每天要重新檢查大量相同資訊

* 不容易知道「今天跟昨天到底差在哪」

* 新聞很多，但真正會影響投資 thesis 的內容很少

* 單一指標變化缺乏上下文

* 很難長期保存市場預期與基本面的變化軌跡



Market Changes Engine 的核心目標不是提供更多資料，而是建立一個：



> 市場狀態的版本控制系統。



系統每天保存股票狀態，並比較不同時間點之間的差異。



---



# 2. Product Goals



## Primary Goal



每天自動回答：



1. 哪些股票發生重要變化？

2. 哪些指標改變？

3. 變化幅度是否異常？

4. 為什麼值得注意？

5. 是否可能影響原本投資 thesis？

6. 接下來需要觀察什麼？



---



## Secondary Goals



建立可以被其他交易工具重複使用的資料基礎。



未來可直接支援：



* Thesis Tracker

* Catalyst Calendar

* Earnings Momentum

* Trade Debate

* Portfolio Risk

* Ask My Portfolio

* Daily Market Brief



Market Changes Engine 應作為上述系統的共用 data layer。



---



# 3. Non-Goals



MVP 不做：



* 自動下單

* 券商交易 API

* HFT

* Tick-level data

* Level 2 order book

* 完整技術分析平台

* AI 股價預測

* 自動 Buy / Sell recommendation

* Bloomberg 等級完整 analyst consensus

* 社群交易

* Portfolio accounting

* 完整回測系統



系統可以指出變化與可能影響，但 MVP 不直接輸出：



> BUY / SELL



---



# 4. Target User



主要使用者：



* 主動投資人

* 中長期股票投資者

* Fundamental / Growth / GARP 投資者

* 同時追蹤台股與美股

* 約追蹤 10–100 檔股票

* 希望透過 AI 減少每天閱讀大量資料的時間



典型 workflow：



```text

每天打開系統



↓



先看 What Changed



↓



查看最重要的 5–10 個變化



↓



進入個股頁面



↓



理解變化原因



↓



決定是否需要進一步研究

```



---



# 5. Core Product Concept



系統不是單純儲存最新值。



每個資料點都必須盡可能保存歷史 snapshot。



例如：



```text

AMD FY27 EPS Estimate



2026-08-01    6.21

2026-08-05    6.27

2026-08-10    6.48

```



Engine 計算：



```text

1D Change

7D Change

30D Change

90D Change

```



並識別：



```text

New

Changed

Significantly Changed

Reversed

Accelerating

Decelerating

```



---



# 6. MVP Coverage



第一版支援：



## Markets



### US



* NYSE

* NASDAQ



### Taiwan



* TWSE

* TPEx



---



# 7. Watchlist



使用者可以建立：



```text

Portfolio

Watchlist

High Conviction

Research

```



每檔股票至少包含：



```text

symbol

market

company_name

currency

watchlist

active

```



例如：



```json

{

  "symbol": "AMD",

  "market": "US",

  "company_name": "Advanced Micro Devices",

  "currency": "USD",

  "watchlist": ["Portfolio", "Semiconductor"]

}

```



---



# 8. Data Domains



MVP 將市場狀態拆成七個 domain。



---



## 8.1 Price



追蹤：



* Close

* Daily return

* 5D return

* 20D return

* 60D return

* Volume

* Relative volume

* 20D volatility

* 52-week high distance

* Benchmark relative return



例如：



```text

AMD



1D          +4.2%

5D          +8.1%

20D        +12.7%



SPY 20D     +2.3%



Relative    +10.4%

```



重要 change：



```text

Price breakout

Large daily move

Abnormal volume

Relative strength improvement

Large drawdown

```



---



# 8.2 Fundamentals



追蹤：



* Revenue

* Revenue YoY

* Revenue QoQ

* EPS

* EPS YoY

* Gross Margin

* Operating Margin

* FCF

* Cash

* Debt



台股增加：



* Monthly Revenue

* Monthly Revenue YoY

* Monthly Revenue MoM



Change example：



```text

TSMC Monthly Revenue



YoY



Previous

+14.8%



Current

+18.3%



Δ

+3.5 ppt

```



---



# 8.3 Expectations



主要先支援美股。



追蹤：



* EPS Estimate

* Revenue Estimate

* Number of analysts

* Estimate revisions

* Earnings surprise



Period：



```text

Current Quarter

Next Quarter

Current FY

Next FY

```



保存歷史 snapshot。



例如：



```text

AMD FY27 EPS



30D Ago       6.21

7D Ago        6.33

Current       6.48



30D Revision

+4.35%

```



---



# 8.4 Institutional / Flow



台股 MVP：



* Foreign investors

* Investment Trust

* Dealer



統計：



```text

1D

5D

20D

```



例如：



```text

TSM



Foreign

1D      +3,281

5D     +18,320

20D    +42,181



Investment Trust

5D      +4,281

```



Change detection：



```text

Foreign flow turned positive

Institutional buying acceleration

Institutional selling acceleration

20D extreme buying

20D extreme selling

```



---



# 8.5 Ownership



主要台股。



資料：



* Shareholding distribution

* Large holder %

* Retail holder %

* Shareholder count



Example：



```text

400+ lot holders



Previous

62.81%



Current

63.24%



Δ

+0.43 ppt

```



---



# 8.6 Catalysts / Events



Event types：



```text

Earnings

Investor Conference

Product Launch

Dividend

Ex-Dividend

Monthly Revenue

Regulatory Event

SEC Filing

Material Announcement

Macro Event

```



每個事件：



```text

event_type

event_date

company

title

source

importance

status

```



Engine 必須可以回答：



```text

Events within 7 days

Events within 14 days

Events within 30 days

```



---



# 8.7 News



新聞本身不是核心資料。



Engine 只保存：



```text

headline

published_at

source

url

company

category

summary

importance

```



AI 需要分類：



```text

Earnings

Guidance

Product

Competition

Regulation

Management

M&A

Macro

Supply Chain

Analyst

Other

```



並評估：



```text

Material

Relevant

Noise

```



---



# 9. Change Detection Engine



Change Detection 是產品核心。



所有資料先轉成：



```text

Current State

Previous State

Difference

Significance

```



---



## Change Schema



```json

{

  "symbol": "AMD",

  "category": "expectation",

  "metric": "fy27_eps_estimate",

  "previous": 6.21,

  "current": 6.48,

  "change": 0.27,

  "change_pct": 4.35,

  "period": "30d",

  "significance": "high"

}

```



---



# 10. Significance Scoring



每個變化計算：



```text

Change Score

0–100

```



考慮：



### Magnitude



變化幅度。



### Historical rarity



相對過去歷史是否異常。



### Recency



越新的事件權重越高。



### Fundamental relevance



EPS / Guidance 高於普通價格波動。



### Portfolio relevance



持倉股票權重大於普通 watchlist。



### Source confidence



官方公告高於二手新聞。



---



## Example



```text

AMD EPS Estimate +4.35%



Magnitude             28

Historical rarity     19

Fundamental impact    25

Recency                15

Source quality         10



Change Score



97 / 100

```



---



# 11. Change Severity



分成：



```text

0–29

Noise



30–49

Minor



50–69

Notable



70–84

Important



85–100

Critical

```



首頁預設只顯示：



```text

Score >= 50

```



---



# 12. What Changed Feed



首頁核心 UI。



格式：



```text

WHAT CHANGED

Last 24 Hours

────────────────────────



AMD

↑ FY27 EPS Estimate +4.3%

Important · Expectations



TSM

↑ Foreign investors bought 18K lots over 5D

Notable · Institutional Flow



MRVL

↓ Revenue estimate -2.1%

Important · Expectations



NVDA

⚡ New SEC filing

Notable · Filing



TSM

⚡ Monthly revenue YoY accelerated

Critical · Fundamental

```



支援 Filter：



```text

Portfolio

Watchlist

US

Taiwan

Price

Fundamental

Expectation

Flow

News

Catalyst

```



---



# 13. Company Change Page



點進個股：



```text

AMD

Advanced Micro Devices



Changes

────────────────────



Expectations

FY27 EPS

6.21 → 6.48

+4.35%



Revenue

42.1B → 43.0B

+2.14%



Price

20D

+12.7%



Relative to SPY

+10.4%



News

3 important stories



Catalysts

Earnings

23 days

```



---



# 14. AI Interpretation



AI 不負責計算原始 change。



Change 必須先由 deterministic engine 計算。



AI 只負責：



* Summarize

* Explain

* Connect signals

* Identify contradictions

* Generate watch items



---



## AI Output



固定格式：



```text

What changed



AMD FY27 EPS estimates increased 4.3% over

the past 30 days.



Why it matters



The revision suggests analysts are raising

their medium-term earnings expectations.



Supporting signals



• Revenue estimates +2.1%

• Price relative strength +10.4%

• Estimate revisions remain positive



Contradictions



• Gross margin expectations unchanged



Watch next



• Next earnings guidance

• Data center revenue growth

```



---



# 15. Thesis Impact



MVP 可以先做簡單版本。



AI 判斷：



```text

Strengthened

Neutral

Weakened

Unknown

```



Example：



```text

Thesis Impact



↑ Strengthened



Reason



EPS and revenue expectations are both

moving higher while price strength

confirms improving market expectations.

```



必須清楚標示：



```text

AI-generated interpretation

```



而不是客觀市場資料。



---



# 16. Daily Digest



每天生成：



```text

Market Changes Daily

2026-08-11

```



內容：



## Portfolio



```text

3 Important Changes

```



## Watchlist



```text

7 Important Changes

```



## Biggest Positive Changes



Top 5。



## Biggest Negative Changes



Top 5。



## Upcoming Catalysts



未來 14 天。



---



# 17. Data Source Architecture



Data Provider 與 Engine 解耦。



統一 interface：



```python

class DataProvider:



    def fetch_price():

        pass



    def fetch_fundamentals():

        pass



    def fetch_estimates():

        pass



    def fetch_news():

        pass



    def fetch_events():

        pass

```



如此未來可以替換：



```text

Free Provider

↓

Paid Provider

```



而不修改 Engine。



---



# 18. Initial Free Data Providers



## Taiwan



優先：



```text

TWSE

TPEx

MOPS

TDCC

```



可補：



```text

Yahoo Finance

```



---



## US



優先：



```text

SEC EDGAR

Alpha Vantage

Stooq

FRED

GDELT

```



Provider 必須記錄：



```text

source

retrieved_at

data_date

```



---



# 19. Data Quality



任何 datapoint 都應包含：



```text

value

source

data_date

retrieved_at

confidence

```



例如：



```json

{

  "metric": "monthly_revenue",

  "value": 323000000000,

  "source": "MOPS",

  "data_date": "2026-07-31",

  "retrieved_at": "2026-08-10T18:00:00",

  "confidence": "official"

}

```



---



# 20. Source Confidence



```text

Official

High

Medium

Low

```



Priority：



```text

Official filing

>

Exchange

>

Company IR

>

Structured data provider

>

News

>

Aggregators

```



---



# 21. Database



推薦 PostgreSQL。



主要 tables：



```text

companies

watchlists

watchlist_items



price_snapshots

fundamental_snapshots

estimate_snapshots

flow_snapshots

ownership_snapshots



events

news



changes

daily_reports

```



---



# 22. Snapshot Architecture



不要 overwrite 舊資料。



例如：



```text

estimate_snapshots



id

symbol

metric

period

value

snapshot_date

source

```



這樣才能回答：



```text

What changed?

```



而不是只有：



```text

What is the current value?

```



---



# 23. Processing Pipeline



```text

Scheduler

   ↓

Data Collectors

   ↓

Raw Data

   ↓

Normalization

   ↓

Snapshot Storage

   ↓

Change Detection

   ↓

Significance Score

   ↓

AI Interpretation

   ↓

API

   ↓

Dashboard

```



---



# 24. Scheduler



推薦每日：



## Taiwan



```text

Market close

↓

Price



Later

↓

Institutional



Evening

↓

Announcements / Revenue / News

```



## US



```text

Market close

↓

Price



After-hours

↓

SEC filings

Earnings

News

Estimate updates

```



MVP 不需要 real-time。



---



# 25. API



基本 endpoints：



```text

GET /changes



GET /changes/{change_id}



GET /companies/{symbol}



GET /companies/{symbol}/history



GET /companies/{symbol}/events



GET /reports/daily



GET /watchlists



POST /watchlists



POST /watchlists/{watchlist_id}/items

```



---



# 26. Example



```http

GET /changes?hours=24&min_score=70

```



Response：



```json

[

  {

    "symbol": "AMD",

    "category": "expectations",

    "title": "FY27 EPS estimate increased",

    "change_pct": 4.35,

    "score": 91,

    "thesis_impact": "strengthened"

  }

]

```



---



# 27. Frontend



MVP Pages：



```text

/dashboard

/company/:symbol

/watchlist

/calendar

/settings

```



---



# 28. Dashboard



首頁四個區塊：



```text

What Changed



Biggest Positive Changes



Biggest Negative Changes



Upcoming Catalysts

```



不要一開始放：



* K 線

* 大量 technical indicators

* heatmap

* full portfolio analytics



避免變成一般看盤網站。



---



# 29. Search



支援：



```text

AMD

TSM

TSMC

2330

台積電

```



Search 結果統一映射 company ID。



---



# 30. Alert



MVP 可以設定：



```text

Critical Changes Only



Score >= 85

```



例如：



```text

AMD



FY27 EPS estimate increased 6.2%



Change Score

92



This is the largest positive revision

in the past 90 days.

```



---



# 31. MVP Ranking



第一階段只完成：



## P0



* Watchlist

* US/TW stock mapping

* Daily price snapshots

* Fundamental snapshots

* TW monthly revenue

* TW institutional flow

* US EPS estimates

* Events

* Change detection

* Change score

* What Changed dashboard



---



## P1



* News

* AI summaries

* Thesis impact

* Daily digest

* Alerts



---



## P2



* Ownership

* Macro context

* Portfolio integration

* Ask My Portfolio

* Trade Debate integration



---



# 32. MVP Success Criteria



MVP 成功不是：



> 資料很多。



而是：



使用者每天能在 **5 分鐘內**了解：



```text

Portfolio / Watchlist



今天真正發生哪些重要變化。

```



具體衡量：



### Signal Reduction



例如：



```text

Raw datapoints

2,000+



↓



Changes detected

120



↓



Meaningful changes

18



↓



Critical / Important

6

```



---



# 33. Key Product Metrics



追蹤：



```text

Daily active usage



Changes opened



Changes dismissed



Changes marked useful



AI summary useful %



Alert click-through



False-positive rate

```



最重要的是：



```text

Signal / Noise Ratio

```



---



# 34. Technical Principles



## Principle 1



Raw data 與 AI 分離。



---



## Principle 2



所有 AI 判斷都必須能追溯 source。



---



## Principle 3



數值計算禁止交給 LLM。



---



## Principle 4



所有變化必須保存 previous value。



---



## Principle 5



所有 source 必須保存 timestamp。



---



## Principle 6



Free provider 可以隨時替換。



---



# 35. Suggested Stack



Backend：



```text

Python

FastAPI

PostgreSQL

SQLAlchemy

```



Scheduler：



```text

APScheduler

```



或：



```text

Celery

```



MVP 建議 APScheduler 即可。



Frontend：



```text

Next.js

TypeScript

Tailwind

```



AI：



```text

OpenAI-compatible API

```



Crawler：



```text

httpx

BeautifulSoup

Playwright / Patchright

```



優先：



```text

API

>

JSON

>

CSV

>

HTML scraping

```



---



# 36. Repository Structure



```text

market-changes-engine/



backend/

  api/

  collectors/

    twse/

    tpex/

    mops/

    sec/

    alpha_vantage/

  normalization/

  changes/

  scoring/

  ai/

  models/

  jobs/



frontend/

  app/

  components/

  services/



tests/



docker/

```



---



# 37. First Development Milestone



第一個真正可以使用的版本只做：



```text

5–10 檔股票

```



例如：



```text

AMD

TSM

NVDA

MRVL

2330

```



每天抓：



```text

Price

Fundamental

Revenue

EPS estimates

Institutional flow

Events

```



然後生成：



```text

What Changed

```



做到這一步後才開始加新聞與 AI。



---



# 38. Core MVP User Story



> 身為投資人，我希望每天打開 Market Changes Engine 時，可以立即看到我的持股與觀察名單中，相較昨天、上週與上個月有哪些真正重要的市場或基本面變化，並快速理解這些變化為什麼值得注意，而不用重新閱讀所有原始資料。



---



# 39. Product North Star



Market Changes Engine 最終不是：



```text

Stock Dashboard

```



而是：



```text

Git diff for the market

```



每一天市場都有一個 snapshot。



系統負責回答：



```text

Yesterday

vs

Today



What changed?

```

