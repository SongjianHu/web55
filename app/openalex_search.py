"""
OpenAlex 文献检索：供「问答模式」按关键词检索学术文献（OpenAlex 完全开放、无需密钥）。

特性：
  - 年份过滤：可指定起止年，默认近三年（当前年及前两年）
  - 英文同义词匹配：内置中英学术同义词词典对查询词做扩展，按 OR 合并多次检索结果
  - 每条结果附 GB/T 7714—2015 顺序编码制著录串，并归一化为可直接存入 Zotero 的结构

OpenAlex 现需免费 API Key（注册：https://openalex.org/settings/api）。
凭据优先用前端传入的 api_key，缺省回退环境变量 OPENALEX_API_KEY。
可选环境变量：
  OPENALEX_API_KEY   免费 API Key（前端未填时回退用此值）
  OPENALEX_TIMEOUT   单次请求读超时秒数（默认 25；网络慢可调大）
"""
import os
import re
from datetime import datetime

import httpx

OPENALEX_API = "https://api.openalex.org/works"

# 一次检索最多扩展的同义词检索串数（控制对 OpenAlex 的请求数）
_MAX_TERMS = 5

# 网络较慢/不稳时：每个请求重试次数 + 读超时（秒，可由环境变量覆盖）
_RETRIES = 2
try:
    _READ_TIMEOUT = max(5.0, float(os.environ.get("OPENALEX_TIMEOUT", "25")))
except (TypeError, ValueError):
    _READ_TIMEOUT = 25.0

# OpenAlex work.type → Zotero itemType（决定 GB/T 7714 类型标识与存库字段集）
_TYPE_MAP = {
    "article":             "journalArticle",
    "journal-article":     "journalArticle",
    "preprint":            "journalArticle",
    "proceedings-article": "conferencePaper",
    "proceedings":         "conferencePaper",
    "book":                "book",
    "monograph":           "book",
    "book-chapter":        "bookSection",
    "reference-entry":     "bookSection",
    "dissertation":        "thesis",
    "report":              "report",
    "dataset":             "dataset",
    "standard":            "standard",
    "peer-review":         "document",
}

# Zotero itemType → GB/T 7714 文献类型标识代码
_TYPE_CODE = {
    "journalArticle":  "J",
    "book":            "M",
    "bookSection":     "M",
    "thesis":          "D",
    "conferencePaper": "C",
    "report":          "R",
    "standard":        "S",
    "dataset":         "DB/OL",
    "document":        "Z",
}

# ── 内置中英学术同义词词典（可按需扩充）──
# 规则：查询串命中某 key（中文按子串、英文按小写子串）时，并入其同义/相关英文检索词。
_SYNONYMS = {
    "机器学习":      ["machine learning", "ML", "statistical learning"],
    "深度学习":      ["deep learning", "deep neural network"],
    "神经网络":      ["neural network", "artificial neural network"],
    "人工智能":      ["artificial intelligence", "AI"],
    "自然语言处理":  ["natural language processing", "NLP", "computational linguistics"],
    "计算机视觉":    ["computer vision", "image recognition"],
    "图像识别":      ["image recognition", "image classification"],
    "目标检测":      ["object detection"],
    "语义分割":      ["semantic segmentation"],
    "强化学习":      ["reinforcement learning"],
    "迁移学习":      ["transfer learning"],
    "联邦学习":      ["federated learning"],
    "大语言模型":    ["large language model", "LLM", "foundation model"],
    "大模型":        ["large language model", "LLM", "foundation model"],
    "生成对抗网络":  ["generative adversarial network", "GAN"],
    "推荐系统":      ["recommender system", "recommendation system"],
    "知识图谱":      ["knowledge graph"],
    "数据挖掘":      ["data mining"],
    "区块链":        ["blockchain", "distributed ledger"],
    "物联网":        ["internet of things", "IoT"],
    "边缘计算":      ["edge computing"],
    "云计算":        ["cloud computing"],
    "情感分析":      ["sentiment analysis", "opinion mining"],
    "machine learning":            ["machine learning", "statistical learning"],
    "deep learning":               ["deep learning", "deep neural network"],
    "neural network":              ["neural network", "artificial neural network"],
    "artificial intelligence":     ["artificial intelligence", "AI"],
    "natural language processing": ["natural language processing", "NLP"],
    "computer vision":             ["computer vision", "image recognition"],
    "object detection":            ["object detection"],
    "reinforcement learning":      ["reinforcement learning"],
    "large language model":        ["large language model", "LLM"],
    "transformer":                 ["transformer", "attention mechanism"],
    "recommender system":          ["recommender system", "recommendation system"],
    "knowledge graph":             ["knowledge graph"],
    "blockchain":                  ["blockchain", "distributed ledger"],
    "internet of things":          ["internet of things", "IoT"],
}


