# 晨間快報 // MORNING.SYS

Cyberpunk 2077 風格的個人晨間儀表板：內湖／基隆天氣、國際／國內／基隆市府新聞（各 5 則，分頁切換）、今日行程、每日鳥類與語音簡報。純靜態網頁，放在 GitHub Pages，任何裝置的瀏覽器都能開。

## 資料怎麼更新

| 項目 | 來源 | 何時更新 |
|---|---|---|
| 天氣、穿著建議 | Open-Meteo（免費、免金鑰） | 每次打開網頁即時抓 |
| 每日鳥類（照片、叫聲、介紹） | Wikimedia Commons、維基百科 | 每天換一隻，打開網頁即時抓 |
| 新聞 15 則 | Google News + Gemini 挑選與摘要 | ① 每天 05:30 GitHub 自動排程 ② 網頁有存 Gemini 金鑰時，打開若不是今天的資料會自動更新 ③ 隨時按「立即更新」 |
| 今日行程 | Google 日曆（加密後存在 data.json） | 每天 05:30 GitHub 自動排程 |

## 安裝步驟

### 1. 建立 GitHub 儲存庫並上傳
在 GitHub 建立一個 **Public** 儲存庫（例如 `morning-dashboard`），把這個資料夾的全部內容上傳。

> ⚠ `.github` 是隱藏資料夾，用網頁拖曳上傳時常被漏掉。建議用下面的終端機指令；若用網頁上傳，請另外在 GitHub 上「Add file → Create new file」，檔名輸入 `.github/workflows/update.yml`，再把內容貼上。

```bash
cd morning-dashboard
git init && git add . && git commit -m "init"
git branch -M main
git remote add origin https://github.com/你的帳號/morning-dashboard.git
git push -u origin main
```

### 2. 開啟 GitHub Pages
儲存庫 → **Settings → Pages** → Source 選 **Deploy from a branch**，Branch 選 `main`、資料夾 `/ (root)` → Save。
約 1 分鐘後網址就是 `https://你的帳號.github.io/morning-dashboard/`。

### 3. 放入 Gemini 金鑰（讓每天自動更新使用 AI 摘要）
1. 到 <https://aistudio.google.com/apikey> 免費產生金鑰。
2. 儲存庫 → **Settings → Secrets and variables → Actions → New repository secret**
   - Name：`GEMINI_API_KEY`　Value：貼上金鑰
3. 打開儀表板網頁 → 右上 **⚙** → 把同一把金鑰貼進「Gemini API Key」→ 儲存。（金鑰只存在那台裝置的瀏覽器，每台手機／電腦各貼一次。）

沒放金鑰也能用：新聞會直接列 Google News 頭條，只是沒有摘要與編輯挑選。

### 4. 同步 Google 日曆（選用）
因為網頁是公開的，行事曆會**加密**後才寫進 `data.json`，只有輸入密語的裝置看得到。
1. Google 日曆（電腦版）→ 每個要同步的日曆 → **設定和共用** → 最下方「**iCal 格式的私密網址**」→ 複製。
2. 新增 Secret `ICAL_URLS`：貼上所有私密網址，一行一個。
3. 新增 Secret `CAL_KEY`：自訂一組密語（例如一句好記的話）。
4. 儀表板 ⚙ →「行事曆密語」輸入同一組密語。

> 私密網址等同日曆的鑰匙，只放在 GitHub Secrets，不要貼在其他地方。別人共用給你的日曆不會有私密網址，那類日曆無法同步。

### 5. 第一次手動執行
儲存庫 → **Actions** → 若有提示請先按啟用 → 左側選 **update-data** → **Run workflow**。跑完（約 1 分鐘）後 `data.json` 就是今天的資料，之後每天 05:30 自動執行。

### 6. 加到手機主畫面
iPhone：Safari 開網址 → 分享 → 加入主畫面。Android：Chrome 選單 → 加到主畫面。

## 檔案
```
index.html                    儀表板（HTML/CSS/JS 單一檔案）
data.json                     每日新聞＋加密行事曆（由排程產生）
scripts/update.py             產生 data.json 的腳本
requirements.txt              腳本的 Python 套件
.github/workflows/update.yml  每日 05:30 排程
```

## 自訂
- 天氣地點：`index.html` 的 `PLACES`
- 鳥類清單：`index.html` 的 `BIRDS`（每天依序輪替一隻）
- 新聞來源與挑選原則：`scripts/update.py` 的 `FEEDS`、`PROMPT`；網頁內即時更新的原則在 `index.html` 的 `PROMPT`
- 排程時間：`.github/workflows/update.yml` 的 `cron`（UTC 時間，`30 21 * * *` = 台灣 05:30）
- 指定 Gemini 模型：Settings → Secrets and variables → Actions → **Variables** 新增 `GEMINI_MODEL`；網頁則在 ⚙ 填寫
