import { useEffect, useRef, useState } from 'react';
import { useSession } from '../../state/SessionContext.jsx';
import { api } from '../../lib/api.js';
import { useDragDrop } from '../../lib/useDragDrop.js';
import Modal from '../ui/Modal.jsx';
import Button from '../ui/Button.jsx';
import Spinner from '../ui/Spinner.jsx';
import { cn } from '../../lib/cn.js';

function formatSize(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
  return (b / (1024 * 1024)).toFixed(2) + ' MB';
}

export default function BatchModal({ open, onClose }) {
  const { checkedDefaultIds } = useSession();
  const [files, setFiles] = useState([]);
  const [message, setMessage] = useState('');
  const [useDefaults, setUseDefaults] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(null); // {done,total,current,pct}
  const [result, setResult] = useState(null); // {data} | {error}
  const fileInputRef = useRef(null);
  const aliveRef = useRef(true);
  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
    };
  }, []);

  function addFiles(fileList) {
    setFiles((cur) => {
      const next = [...cur];
      for (const f of fileList) {
        if (!f.name.toLowerCase().endsWith('.docx')) continue;
        if (next.some((b) => b.name === f.name && b.size === f.size)) continue;
        next.push(f);
      }
      return next;
    });
  }

  const { dragging, handlers } = useDragDrop(addFiles);

  function clearAll() {
    setFiles([]);
    setMessage('');
    setResult(null);
    setProgress(null);
  }

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function runBatch() {
    const ids = useDefaults ? checkedDefaultIds : [];
    const msg = message.trim();
    if (files.length === 0) return;
    if (ids.length === 0 && !msg) {
      alert(
        useDefaults
          ? '请先在左侧勾选默认排版功能，或填写附加指令'
          : '已取消应用默认排版功能 — 请填写附加指令以指定要执行的操作',
      );
      return;
    }
    setProcessing(true);
    setResult(null);
    setProgress(null);
    try {
      const resp = await api.batch(files, ids, msg);
      if (resp.queued) {
        // 异步：轮询 job 状态直至终态（SSE 亦可，轮询足够稳）
        let st = { status: 'queued' };
        while (st.status === 'queued' || st.status === 'in_progress') {
          await sleep(1500);
          if (!aliveRef.current) return;
          st = await api.jobStatus(resp.job_id);
          if (st.progress) setProgress(st.progress);
        }
        if (st.status === 'complete') setResult({ data: st.result });
        else setResult({ error: st.error || `任务状态：${st.status}` });
      } else {
        // 同步降级（无 Redis）：直接拿到完整结果
        setResult({ data: resp });
      }
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      if (aliveRef.current) {
        setProcessing(false);
        setProgress(null);
      }
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="批量排版 · 同规则多文档"
      footer={
        <>
          <Button
            variant="ghost"
            size="sm"
            disabled={files.length === 0 && !message}
            onClick={clearAll}
          >
            清空
          </Button>
          <div className="flex-1" />
          <Button
            variant="primary"
            size="sm"
            disabled={files.length === 0 || processing}
            onClick={runBatch}
          >
            {processing ? '处理中…' : '开始批量处理'}
          </Button>
        </>
      }
    >
      <div
        {...handlers}
        role="button"
        tabIndex={0}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        className={cn(
          'glass block cursor-pointer select-none rounded-card border-[1.5px] border-dashed p-5 text-center text-[12.5px] text-ink-body transition',
          dragging
            ? 'border-gold ring-2 ring-gold/20'
            : 'border-white/60 hover:border-gold',
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx"
          multiple
          hidden
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = '';
          }}
        />
        <div>
          📂 拖入或点击选择 <strong className="text-gold">多个 .docx</strong> 文件
        </div>
        <div className="mt-1 text-[11px] text-ink-faint">
          所选文件将按相同规则处理并打包成 zip 下载
        </div>
      </div>

      {files.length > 0 && (
        <div className="scroll-thin mt-2.5 max-h-[140px] overflow-y-auto rounded-btn border border-white/55 bg-white/45">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${f.size}`}
              className="flex items-center gap-2 border-b border-white/40 px-2.5 py-1.5 text-xs text-ink-heading last:border-b-0"
            >
              <span className="flex-1 truncate">{f.name}</span>
              <span className="text-[11px] text-ink-faint">
                {formatSize(f.size)}
              </span>
              <button
                type="button"
                title="移除"
                onClick={() =>
                  setFiles((cur) => cur.filter((_, idx) => idx !== i))
                }
                className="px-0.5 text-ink-faint hover:text-red-600"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mb-1.5 mt-3.5 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
        应用规则
      </div>
      <label
        className="flex cursor-pointer items-center gap-2 rounded-btn bg-gold/10 px-3 py-2 text-xs text-ink-body"
        style={{ opacity: useDefaults ? 1 : 0.55 }}
      >
        <input
          type="checkbox"
          className="h-3.5 w-3.5 flex-shrink-0 cursor-pointer accent-gold"
          checked={useDefaults}
          onChange={(e) => setUseDefaults(e.target.checked)}
        />
        <span>
          应用左侧已勾选的{' '}
          <strong className="font-semibold text-gold-deep">
            {checkedDefaultIds.length}
          </strong>{' '}
          项默认排版功能
        </span>
      </label>

      <div className="mb-1.5 mt-3.5 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
        附加指令（可选，对全部文件生效）
      </div>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="例：把所有标题改成黑体居中，参考文献改成宋体五号"
        className="scroll-thin max-h-[200px] min-h-[60px] w-full resize-none rounded-btn border border-white/55 bg-white/45 px-3 py-2 text-[12.5px] leading-normal text-ink-heading outline-none focus:border-gold focus:ring-2 focus:ring-gold/20"
      />

      {(processing || result) && (
        <div className="mt-3.5 border-t border-dashed border-white/45 pt-2">
          {processing && (
            <div className="flex items-center gap-2.5 p-3 text-[12.5px] text-ink-body">
              <Spinner size={20} />
              <span>
                {progress
                  ? `处理中 ${progress.done}/${progress.total}` +
                    (progress.current ? ` · ${progress.current}` : '') +
                    ` (${progress.pct}%)`
                  : `正在排队/处理 ${files.length} 个文件…（每份约 1-3 秒，如含 LLM 解析会更慢）`}
              </span>
            </div>
          )}
          {result?.error && (
            <div className="p-3 text-[12.5px] text-red-600">
              批量处理失败：{result.error}
            </div>
          )}
          {result?.data && (
            <>
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
                处理结果：成功 {result.data.success_count} / 失败{' '}
                {result.data.fail_count}
              </div>
              {result.data.results.map((res, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-center gap-2 border-b border-white/40 px-1 py-1.5 text-[12.5px] last:border-b-0"
                >
                  <span
                    className={cn(
                      'flex h-[18px] w-[18px] flex-shrink-0 items-center justify-center rounded-full text-[11px] font-bold',
                      res.status === 'ok'
                        ? 'bg-emerald-500/20 text-emerald-700'
                        : 'bg-red-500/20 text-red-600',
                    )}
                  >
                    {res.status === 'ok' ? '✓' : '×'}
                  </span>
                  <span className="flex-1 truncate">{res.filename}</span>
                  {res.status === 'ok' && (
                    <span className="text-[11px] text-ink-faint">
                      {res.ops_count} ops
                      {res.title_used ? ` · 题目: ${res.title_used}` : ''}
                    </span>
                  )}
                  {res.status !== 'ok' && (
                    <div className="basis-full pl-[26px] text-[11px] text-red-600">
                      {res.error || ''}
                    </div>
                  )}
                </div>
              ))}
              {result.data.download_url && (
                <div className="mt-3 text-center">
                  <a
                    href={result.data.download_url}
                    download
                    className="inline-flex items-center justify-center rounded-btn bg-gold px-4 py-2 text-sm font-medium text-white no-underline shadow-gold-glow hover:bg-gold-deep"
                  >
                    下载结果 (zip)
                  </a>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </Modal>
  );
}
