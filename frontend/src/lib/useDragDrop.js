import { useState, useCallback } from 'react';

// 拖放上传：返回 dragging 状态与可展开到目标元素的事件处理器。
// onFiles 收到原始 FileList。
export function useDragDrop(onFiles) {
  const [dragging, setDragging] = useState(false);

  const handlers = {
    onDragOver: useCallback((e) => {
      e.preventDefault();
      setDragging(true);
    }, []),
    onDragLeave: useCallback(() => setDragging(false), []),
    onDrop: useCallback(
      (e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files?.length) onFiles(e.dataTransfer.files);
      },
      [onFiles],
    ),
  };

  return { dragging, handlers };
}
