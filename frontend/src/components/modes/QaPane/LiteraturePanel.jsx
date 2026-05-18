import { useEffect, useRef, useState } from 'react';
import { api } from '../../../lib/api.js';
import { useLocalStorageState } from '../../../lib/useLocalStorageState.js';
import Button from '../../ui/Button.jsx';
import Collapsible from '../../ui/Collapsible.jsx';
import { InfoTip } from '../../ui/Tooltip.jsx';

function LitCard({ it, selected, onToggle }) {
  const [copyText, setCopyText] = useState('复制著录');
  const meta = [
    it.authors,
    it.year,
    it.publication,
    it.cited_by ? `被引 ${it.cited_by}` : '',
  ]
    .filter(Boolean)
    .join(' · ');

  async function copy() {
    try {
      await navigator.clipboard.writeText(it.citation);
      setCopyText('已复制');
    } catch {
      setCopyText('复制失败');
    }
    setTimeout(() => setCopyText('复制著录'), 1500);
  }

  return (
    <div className="rounded-btn border border-white/55 bg-white/45 px-2.5 py-2 text-xs leading-normal">
      <label className="float-right cursor-pointer select-none text-[11px] text-gold">
        <input
          type="checkbox"
          className="mr-1 accent-gold"
          checked={selected}
          onChange={(e) => onToggle(it, e.target.checked)}
        />
        选择
      </label>
      <div className="my-0.5 font-bold text-ink-heading">{it.title}</div>
      <div className="text-[11px] text-ink-faint">{meta}</div>
      <div className="mt-1.5 whitespace-pre-wrap rounded-md border border-dashed border-line bg-surface p-1.5 font-mono text-[11px] text-ink-body">
        {it.citation}
      </div>
      <button
        type="button"
        onClick={copy}
        className="mt-1.5 rounded-md border border-line bg-surface px-2 py-0.5 text-[11px] text-ink-body hover:border-gold hover:text-gold"
      >
        {copyText}
      </button>
    </div>
  );
}

