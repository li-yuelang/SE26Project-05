import { Alert, Button, Empty, Spin } from 'antd';

export default function AsyncPageState({ error, loading, onRetry }) {
  if (loading) {
    return (
      <div className="page-state" role="status" aria-label="数据加载中">
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="页面数据加载失败"
        description={error.message || '请稍后重试'}
        action={<Button onClick={onRetry}>重试</Button>}
      />
    );
  }

  return <Empty description="暂无数据" />;
}
