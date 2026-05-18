import { Info } from 'lucide-react';
import { cn } from '../../lib/cn.js';

// 纯 CSS 悬浮提示：仅 hover 时弹出，避免常驻说明文字占位。
export function Tooltip({ content, children, className = '' }) {
  return (
    <span className={cn('group/tt relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-[calc(100%+6px)] left-1/2 z-[60] w-max max-w-[240px] -translate-x-1/2 whitespace-normal rounded-btn bg-ink-heading/95 px-2.5 py-1.5 text-left text-[11px] font-normal leading-relaxed text-white opacity-0 shadow-card-hover backdrop-blur-sm transition-opacity duration-150 group-hover/tt:opacity-100"
      >
        {content}
      </span>
    </span>
  );
}

export function InfoTip({ content, className = '' }) {
  return (
    <Tooltip content={content} className={className}>
      <Info
        size={13}
        strokeWidth={1.5}
        className="cursor-help text-ink-faint transition-colors hover:text-gold"
        aria-hidden="true"
      />
    </Tooltip>
  );
}
