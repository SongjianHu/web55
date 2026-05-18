import { useState, useCallback } from 'react';

// 点击波纹特效：在点击点生成一个扩散+淡出的圆，0.6s 后清理。
// 用法：宿主元素需 relative + overflow-hidden，onPointerDown={add}，
// 渲染 <RippleLayer ripples={ripples} color=.. />。
export function useRipple() {
  const [ripples, setRipples] = useState([]);

  const add = useCallback((e) => {
    const el = e.currentTarget;
    const rect = el.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;
    const key = Date.now() + Math.random();
    setRipples((r) => [...r, { key, x, y, size }]);
    setTimeout(
      () => setRipples((r) => r.filter((p) => p.key !== key)),
      600,
    );
  }, []);

  return { ripples, add };
}

export function RippleLayer({ ripples, color = 'rgba(255,255,255,0.5)' }) {
  return ripples.map((r) => (
    <span
      key={r.key}
      className="pointer-events-none absolute z-0 rounded-full"
      style={{
        left: r.x,
        top: r.y,
        width: r.size,
        height: r.size,
        background: color,
        animation: 'ripple 0.6s ease-out forwards',
      }}
    />
  ));
}
