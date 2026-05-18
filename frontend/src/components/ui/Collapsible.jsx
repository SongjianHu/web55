import { useState } from 'react';
import { cn } from '../../lib/cn.js';

// 受控（传 open + onToggle）或非受控（defaultOpen）折叠面板。
export default function Collapsible({
  summary,
  right,
  open,
  defaultOpen = false,
  onToggle,
  className = '',
  summaryClassName = '',
  bodyClassName = '',
  children,
}) {
  const [internal, setInternal] = useState(defaultOpen);
  const isOpen = open !== undefined ? open : internal;

  const toggle = () => {
    const next = !isOpen;
    if (open === undefined) setInternal(next);
    onToggle?.(next);
  };

  return (
    <div className={className}>
      <button
        type="button"
        onClick={toggle}
        className={cn(
          'flex w-full items-center gap-2 text-left',
          summaryClassName,
        )}
      >
        <span
          className={cn(
            'text-[10px] text-ink-faint transition-transform duration-200',
            isOpen && 'rotate-90',
          )}
        >
          ▸
        </span>
        <span className="flex flex-1 items-center gap-2">{summary}</span>
        {right}
      </button>
      {isOpen && <div className={bodyClassName}>{children}</div>}
    </div>
  );
}
