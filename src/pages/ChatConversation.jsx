import { useParams } from 'react-router-dom';

export default function ChatConversation() {
  const { conversationId } = useParams();

  return (
    <div className="page">
      <h2>历史对话</h2>
      <p>对话 ID: {conversationId}</p>
    </div>
  );
}