export default function LiteraturePanel({ selected, setSelected }) {
  const [oaKey, setOaKey] = useLocalStorageState('oaKey');
  const [zoKey, setZoKey] = useLocalStorageState('zoKey');
  const [zoUid, setZoUid] = useLocalStorageState('zoUid');

  const [query, setQuery] = useState('');
  const [fromYear, setFromYear] = useState('');
  const [toYear, setToYear] = useState('');
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState('');
  const [searching, setSearching] = useState(false);
  const [savingZo, setSavingZo] = useState(false);
  const [oaBoxOpen, setOaBoxOpen] = useState(false);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    if (!oaKey) setOaBoxOpen(true);
    api
      .openalexDefaults()
      .then((d) => {
        setFromYear((v) => v || d.from_year);
        setToYear((v) => v || d.to_year);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selMap = new Map(selected.map((it) => [it.id, it]));

  function onToggle(it, checked) {
    setSelected((cur) =>
      checked
        ? [...cur.filter((x) => x.id !== it.id), it]
        : cur.filter((x) => x.id !== it.id),
    );
  }

  async function searchLit() {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    setStatus('');
    setResults([]);
    try {
      const data = await api.openalexSearch({
        query: q,
        fromYear: fromYear || undefined,
        toYear: toYear || undefined,
        limit: 20,
        apiKey: oaKey.trim() || undefined,
      });
      if (!data.items.length) {
        setStatus('未检索到匹配文献（可放宽年份范围）');
        return;
      }
      const yr = data.year_range
        ? `${data.year_range[0]}–${data.year_range[1]}`
        : '';
      setStatus(
        `共 ${data.count} 条 · ${yr} · 同义词：${(data.terms || []).join(' / ')}` +
          (data.partial ? '（部分同义词请求超时，已返回可用结果）' : ''),
      );
      setResults(data.items);
    } catch (err) {
      setStatus('检索失败：' + err.message);
    } finally {
      setSearching(false);
    }
  }

  function exportGbt() {
    const items = selected.length ? selected : results;
    if (!items.length) return;
    const text = items.map((it, i) => `[${i + 1}] ${it.citation}`).join('\r\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'references-gbt7714.txt';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function saveToZotero() {
    if (!selected.length) return;
    const key = zoKey.trim();
    const uid = zoUid.trim();
    if (!key || !uid) {
      setStatus('请先在「⚙️ Zotero 账号」里填写 API Key 与 User ID');
      return;
    }
    setSavingZo(true);
    try {
      const d = await api.zoteroSave(key, uid, selected);
      let msg = `已存入 Zotero ${d.saved} 篇`;
      if (d.failed)
        msg += `，失败 ${d.failed} 篇（${(d.errors || []).join('；')}）`;
      setStatus(msg);
      if (d.saved && !d.failed) setSelected([]);
    } catch (err) {
      setStatus('存入 Zotero 失败：' + err.message);
    } finally {
      setSavingZo(false);
    }
  }

  const n = selected.length;
  const exportN = n || results.length;
  const inputCls =
    'rounded-btn border border-white/55 bg-white/50 px-2 py-1.5 text-sm outline-none backdrop-blur-sm focus:border-gold';

  return (
    <Collapsible
      className="glass mb-2.5 rounded-card"
      summaryClassName="px-3 py-2.5 text-xs font-bold text-ink-heading hover:bg-white/30"
      bodyClassName="border-t border-white/40 px-3 pb-3 pt-2"
      summary={
        <>
          🔎 文献检索（OpenAlex）
          <InfoTip content="自动扩展英文同义词检索，默认近三年。可复制 GB/T 7714 著录、勾选「带入提问」，或选中后「存入 Zotero」。" />
        </>
      }
      right={
        <span className="ml-auto rounded-full bg-gold/10 px-2 py-0.5 text-[10.5px] font-medium text-gold-deep">
          {n ? `已选 ${n}` : results.length ? `${results.length} 条` : '展开'}
        </span>
      }
    >
      <div className="flex flex-wrap gap-1.5">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              searchLit();
            }
          }}
          type="text"
          placeholder="关键词（中/英均可），如：深度学习"
          className={`${inputCls} min-w-[160px] flex-1`}
        />
        <input
          value={fromYear}
          onChange={(e) => setFromYear(e.target.value)}
          type="number"
          min="1900"
          max="2100"
          title="起始年"
          className={`${inputCls} w-[74px]`}
        />
        <span className="self-center text-ink-faint">–</span>
        <input
          value={toYear}
          onChange={(e) => setToYear(e.target.value)}
          type="number"
          min="1900"
          max="2100"
          title="结束年"
          className={`${inputCls} w-[74px]`}
        />
        <Button
          variant="secondary"
          size="sm"
          disabled={searching}
          onClick={searchLit}
        >
          {searching ? '搜索中…' : '搜索'}
        </Button>
      </div>

      <details
        open={oaBoxOpen}
        onToggle={(e) => setOaBoxOpen(e.target.open)}
        className="mt-1.5"
      >
        <summary className="flex cursor-pointer items-center gap-1 text-[11px] text-ink-faint">
          ⚙️ OpenAlex API Key
          <InfoTip content="必填，免费；仅存本机浏览器。在 openalex.org/settings/api 注册获取后填入。" />
        </summary>
        <input
          value={oaKey}
          onChange={(e) => setOaKey(e.target.value)}
          type="password"
          placeholder="OpenAlex API Key"
          className={`${inputCls} mt-1.5 w-full`}
        />
        <a
          href="https://openalex.org/settings/api"
          target="_blank"
          rel="noopener"
          className="mt-1 inline-block text-[11px] font-medium text-gold hover:text-gold-deep"
        >
          获取免费 Key ↗
        </a>
      </details>

      {status && (
        <div className="mt-1.5 text-[11px] text-ink-faint">{status}</div>
      )}

      <div className="scroll-thin mt-2 flex max-h-[260px] flex-col gap-1.5 overflow-auto">
        {results.map((it) => (
          <LitCard
            key={it.id}
            it={it}
            selected={selMap.has(it.id)}
            onToggle={onToggle}
          />
        ))}
      </div>

      <details className="mt-2">
        <summary className="flex cursor-pointer items-center gap-1 text-[11px] text-ink-faint">
          ⚙️ Zotero 账号
          <InfoTip content="用于「存入 Zotero」，仅存本机浏览器。在 zotero.org/settings/keys 创建带写权限的 Key；User ID 见该页顶部。" />
        </summary>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          <input
            value={zoKey}
            onChange={(e) => setZoKey(e.target.value)}
            type="password"
            placeholder="Zotero API Key"
            className={`${inputCls} min-w-[150px] flex-1`}
          />
          <input
            value={zoUid}
            onChange={(e) => setZoUid(e.target.value)}
            type="text"
            placeholder="Zotero User ID（数字）"
            className={`${inputCls} min-w-[150px] flex-1`}
          />
        </div>
      </details>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1">
          <Button
            variant="secondary"
            size="sm"
            disabled={exportN === 0}
            onClick={exportGbt}
          >
            导出 GB/T 7714（{exportN}）
          </Button>
          <InfoTip content="未勾选时「导出 GB/T 7714」将导出全部检索结果。" />
        </span>
        <Button
          variant="secondary"
          size="sm"
          disabled={n === 0 || savingZo}
          onClick={saveToZotero}
        >
          {savingZo ? '保存中…' : `存入 Zotero（${n}）`}
        </Button>
        {n > 0 && (
          <div className="basis-full text-[11px] text-gold">
            已选 {n} 篇：可导出/存入 Zotero，或直接提问让助手据此生成/校对参考文献
          </div>
        )}
      </div>
    </Collapsible>
  );
}