def default_year_range() -> tuple:
    """默认近三年：当前年及其前两年。"""
    y = datetime.now().year
    return y - 2, y


def expand_query(query: str) -> list:
    """把查询词扩展为一组检索串（含英文同义词），去重保序，上限 _MAX_TERMS。"""
    q = (query or "").strip()
    terms = [q] if q else []
    low = q.lower()
    for key, syns in _SYNONYMS.items():
        hit = (key in q) if re.search(r"[一-鿿]", key) else (key in low)
        if hit:
            terms.extend(syns)
    seen, out = set(), []
    for t in terms:
        t = t.strip()
        k = t.lower()
        if t and k not in seen:
            seen.add(k)
            out.append(t)
        if len(out) >= _MAX_TERMS:
            break
    return out


# ============================================================
# 工具函数（著者/年份/著录格式）
# ============================================================

def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _year(date_str: str) -> str:
    m = re.search(r"\b(\d{4})\b", str(date_str or ""))
    return m.group(1) if m else ""


def _date_compact(date_str: str) -> str:
    if not date_str:
        return ""
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(date_str))
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return _year(date_str)


def _split_name(display_name: str) -> dict:
    """OpenAlex 仅给 display_name；西文按末段为姓拆分，中文姓名整体保留。"""
    name = (display_name or "").strip()
    if not name:
        return {}
    if _is_ascii(name) and " " in name:
        parts = name.split()
        return {"firstName": " ".join(parts[:-1]), "lastName": parts[-1]}
    return {"name": name}


def _authors(creators: list, max_n: int = 3) -> str:
    """GB/T 7714：≤3 名全列；>3 名取前 3 名后加“等 / et al”。"""
    names = []
    for c in creators or []:
        if c.get("name"):
            names.append(c["name"].strip())
            continue
        last = (c.get("lastName") or "").strip()
        first = (c.get("firstName") or "").strip()
        if last and first:
            if _is_ascii(last + first):
                initials = "".join(p[0].upper() + "." for p in first.split() if p)
                names.append(f"{last} {initials}".strip())
            else:
                names.append(f"{last}{first}")
        elif last or first:
            names.append(last or first)
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) <= max_n:
        return ", ".join(names)
    tail = "et al" if _is_ascii(names[0]) else "等"
    return ", ".join(names[:max_n]) + f", {tail}"


def _loc(place: str, pub: str) -> str:
    place, pub = (place or "").strip(), (pub or "").strip()
    if place and pub:
        return f"{place}:{pub}"
    return pub or place


def _tidy(s: str) -> str:
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\.{2,}", ".", s)
    s = re.sub(r"\s+\.", ".", s)
    s = re.sub(r"[,:;]\s*\.", ".", s)
    s = re.sub(r"\(\s*\)", "", s)
    return s.strip(" ,;:")


