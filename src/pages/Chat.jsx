import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Layout,
  Button,
  Input,
  Avatar,
  Tag,
  Typography,
  List,
  Empty,
  Flex,
  Space,
  Tooltip,
  theme,
} from 'antd';
import {
  PlusOutlined,
  SendOutlined,
  UserOutlined,
  RobotOutlined,
  FileTextOutlined,
  MessageOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';

const { Sider, Content } = Layout;
const { TextArea } = Input;
const { Text, Title } = Typography;

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

const SUGGESTIONS = [
  '什么是 Transformer 中的自注意力机制？',
  'BERT 和 GPT 的主要区别是什么？',
  'LoRA 微调的原理是什么？',
];

/** 模拟 API：发送消息 */
function mockSendMessage(_conversationId, content) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        role: 'assistant',
        content:
          '功能尚未完善，API 接口正在开发中。您的提问："' +
          content +
          '" 已收到，管理员将尽快上线智能问答服务。',
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

/** 共享聊天室组件 */
export function ChatRoom({ initialConversationId } = {}) {
  const navigate = useNavigate();
  const { token } = theme.useToken();

  const [conversations, setConversations] = useState(MOCK_CONVERSATIONS);
  const [activeId, setActiveId] = useState(initialConversationId ? Number(initialConversationId) : null);
  const [messages, setMessages] = useState({});
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
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

  // 自动选中指定对话
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

  const selectConversation = (id) => {
    setActiveId(id);
    navigate(`/chat/${id}`, { replace: true });
  };

  const handleNewConversation = async () => {
    const newConv = await mockCreateConversation();
    setConversations((prev) => [newConv, ...prev]);
    setMessages((prev) => ({ ...prev, [newConv.id]: [] }));
    setActiveId(newConv.id);
    navigate(`/chat/${newConv.id}`, { replace: true });
  };

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

  const createAutoConversation = async () => {
    const newConv = await mockCreateConversation();
    setConversations((prev) => [newConv, ...prev]);
    setActiveId(newConv.id);
    return newConv.id;
  };

  return (
    <Layout className="chat-page" hasSider>
      {/* 左侧对话列表 */}
      <Sider
        width={300}
        collapsible
        collapsed={sidebarCollapsed}
        collapsedWidth={0}
        onCollapse={setSidebarCollapsed}
        trigger={null}
        style={{
          background: token.colorBgContainer,
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          overflow: 'hidden',
        }}
      >
        <Flex
          vertical
          style={{ height: '100%' }}
        >
          {/* Sider Header */}
          <Flex
            align="center"
            justify="space-between"
            style={{
              padding: '12px 16px',
              borderBottom: `1px solid ${token.colorBorderSecondary}`,
              flexShrink: 0,
            }}
          >
            <Title level={5} style={{ margin: 0 }}>
              <MessageOutlined style={{ marginRight: 8 }} />
              对话列表
            </Title>
            <Space size={4}>
              <Tooltip title="关闭侧栏">
                <Button
                  type="text"
                  size="small"
                  icon={<MenuFoldOutlined />}
                  onClick={() => setSidebarCollapsed(true)}
                />
              </Tooltip>
              <Tooltip title="新建对话">
                <Button
                  type="primary"
                  size="small"
                  icon={<PlusOutlined />}
                  onClick={handleNewConversation}
                />
              </Tooltip>
            </Space>
          </Flex>

          {/* Conversation List */}
          <div style={{ flex: 1, overflow: 'auto' }}>
            <List
              dataSource={conversations}
              split={false}
              renderItem={(conv) => {
                const isActive = activeId === conv.id;
                return (
                  <List.Item
                    key={conv.id}
                    onClick={() => selectConversation(conv.id)}
                    style={{
                      cursor: 'pointer',
                      padding: '10px 16px',
                      background: isActive ? token.colorPrimaryBg : 'transparent',
                      borderInlineEnd: isActive ? `3px solid ${token.colorPrimary}` : '3px solid transparent',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) e.currentTarget.style.background = token.colorBgTextHover;
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <Flex vertical style={{ width: '100%', overflow: 'hidden' }} gap={2}>
                      <Flex align="center" justify="space-between">
                        <Text
                          strong={isActive}
                          style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            fontSize: 14,
                          }}
                        >
                          {conv.title}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 11, flexShrink: 0, marginLeft: 8 }}>
                          {conv.date}
                        </Text>
                      </Flex>
                      <Text
                        type="secondary"
                        style={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          fontSize: 12,
                        }}
                      >
                        {conv.preview || '新对话'}
                      </Text>
                    </Flex>
                  </List.Item>
                );
              }}
            />
          </div>
        </Flex>
      </Sider>

      {/* 右侧聊天区 */}
      <Content style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {activeConv ? (
          <>
            {/* Chat Header */}
            <Flex
              align="center"
              justify="space-between"
              style={{
                padding: '12px 20px',
                borderBottom: `1px solid ${token.colorBorderSecondary}`,
                flexShrink: 0,
              }}
            >
              <Flex align="center" gap={8}>
                {sidebarCollapsed && (
                  <Button
                    type="text"
                    icon={<MenuUnfoldOutlined />}
                    onClick={() => setSidebarCollapsed(false)}
                  />
                )}
                <Title level={5} style={{ margin: 0 }}>
                  {activeConv.title}
                </Title>
              </Flex>
              <Text type="secondary" style={{ fontSize: 13 }}>
                {activeConv.date}
              </Text>
            </Flex>

            {/* Messages Area */}
            <div className="chat-messages" style={{ flex: 1 }}>
              {activeMessages.length === 0 ? (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                  <Flex vertical align="center" gap={16}>
                    <Empty
                      image={<MessageOutlined style={{ fontSize: 48, color: token.colorTextQuaternary }} />}
                      description="开始新的对话，向 PaperMate 提问论文相关问题"
                    />
                    <Flex align="center" gap={8} wrap="wrap" justify="center">
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        试试问：
                      </Text>
                      {SUGGESTIONS.map((s) => (
                        <Tag
                          key={s}
                          color="blue"
                          style={{ cursor: 'pointer', padding: '2px 10px' }}
                          onClick={() => setInput(s)}
                        >
                          {s.length > 16 ? s.slice(0, 16) + '…' : s}
                        </Tag>
                      ))}
                    </Flex>
                  </Flex>
                </div>
              ) : (
                activeMessages.map((msg, i) => (
                  <MessageBubble key={i} msg={msg} token={token} />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <Flex
              align="flex-end"
              gap={10}
              style={{
                padding: '14px 20px',
                borderTop: `1px solid ${token.colorBorderSecondary}`,
                flexShrink: 0,
                background: token.colorBgContainer,
              }}
            >
              <TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="输入你的问题，Enter 发送，Shift+Enter 换行…"
                autoSize={{ minRows: 1, maxRows: 5 }}
                disabled={sending}
                style={{ flex: 1 }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                disabled={!input.trim() || sending}
                loading={sending}
              >
                发送
              </Button>
            </Flex>
          </>
        ) : (
          <Flex
            vertical
            align="center"
            justify="center"
            style={{ height: '100%' }}
            gap={16}
          >
            {sidebarCollapsed && (
              <Button
                type="text"
                icon={<MenuUnfoldOutlined />}
                onClick={() => setSidebarCollapsed(false)}
                style={{ position: 'absolute', top: 12, left: 12 }}
              />
            )}
            <Empty
              image={<MessageOutlined style={{ fontSize: 48, color: token.colorTextQuaternary }} />}
              description="选择左侧对话或创建新对话开始提问"
            >
              <Button type="primary" icon={<PlusOutlined />} onClick={handleNewConversation}>
                新建对话
              </Button>
            </Empty>
          </Flex>
        )}
      </Content>
    </Layout>
  );
}

// ---------- 工具组件 ----------

/** 消息气泡 */
function MessageBubble({ msg, token }) {
  const isUser = msg.role === 'user';

  return (
    <Flex
      gap={10}
      style={{
        maxWidth: '80%',
        alignSelf: isUser ? 'flex-end' : 'flex-start',
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
    >
      <Avatar
        size={34}
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
        style={{
          background: isUser ? token.colorPrimary : token.colorFillContent,
          color: isUser ? '#fff' : token.colorTextSecondary,
          flexShrink: 0,
        }}
      />
      <Flex vertical gap={4} style={{ alignItems: isUser ? 'flex-end' : 'flex-start' }}>
        <div
          className={`chat-msg-content-bubble ${isUser ? 'user' : 'assistant'}`}
          style={{
            padding: '10px 14px',
            borderRadius: 12,
            fontSize: 14,
            lineHeight: 1.65,
            wordBreak: 'break-word',
            background: isUser ? token.colorPrimary : token.colorFillContent,
            color: isUser ? '#fff' : token.colorText,
            borderBottomRightRadius: isUser ? 4 : undefined,
            borderBottomLeftRadius: isUser ? undefined : 4,
          }}
        >
          {msg.content.split('\n').map((line, j, arr) => (
            <span key={j}>
              {line}
              {j < arr.length - 1 && <br />}
            </span>
          ))}
        </div>

        {msg.sources && msg.sources.length > 0 && (
          <Flex align="center" gap={4} wrap="wrap" style={{ padding: '0 4px' }}>
            <FileTextOutlined style={{ fontSize: 11, color: token.colorTextQuaternary }} />
            {msg.sources.map((s, j) => (
              <Tooltip key={j} title={`arXiv: ${s.paperId}`}>
                <Tag
                  color="processing"
                  style={{ cursor: 'pointer', fontSize: 11, margin: 0 }}
                >
                  {s.title}
                </Tag>
              </Tooltip>
            ))}
          </Flex>
        )}

        <Text type="secondary" style={{ fontSize: 11, padding: '0 4px' }}>
          {msg.time}
        </Text>
      </Flex>
    </Flex>
  );
}
