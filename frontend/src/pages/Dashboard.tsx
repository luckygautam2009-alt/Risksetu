import { useMapContext } from '../context/MapContext';
import { RiskMap } from '../components/map/RiskMap';
import { FloatingLocationPanel } from '../components/map/FloatingLocationPanel';
import { MapEmptyState } from '../components/map/MapEmptyState';
import { RoadSimulationControl } from '../components/simulation/RoadSimulationControl';
import { RoadImpactPanel } from '../components/simulation/RoadImpactPanel';
import { WorkflowNav } from '../components/workflow/WorkflowNav';
import { PriorityRankedList } from '../components/priority/PriorityRankedList';
import { GroundObservationPanel } from '../components/intelligence/GroundObservationPanel';
import { AlertDetailPanel } from '../components/alerts/AlertDetailPanel';
import { DemoController } from '../components/demo/DemoController';
import './Dashboard.css';

export function Dashboard() {
  const {
    selectedHazardId,
    simulationPhase,
    simulationResult,
    workflowTab,
    selectedObservationId,
    selectedAlertId,
  } = useMapContext();

  const isFailedSimulation = simulationPhase === 'failed' && Boolean(simulationResult);

  // Determine active right intelligence dock panel based on continuous workflow
  const renderRightPanel = () => {
    // 1. If an observation point is explicitly selected, inspect it
    if (selectedObservationId) {
      return <GroundObservationPanel />;
    }

    // 2. If an alert is explicitly selected or user is in Alerts tab, show alert detail
    if (selectedAlertId || workflowTab === 'alerts') {
      return <AlertDetailPanel />;
    }

    // 3. If in Priority tab, show ranked intervention list
    if (workflowTab === 'priority') {
      return <PriorityRankedList />;
    }

    // 4. If simulation has completed, show Road Failure Impact panel
    if (isFailedSimulation || workflowTab === 'impact') {
      return <RoadImpactPanel />;
    }

    // 5. If hazard is selected, show Risk Explainability Story
    if (selectedHazardId) {
      return <FloatingLocationPanel />;
    }

    // 6. Default map empty state prompt
    return <MapEmptyState />;
  };

  return (
    <div className="dashboard">
      {/* Full-Bleed Living Risk Map — 75-80% Visual Importance */}
      <RiskMap />

      {/* Demo Mode Controller — floating trigger + HUD ribbon */}
      <DemoController />

      {/* Top Left: Continuous Intelligence Workflow Navigation (Risk → Impact → Priority → Alerts) */}
      <WorkflowNav />

      {/* Floating Road Failure Simulation Control & Launcher */}
      <RoadSimulationControl />

      {/* Right Intelligence Dock */}
      {renderRightPanel()}
    </div>
  );
}


