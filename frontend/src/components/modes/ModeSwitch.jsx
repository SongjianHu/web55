import { useSession } from '../../state/SessionContext.jsx';
import { cn } from '../../lib/cn.js';

const MODES = [
  { id: 'format', label: '排版模式' },
  { id: 'check', label: '检查模式' },
  { id: 'qa', label: '问答模式' },
];

export default function ModeSwitch() {
  const { mode, setMode } = useSession();
  const idx = Math.max(
    0,
    MODES.findIndex((m) => m.id === mode),
  );

  return (
    <div className="glass relative flex rounded-card p-1">
      {/* 滑动指示器：随激活项平移，液态玻璃轨道上的金色胶囊 */}
      <span
        className="absolute bottom-1 top-1 left-1 rounded-btn bg-gold shadow-gold-glow transition-transform duration-300 ease-out"
        style={{
          width: 'calc((100% - 0.5rem) / 3)',
          transform: `translateX(calc(${idx} * 100%))`,
        }}
      />
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          onClick={() => setMode(m.id)}
          className={cn(
            'relative z-10 flex-1 rounded-btn px-1.5 py-2 text-[12.5px] font-semibold transition-[color,transform] duration-200 active:scale-95',
            mode === m.id
              ? 'text-white'
              : 'text-ink-body hover:text-ink-heading',
          )}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
