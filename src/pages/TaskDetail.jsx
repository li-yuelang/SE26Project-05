import { useParams } from 'react-router-dom';

export default function TaskDetail() {
  const { taskId } = useParams();

  return (
    <div className="page">
      <h2>任务详情</h2>
      <p>任务 ID: {taskId}</p>
    </div>
  );
}
