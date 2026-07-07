import { useParams } from 'react-router-dom';

export default function PaperDetail() {
  const { paperId } = useParams();

  return (
    <div className="page">
      <h2>论文详情</h2>
      <p>论文 ID: {paperId}</p>
    </div>
  );
}
