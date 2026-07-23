import { useState, useRef, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
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
  Popconfirm,
  theme,
  message,
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
  DeleteOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import ReactMarkdown from 'react-markdown';
import { formatConversationDate, getLocalDateString } from '../utils/date';
import {
  createConversation,
  deleteConversation,
  getChatBootstrap,
  streamChatMessage,
} from '../services/chatService';

const { Sider, Content } = Layout;
const { TextArea } = Input;
const { Text, Title } = Typography;

export default function Chat() {
  const { conversationId } = useParams();

  return <ChatRoom initialConversationId={conversationId} />;
}

/** 共享聊天室组件 */
export function ChatRoom({ initialConversationId } = {}) {
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const resource = useAsyncResource(getChatBootstrap, []);

  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(initialConversationId || null);
  const [messages, setMessages] = useState({});
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const messagesContainerRef = useRef(null);
  const messagesEndRef = useRef(null);
  const suggestions = resource.data?.suggestions || [];

  useEffect(() => {
    if (!resource.data) return;
    setConversations(resource.data.conversations);
    setMessages(resource.data.messages);
  }, [resource.data]);

  // URL 是当前对话的持久化来源，前进、后退或回到 /chat 时同步选中状态。
  useEffect(() => {
    setActiveId(initialConversationId || null);
  }, [initialConversationId]);

  // 滚动到底部（直接设置 scrollTop，避免流式响应时 smooth 动画被频繁中断）
  useEffect(() => {
    const el = messagesContainerRef.current;
    if (el) {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    }
  }, [messages, activeId]);

  const activeMessages = activeId && messages[activeId] ? messages[activeId] : [];
  const activeConv = conversations.find((c) => c.id === activeId);

  const selectConversation = (id) => {
    setActiveId(id);
    navigate(`/chat/${id}`, { replace: true });
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await createConversation();
      setConversations((prev) => [newConv, ...prev]);
      setMessages((prev) => ({ ...prev, [newConv.id]: [] }));
      setActiveId(newConv.id);
      navigate(`/chat/${newConv.id}`, { replace: true });
    } catch (error) {
      message.error(error.message || '创建对话失败');
    }
  };

  const handleDeleteConversation = async (id) => {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      setMessages((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      if (activeId === id) {
        setActiveId(null);
        navigate('/chat', { replace: true });
      }
    } catch (error) {
      message.error(error.message || '删除对话失败');
    }
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    const targetId = activeId || (await createAutoConversation());
    const userMsg = {
      id: `user-${Date.now()}`,
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

    const draftId = `assistant-${Date.now()}`;
    setMessages((prev) => ({
      ...prev,
      [targetId]: [
        ...(prev[targetId] || []),
        { id: draftId, role: 'assistant', content: '', sources: [], time: '', streaming: true },
      ],
    }));

    try {
      const reply = await streamChatMessage(targetId, trimmed, {
        onDelta: (delta) => setMessages((prev) => ({
          ...prev,
          [targetId]: (prev[targetId] || []).map((item) => (
            item.id === draftId ? { ...item, content: item.content + delta } : item
          )),
        })),
      });
      setMessages((prev) => ({
        ...prev,
        [targetId]: (prev[targetId] || []).map((item) => (
          item.id === draftId ? { ...reply, id: reply.id || draftId, streaming: false } : item
        )),
      }));
      setConversations((prev) => prev.map((conversation) => (
        conversation.id === targetId
          ? {
              ...conversation,
              title: ['新对话', 'New conversation'].includes(conversation.title)
                ? trimmed.slice(0, 40)
                : conversation.title,
              date: getLocalDateString(),
              preview: reply.content.slice(0, 80),
            }
          : conversation
      )));
    } catch (error) {
      setMessages((prev) => ({
        ...prev,
        [targetId]: (prev[targetId] || []).filter((item) => item.id !== draftId),
      }));
      message.error(error.message || '消息发送失败');
    } finally {
      setSending(false);
    }
  };

  const createAutoConversation = async () => {
    const newConv = await createConversation();
    setConversations((prev) => [newConv, ...prev]);
    setMessages((prev) => ({ ...prev, [newConv.id]: [] }));
    setActiveId(newConv.id);
    navigate(`/chat/${newConv.id}`, { replace: true });
    return newConv.id;
  };

  if (resource.loading || resource.error) {
    return (
      <div className="chat-page">
        <AsyncPageState
          loading={resource.loading}
          error={resource.error}
          onRetry={resource.reload}
        />
      </div>
    );
  }

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
        zeroWidthTriggerStyle={{ display: 'none' }}
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
            className="chat-panel-header"
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
              <Button
                type="text"
                size="small"
                aria-label="关闭侧栏"
                icon={<MenuFoldOutlined />}
                onClick={() => setSidebarCollapsed(true)}
              />
              <Button
                type="primary"
                size="small"
                aria-label="新建对话"
                icon={<PlusOutlined />}
                onClick={handleNewConversation}
              />
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
                    className="chat-conversation-item"
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
                            flex: 1,
                          }}
                        >
                          {conv.title}
                        </Text>
                        <Flex align="center" gap={4} style={{ flexShrink: 0, marginLeft: 8 }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {formatConversationDate(conv.date)}
                          </Text>
                          <Popconfirm
                            title="确定删除该对话？"
                            description="删除后无法恢复"
                            onConfirm={(e) => {
                              e.stopPropagation();
                              handleDeleteConversation(conv.id);
                            }}
                            onCancel={(e) => e.stopPropagation()}
                            okText="删除"
                            cancelText="取消"
                            placement="right"
                          >
                            <Button
                              type="text"
                              size="small"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={(e) => e.stopPropagation()}
                              className="conv-delete-btn"
                            />
                          </Popconfirm>
                        </Flex>
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
      <Content style={{ display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative' }}>
        {/* 侧栏折叠时的展开按钮：始终显示 */}
        {sidebarCollapsed && (
          <Button
            type="text"
            icon={<MenuUnfoldOutlined />}
            onClick={() => setSidebarCollapsed(false)}
            style={{
              position: 'absolute',
              top: 12,
              left: 12,
              zIndex: 10,
            }}
          />
        )}

        {activeConv ? (
          <>
            {/* Chat Header */}
            <Flex
              align="center"
              justify="space-between"
              className="chat-panel-header"
              style={{
                padding: '12px 20px',
                borderBottom: `1px solid ${token.colorBorderSecondary}`,
                flexShrink: 0,
                paddingLeft: sidebarCollapsed ? 52 : 20,
              }}
            >
              <Flex align="center" gap={8}>
                <Title level={5} style={{ margin: 0 }}>
                  {activeConv.title}
                </Title>
              </Flex>
              <Text type="secondary" style={{ fontSize: 13 }}>
                {formatConversationDate(activeConv.date)}
              </Text>
            </Flex>

            {/* Messages Area */}
            <div className="chat-messages" ref={messagesContainerRef} style={{ flex: 1, overflowY: 'auto' }}>
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
                      {suggestions.map((s) => (
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
                  <MessageBubble key={msg.id || i} msg={msg} token={token} navigate={navigate} />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <Flex
              align="flex-end"
              gap={10}
              className="chat-composer-region"
              style={{
                padding: '18px 28px 20px',
                borderTop: `1px solid ${token.colorBorderSecondary}`,
                flexShrink: 0,
                background: token.colorBgContainer,
              }}
            >
              <TextArea
                className="chat-composer-input"
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
function MessageBubble({ msg, token, navigate }) {
  const isUser = msg.role === 'user';

  return (
    <Flex
      gap={10}
      style={{
        maxWidth: '92%',
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
            padding: '16px 22px',
            borderRadius: 12,
            fontSize: 15,
            lineHeight: 1.75,
            wordBreak: 'break-word',
            background: isUser ? token.colorPrimary : token.colorFillContent,
            color: isUser ? '#fff' : token.colorText,
            borderBottomRightRadius: isUser ? 4 : undefined,
            borderBottomLeftRadius: isUser ? undefined : 4,
          }}
        >
          {isUser ? (
            msg.content.split('\n').map((line, j, arr) => (
              <span key={j}>
                {line}
                {j < arr.length - 1 && <br />}
              </span>
            ))
          ) : (
            <ReactMarkdown
              components={{
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: token.colorPrimary }}>
                    {children}
                  </a>
                ),
                code: ({ className, children, ...props }) => {
                  const isInline = !className;
                  if (isInline) return <code style={{ background: token.colorBgElevated, padding: '1px 5px', borderRadius: 4, fontSize: '0.9em' }} {...props}>{children}</code>;
                  return <pre style={{ background: token.colorBgElevated, padding: 12, borderRadius: 8, overflow: 'auto', fontSize: 13 }}><code className={className} {...props}>{children}</code></pre>;
                },
              }}
            >
              {msg.content}
            </ReactMarkdown>
          )}
        </div>

        {msg.sources && msg.sources.length > 0 && (
          <Flex align="center" gap={4} wrap="wrap" style={{ padding: '0 4px' }}>
            <FileTextOutlined style={{ fontSize: 11, color: token.colorTextQuaternary }} />
            {msg.sources.map((s, j) => (
              <Tag
                key={`${s.paperId}-${s.chunkIndex ?? j}`}
                color="processing"
                role="link"
                aria-label={`查看引用：${s.title}${s.chunkIndex == null ? '' : `，片段 ${s.chunkIndex}`}`}
                style={{ cursor: 'pointer', fontSize: 11, margin: 0 }}
                onClick={() => navigate(
                  `/papers/${s.paperId}${s.chunkIndex == null ? '' : `?chunk=${s.chunkIndex}`}`,
                )}
              >
                [{j + 1}] {s.title}
                {s.chunkIndex == null ? '' : ` · 片段 ${s.chunkIndex}`}
              </Tag>
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
