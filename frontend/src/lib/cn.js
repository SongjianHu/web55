// 轻量 className 合并：过滤 falsy，空格连接。
export function cn(...parts) {
  return parts.filter(Boolean).join(' ');
}
