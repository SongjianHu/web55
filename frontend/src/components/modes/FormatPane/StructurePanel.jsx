import { useEffect, useState } from 'react';
import { useSession } from '../../../state/SessionContext.jsx';
import { api } from '../../../lib/api.js';
import Collapsible from '../../ui/Collapsible.jsx';
import Icon from '../../ui/Icon.jsx';
import { cn } from '../../../lib/cn.js';
import {
  STRUCTURE_BADGE_CFG,
  STRUCTURE_INDENT,
  SECTION_LABELS,
  SECTION_ORDER,
  INLINE_TYPES,
} from '../../../constants/structure.js';

const clip = (t) => (t.length > 44 ? t.slice(0, 42) + '…' : t);

// 二级及更深标题归为章节的子节点，默认折叠（与一键论文默认样式应用的章节识别一致）
const CHILD_TYPES = new Set([
  'heading_2',
  'heading_3',
  'heading_4',
  'heading_5',
  'heading_6',
]);

// 把扁平有序列表组装成「章节(顶层) → 二级+子标题」的两层结构
function buildTree(items) {
  const nodes = [];
  let cur = null;
  for (const it of items) {
    if (CHILD_TYPES.has(it.type)) {
      if (cur) cur.children.push(it);
      else nodes.push({ item: it, children: [] }); // 无父章节的孤立子标题：独立显示
    } else {
      cur = { item: it, children: [] };
      nodes.push(cur);
    }
  }
  return nodes;
}

function Badge({ item }) {
  const cfg = STRUCTURE_BADGE_CFG[item.type] || {
    label: item.label,
    color: '#64748b',
    bg: 'rgba(100,116,139,0.10)',
  };
  return (
    <span
      className="flex-shrink-0 rounded-[3px] px-1.5 py-px text-[10px] font-semibold"
      style={{ color: cfg.color, background: cfg.bg, minWidth: 28, textAlign: 'center' }}
    >
      {cfg.label}
    </span>
  );
}

function Item({ item }) {
  const indent = STRUCTURE_INDENT[item.type] || 0;
  return (
    <div
      className="flex items-baseline gap-1.5 rounded-btn py-[3px] pr-1 leading-normal hover:bg-gray-50"
      style={{ paddingLeft: 4 + indent }}
    >
      <Badge item={item} />
      <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-[11.5px] text-ink-body">
        {clip(item.text)}
      </span>
    </div>
  );
}

function ChapterNode({ node, nodeKey, openCh, toggle }) {
  if (node.children.length === 0) return <Item item={node.item} />;
  const isOpen = openCh.has(nodeKey);
  return (
    <div>
      <button
        type="button"
        onClick={() => toggle(nodeKey)}
        className="flex w-full items-baseline gap-1 rounded-btn py-[3px] pl-1 pr-1 text-left hover:bg-gray-50"
      >
        <span
          className={cn(
            'w-2.5 flex-shrink-0 text-[9px] text-ink-faint transition-transform',
            isOpen && 'rotate-90',
          )}
        >
          ▸
        </span>
        <Badge item={node.item} />
        <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-[11.5px] text-ink-body">
          {clip(node.item.text)}
        </span>
        {!isOpen && (
          <span className="flex-shrink-0 rounded-full bg-gray-100 px-1.5 text-[10px] text-ink-faint">
            {node.children.length} 节
          </span>
        )}
      </button>
      {isOpen &&
        node.children.map((c, i) => <Item key={i} item={c} />)}
    </div>
  );
}

export default function StructurePanel() {
  const { sessionId, structureSignal, structureAutoOpen } = useSession();
  const [open, setOpen] = useState(false);
  const [openCh, setOpenCh] = useState(new Set());
  const [state, setState] = useState({ status: 'idle', data: null, error: '' });

  const toggle = (key) =>
    setOpenCh((s) => {
      const n = new Set(s);
      n.has(key) ? n.delete(key) : n.add(key);
      return n;
    });

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setState({ status: 'loading', data: null, error: '' });
    setOpenCh(new Set()); // 新数据：章节默认全部折叠
    if (structureAutoOpen) setOpen(true);
    api
      .structure(sessionId)
      .then((d) => !cancelled && setState({ status: 'ok', data: d, error: '' }))
      .catch(
        (e) =>
          !cancelled &&
          setState({ status: 'error', data: null, error: e.message }),
      );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, structureSignal]);

  const { status, data, error } = state;
  const sections = data?.sections || null;
  const stats = data?.stats || {};
  const totalItems = sections
    ? Object.values(sections).reduce((n, s) => n + s.length, 0)
    : (data?.items || []).filter((x) => !INLINE_TYPES.has(x.type)).length;

  let tag = '上传后识别';
  if (status === 'loading') tag = '识别中…';
  else if (status === 'error') tag = '识别失败';
  else if (status === 'ok') tag = totalItems ? `${totalItems} 项` : '未识别';

  const statParts = [];
  if (stats.figures) statParts.push(`图 ${stats.figures} 个`);
  if (stats.tables) statParts.push(`表 ${stats.tables} 个`);
  if (stats.equations) statParts.push(`公式 ${stats.equations} 个`);

  return (
    <Collapsible
      className="glass mx-3.5 flex-shrink-0 overflow-hidden rounded-card"
      summaryClassName="px-3.5 py-2.5 text-[12.5px] font-medium text-ink-body hover:bg-gray-50"
      bodyClassName="scroll-thin max-h-[340px] overflow-y-auto border-t border-dashed border-line px-3.5 py-2"
      open={open}
      onToggle={setOpen}
      summary={
        <>
          <Icon name="file" size={13} />
          论文结构识别
        </>
      }
      right={
        <span className="ml-auto rounded-full bg-teal-500/10 px-2 py-0.5 text-[10.5px] font-medium text-teal-700">
          {tag}
        </span>
      }
    >
      {status === 'loading' && (
        <div className="py-3 text-center text-xs text-ink-faint">识别中…</div>
      )}
      {status === 'error' && (
        <div className="text-xs text-red-600">识别失败：{error}</div>
      )}
      {status === 'ok' && !totalItems && (
        <div className="py-3 text-center text-xs text-ink-faint">
          未识别到结构元素
        </div>
      )}
      {status === 'ok' && totalItems > 0 && (
        <>
          {sections
            ? SECTION_ORDER.filter((k) => (sections[k] || []).length).map((k) => {
                const meta = SECTION_LABELS[k] || { zh: k, color: '#64748b' };
                return (
                  <div key={k}>
                    <div
                      className="px-1.5 pb-0.5 pt-1.5 text-[10px] font-semibold tracking-wider opacity-80"
                      style={{ color: meta.color }}
                    >
                      {meta.zh}
                    </div>
                    {buildTree(sections[k]).map((node, i) => (
                      <ChapterNode
                        key={i}
                        node={node}
                        nodeKey={`${k}:${i}`}
                        openCh={openCh}
                        toggle={toggle}
                      />
                    ))}
                  </div>
                );
              })
            : buildTree(
                (data.items || []).filter((x) => !INLINE_TYPES.has(x.type)),
              ).map((node, i) => (
                <ChapterNode
                  key={i}
                  node={node}
                  nodeKey={`flat:${i}`}
                  openCh={openCh}
                  toggle={toggle}
                />
              ))}

          {statParts.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5 border-t border-dashed border-line pt-2">
              {statParts.map((s) => (
                <span
                  key={s}
                  className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-ink-faint"
                >
                  {s}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </Collapsible>
  );
}
