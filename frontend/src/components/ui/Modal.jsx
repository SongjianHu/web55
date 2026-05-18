import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import Icon from './Icon.jsx';

// 居中弹窗，半透明遮罩；点击遮罩 / Esc 关闭。
export default function Modal({ open, onClose, title, footer, children }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/30 p-4 backdrop-blur-[3px]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div className="glass flex max-h-[86vh] w-[min(560px,92vw)] flex-col overflow-hidden rounded-card-lg">
        <div className="flex items-center gap-3 border-b border-white/40 px-5 py-4">
          <h3 className="flex-1 text-[15px] font-medium text-ink-heading">
            {title}
          </h3>
          <button
            type="button"
            onClick={onClose}
            title="关闭"
            className="flex h-7 w-7 items-center justify-center rounded-btn text-ink-faint transition hover:bg-gray-100 hover:text-ink-heading"
          >
            <Icon name="close" size={16} />
          </button>
        </div>
        <div className="scroll-thin flex-1 overflow-y-auto px-5 py-4">
          {children}
        </div>
        {footer && (
          <div className="flex gap-2 border-t border-white/40 bg-white/20 px-5 py-3">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
