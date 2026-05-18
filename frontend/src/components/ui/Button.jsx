import { cn } from '../../lib/cn.js';
import { useRipple, RippleLayer } from '../../lib/useRipple.jsx';

// variant: primary（金填充白字）| secondary（浅灰底深灰字）| ghost（玻璃描边）
const VARIANTS = {
  primary: 'bg-gold text-white shadow-gold-glow hover:bg-gold-deep hover:shadow-[0_4px_18px_rgba(212,175,55,0.45)]',
  secondary: 'bg-gray-100 text-ink-heading hover:bg-gray-200',
  ghost:
    'bg-white/45 backdrop-blur border border-white/55 text-ink-body hover:bg-white/65 hover:text-ink-heading',
};

const RIPPLE = {
  primary: 'rgba(255,255,255,0.5)',
  secondary: 'rgba(212,175,55,0.28)',
  ghost: 'rgba(212,175,55,0.22)',
};

export default function Button({
  variant = 'secondary',
  size = 'md',
  className = '',
  children,
  onPointerDown,
  ...rest
}) {
  const { ripples, add } = useRipple();
  return (
    <button
      onPointerDown={(e) => {
        add(e);
        onPointerDown?.(e);
      }}
      className={cn(
        'relative isolate inline-flex items-center justify-center overflow-hidden rounded-btn font-medium',
        'transition-[transform,background-color,box-shadow] duration-150',
        'active:scale-[0.96] disabled:pointer-events-none disabled:opacity-40',
        size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-4 py-2 text-sm',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      <span className="relative z-10 inline-flex items-center justify-center gap-1.5">
        {children}
      </span>
      <RippleLayer ripples={ripples} color={RIPPLE[variant]} />
    </button>
  );
}