def format_gbt7714(it: dict) -> str:
    """把归一化条目格式化为 GB/T 7714—2015 著录串（不含序号）。"""
    t = it.get("itemType", "document")
    code = _TYPE_CODE.get(t, "Z")
    authors = _authors(it.get("creators"))
    title = (it.get("title") or "").strip().rstrip(". ")
    year = _year(it.get("date"))
    url = (it.get("url") or "").strip()
    head = f"{authors}. {title}[{code}]" if authors else f"{title}[{code}]"

    if t == "journalArticle":
        seg = (it.get("publication") or "").strip()
        if year:
            seg = f"{seg},{year}" if seg else year
        if it.get("volume"):
            seg += f",{it['volume']}"
        if it.get("issue"):
            seg += f"({it['issue']})"
        if it.get("pages"):
            seg += f":{it['pages']}"
        body = _tidy(f"{head}. {seg}.")
        return f"{body} DOI:{it['doi']}." if it.get("doi") else body

    if t == "conferencePaper":
        proc = (it.get("publication") or "").strip()
        tail = _loc(it.get("place"), it.get("publisher"))
        if year:
            tail = f"{tail},{year}" if tail else year
        if it.get("pages"):
            tail += f":{it['pages']}"
        lead = f"{authors}. " if authors else ""
        if proc:
            return _tidy(f"{lead}{title}[C]//{proc}. {tail}.")
        return _tidy(f"{head}. {tail}.")

    if t in ("book", "document"):
        seg = _loc(it.get("place"), it.get("publisher"))
        if year:
            seg = f"{seg},{year}" if seg else year
        return _tidy(f"{head}. {seg}.")

    if t == "bookSection":
        booktitle = (it.get("publication") or "").strip()
        tail = _loc(it.get("place"), it.get("publisher"))
        if year:
            tail = f"{tail},{year}" if tail else year
        if it.get("pages"):
            tail += f":{it['pages']}"
        lead = f"{authors}. " if authors else ""
        return _tidy(f"{lead}{title}[M]//{booktitle}. {tail}.")

    if t == "thesis":
        seg = _loc(it.get("place"), it.get("publisher") or it.get("publication"))
        if year:
            seg = f"{seg},{year}" if seg else year
        return _tidy(f"{head}. {seg}.")

    if t == "report":
        seg = _loc(it.get("place"), it.get("publisher"))
        if year:
            seg = f"{seg},{year}" if seg else year
        return _tidy(f"{head}. {seg}.")

    if t == "dataset":
        pub_date = _date_compact(it.get("date"))
        seg = f"({pub_date})" if pub_date else ""
        body = _tidy(f"{head}. {seg}.")
        return f"{body} {url}." if url else body

    seg = (it.get("publisher") or "").strip()
    if year:
        seg = f"{seg},{year}" if seg else year
    body = _tidy(f"{head}. {seg}.")
    return f"{body} {url}." if url else body


# ============================================================
# OpenAlex → 归一化条目
# ============================================================

def _abstract(inv: dict) -> str:
    """由 OpenAlex 的 abstract_inverted_index 还原摘要（用于存入 Zotero）。"""
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    if not pos:
        return ""
    return " ".join(pos[i] for i in range(max(pos) + 1) if i in pos)


def _normalize(w: dict) -> dict:
    t = (w.get("type") or "").lower()
    item_type = _TYPE_MAP.get(t, "document")

    creators = []
    for a in (w.get("authorships") or []):
        nm = (a.get("author") or {}).get("display_name") or a.get("raw_author_name")
        c = _split_name(nm)
        if c:
            creators.append(c)

    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    biblio = w.get("biblio") or {}
    fp, lp = biblio.get("first_page"), biblio.get("last_page")
    pages = f"{fp}-{lp}" if fp and lp else (fp or lp or "")

    doi = (w.get("doi") or "")
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi).strip()
    url = (loc.get("landing_page_url")
           or (f"https://doi.org/{doi}" if doi else "")
           or w.get("id") or "")

    # 学位论文：授予单位优先取首作者机构
    publisher = src.get("host_organization_name") or ""
    if item_type == "thesis":
        insts = ((w.get("authorships") or [{}])[0].get("institutions") or [])
        if insts:
            publisher = insts[0].get("display_name") or publisher

    return {
        "id":       w.get("id", ""),
        "title":    (w.get("display_name") or w.get("title") or "(无标题)").strip(),
        "creators": creators,
        "authors":  _authors(creators),
        "date":     w.get("publication_date") or str(w.get("publication_year") or ""),
        "year":     str(w.get("publication_year") or _year(w.get("publication_date"))),
        "itemType": item_type,
        "publication": (src.get("display_name") or "").strip(),
        "publisher":   publisher.strip(),
        "place":       "",
        "volume":      str(biblio.get("volume") or ""),
        "issue":       str(biblio.get("issue") or ""),
        "pages":       str(pages or ""),
        "doi":         doi,
        "url":         url,
        "abstract":    _abstract(w.get("abstract_inverted_index")),
        "cited_by":    int(w.get("cited_by_count") or 0),
    }


_NEED_KEY_MSG = ("OpenAlex 需要免费 API Key：请在检索面板「⚙️ API Key」处填写，"
                 "或设置环境变量 OPENALEX_API_KEY。"
                 "注册地址 https://openalex.org/settings/api")


