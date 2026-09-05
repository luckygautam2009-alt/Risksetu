import { useState, useEffect } from 'react';
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
import { AlertCenter } from '../components/alerts/AlertCenter';
import { DemoController } from '../components/demo/DemoController';
import { TopActionBar } from '../components/layout/TopActionBar';
import { WeatherPanel } from '../components/weather/WeatherPanel';
import { SosPanel } from '../components/sos/SosPanel';
import { RegionalWatchBanner } from '../components/weather/RegionalWatchBanner';
import { ReportIncidentModal } from '../components/intelligence/ReportIncidentModal';
import { OfficerWorkspaceModal } from '../components/officer/OfficerWorkspaceModal';
import './Dashboard.css';

export function Dashboard() {
  const {
    selectedHazardId,
    selectedHazard,
    simulationPhase,
    simulationResult,
    workflowTab,
    setWorkflowTab,
    selectAlert,
    startSimulation,
    selectedObservationId,
    selectedAlertId,
    sosState,
    openSosPanel,
    demoOpenWeather,
    demoOpenSos,
    reportModalOpen,
    closeReportModal,
    officerModalOpen,
    closeOfficerModal,
    openReportModal,
    selectedLandslideId,
    selectedSosId,
    selectedLocation,
  } = useMapContext();

  const [weatherOpen, setWeatherOpen] = useState(false);
  const [sosOpen, setSosOpen] = useState(false);

  // Demo triggers
  useEffect(() => {
    if (demoOpenWeather > 0) { setWeatherOpen(true); setSosOpen(false); }
  }, [demoOpenWeather]);

  useEffect(() => {
    if (demoOpenSos > 0) {
      setSosOpen(true);
      setWeatherOpen(false);
      if (sosState.step === 'idle') openSosPanel();
    }
  // openSosPanel and sosState.step intentionally excluded — only react to counter change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoOpenSos]);

  const isFailedSimulation = simulationPhase === 'failed' && Boolean(simulationResult);

  const handleWeatherToggle = () => { setWeatherOpen((v) => !v); setSosOpen(false); };
  const handleSosToggle = () => {
    if (sosOpen) { setSosOpen(false); return; }
    setSosOpen(true);
    setWeatherOpen(false);
    if (sosState.step === 'idle') openSosPanel();
  };

  const renderRightPanel = () => {
    if (sosOpen && sosState.step !== 'idle') return <SosPanel onClose={() => setSosOpen(false)} />;
    if (weatherOpen) return <WeatherPanel onClose={() => setWeatherOpen(false)} />;
    if (selectedObservationId) return <GroundObservationPanel />;
    if (selectedAlertId) return <AlertDetailPanel />;
    if (workflowTab === 'alerts') return <AlertCenter />;
    if (workflowTab === 'priority') return <PriorityRankedList />;
    if (isFailedSimulation || workflowTab === 'impact') return <RoadImpactPanel />;
    // Show location panel when a hazard, landslide, SOS, or arbitrary location is selected
    if (selectedHazardId || selectedHazard || selectedLandslideId || selectedSosId || selectedLocation) return <FloatingLocationPanel />;
    return <MapEmptyState />;
  };

  return (
    <div className="dashboard">
      {/* ── Map Pane (68% desktop) ── */}
      <div className="dashboard__map-pane">
        <RiskMap />
        <RegionalWatchBanner />
        <DemoController />
        <WorkflowNav />
        <TopActionBar
          onWeatherClick={handleWeatherToggle}
          onSosClick={handleSosToggle}
          weatherOpen={weatherOpen}
          sosOpen={sosOpen && sosState.step !== 'idle'}
        />
        <RoadSimulationControl />

        {/* ── Bottom Action Dock ── */}
        <div className="dashboard__action-dock">
          <button
            className={`dashboard__dock-btn ${weatherOpen ? 'dashboard__dock-btn--active' : ''}`}
            onClick={handleWeatherToggle}
            title="Weather Intelligence"
          >
            <span className="dashboard__dock-icon">🌦</span>
            WEATHER
          </button>

          <div className="dashboard__dock-sep" />

          <button
            className={`dashboard__dock-btn ${workflowTab === 'risk' && !weatherOpen && !sosOpen ? 'dashboard__dock-btn--active' : ''}`}
            onClick={() => {
              setWorkflowTab('risk');
              setWeatherOpen(false);
              setSosOpen(false);
            }}
            title="Live Risk Assessment"
          >
            <span className="dashboard__dock-icon">⚡</span>
            LIVE RISK
          </button>

          <div className="dashboard__dock-sep" />

          <button
            className={`dashboard__dock-btn dashboard__dock-btn--sos ${sosOpen ? 'dashboard__dock-btn--active' : ''}`}
            onClick={handleSosToggle}
            title="Emergency SOS"
          >
            <span className="dashboard__dock-icon">🆘</span>
            SOS
          </button>

          <div className="dashboard__dock-sep" />

          <button
            className="dashboard__dock-btn"
            onClick={openReportModal}
            title="Report Ground Incident"
          >
            <span className="dashboard__dock-icon">📋</span>
            REPORT INCIDENT
          </button>

          <div className="dashboard__dock-sep" />

          <button
            className={`dashboard__dock-btn ${workflowTab === 'impact' ? 'dashboard__dock-btn--active' : ''}`}
            onClick={() => {
              setWorkflowTab('impact');
              setWeatherOpen(false);
              setSosOpen(false);
              startSimulation();
            }}
            title="Simulate Road Blockage Failure"
          >
            <span className="dashboard__dock-icon">🛣</span>
            SIMULATE ROAD FAILURE
          </button>

          <div className="dashboard__dock-sep" />

          <button
            className={`dashboard__dock-btn ${workflowTab === 'alerts' ? 'dashboard__dock-btn--active' : ''}`}
            onClick={() => {
              setWorkflowTab('alerts');
              selectAlert(null);
              setWeatherOpen(false);
              setSosOpen(false);
            }}
            title="Operational Alerts Command Center"
          >
            <span className="dashboard__dock-icon">⚠</span>
            ALERTS
          </button>
        </div>
      </div>

      {/* ── Right Intelligence Panel (32% desktop) ── */}
      <div className="dashboard__right-panel">
        {renderRightPanel()}
      </div>

      {/* Citizen Report Modal */}
      {reportModalOpen && <ReportIncidentModal onClose={closeReportModal} />}

      {/* Officer Command Workspace Modal */}
      <OfficerWorkspaceModal isOpen={officerModalOpen} onClose={closeOfficerModal} />
    </div>
  );
}
