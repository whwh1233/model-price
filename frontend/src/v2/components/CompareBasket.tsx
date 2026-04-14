import { Link } from 'react-router-dom';
import { useCompareBasket } from '../compareBasketContext';
import './CompareBasket.css';

export function CompareBasket() {
  const basket = useCompareBasket();

  if (basket.count === 0) return null;

  const href = `/compare/${basket.slugs.join(',')}`;

  return (
    <div className="v2-basket" role="region" aria-label="Comparison basket">
      <div className="v2-basket-label">
        <span className="v2-basket-count num">{basket.count}</span>
        <span>in compare</span>
      </div>
      <div className="v2-basket-chips">
        {basket.slugs.map((slug) => (
          <button
            key={slug}
            type="button"
            className="v2-basket-chip"
            onClick={() => basket.remove(slug)}
            title={`Remove ${slug}`}
          >
            {slug}
            <span className="v2-basket-chip-x">×</span>
          </button>
        ))}
      </div>
      <div className="v2-basket-actions">
        <button
          type="button"
          className="v2-btn"
          onClick={basket.clear}
        >
          Clear
        </button>
        <Link to={href} className="v2-btn v2-btn-primary">
          Compare →
        </Link>
      </div>
    </div>
  );
}
