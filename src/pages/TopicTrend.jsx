import { useParams } from 'react-router-dom';

export default function TopicTrend() {
  const { topicId } = useParams();

  return (
    <div className="page">
      <h2>研究主题发展脉络</h2>
      <p>主题 ID: {topicId}</p>
    </div>
  );
}
