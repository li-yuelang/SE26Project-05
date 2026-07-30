import {
  chatConversations,
  chatMessages,
  chatSuggestions,
} from '../data/chatData';
import { cloneMockData, createEndpoint, request } from './apiClient';

let conversationStore = cloneMockData(chatConversations);
let messageStore = cloneMockData(chatMessages);

export const getChatBootstrap = createEndpoint({
  mock: () => ({
    conversations: conversationStore,
    messages: messageStore,
    suggestions: chatSuggestions,
  }),
  http: () => request('/chat'),
});

export const createConversation = createEndpoint({
  mock: () => {
    const conversation = {
      id: String(Date.now()),
      title: '新对话',
      date: new Date().toISOString().split('T')[0],
      preview: '',
    };
    conversationStore = [conversation, ...conversationStore];
    messageStore[conversation.id] = [];
    return conversation;
  },
  http: () => request('/chat/conversations', { method: 'POST' }),
});

export const sendChatMessage = createEndpoint({
  mock: (conversationId, content) => {
    const reply = {
      role: 'assistant',
      content: `功能尚未完善，API 接口正在开发中。您的提问："${content}" 已收到，管理员将尽快上线智能问答服务。`,
      time: new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      sources: [],
    };
    messageStore[conversationId] = [
      ...(messageStore[conversationId] || []),
      { role: 'user', content, time: reply.time },
      reply,
    ];
    return reply;
  },
  http: (conversationId, content) => request(
    `/chat/conversations/${conversationId}/messages`,
    { body: { content }, method: 'POST' },
  ),
});

export const deleteConversation = createEndpoint({
  mock: (conversationId) => {
    conversationStore = conversationStore.filter((item) => item.id !== conversationId);
    delete messageStore[conversationId];
    return { id: conversationId };
  },
  http: (conversationId) => request(`/chat/conversations/${conversationId}`, {
    method: 'DELETE',
  }),
});
