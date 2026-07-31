import { useParams } from 'react-router-dom';
import { ChatRoom } from './Chat';

export default function ChatConversation() {
  const { conversationId } = useParams();

  return <ChatRoom initialConversationId={conversationId} />;
}
