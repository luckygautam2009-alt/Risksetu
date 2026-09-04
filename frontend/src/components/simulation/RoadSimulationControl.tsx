import { useState } from 'react';
import { useMapContext } from '../../context/MapContext';
import { Button } from '../ui/Button';
import './RoadSimulationControl.css';

export function RoadSimulationControl() {
  const {
    roadsList,
    selectedRoadId,
    selectedRoad,
    simulationPhase,
    selectRoad,
    startSimulation,
    resetSimulation,
  } = useMapContext();

  const [isOpen, setIsOpen] = useState(false);

  // If simulation is idle and control is not opened, show the subtle trigger button
  if (simulationPhase === 'idle' && !isOpen) {
    return (
      <div className="sim-trigger" aria-label="Road Failure Simulation launcher">
        <button
          type="button"
          className="sim-trigger__button"
          onClick={() => {
            setIsOpen(true);
            if (!selectedRoadId) {
              selectRoad('road-nh58');
            }
          }}
          title="Launch Road Failure Simulation & Connectivity Impact"
        >
          <span className="sim-trigger__pulse-dot" aria-hidden="true" />
          <svg
            className="sim-trigger__icon"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
          >
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
          </svg>
          <span className="sim-trigger__label">SIMULATE ROAD FAILURE</span>
        </button>
      </div>
    );
  }

  // Active or configuring simulation control bar
  const activeRoad = selectedRoad ?? roadsList.find((r) => r.id === (selectedRoadId ?? 'road-nh58'));
  const isSimulating = simulationPhase === 'simulating';

  return (
    <aside className="sim-control" aria-label="Road Failure Simulation Controller">
      <div className="sim-control__dock">
        <div className="sim-control__header">
          <div className="sim-control__badge-group">
            <span className="sim-control__tag font-mono">
              <span className="sim-control__tag-dot" aria-hidden="true" />
              SIMULATION MODE
            </span>
            <span className="sim-control__phase font-mono">
              {isSimulating ? 'TOPOLOGY CALCULATION' : simulationPhase.toUpperCase()}
            </span>
          </div>

          <button
            type="button"
            className="sim-control__close"
            onClick={() => {
              setIsOpen(false);
              resetSimulation();
              selectRoad(null);
            }}
            title="Exit simulation mode"
            aria-label="Exit simulation mode"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="sim-control__body">
          <div className="sim-control__corridor-select">
            <label htmlFor="corridor-select" className="sim-control__label">
              CORRIDOR SEGMENT
            </label>
            <div className="sim-control__select-wrapper">
              <select
                id="corridor-select"
                className="sim-control__select font-mono"
                value={activeRoad?.id ?? 'road-nh58'}
                disabled={isSimulating}
                onChange={(e) => selectRoad(e.target.value)}
              >
                {roadsList.map((road) => (
                  <option key={road.id} value={road.id}>
                    {road.name} — Way {road.wayId}
                  </option>
                ))}
              </select>
              <svg
                className="sim-control__select-chevron"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </div>
          </div>

          <div className="sim-control__meta font-mono">
            <span>WAY: {activeRoad?.wayId ?? '33815196'}</span>
            <span>CLASS: {activeRoad?.highwayClass.toUpperCase() ?? 'TRUNK'}</span>
            <span className={`sim-control__status sim-control__status--${activeRoad?.status ?? 'critical'}`}>
              STATUS: {activeRoad?.status.toUpperCase() ?? 'CRITICAL'}
            </span>
          </div>

          <div className="sim-control__actions">
            <Button
              variant="default"
              size="sm"
              disabled={isSimulating}
              onClick={() => startSimulation(activeRoad?.id)}
              className="sim-control__btn-start"
            >
              {isSimulating ? (
                <>
                  <span className="sim-control__spinner" aria-hidden="true" />
                  ANALYZING CONNECTIVITY...
                </>
              ) : (
                <>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                  SIMULATE ROAD FAILURE
                </>
              )}
            </Button>

            {simulationPhase === 'failed' && (
              <Button
                variant="subtle"
                size="sm"
                onClick={resetSimulation}
                className="sim-control__btn-reset"
              >
                RESTORE NETWORK
              </Button>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