def _request(params: dict, api_key: str = "") -> list:
    """单次检索，超时/网络错误自动重试 _RETRIES 次；仍失败抛 RuntimeError。"""
    if api_key:
        params = {**params, "api_key": api_key}
    headers = {"User-Agent": "thesis-formatter"}
    timeout = httpx.Timeout(_READ_TIMEOUT, connect=10.0)

    last = None
    for _ in range(_RETRIES + 1):
        try:
            resp = httpx.get(OPENALEX_API, params=params,
                             headers=headers, timeout=timeout)
        except httpx.TimeoutException as e:
            last = f"请求超时（{e}）"
            continue
        except httpx.HTTPError as e:
            last = f"网络错误（{e}）"
            continue
        if resp.status_code == 200:
            try:
                return resp.json().get("results", [])
            except ValueError as e:
                raise RuntimeError(f"OpenAlex 返回非 JSON：{e}")
        if resp.status_code in (401, 403):
            raise RuntimeError(_NEED_KEY_MSG)
        if resp.status_code in (429, 500, 502, 503, 504):
            last = f"OpenAlex 暂时不可用（HTTP {resp.status_code}）"
            continue
        raise RuntimeError(f"OpenAlex 返回 {resp.status_code}：{resp.text[:200]}")
    raise RuntimeError(last or "连接 OpenAlex 失败")


def search_works(query: str, from_year: int = None, to_year: int = None,
                 limit: int = 20, api_key: str = "") -> dict:
    """按关键词（含英文同义词扩展）检索 OpenAlex，返回归一化条目 + GB/T 7714 著录。

    api_key 优先用前端传入，缺省回退环境变量 OPENALEX_API_KEY。
    出错时抛 ValueError（入参，→ 400）或 RuntimeError（外部 API，→ 502）。
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("检索关键词不能为空")
    api_key = (api_key or "").strip() or os.environ.get("OPENALEX_API_KEY", "").strip()
    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit = 20

    dfrom, dto = default_year_range()
    try:
        from_year = int(from_year) if from_year else dfrom
        to_year = int(to_year) if to_year else dto
    except (TypeError, ValueError):
        from_year, to_year = dfrom, dto
    if from_year > to_year:
        from_year, to_year = to_year, from_year

    terms = expand_query(query) or [query]
    year_filter = (f"from_publication_date:{from_year}-01-01,"
                   f"to_publication_date:{to_year}-12-31")

    merged, seen, errors = [], set(), []
    for term in terms:
        try:
            results = _request({
                "search":   term,
                "filter":   year_filter,
                "per-page": limit,
                "sort":     "relevance_score:desc",
            }, api_key=api_key)
        except RuntimeError as e:
            # 鉴权类错误直接抛出（重试无意义）；其余（多为网络超时）记录后继续
            if str(e) == _NEED_KEY_MSG:
                raise
            errors.append(str(e))
            continue
        for w in results:
            wid = w.get("id")
            if wid and wid in seen:
                continue
            seen.add(wid)
            merged.append(w)
        # 已够量则提前结束，避免多余往返放大网络延迟
        if len(merged) >= max(limit, 25):
            break

    # 全部请求都失败且无结果 → 区分“缺 Key”与“网络问题”给出对应指引
    if not merged and errors:
        hint = ("（已使用 API Key；若仍失败多为网络问题：检查网络/代理能否访问 "
                "api.openalex.org，或调大环境变量 OPENALEX_TIMEOUT 秒数后重试）"
                if api_key else
                f"（未提供 API Key。OpenAlex 现需免费 Key，"
                f"注册 https://openalex.org/settings/api 后填入面板「⚙️ API Key」）")
        raise RuntimeError(f"{errors[-1]}{hint}")

    # 跨同义词合并后按被引量、年份排序，截断到 limit
    merged.sort(
        key=lambda w: (w.get("cited_by_count") or 0,
                       w.get("publication_year") or 0),
        reverse=True,
    )
    items = []
    for w in merged[:limit]:
        norm = _normalize(w)
        norm["citation"] = format_gbt7714(norm)
        items.append(norm)

    return {
        "count":      len(items),
        "terms":      terms,
        "year_range": [from_year, to_year],
        "items":      items,
        "partial":    bool(errors and merged),
    }
