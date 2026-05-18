import { useEffect, useRef } from 'react';
import { useSession } from '../../../state/SessionContext.jsx';
import MessageBubble from './MessageBubble.jsx';

export default function Chat() {
  const { messages } = useSession();
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [messages]);

  return (
    <div className="scroll-thin flex flex-1 flex-col gap-2.5 overflow-y-auto px-3.5 py-3.5">
      {messages.map((m) => (
        <MessageBubble key={m.id} msg={m} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
