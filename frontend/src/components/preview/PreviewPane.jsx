import { useSession } from '../../state/SessionContext.jsx';
import { useDocxPreview } from '../../lib/useDocxPreview.js';
import Icon from '../ui/Icon.jsx';

export default function PreviewPane() {
  const { sessionId, hasDoc, previewSignal, bumpPreview } = useSession();
  const { containerRef, status } = useDocxPreview(sessionId, previewSignal);

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="glass-bar flex h-11 flex-shrink-0 items-center gap-2.5 px-4">
        <div className="flex items-center gap-1.5 text-[12.5px] font-medium text-ink-body">
          <Icon name="screen" size={14} />
          文档预览
        </div>
        <span className="flex-1 text-[11.5px] text-ink-faint">{status}</span>
        <button
          type="button"
          disabled={!hasDoc}
          onClick={bumpPreview}
          className="glass flex items-center gap-1.5 rounded-btn px-2.5 py-1 text-xs text-ink-body transition-[transform,color] duration-150 hover:text-ink-heading active:scale-95 disabled:opacity-40"
        >
          <Icon name="refresh" size={13} />
          刷新
        </button>
      </div>
      <div className="scroll-thin flex flex-1 flex-col items-center overflow-y-auto p-7">
        {!hasDoc && (
          <div className="mt-[90px] flex flex-col items-center gap-2 text-center text-ink-faint">
            <div className="glass mb-1 flex h-[58px] w-[58px] items-center justify-center rounded-card-lg">
              <Icon name="file" size={26} />
            </div>
            <p className="text-[13px] font-medium text-ink-body">
              上传文档后在此显示预览
            </p>
            <p className="text-xs">每次修改后自动刷新</p>
          </div>
        )}
        <div id="previewContainer" ref={containerRef} />
      </div>
    </div>
  );
}
