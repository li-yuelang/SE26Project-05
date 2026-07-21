import {
  chatConversations,
  chatMessages,
  chatSuggestions,
} from '../data/chatData';
import {
  apiMode,
  buildWebSocketUrl,
  cloneMockData,
  createEndpoint,
  getAccessToken,
  getMockUserScope,
  request,
} from './apiClient';

const chatStores = new Map();

function getChatStore() {
  const scope = getMockUserScope();
  if (!chatStores.has(scope)) {
    chatStores.set(scope, {
      conversationStore: cloneMockData(chatConversations),
      messageStore: cloneMockData(chatMessages),
    });
  }
  return chatStores.get(scope);
}

export const getChatBootstrap = createEndpoint({
  mock: () => ({
    conversations: getChatStore().conversationStore,
    messages: getChatStore().messageStore,
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
    const store = getChatStore();
    store.conversationStore = [conversation, ...store.conversationStore];
    store.messageStore[conversation.id] = [];
    return conversation;
  },
  http: () => request('/chat/conversations', { method: 'POST' }),
});

export const sendChatMessage = createEndpoint({
  mock: (conversationId, content) => {
    const reply = {
      role: 'assistant',
      content: `已针对“${content}”执行检索与证据重排。当前示例知识库表明，可靠的论文问答需要先选择段落级证据，再进行引用约束生成，从而让回答能够回查到具体来源，并减少无依据扩展。[1]\n\n证据边界：Mock 模式仅展示完整交互链路；切换真实后端后，回答会由实际入库论文片段生成。`,
      time: new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      sources: [
        {
          title: 'Long-Context Scientific Question Answering with Citation Grounding',
          paperId: '2405.11890',
          arxivId: '2405.11890',
          chunkIndex: 2,
          excerpt: '通过段落级引用约束降低长上下文论文问答中的幻觉回答。',
        },
      ],
    };
    const store = getChatStore();
    store.messageStore[conversationId] = [
      ...(store.messageStore[conversationId] || []),
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

export async function streamChatMessage(conversationId, content, { onDelta } = {}) {
  if (apiMode === 'mock') {
    const reply = await sendChatMessage(conversationId, content);
    for (let index = 0; index < reply.content.length; index += 18) {
      const delta = reply.content.slice(index, index + 18);
      onDelta?.(delta);
      await new Promise((resolve) => window.setTimeout(resolve, 18));
    }
    return reply;
  }

  const token = getAccessToken();
  if (!token) {
    const reply = await sendChatMessage(conversationId, content);
    onDelta?.(reply.content);
    return reply;
  }

  return new Promise((resolve, reject) => {
    const url = buildWebSocketUrl(`/chat/conversations/${conversationId}/stream`);
    url.searchParams.set('token', token);
    const socket = new WebSocket(url);
    let settled = false;

    socket.addEventListener('open', () => socket.send(JSON.stringify({ content })));
    socket.addEventListener('message', (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'delta') onDelta?.(payload.content);
      if (payload.type === 'done') {
        settled = true;
        resolve(payload.message);
      }
      if (payload.type === 'error') {
        settled = true;
        reject(new Error(payload.message || '生成回答失败'));
      }
    });
    socket.addEventListener('error', () => {
      if (!settled) reject(new Error('流式连接失败'));
    });
    socket.addEventListener('close', () => {
      if (!settled) reject(new Error('流式连接已中断'));
    });
  });
}

export const deleteConversation = createEndpoint({
  mock: (conversationId) => {
    const store = getChatStore();
    store.conversationStore = store.conversationStore.filter((item) => item.id !== conversationId);
    delete store.messageStore[conversationId];
    return { id: conversationId };
  },
  http: (conversationId) => request(`/chat/conversations/${conversationId}`, {
    method: 'DELETE',
  }),
});
