import { cn } from '../../lib/cn.js';

export default function Spinner({ size = 26, className = '' }) {
  return (
    <div
      className={cn(
        'rounded-full border-[2.5px] border-line border-t-gold animate-spin',
        className,
      )}
      style={{ width: size, height: size }}
    />
  );
}
