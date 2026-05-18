import { useEffect, useState } from 'react';
import { useSession } from '../../../state/SessionContext.jsx';
import { api } from '../../../lib/api.js';
import Collapsible from '../../ui/Collapsible.jsx';
import Button from '../../ui/Button.jsx';
import Icon from '../../ui/Icon.jsx';

const CAT_ORDER = ['页面', '字体', '标题', '节专属', '题注', '表格', '页眉页脚', '编号'];

export default function DefaultsPanel() {
  const {
    sessionId,
    defaultsList,
    setDefaultsList,
    checkedDefaultIds,
    setCheckedDefaultIds,
    addMsg,
    updateMsg,
    removeMsg,
    addError,
    setHistoryCount,
    bumpPreview,
    bumpStructure,
  } = useSession();

  const [loadErr, setLoadErr] = useState('');
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    api
      .defaults()
      .then((data) => {
        const list = data.defaults || [];
        setDefaultsList(list);
        setCheckedDefaultIds(list.filter((d) => d.preselected).map((d) => d.id));
      })
      .catch((e) => setLoadErr(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checked = new Set(checkedDefaultIds);
  const toggle = (id) =>
    setCheckedDefaultIds((ids) =>
      ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id],
    );
  const setAll = (on) =>
    setCheckedDefaultIds(on ? defaultsList.map((d) => d.id) : []);

  // 分组（类目顺序与后端 CATEGORY_ORDER 一致）
  const groups = {};
  for (const d of defaultsList) (groups[d.category] ||= []).push(d);
  const cats = CAT_ORDER.filter((c) => groups[c]).concat(
    Object.keys(groups).filter((c) => !CAT_ORDER.includes(c)),
  );

  async function applyDefaults() {
    if (!sessionId || !checkedDefaultIds.length) return;
    setApplying(true);
    const id = addMsg('bot', `正在应用 ${checkedDefaultIds.length} 项默认排版…`);
    try {
      const data = await api.applyDefaults(sessionId, checkedDefaultIds);
      updateMsg(id, {
        text: data.explanation || '已完成',
        distilled:
          data.applied && data.applied.length
            ? data.applied.map((n, i) => `${i + 1}. ${n}`).join('\n')
            : undefined,
        distilledSummary:
          data.applied && data.applied.length
            ? `已应用 ${data.applied.length} 项功能（点击展开）`
            : undefined,
        ops:
          data.operations && data.operations.length
            ? data.operations
            : undefined,
      });
      if (data.history_count != null) setHistoryCount(data.history_count);
      bumpPreview();
      bumpStructure();
    } catch (err) {
      removeMsg(id);
      addError(err.message);
    } finally {
      setApplying(false);
    }
  }

  return (
    <Collapsible
      className="glass mx-3.5 flex-shrink-0 overflow-hidden rounded-card"
      summaryClassName="px-3.5 py-2.5 text-[12.5px] font-medium text-ink-body hover:bg-gray-50"
      bodyClassName="scroll-thin max-h-[320px] overflow-y-auto border-t border-dashed border-line px-3.5 py-2"
      summary={
        <>
          <Icon name="checklist" size={13} />
          默认排版功能
        </>
      }
      right={
        <span className="ml-auto rounded-full bg-gold/10 px-2 py-0.5 text-[10.5px] font-medium text-gold-deep">
          {loadErr
            ? '加载失败'
            : `${checkedDefaultIds.length} / ${defaultsList.length} 项`}
        </span>
      }
    >
      {loadErr ? (
        <div className="text-xs text-red-600">加载失败：{loadErr}</div>
      ) : defaultsList.length === 0 ? (
        <div className="py-4 text-center text-xs text-ink-faint">加载中…</div>
      ) : (
        <>
          {cats.map((cat) => (
            <div key={cat} className="mt-2 first:mt-0">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
                {cat}
              </div>
              {groups[cat].map((d) => (
                <label
                  key={d.id}
                  className="group relative flex cursor-pointer items-center gap-1.5 rounded-btn px-1.5 py-1.5 text-[12.5px] text-ink-heading hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    className="h-3.5 w-3.5 flex-shrink-0 cursor-pointer accent-gold"
                    checked={checked.has(d.id)}
                    onChange={() => toggle(d.id)}
                  />
                  <span className="flex-1">{d.name}</span>
                  <span className="flex h-4 w-4 cursor-help items-center justify-center rounded-full bg-gray-100 text-[9px] font-bold text-ink-faint">
                    i
                  </span>
                  <span className="pointer-events-none absolute bottom-[calc(100%+4px)] left-3.5 right-3.5 z-50 rounded-btn bg-ink-heading/95 px-2.5 py-2 text-[11.5px] leading-relaxed text-white opacity-0 shadow-card-hover transition-opacity group-hover:opacity-100">
                    {d.description}
                  </span>
                </label>
              ))}
            </div>
          ))}
          <div className="mt-2.5 flex gap-1.5 border-t border-dashed border-line pt-2">
            <Button
              variant="primary"
              size="sm"
              disabled={!sessionId || !checkedDefaultIds.length || applying}
              onClick={applyDefaults}
            >
              {applying ? '应用中…' : '应用所选'}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setAll(true)}>
              全选
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setAll(false)}>
              全不选
            </Button>
          </div>
        </>
      )}
    </Collapsible>
  );
}
