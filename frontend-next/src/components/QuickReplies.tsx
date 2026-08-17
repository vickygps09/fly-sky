'use client';

interface QuickRepliesProps {
  replies: string[];
  onReply: (reply: string) => void;
}

export default function QuickReplies({ replies, onReply }: QuickRepliesProps) {
  if (!replies || replies.length === 0) return null;

  return (
    <div className="quick-replies">
      {replies.map((reply, i) => (
        <div key={i} className="quick-reply" onClick={() => onReply(reply)}>
          {reply}
        </div>
      ))}
    </div>
  );
}
