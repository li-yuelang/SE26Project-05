import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

/** 模拟对话列表数据 */
const MOCK_CONVERSATIONS = [
  { id: '1', title: 'Transformer 架构讨论',   date: '2026-07-07', preview: '关于注意力机制的深入探讨…' },
  { id: '2', title: 'BERT 预训练方法对比',    date: '2026-07-06', preview: 'MLM 与 NSP 任务的区别与应用…' },
  { id: '3', title: '大模型微调技术',         date: '2026-07-05', preview: 'LoRA 和 P-Tuning 的效率对比…' },
  { id: '4', title: '图神经网络综述',         date: '2026-07-04', preview: 'GCN、GAT、GraphSAGE 的关系…' },
  { id: '5', title: '扩散模型原理',           date: '2026-07-03', preview: 'DDPM 与 Score-based 统一视角…' },
];

/** 模拟消息数据 */
const MOCK_MESSAGES = {
  1: [
    { role: 'user', content: '什么是 Transformer 中的自注意力机制？', time: '10:30' },
    {
      role: 'assistant',
      content:
        '自注意力机制（Self-Attention）是 Transformer 架构的核心组件。它允许序列中的每个位置关注所有位置，通过 Query、Key、Value 三个矩阵计算注意力权重，从而捕获全局依赖关系。\n\n核心公式：Attention(Q,K,V) = softmax(QK^T/√d_k)V\n\n与 RNN 不同，自注意力完全并行计算，大幅提升了训练效率。',
      time: '10:30',
      sources: [
        { title: 'Attention Is All You Need', paperId: '1706.03762' },
        { title: 'The Annotated Transformer', paperId: '1706.03762' },
      ],
    },
  ],
  2: [
    { role: 'user', content: 'BERT 的 MLM 和 NSP 任务分别是什么？', time: '昨天 14:20' },
    {
      role: 'assistant',
      content:
        'MLM（Masked Language Model）：随机遮盖输入中 15% 的 token，让模型预测被遮盖的词，迫使模型学习双向上下文。\n\nNSP（Next Sentence Prediction）：判断两个句子是否为连续文本，帮助模型理解句子间关系。\n\n后续研究（如 RoBERTa）表明 NSP 并非必要，仅用 MLM 也能取得更好效果。',
      time: '昨天 14:20',
      sources: [
        { title: 'BERT: Pre-training of Deep Bidirectional Transformers', paperId: '1810.04805' },
      ],
    },
  ],
};

/** 模拟 API：发送消息 */
function mockSendMessage(conversationId, content) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        role: 'assistant',
        content: '功能尚未完善，API 接口正在开发中。您的提问："' + content + '" 已收到，管理员将尽快上线智能问答服务。',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        sources: [],
      });
    }, 800);
  });
}

/** 模拟 API：创建新对话 */
function mockCreateConversation() {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        id: String(Date.now()),
        title: '新对话',
        date: new Date().toISOString().split('T')[0],
        preview: '',
      });
    }, 200);
  });
}

export default function Chat() {
  return <ChatRoom />;
}

