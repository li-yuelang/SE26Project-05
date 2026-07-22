import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Avatar,
  Button,
  Flex,
  Input,
  Layout,
  message,
  Popconfirm,
  Tag,
  theme,
  Tooltip,
  Typography,
} from 'antd';
import {
  DatabaseOutlined,
  DeleteOutlined,
  FileTextOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MessageOutlined,
  PlusOutlined,
  RobotOutlined,
  SearchOutlined,
  SendOutlined,
  UserOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import {
  createConversation,
  deleteConversation,
  getChatBootstrap,
  streamChatMessage,
} from '../services/chatService';

const { Content, Sider } = Layout;
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
  const [conversationQuery, setConversationQuery] = useState('');
  const [sending, setSending] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => window.matchMedia('(max-width: 900px)').matches,
  );
  const composerRef = useRef(null);
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeId]);

  const activeMessages = activeId && messages[activeId] ? messages[activeId] : [];
  const activeConv = conversations.find((conversation) => conversation.id === activeId);

  const conversationGroups = useMemo(() => {
    const query = conversationQuery.trim().toLocaleLowerCase('zh-CN');
    const filtered = query
      ? conversations.filter((conversation) => (
        `${conversation.title} ${conversation.preview || ''}`
          .toLocaleLowerCase('zh-CN')
          .includes(query)
      ))
      : conversations;

    return [
      { label: '最近', items: filtered.slice(0, 3) },
      { label: '更早', items: filtered.slice(3) },
    ].filter((group) => group.items.length > 0);
  }, [conversationQuery, conversations]);

  const selectConversation = (id) => {
    setActiveId(id);
    navigate(`/chat/${id}`, { replace: true });
  };

  const handleNewConversation = async () => {
    try {
      const newConversation = await createConversation();
      setConversations((previous) => [newConversation, ...previous]);
      setMessages((previous) => ({ ...previous, [newConversation.id]: [] }));
      setActiveId(newConversation.id);
      navigate(`/chat/${newConversation.id}`, { replace: true });
      window.requestAnimationFrame(() => composerRef.current?.focus());
    } catch (error) {
      message.error(error.message || '创建对话失败');
    }
  };

  const handleDeleteConversation = async (id) => {
    try {
      await deleteConversation(id);
      setConversations((previous) => previous.filter((conversation) => conversation.id !== id));
      setMessages((previous) => {
        const next = { ...previous };
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

  const createAutoConversation = async () => {
    const newConversation = await createConversation();
    setConversations((previous) => [newConversation, ...previous]);
    setMessages((previous) => ({ ...previous, [newConversation.id]: [] }));
    setActiveId(newConversation.id);
    navigate(`/chat/${newConversation.id}`, { replace: true });
    return newConversation.id;
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    let targetId = activeId;
    if (!targetId) {
      try {
        targetId = await createAutoConversation();
      } catch (error) {
        message.error(error.message || '创建对话失败');
        return;
      }
    }

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((previous) => ({
      ...previous,
      [targetId]: [...(previous[targetId] || []), userMessage],
    }));
    setInput('');
    setSending(true);

    const draftId = `assistant-${Date.now()}`;
    setMessages((previous) => ({
      ...previous,
      [targetId]: [
        ...(previous[targetId] || []),
        { id: draftId, role: 'assistant', content: '', sources: [], time: '', streaming: true },
      ],
    }));

    try {
      const reply = await streamChatMessage(targetId, trimmed, {
        onDelta: (delta) => setMessages((previous) => ({
          ...previous,
          [targetId]: (previous[targetId] || []).map((item) => (
            item.id === draftId ? { ...item, content: item.content + delta } : item
          )),
        })),
      });
      setMessages((previous) => ({
        ...previous,
        [targetId]: (previous[targetId] || []).map((item) => (
          item.id === draftId ? { ...reply, id: reply.id || draftId, streaming: false } : item
        )),
      }));
      setConversations((previous) => previous.map((conversation) => (
        conversation.id === targetId
          ? {
              ...conversation,
              title: ['新对话', 'New conversation'].includes(conversation.title)
                ? trimmed.slice(0, 40)
                : conversation.title,
              preview: reply.content.slice(0, 80),
            }
          : conversation
      )));
    } catch (error) {
      setMessages((previous) => ({
        ...previous,
        [targetId]: (previous[targetId] || []).filter((item) => item.id !== draftId),
      }));
      message.error(error.message || '消息发送失败');
    } finally {
      setSending(false);
    }
  };

  const chooseSuggestion = (suggestion) => {
    setInput(suggestion);
    window.requestAnimationFrame(() => composerRef.current?.focus());
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
      <Sider
        width={286}
        collapsible
        collapsed={sidebarCollapsed}
        collapsedWidth={0}
        onCollapse={setSidebarCollapsed}
        trigger={null}
        zeroWidthTriggerStyle={{ display: 'none' }}
        className="chat-conversation-sider"
      >
        <Flex vertical className="chat-conversation-panel">
          <div className="chat-conversation-header">
            <Flex align="center" justify="space-between">
              <div>
                <Text className="chat-conversation-eyebrow">PaperMate AI</Text>
                <Title level={5} className="chat-conversation-title">对话</Title>
              </div>
              <Flex gap={4}>
                <Tooltip title="收起对话列表">
                  <Button
                    type="text"
                    size="small"
                    icon={<MenuFoldOutlined />}
                    onClick={() => setSidebarCollapsed(true)}
                    aria-label="收起对话列表"
                  />
                </Tooltip>
                <Tooltip title="新建对话">
                  <Button
                    type="primary"
                    size="small"
                    icon={<PlusOutlined />}
                    onClick={handleNewConversation}
                    aria-label="新建对话"
                  />
                </Tooltip>
              </Flex>
            </Flex>
            <Input
              allowClear
              value={conversationQuery}
              onChange={(event) => setConversationQuery(event.target.value)}
              prefix={<SearchOutlined />}
              placeholder="搜索对话"
              className="chat-conversation-search"
            />
          </div>

          <div className="chat-conversation-list">
            {conversationGroups.length === 0 ? (
              <div className="chat-conversation-empty">
                <SearchOutlined />
                <Text type="secondary">没有匹配的对话</Text>
              </div>
            ) : conversationGroups.map((group) => (
              <section className="chat-conversation-group" key={group.label}>
                <Text className="chat-conversation-group-label">{group.label}</Text>
                {group.items.map((conversation) => (
                  <ConversationItem
                    key={conversation.id}
                    conversation={conversation}
                    active={activeId === conversation.id}
                    onSelect={selectConversation}
                    onDelete={handleDeleteConversation}
                  />
                ))}
              </section>
            ))}
          </div>
        </Flex>
      </Sider>

      <Content className="chat-workspace">
        {sidebarCollapsed && (
          <Tooltip title="展开对话列表">
            <Button
              type="text"
              icon={<MenuUnfoldOutlined />}
              onClick={() => setSidebarCollapsed(false)}
              className="chat-sider-open-button"
              aria-label="展开对话列表"
            />
          </Tooltip>
        )}

        <header className={`chat-thread-header${sidebarCollapsed ? ' sider-collapsed' : ''}`}>
          <div className="chat-thread-heading">
            <Title level={5}>{activeConv?.title || '新对话'}</Title>
            <Text type="secondary">
              {activeConv?.date || '基于你的论文知识库进行检索与回答'}
            </Text>
          </div>
          <Tag icon={<DatabaseOutlined />} className="chat-scope-tag">全部论文</Tag>
        </header>

        <div className="chat-thread-scroll">
          <div className={`chat-messages${activeMessages.length === 0 ? ' is-empty' : ''}`}>
            {activeMessages.length === 0 ? (
              <div className="chat-welcome">
                <div className="chat-welcome-icon"><MessageOutlined /></div>
                <Text className="chat-welcome-eyebrow">RESEARCH ASSISTANT</Text>
                <Title level={2}>今天想研究什么？</Title>
                <Text type="secondary" className="chat-welcome-copy">
                  直接提问即可开始新对话。PaperMate 会检索你的论文库，并在回答中标注来源。
                </Text>
                <div className="chat-suggestion-grid">
                  {suggestions.map((suggestion) => (
                    <button
                      type="button"
                      key={suggestion}
                      className="chat-suggestion-card"
                      onClick={() => chooseSuggestion(suggestion)}
                    >
                      <MessageOutlined />
                      <span>{suggestion}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              activeMessages.map((chatMessage, index) => (
                <MessageBubble
                  key={chatMessage.id || index}
                  msg={chatMessage}
                  token={token}
                  navigate={navigate}
                />
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="chat-composer-region">
          <div className="chat-composer-shell">
            <TextArea
              ref={composerRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onPressEnter={(event) => {
                if (!event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
              placeholder="询问论文、概念或研究方向…"
              autoSize={{ minRows: 1, maxRows: 6 }}
              disabled={sending}
              variant="borderless"
              className="chat-composer-input"
            />
            <div className="chat-composer-toolbar">
              <div className="chat-composer-scope">
                <DatabaseOutlined />
                <span>全部论文</span>
              </div>
              <Tooltip title="Enter 发送，Shift + Enter 换行">
                <Button
                  type="primary"
                  shape="circle"
                  icon={<SendOutlined />}
                  onClick={handleSend}
                  disabled={!input.trim() || sending}
                  loading={sending}
                  aria-label="发送消息"
                />
              </Tooltip>
            </div>
          </div>
          <Text type="secondary" className="chat-composer-hint">
            AI 生成内容可能不准确，请结合引用原文核对。
          </Text>
        </div>
      </Content>
    </Layout>
  );
}

function ConversationItem({ active, conversation, onDelete, onSelect }) {
  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect(conversation.id);
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-current={active ? 'page' : undefined}
      className={`chat-conversation-item${active ? ' active' : ''}`}
      onClick={() => onSelect(conversation.id)}
      onKeyDown={handleKeyDown}
    >
      <div className="chat-conversation-item-heading">
        <Text strong={active}>{conversation.title}</Text>
        <Text type="secondary" className="chat-conversation-date">
          {formatConversationDate(conversation.date)}
        </Text>
      </div>
      <div className="chat-conversation-item-footer">
        <Text type="secondary" className="chat-conversation-preview">
          {conversation.preview || '还没有消息'}
        </Text>
        <Popconfirm
          title="确定删除该对话？"
          description="删除后无法恢复"
          onConfirm={(event) => {
            event?.stopPropagation();
            onDelete(conversation.id);
          }}
          onCancel={(event) => event?.stopPropagation()}
          okText="删除"
          cancelText="取消"
          placement="right"
        >
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            aria-label={`删除对话：${conversation.title}`}
            onClick={(event) => event.stopPropagation()}
            className="conv-delete-btn"
          />
        </Popconfirm>
      </div>
    </div>
  );
}

function formatConversationDate(date) {
  if (!date) return '';
  const parsed = new Date(`${date}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return date;
  return `${parsed.getMonth() + 1}月${parsed.getDate()}日`;
}

/** 消息气泡 */
function MessageBubble({ msg, token, navigate }) {
  const isUser = msg.role === 'user';

  return (
    <Flex
      gap={10}
      className={`chat-message${isUser ? ' user' : ' assistant'}`}
      style={{ flexDirection: isUser ? 'row-reverse' : 'row' }}
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
            background: isUser ? token.colorPrimary : token.colorFillContent,
            color: isUser ? '#fff' : token.colorText,
            borderBottomRightRadius: isUser ? 4 : undefined,
            borderBottomLeftRadius: isUser ? undefined : 4,
          }}
        >
          {msg.content.split('\n').map((line, index, lines) => (
            <span key={`${index}-${line.slice(0, 12)}`}>
              {line}
              {index < lines.length - 1 && <br />}
            </span>
          ))}
        </div>

        {msg.sources && msg.sources.length > 0 && (
          <Flex align="center" gap={4} wrap="wrap" className="chat-message-sources">
            <FileTextOutlined style={{ fontSize: 11, color: token.colorTextQuaternary }} />
            {msg.sources.map((source, index) => (
              <Tooltip
                key={`${source.paperId}-${source.chunkIndex ?? index}`}
                title={source.excerpt || `arXiv: ${source.arxivId || source.paperId}`}
              >
                <Tag
                  color="processing"
                  className="chat-source-tag"
                  onClick={() => navigate(
                    `/papers/${source.paperId}${
                      source.chunkIndex == null ? '' : `?chunk=${source.chunkIndex}`
                    }`,
                  )}
                >
                  [{index + 1}] {source.title}
                  {source.chunkIndex == null ? '' : ` · 片段 ${source.chunkIndex}`}
                </Tag>
              </Tooltip>
            ))}
          </Flex>
        )}

        <Text type="secondary" className="chat-message-time">{msg.time}</Text>
      </Flex>
    </Flex>
  );
}
