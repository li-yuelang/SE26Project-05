import { useParams } from 'react-router-dom';

export default function ConceptDetail() {
  const { conceptId } = useParams();

  return (
    <div className="page">
      <h2>概念详情</h2>
      <p>概念 ID: {conceptId}</p>
    </div>
  );
}
