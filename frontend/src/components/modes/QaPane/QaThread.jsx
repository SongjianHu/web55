import { useEffect, useRef } from 'react';

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
              <div className="glass whitespace-pre-wrap rounded-card p-3.5 text-ink-heading">
                {b.text}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
