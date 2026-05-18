import { useRef } from 'react';
import { useSession } from '../../state/SessionContext.jsx';
import { useDragDrop } from '../../lib/useDragDrop.js';
import { api } from '../../lib/api.js';
import Icon from '../ui/Icon.jsx';
import { cn } from '../../lib/cn.js';

export default function UploadZone() {
  const {
    hasDoc,
    setSession,
    setStatus,
    addMsg,
    addError,
    bumpPreview,
    bumpStructure,
  } = useSession();
  const inputRef = useRef(null);

  async function uploadFile(file) {
    if (!file.name.toLowerCase().endsWith('.docx')) {
      addError('只支持 .docx 文件');
      return;
    }
    setStatus('上传中…');
    try {
      const data = await api.upload(file);
      setSession(data.session_id, data.filename);
      addMsg('bot', `已加载 ${data.filename}，告诉我你想怎么修改吧。`);
      bumpPreview();
      bumpStructure(true);
    } catch (err) {
      setStatus('上传失败');
      addError(err.message);
    }
  }

  const { dragging, handlers } = useDragDrop((files) => {
    if (files[0]) uploadFile(files[0]);
  });

  if (hasDoc) return null;

  return (
    <label
      {...handlers}
      className={cn(
        'glass relative mx-3.5 mt-3.5 block flex-shrink-0 cursor-pointer overflow-hidden',
        'rounded-card-lg border-[1.5px] border-dashed px-4 pb-5 pt-6 text-center transition',
        dragging
          ? 'border-gold ring-2 ring-gold/20'
          : 'border-white/60 hover:border-gold',
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".docx"
        className="hidden"
        onChange={(e) => {
          if (e.target.files[0]) uploadFile(e.target.files[0]);
          e.target.value = '';
        }}
      />
      <div className="mx-auto mb-2.5 flex h-11 w-11 items-center justify-center rounded-card bg-gold/10 text-gold">
        <Icon name="upload" size={21} />
      </div>
      <p className="text-[13px] font-medium text-ink-heading">
        点击或拖入 .docx 文件
      </p>
      <p className="mt-1 text-[11.5px] text-ink-faint">
        上传后即可用自然语言修改格式
      </p>
    </label>
  );
}
