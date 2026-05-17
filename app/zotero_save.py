"""
Zotero 写入：把用户在 OpenAlex 检索中勾选的文献存入其个人 Zotero 文献库。

凭据由前端传入（用户在界面填写并存浏览器 localStorage）：
  api_key  Zotero API 密钥（须含对该用户库的写权限）
  user_id  Zotero 数字 userID（见 zotero.org/settings/keys）

接收前端回传的归一化条目（openalex_search._normalize 的结构），
按 itemType 选择 Zotero 合法字段集后批量 POST 创建。
"""
import httpx

ZOTERO_API = "https://api.zotero.org"
_API_VERSION = "3"
_MAX_BATCH = 50  # Zotero 单次创建上限


def _creators(creators: list) -> list:
    out = []
    for c in creators or []:
        if c.get("name"):
            out.append({"creatorType": "author", "name": c["name"]})
        else:
            out.append({
                "creatorType": "author",
                "firstName": c.get("firstName", ""),
                "lastName": c.get("lastName", ""),
            })
    return out


def _zotero_item(it: dict) -> dict:
    """归一化条目 → Zotero item（按 itemType 仅填该类型合法字段）。"""
    t = it.get("itemType") or "document"
    base = {
        "itemType": t,
        "title": it.get("title", ""),
        "creators": _creators(it.get("creators")),
        "date": it.get("date", "") or it.get("year", ""),
        "url": it.get("url", ""),
        "abstractNote": it.get("abstract", ""),
        "extra": (f"OpenAlex: {it['id']}" if it.get("id") else ""),
    }
    doi = it.get("doi", "")
    venue = it.get("publication", "")
    pub = it.get("publisher", "")
    place = it.get("place", "")
    vol, iss, pages = it.get("volume", ""), it.get("issue", ""), it.get("pages", "")

    if t == "journalArticle":
        base.update(publicationTitle=venue, volume=vol, issue=iss,
                    pages=pages, DOI=doi)
    elif t == "conferencePaper":
        base.update(proceedingsTitle=venue, pages=pages, publisher=pub,
                    place=place, DOI=doi)
    elif t == "book":
        base.update(publisher=pub, place=place)
    elif t == "bookSection":
        base.update(bookTitle=venue, publisher=pub, place=place, pages=pages)
    elif t == "thesis":
        base.update(university=pub or venue, place=place)
    elif t == "report":
        base.update(institution=pub or venue, place=place)
    elif t == "dataset":
        base.update(repository=venue, DOI=doi)
    else:  # document
        base.update(publisher=pub)
        if doi:
            base["extra"] = (base["extra"] + f"\nDOI: {doi}").strip()
    return {k: v for k, v in base.items() if v not in ("", None, [])}


def save_items(api_key: str, user_id: str, items: list) -> dict:
    """把条目写入用户 Zotero 库。返回 {saved, failed, errors, keys}。"""
    api_key = (api_key or "").strip()
    user_id = str(user_id or "").strip()
    if not api_key or not user_id:
        raise ValueError("请先填写 Zotero API Key 与 User ID")
    if not user_id.isdigit():
        raise ValueError("Zotero User ID 应为纯数字")
    items = [it for it in (items or []) if isinstance(it, dict)]
    if not items:
        raise ValueError("没有可保存的文献")
    if len(items) > _MAX_BATCH:
        raise ValueError(f"单次最多保存 {_MAX_BATCH} 条，请减少勾选数量")

    payload = [_zotero_item(it) for it in items]
    headers = {
        "Zotero-API-Key":     api_key,
        "Zotero-API-Version": _API_VERSION,
        "Content-Type":       "application/json",
    }
    url = f"{ZOTERO_API}/users/{user_id}/items"
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=20.0)
    except httpx.HTTPError as e:
        raise RuntimeError(f"连接 Zotero API 失败：{e}")

    if resp.status_code in (401, 403):
        raise RuntimeError("Zotero 鉴权失败：请检查 API Key 是否有该库写权限、User ID 是否正确")
    if resp.status_code == 404:
        raise RuntimeError("Zotero 用户库不存在：请检查 User ID")
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Zotero 写入返回 {resp.status_code}：{resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"Zotero 返回非 JSON：{e}")

    success = data.get("success", {}) or {}
    failed = data.get("failed", {}) or {}
    errors = [f"第{int(k) + 1}条：{v.get('message', v)}" for k, v in failed.items()]
    return {
        "saved":  len(success),
        "failed": len(failed),
        "errors": errors,
        "keys":   list(success.values()),
    }
