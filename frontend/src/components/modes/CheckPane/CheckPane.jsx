import { useRef, useState } from 'react';
import { useSession } from '../../../state/SessionContext.jsx';
import { api } from '../../../lib/api.js';
import Button from '../../ui/Button.jsx';
import CheckReport from './CheckReport.jsx';

const CATS = [
  { value: 'citation', label: '引用对应性' },
  { value: 'reference_format', label: '参考文献格式' },
  { value: 'structure', label: '结构完整性' },
  { value: 'compliance', label: '格式合规' },
];

export default function CheckPane() {
  const { sessionId } = useSession();
  const [cats, setCats] = useState(CATS.map((c) => c.value));
  const [reviewFile, setReviewFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [loadingText, setLoadingText] = useState('');
  const reviewRef = useRef(null);

  const toggle = (v) =>
    setCats((c) => (c.includes(v) ? c.filter((x) => x !== v) : [...c, v]));

  async function runCheck() {
    if (!sessionId) {
      alert('请先在「排版模式」上传论文 .docx');
      return;
    }
    if (!cats.length) {
      alert('请至少选择一个检查项');
      return;
    }
    setBusy(true);
    setError('');
    setReport(null);
    setLoadingText('正在分析论文，请稍候…');
    try {
      const rep = await api.check(sessionId, cats, reviewFile);
      setReport(rep);
    } catch (err) {
      setError(`检查失败：${err.message}`);
    } finally {
      setBusy(false);
      setLoadingText('');
    }
  }

  return (
    <div className="scroll-thin flex-1 overflow-auto pt-1">
      <div className="card mb-3 p-3.5">
        <h3 className="mb-2.5 text-[13px] font-bold text-ink-heading">
          ① 选择检查项
        </h3>
        <div className="mb-3 flex flex-wrap gap-2">
          {CATS.map((c) => (
            <label
              key={c.value}
              className="flex cursor-pointer items-center gap-1.5 rounded-btn border border-white/55 bg-white/40 px-2.5 py-1.5 text-[12.5px] text-ink-body backdrop-blur-sm"
            >
              <input
                type="checkbox"
                className="cursor-pointer accent-gold"
                checked={cats.includes(c.value)}
                onChange={() => toggle(c.value)}
              />
              {c.label}
            </label>
          ))}
        </div>
        <h3 className="mb-2.5 text-[13px] font-bold text-ink-heading">
          ② 文献综述（可选，用于引用对应性交叉核对）
        </h3>
        <button
          type="button"
          onClick={() => reviewRef.current?.click()}
          className="glass mb-2.5 block w-full cursor-pointer rounded-btn border-[1.5px] border-dashed border-white/60 p-3 text-center text-xs text-ink-faint transition-colors hover:border-gold hover:text-gold"
        >
          {reviewFile
            ? `已选择：${reviewFile.name}（点击可更换）`
            : '点击选择文献综述文件（.docx / .pdf / .txt）'}
        </button>
        <input
          ref={reviewRef}
          type="file"
          accept=".pdf,.docx,.txt"
          hidden
          onChange={(e) => {
            // 先读取 File 存入 state，再清空 input.value：
            // 否则再次选择同一文件不会触发 change，表现为“偶发上传失败需重选”。
            setReviewFile(e.target.files[0] || null);
            e.target.value = '';
          }}
        />
        <Button
          variant="primary"
          className="w-full"
          disabled={!sessionId || busy}
          onClick={runCheck}
        >
          {busy ? '检查中…' : '开始检查当前论文'}
        </Button>
        <div className="mt-2 text-[11px] text-ink-faint">
          检查对象为上方上传的论文。请先在「排版模式」上传 .docx 论文。
        </div>
      </div>
      <div>
        {loadingText && (
          <div className="py-6 text-center text-[13px] text-ink-faint">
            {loadingText}
          </div>
        )}
        {error && (
          <div className="rounded-md border-l-[3px] border-red-500 bg-red-500/[0.07] px-2.5 py-1.5 text-xs text-ink-heading">
            {error}
          </div>
        )}
        {report && <CheckReport report={report} />}
      </div>
    </div>
  );
}
