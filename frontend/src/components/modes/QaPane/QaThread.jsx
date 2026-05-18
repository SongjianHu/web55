import { useEffect, useRef } from 'react';
import Markdown from '../../ui/Markdown.jsx';
import Spinner from '../../ui/Spinner.jsx';

export default function QaThread({ bubbles }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [bubbles]);

  return (
    <div ref={ref} className="scroll-thin min-h-[120px] flex-1 overflow-y-auto">
      {bubbles.map((b, i) => (
        <div key={i} className="mb-2.5 text-[13px] leading-relaxed">
          {b.role === 'user' ? (
            <>
              <div className="mb-1 font-bold text-gold">你</div>
              <div className="whitespace-pre-wrap text-ink-heading">
                {b.text}
              </div>
            </>
          ) : (
            <>
              <div className="mb-1 font-bold text-ink-heading">助手</div>
              <div className="glass rounded-card p-3.5 text-ink-heading">
                {b.pending ? (
                  <span className="flex items-center gap-2 text-ink-body">
                    <Spinner size={15} />
                    思考中…
                  </span>
                ) : (
                  <Markdown>{b.text}</Markdown>
                )}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
