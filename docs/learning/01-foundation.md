# 第 1 課：專案地基（Phase 0）

這一課對應目前已經寫好的程式碼。建議打開檔案對照著讀。

---

## 1. 為什麼用 `src/` layout

```
backend/
├── src/life200/   ← 套件本體
└── tests/
```

如果套件直接放在 `backend/life200/`，測試可能「不小心」從資料夾直接 import，而不是從安裝好的套件 import。這樣會出現「本機會過、部署會壞」的問題。`src/` layout 強迫你一定要先安裝套件才能 import，本機和正式環境的行為就會一致。

**面試會被問：** "Why src layout?" → 避免 import 到未安裝的程式碼，測試的就是真正會被發佈的東西。

## 2. uv 與 `pyproject.toml`

- `pyproject.toml` 是 Python 現在的標準設定檔，取代了 `setup.py` 和 `requirements.txt`。依賴、工具設定（ruff、mypy、pytest）全部集中在這一個檔案。
- `uv` 是 Rust 寫的套件管理器，比 pip 快 10–100 倍。`uv sync` 會建立 `.venv` 並產生 `uv.lock`。
- **`uv.lock` 一定要 commit。** 它鎖住每個套件的精確版本，確保你、CI、正式環境裝到的是同一套。
- `[dependency-groups] dev` 是開發用工具（pytest、mypy），不會被裝到正式環境。

常用指令：
```bash
uv add httpx           # 加正式依賴
uv add --dev pytest    # 加開發依賴
uv run pytest          # 在 venv 裡執行
```

## 3. Pydantic：用型別描述資料（`domain/profile.py`）

Pydantic 是 FastAPI 的核心，也是讓 LLM 輸出可靠的關鍵工具。

```python
class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
```

| 設定 | 意思 | 為什麼 |
|---|---|---|
| `extra="forbid"` | 不認識的欄位直接報錯 | LLM 若亂加欄位會立刻被抓到，不會默默通過 |
| `frozen=True` | 物件建立後不能修改 | 避免某段程式偷偷改到別人也在用的資料 |
| `str_strip_whitespace` | 自動去掉字串前後空白 | 從 PDF 抽出的文字常有多餘空白 |

**Validator（驗證器）** 把商業規則寫進資料模型裡：

```python
@model_validator(mode="after")
def _end_after_start(self) -> "Period":
    if self.end is not None and self.end < self.start:
        raise ValueError("period end must not be before start")
    return self
```

`MasterProfile` 還有一個驗證器：任何 achievement 用到的技能，都必須在 `skills` 裡宣告過。這就是「不能新增事實」的第一道防線，在資料層就擋掉。

**為什麼用 `tuple` 而不是 `list`？** 因為 model 是 frozen 的，`list` 本身仍然可以被 `.append()`，`tuple` 則完全不可變。

## 4. Fact guard：確定性檢查（`services/fact_guard.py`）

LLM 改寫 CV 時可能「創造」數字。我們不讓另一個 LLM 來檢查（它也可能出錯），而是用**確定性的程式碼**：

1. 用正規表達式抽出改寫後文字裡的所有數字（`6,810` 會正規化成 `6810`）
2. 抽出原始 achievement 裡的所有數字
3. 改寫後多出來的數字 → 標記為 violation

這是 LLM 工程很重要的原則：**能用確定性程式檢查的，就不要交給模型判斷。**

## 5. FastAPI 的 app factory（`main.py`）

```python
def create_app() -> FastAPI:
    app = FastAPI(title="Life200", version=__version__)
    app.include_router(health.router)
    return app
```

用函式建立 app，而不是在模組層直接 `app = FastAPI()`。這樣每個測試都能拿到一個乾淨、獨立的 app，之後也能依環境（test/prod）注入不同設定。

跑起來後打開 `http://localhost:8000/docs`，FastAPI 會根據你的 Pydantic 型別自動產生互動式 API 文件。

## 6. 設定管理：12-Factor（`core/config.py`）

- 設定一律來自**環境變數**，不寫死在程式碼裡。本機用 `.env`，正式環境用雲端的 secret 管理。
- `.env` 被 `.gitignore` 擋掉，**永遠不 commit**；`.env.example` 才 commit，告訴別人需要哪些變數。
- API key 用 `SecretStr`，`print(settings)` 時會顯示 `**********`，避免 key 出現在 log 裡。

## 7. 測試（`tests/`）

**Fixture**（`conftest.py`）是可重複使用的測試資料。例如 `profile` fixture 會建一個含你論文 achievement 的 MasterProfile，任何測試只要在參數寫 `profile` 就能拿到。

**Parametrize** 讓同一個測試跑多組輸入：
```python
@pytest.mark.parametrize(("text", "expected"), [
    ("6,810 task-runs", {"6810"}),
    ("42.9% of tasks", {"42.9"}),
])
```

**測試命名**：`test_<行為>`，讀起來像規格書，例如 `test_invented_number_is_flagged`。

**Coverage**：目前 99%。不用追求 100%，但核心邏輯（fact_guard、profile 驗證）一定要完整覆蓋。

## 8. 品質工具鏈

| 工具 | 做什麼 | 什麼時候跑 |
|---|---|---|
| **ruff** | lint + 自動排版（取代 flake8、isort、black） | 存檔時、commit 前、CI |
| **mypy --strict** | 靜態型別檢查，所有函式都要有型別標註 | commit 前、CI |
| **pre-commit** | `git commit` 時自動跑 ruff 和檢查有沒有不小心 commit 私鑰 | 每次 commit |
| **GitHub Actions** | push 後在雲端跑 `lint → typecheck → test` | 每次 push / PR |

`make check` 會在本機跑跟 CI 完全一樣的檢查。**習慣：push 前先跑 `make check`。**

---

## 練習

1. 在 `profile.py` 的 `SkillCategory` 加一個 `SOFT = "soft"`，跑 `make check`。
2. 找出 `fact_guard` 的一個漏洞：改寫時把 `6,810` 寫成 `six thousand eight hundred and ten`，會被抓到嗎？寫一個測試證明你的答案。（提示：這是之後要處理的已知限制。）
3. 在 `api/` 新增 `GET /version`，回傳 `{"version": "0.1.0"}`，並寫對應的測試。

## 下一課預告：第 2 課 — 資料庫與上傳履歷

SQLAlchemy 2.0 ORM、Alembic migration、把 MasterProfile 存進 Postgres，以及上傳 PDF/DOCX → LLM 抽取 achievements → 你審核後合併進主資料庫。