/** 共享聊天室组件，ChatConversation 也会复用 */
export function ChatRoom({ initialConversationId } = {}) {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState(MOCK_CONVERSATIONS);
  const [activeId, setActiveId] = useState(initialConversationId || null);
  const [messages, setMessages] = useState({});
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  // 初始化消息
  useEffect(() => {
    const initial = {};
    MOCK_CONVERSATIONS.forEach((c) => {
      if (MOCK_MESSAGES[c.id]) {
        initial[c.id] = [...MOCK_MESSAGES[c.id]];
      }
    });
    setMessages(initial);
  }, []);

  // 如果传入了 initialConversationId，自动选中
  useEffect(() => {
    if (initialConversationId) {
      setActiveId(Number(initialConversationId));
    }
  }, [initialConversationId]);

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeId]);

  const activeMessages = activeId && messages[activeId] ? messages[activeId] : [];
  const activeConv = conversations.find((c) => c.id === activeId);

  /** 选择对话 */
  const selectConversation = (id) => {
    setActiveId(id);
    navigate(`/chat/${id}`, { replace: true });
  };

  /** 新建对话 */
  const handleNewConversation = async () => {
    const newConv = await mockCreateConversation();
    setConversations((prev) => [newConv, ...prev]);
    setMessages((prev) => ({ ...prev, [newConv.id]: [] }));
    setActiveId(newConv.id);
    navigate(`/chat/${newConv.id}`, { replace: true });
  };

  /** 发送消息 */
  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    const targetId = activeId || (await createAutoConversation());
    const userMsg = {
      role: 'user',
      content: trimmed,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => ({
      ...prev,
      [targetId]: [...(prev[targetId] || []), userMsg],
    }));
    setInput('');
    setSending(true);

    try {
      const reply = await mockSendMessage(targetId, trimmed);
      setMessages((prev) => ({
        ...prev,
        [targetId]: [...(prev[targetId] || []), reply],
      }));
    } finally {
      setSending(false);
    }
  };

  /** 自动创建对话 */
  const createAutoConversation = async () => {
    const newConv = await mockCreateConversation();
    setConversations((prev) => [newConv, ...prev]);
    setActiveId(newConv.id);
    return newConv.id;
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-page">
      {/* 左侧对话列表 */}
      <aside className="chat-sidebar">
        <div className="chat-sidebar-header">
          <h2>对话列表</h2>
          <button className="btn-new-chat" onClick={handleNewConversation}>
            + 新对话
          </button>
        </div>
        <div className="chat-conv-list">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={`chat-conv-item${activeId === conv.id ? ' active' : ''}`}
              onClick={() => selectConversation(conv.id)}
            >
              <div className="chat-conv-title">{conv.title}</div>
              <div className="chat-conv-preview">{conv.preview || '新对话'}</div>
              <div className="chat-conv-date">{conv.date}</div>
            </div>
          ))}
        </div>
      </aside>

      {/* 右侧聊天区 */}
      <section className="chat-main">
        {activeConv ? (
          <>
            <header className="chat-header">
              <h3>{activeConv.title}</h3>
              <span className="chat-header-date">{activeConv.date}</span>
            </header>

            <div className="chat-messages">
              {activeMessages.length === 0 ? (
                <div className="chat-empty">
                  <div className="chat-empty-icon">💬</div>
                  <p>开始新的对话，向 PaperMate 提问论文相关问题</p>
                  <div className="chat-suggestions">
                    <span>试试问：</span>
                    <button onClick={() => setInput('什么是 Transformer 中的自注意力机制？')}>
                      Transformer 自注意力机制
                    </button>
                    <button onClick={() => setInput('BERT 和 GPT 的主要区别是什么？')}>
                      BERT vs GPT
                    </button>
                    <button onClick={() => setInput('LoRA 微调的原理是什么？')}>
                      LoRA 微调原理
                    </button>
                  </div>
                </div>
              ) : (
                activeMessages.map((msg, i) => (
                  <div key={i} className={`chat-msg ${msg.role}`}>
                    <div className="chat-msg-avatar">
                      {msg.role === 'user' ? '👤' : '🤖'}
                    </div>
                    <div className="chat-msg-body">
                      <div className="chat-msg-content">
                        {msg.content.split('\n').map((line, j) => (
                          <span key={j}>
                            {line}
                            {j < msg.content.split('\n').length - 1 && <br />}
                          </span>
                        ))}
                      </div>
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="chat-msg-sources">
                          <span className="sources-label">参考论文：</span>
                          {msg.sources.map((s, j) => (
                            <span key={j} className="source-tag">
                              {s.title}
                            </span>
                          ))}
                        </div>
                      )}
                      <span className="chat-msg-time">{msg.time}</span>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-area">
              <textarea
                className="chat-input"
                placeholder="输入你的问题，按 Enter 发送，Shift+Enter 换行…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={2}
                disabled={sending}
              />
              <button
                className="btn-send"
                onClick={handleSend}
                disabled={!input.trim() || sending}
              >
                {sending ? '发送中…' : '发送'}
              </button>
            </div>
          </>
        ) : (
          <div className="chat-empty">
            <div className="chat-empty-icon">💬</div>
            <p>选择左侧对话或创建新对话开始提问</p>
            <button className="btn-new-chat" onClick={handleNewConversation}>
              + 新建对话
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
