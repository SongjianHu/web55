import { useCallback, useLayoutEffect } from 'react';

// textarea 自适应高度：内容高度与 max 取较小值（移植旧 autoResize）。
export function useAutosize(ref, value, max = 320) {
  const resize = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, max) + 'px';
  }, [ref, max]);

  useLayoutEffect(resize, [value, resize]);

  return resize;
}
