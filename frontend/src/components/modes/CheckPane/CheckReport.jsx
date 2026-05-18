import { cn } from '../../../lib/cn.js';

const ITEM_TONE = {
  ok: 'border-emerald-500 bg-emerald-500/[0.07]',
  warn: 'border-amber-500 bg-amber-500/[0.08]',
  error: 'border-red-500 bg-red-500/[0.07]',
};

export default function CheckReport({ report }) {
  if (!report) return null;
  const s = report.summary || {};
  return (
    <div>
      <div className="mb-3 flex gap-2.5">
        <div className="flex-1 rounded-btn bg-emerald-500/[0.13] py-2.5 text-center text-xs font-bold text-emerald-700">
          通过 {s.ok || 0}
        </div>
        <div className="flex-1 rounded-btn bg-amber-500/[0.14] py-2.5 text-center text-xs font-bold text-amber-700">
          提示 {s.warn || 0}
        </div>
        <div className="flex-1 rounded-btn bg-red-500/[0.13] py-2.5 text-center text-xs font-bold text-red-700">
          问题 {s.error || 0}
        </div>
      </div>
      {report.review_used && (
        <div className="mb-2.5 text-[11px] text-ink-faint">
          已结合文献综述做交叉核对
        </div>
      )}
      {(report.categories || []).map((cat, ci) => (
        <div key={ci} className="mb-3.5">
          <div className="mb-1.5 border-b border-line pb-1 text-[12.5px] font-bold text-ink-heading">
            {cat.title}
          </div>
          {cat.items.map((it, ii) => (
            <div
              key={ii}
              className={cn(
                'mb-1.5 rounded-md border-l-[3px] px-2.5 py-1.5 text-xs leading-normal text-ink-heading',
                ITEM_TONE[it.level] || ITEM_TONE.warn,
              )}
            >
              {it.msg}
              {it.detail && (
                <div className="scroll-thin mt-1.5 max-h-[160px] overflow-auto whitespace-pre-wrap font-mono text-[11px] text-ink-faint">
                  {it.detail}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
