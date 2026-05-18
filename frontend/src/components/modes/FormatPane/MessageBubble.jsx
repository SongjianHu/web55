import { cn } from '../../../lib/cn.js';
import Markdown from '../../ui/Markdown.jsx';

// 折叠块（蒸馏清单 / 长文本原文）—— 用原生 details，简洁可访问。
function Disclosure({ summary, body, tone = 'bot' }) {
  return (
    <details
      className={cn(
        'mt-2 overflow-hidden rounded-btn border',
        tone === 'user'
          ? 'border-white/30 bg-white/15'
          : 'border-line bg-gold/[0.06]',
      )}
    >
      <summary
        className={cn(
          'cursor-pointer select-none px-2.5 py-1.5 text-[11.5px] font-medium',
          tone === 'user' ? 'text-white/90' : 'text-ink-body',
        )}
      >
        {summary}
      </summary>
      <div
        className={cn(
          'scroll-thin max-h-[260px] overflow-y-auto whitespace-pre-wrap border-t px-2.5 py-2 text-xs leading-relaxed',
          tone === 'user'
            ? 'border-white/20 text-white'
            : 'border-line text-ink-heading',
        )}
      >
        {body}
      </div>
    </details>
  );
}

export default function MessageBubble({ msg }) {
  const { role, text, ops, distilled, distilledSummary, error } = msg;
  const isUser = role === 'user';
  const longUser = isUser && text && text.length > 400;

  return (
    <div className={cn('flex animate-fadeUp', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[84%] whitespace-pre-wrap break-words px-3.5 py-2.5 text-[13px] leading-relaxed',
          isUser
            ? 'rounded-card-lg rounded-br-[4px] bg-gold text-white shadow-gold-glow'
            : error
              ? 'rounded-card border border-red-200 bg-red-50 text-red-600'
              : 'glass rounded-card-lg rounded-bl-[4px] text-ink-heading',
        )}
      >
        {error ? (
          <span>❌ {text}</span>
        ) : longUser ? (
          <>
            <div>📄 已发送 {text.length} 字格式要求</div>
            <Disclosure summary="查看原文" body={text} tone="user" />
          </>
        ) : isUser ? (
          <span>{text}</span>
        ) : (
          <Markdown>{text}</Markdown>
        )}

        {distilled && (
          <Disclosure
            summary={distilledSummary || '已提取的排版要求清单（点击展开）'}
            body={distilled}
          />
        )}

        {ops && ops.length > 0 && (
          <pre className="scroll-thin mt-2 max-h-[150px] overflow-y-auto whitespace-pre-wrap rounded-btn border border-line bg-gray-50 px-2.5 py-2 font-mono text-[10.5px] leading-relaxed text-ink-body">
            {JSON.stringify(ops, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
