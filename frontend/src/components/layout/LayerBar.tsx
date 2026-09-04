import { useMapContext } from '../../context/MapContext';
import { Button } from '../ui/Button';
import type { LayerId } from '../../types';
import './LayerBar.css';

export function LayerBar() {
  const { layers, toggleLayer } = useMapContext();

  return (
    <nav className="layer-bar" aria-label="Geospatial layer controls">
      <div className="layer-bar__dock">
        <div className="layer-bar__title-group">
          <span className="layer-bar__heading">GIS LAYERS</span>
          <span className="layer-bar__count font-mono">{layers.filter((l) => l.active).length}/{layers.length}</span>
        </div>

        <div className="layer-bar__divider" aria-hidden="true" />

        <div className="layer-bar__controls">
          {layers.map((layer) => (
            <Button
              key={layer.id}
              variant={layer.active ? 'default' : 'subtle'}
              size="sm"
              active={layer.active}
              onClick={() => toggleLayer(layer.id as LayerId)}
              aria-pressed={layer.active}
              className="layer-bar__btn"
            >
              <span
                className={`layer-bar__indicator layer-bar__indicator--${layer.category} ${
                  layer.active ? 'layer-bar__indicator--active' : ''
                }`}
                aria-hidden="true"
              />
              {layer.label}
            </Button>
          ))}
        </div>
      </div>
    </nav>
  );
}

