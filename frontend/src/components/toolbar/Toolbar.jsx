import { useState } from 'react';
import { useSession } from '../../state/SessionContext.jsx';
import { api } from '../../lib/api.js';
import Button from '../ui/Button.jsx';
import Icon from '../ui/Icon.jsx';

export default function Toolbar({ onOpenBatch }) {
  const {
    sessionId,
    hasDoc,
    canUndo,
    setHistoryCount,
    addMsg,
    updateMsg,
    removeMsg,
    addError,
    reset,
    bumpPreview,
    bumpStructure,
  } = useSession();
  const [thesisBusy, setThesisBusy] = useState(false);
  const [undoBusy, setUndoBusy] = useState(false);

  function download() {
    if (sessionId) window.location.href = api.downloadUrl(sessionId);
  }

  async function applyThesisTemplate() {
    if (!sessionId) return;
    setThesisBusy(true);
    const id = addMsg('bot', '正在应用论文模板排版，建立全套命名样式…');
    try {
      const data = await api.applyDefaults(sessionId, ['smart_thesis_format_all']);
      updateMsg(id, {
        text: data.explanation || '论文模板样式已应用，可在 Word 样式面板查看。',
      });
      if (data.history_count != null) setHistoryCount(data.history_count);
      bumpPreview();
      bumpStructure();
    } catch (err) {
      removeMsg(id);
      addError(err.message);
    } finally {
      setThesisBusy(false);
    }
  }

  async function undo() {
    if (!sessionId) return;
    setUndoBusy(true);
    try {
      const data = await api.undo(sessionId);
      setHistoryCount(data.history_count);
      addMsg('bot', '已撤销上一步操作');
      bumpPreview();
      bumpStructure();
    } catch (err) {
      addError(err.message);
    } finally {
      setUndoBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b border-white/40 px-3.5 py-2.5">
      <Button variant="secondary" size="sm" disabled={!hasDoc} onClick={download}>
        <Icon name="download" size={15} />
        下载文档
      </Button>
      <Button
        variant="primary"
        size="sm"
        disabled={!hasDoc || thesisBusy}
        onClick={applyThesisTemplate}
      >
        <Icon name="wand" size={15} />
        {thesisBusy ? '排版中…' : '一键论文排版'}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        disabled={!canUndo || undoBusy}
        onClick={undo}
      >
        <Icon name="undo" size={15} />
        撤销
      </Button>
      <Button variant="ghost" size="sm" onClick={reset}>
        <Icon name="reset" size={15} />
        重新上传
      </Button>
      <Button variant="ghost" size="sm" onClick={onOpenBatch}>
        <Icon name="grid" size={15} />
        批量
      </Button>
    </div>
  );
}
