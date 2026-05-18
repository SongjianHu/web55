import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// AI 输出按 Markdown 渲染，样式贴合设计令牌（ink 文字 / 金色强调）。
// 注意：react-markdown v9 会传入 node 属性，需剥离后再展开到 DOM 元素。
const COMPONENTS = {
  p: ({ node, ...p }) => <p className="my-1.5 leading-relaxed" {...p} />,
  ul: ({ node, ...p }) => (
    <ul className="my-1.5 list-disc space-y-1 pl-5" {...p} />
  ),
  ol: ({ node, ...p }) => (
    <ol className="my-1.5 list-decimal space-y-1 pl-5" {...p} />
  ),
  li: ({ node, ...p }) => <li className="leading-relaxed" {...p} />,
  strong: ({ node, ...p }) => (
    <strong className="font-semibold text-ink-heading" {...p} />
  ),
  em: ({ node, ...p }) => <em className="italic" {...p} />,
  a: ({ node, ...p }) => (
    <a
      className="font-medium text-gold underline underline-offset-2 hover:text-gold-deep"
      target="_blank"
      rel="noopener noreferrer"
      {...p}
    />
  ),
  h1: ({ node, ...p }) => (
    <h1 className="mb-1 mt-3 text-[1.08em] font-semibold text-ink-heading" {...p} />
  ),
  h2: ({ node, ...p }) => (
    <h2 className="mb-1 mt-3 text-[1.05em] font-semibold text-ink-heading" {...p} />
  ),
  h3: ({ node, ...p }) => (
    <h3 className="mb-1 mt-2.5 text-[1em] font-semibold text-ink-heading" {...p} />
  ),
  blockquote: ({ node, ...p }) => (
    <blockquote
      className="my-2 border-l-2 border-gold/40 pl-3 text-ink-body"
      {...p}
    />
  ),
  code: ({ node, ...p }) => (
    <code
      className="rounded bg-gold/10 px-1 py-0.5 font-mono text-[0.85em] text-gold-deep"
      {...p}
    />
  ),
  pre: ({ node, ...p }) => (
    <pre
      className="scroll-thin my-2 overflow-x-auto rounded-btn border border-line bg-black/[0.04] p-3 text-xs [&>code]:bg-transparent [&>code]:p-0 [&>code]:text-ink-heading"
      {...p}
    />
  ),
  hr: () => <hr className="my-3 border-line" />,
  table: ({ node, ...p }) => (
    <div className="scroll-thin my-2 overflow-x-auto">
      <table className="w-full border-collapse text-[0.92em]" {...p} />
    </div>
  ),
  th: ({ node, ...p }) => (
    <th
      className="border border-line bg-black/[0.03] px-2 py-1 text-left font-semibold"
      {...p}
    />
  ),
  td: ({ node, ...p }) => <td className="border border-line px-2 py-1" {...p} />,
};

export default function Markdown({ children, className = '' }) {
  return (
    <div
      className={`text-[13px] leading-relaxed [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 ${className}`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children || ''}
      </ReactMarkdown>
    </div>
  );
}
