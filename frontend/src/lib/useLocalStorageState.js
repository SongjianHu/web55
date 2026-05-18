import { useState, useCallback } from 'react';

// 仅用于 oaKey / zoKey / zoUid 三个键：初始化读 localStorage，写时 trim 后回存。
export function useLocalStorageState(key) {
  const [value, setValue] = useState(() => {
    try {
      return localStorage.getItem(key) || '';
    } catch {
      return '';
    }
  });

  const set = useCallback(
    (v) => {
      setValue(v);
      try {
        localStorage.setItem(key, (v || '').trim());
      } catch {
        /* ignore */
      }
    },
    [key],
  );

  return [value, set];
}
