import { useRef, useState } from 'react';
import { api } from '../../../lib/api.js';
import Button from '../../ui/Button.jsx';
import { InfoTip } from '../../ui/Tooltip.jsx';
import LiteraturePanel from './LiteraturePanel.jsx';
import QaThread from './QaThread.jsx';

export default function QaPane() {
  const [selected, setSelected] = useState([]); // 勾选带入提问的文献
  const [bubbles, setBubbles] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const historyRef = useRef([]);

  async function askQa() {
    const q = input.trim();
    const refs = selected.map((it) => it.citation).filter(Boolean);
    if (!q && !refs.length) return;
    setInput('');
    const userText = q
      ? refs.length
        ? `${q}\n（附带 ${refs.length} 篇检索文献）`
        : q
      : `请按 GB/T 7714—2015 规范以下 ${refs.length} 篇检索文献的著录格式`;
    setBubbles((b) => [
      ...b,
      { role: 'user', text: userText },
      { role: 'bot', pending: true },
    ]);
    setSending(true);
    const settle = (patch) =>
      setBubbles((b) =>
        b.map((x, i) => (i === b.length - 1 && x.pending ? patch : x)),
      );
    try {
      const data = await api.qa(q, historyRef.current.slice(-6), refs);
      settle({ role: 'bot', text: data.answer });
      historyRef.current.push({ role: 'user', content: userText });
      historyRef.current.push({ role: 'assistant', content: data.answer });
    } catch (err) {
      settle({ role: 'bot', text: '出错了：' + err.message });
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="scroll-thin flex-1 overflow-auto pt-1">
      <div className="card flex flex-col p-3.5">
        <h3 className="mb-2 flex items-center gap-1.5 text-[13px] font-bold text-ink-heading">
          💬 论文格式答疑
          <InfoTip content="基于 GB/T 7714 / GB/T 7713 等国标与通用排版规范作答。" />
        </h3>

        <LiteraturePanel selected={selected} setSelected={setSelected} />

        <QaThread bubbles={bubbles} />

        <textarea
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) askQa();
          }}
          placeholder="例：参考文献里的学位论文该怎么著录？前置部分页码用什么数字？"
          className="mt-2 w-full resize-y rounded-btn border border-white/55 bg-white/50 p-2.5 text-sm outline-none backdrop-blur-sm focus:border-gold"
        />
        <Button
          variant="primary"
          className="mt-2 w-full"
          disabled={sending}
          onClick={askQa}
        >
          {sending ? '思考中…' : '提问'}
        </Button>
      </div>
    </div>
  );
}
