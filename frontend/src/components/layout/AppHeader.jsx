import { useSession } from '../../state/SessionContext.jsx';
import Icon from '../ui/Icon.jsx';
import { cn } from '../../lib/cn.js';

export default function AppHeader() {
  const { status, hasDoc } = useSession();
  return (
    <header className="glass-bar z-[100] flex h-[52px] flex-shrink-0 items-center gap-3 px-5">
      <div className="flex items-center gap-2.5">
        <div className="flex h-7 w-7 items-center justify-center rounded-btn bg-gold text-white shadow-gold-glow">
          <Icon name="file" size={15} />
        </div>
        <span className="text-sm font-semibold tracking-tight text-ink-heading">
          Docx Chat Editor
        </span>
      </div>
      <div className="mx-1 h-[18px] w-px bg-line" />
      <div className="flex items-center gap-1.5 text-xs text-ink-faint">
        <span
          className={cn(
            'h-1.5 w-1.5 flex-shrink-0 rounded-full transition-all',
            hasDoc
              ? 'bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.22)]'
              : 'bg-ink-faint/50',
          )}
        />
        <span>{status}</span>
      </div>
    </header>
  );
}
