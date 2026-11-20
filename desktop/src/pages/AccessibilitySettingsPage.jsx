import React from 'react';
import { Sliders, MousePointer, Clock, Eye, ShieldCheck, RotateCcw, Save, Zap, Compass } from 'lucide-react';
import { useMotionEase } from '../context/MotionEaseContext';
import SettingsCard from '../components/SettingsCard';
import SliderControl from '../components/SliderControl';
import ToggleSwitch from '../components/ToggleSwitch';
import StatusBadge from '../components/StatusBadge';
import PageHeader from '../components/PageHeader';

export const AccessibilitySettingsPage = () => {
  const { settings, updateSettings, resetCalibration, addToast } = useMotionEase();

  const handleResetDefaults = () => {
    updateSettings({
      invert_x: true,
      invert_y: false,
      cursor_speed: 1.0,
      deadband_px: 8,
      cursor_rate_hz: 60,
      min_cutoff: 0.25,
      beta: 0.012,
      min_dwell_ms: 600,
      max_dwell_ms: 1500,
      dwell_radius_px: 35
    });
    addToast('Settings reset to optimized defaults', 'info');
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <PageHeader
        title="Accessibility & Filter Calibration"
        subtitle="Fine-tune cursor direction, tracking frequency, jitter damping, and dwell thresholds."
        badge={<StatusBadge status="active" text="Settings Synchronized" />}
        actionButton={
          <div className="flex items-center gap-2">
            <button
              onClick={handleResetDefaults}
              className="btn-secondary h-9 px-3 text-xs flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset Defaults</span>
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Pointer Movement & Direction Tuning */}
        <SettingsCard
          title="Pointer Movement & Direction"
          description="Adjust axis orientation and cursor speed response to match user posture."
          icon={Compass}
        >
          <div className="flex items-center justify-between pt-1">
            <div>
              <div className="text-sm font-medium text-txt-primary">Invert Horizontal Axis (X)</div>
              <p className="text-[11px] text-txt-muted">
                {settings.invert_x
                  ? 'Active: Looking Right moves cursor Right (Mirrored Mode)'
                  : 'Disabled: Raw camera orientation'}
              </p>
            </div>
            <ToggleSwitch
              checked={settings.invert_x}
              onChange={(val) => updateSettings({ invert_x: val })}
            />
          </div>

          <div className="flex items-center justify-between pt-1">
            <div>
              <div className="text-sm font-medium text-txt-primary">Invert Vertical Axis (Y)</div>
              <p className="text-[11px] text-txt-muted">Looking Down moves cursor Down.</p>
            </div>
            <ToggleSwitch
              checked={settings.invert_y}
              onChange={(val) => updateSettings({ invert_y: val })}
            />
          </div>

          <SliderControl
            label="Cursor Speed / Sensitivity"
            value={settings.cursor_speed}
            min={0.4}
            max={2.5}
            step={0.1}
            unit="x"
            onChange={(val) => updateSettings({ cursor_speed: val })}
            helperText="0.6x is slow precision mode, 1.0x is balanced, 1.8x allows reaching screen edges with less head movement."
          />

          <div className="pt-2">
            <label className="text-xs font-semibold text-txt-muted block mb-2">
              Cursor Update Frequency (Rate)
            </label>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => updateSettings({ cursor_rate_hz: 30 })}
                className={`p-2.5 rounded-xl border text-center font-medium transition-all ${
                  settings.cursor_rate_hz === 30
                    ? 'border-accent-primary bg-accent-primary/20 text-cyan-300 shadow-sm'
                    : 'border-border-color bg-surface-secondary text-txt-muted hover:border-border-color/80'
                }`}
              >
                <div className="font-bold">30 Hz</div>
                <div className="text-[10px] opacity-75">Standard (Low CPU)</div>
              </button>

              <button
                type="button"
                onClick={() => updateSettings({ cursor_rate_hz: 60 })}
                className={`p-2.5 rounded-xl border text-center font-medium transition-all ${
                  settings.cursor_rate_hz === 60
                    ? 'border-emerald-400 bg-emerald-500/20 text-emerald-300 shadow-sm'
                    : 'border-border-color bg-surface-secondary text-txt-muted hover:border-border-color/80'
                }`}
              >
                <div className="font-bold flex items-center justify-center gap-1">
                  <Zap className="w-3.5 h-3.5 text-emerald-400" />
                  <span>60 Hz</span>
                </div>
                <div className="text-[10px] opacity-75">Ultra-Smooth (60 FPS)</div>
              </button>
            </div>
          </div>
        </SettingsCard>

        {/* Jitter Elimination & Signal Filtering */}
        <SettingsCard
          title="Jitter Elimination & Filtering"
          description="Eradicates high-frequency micro-tremors during fixation while eliminating lag during fast saccades."
          icon={Sliders}
        >
          <SliderControl
            label="Fixation Deadband (Jitter Killer)"
            value={settings.deadband_px}
            min={2}
            max={20}
            step={1}
            unit="px"
            onChange={(val) => updateSettings({ deadband_px: val })}
            helperText="Higher values freeze the cursor rock-solid during eye fixation. Default: 8px."
          />

          <SliderControl
            label="Minimum Cutoff Frequency (Min Cutoff)"
            value={settings.min_cutoff}
            min={0.1}
            max={1.5}
            step={0.05}
            unit="Hz"
            onChange={(val) => updateSettings({ min_cutoff: val })}
            helperText="Lower values filter out tremor jitter when stationary. Default: 0.25 Hz."
          />

          <SliderControl
            label="Speed Coefficient (Beta)"
            value={settings.beta}
            min={0.002}
            max={0.1}
            step={0.002}
            unit="coeff"
            onChange={(val) => updateSettings({ beta: val })}
            helperText="Higher values reduce pointer lag when your gaze shifts rapidly. Default: 0.012."
          />
        </SettingsCard>

        {/* Dynamic Dwell Scaling */}
        <SettingsCard
          title="Context-Aware Dynamic Dwell Scaling"
          description="Fixation dwell timer with automatic velocity scaling to prevent the Midas Touch."
          icon={Clock}
        >
          <SliderControl
            label="Minimum Dwell Hold Duration"
            value={settings.min_dwell_ms}
            min={300}
            max={1200}
            step={50}
            unit="ms"
            onChange={(val) => updateSettings({ min_dwell_ms: val })}
            helperText="Base dwell duration on stationary targets. Default: 600ms."
          />

          <SliderControl
            label="Dwell Target Radius Tolerance"
            value={settings.dwell_radius_px}
            min={15}
            max={70}
            step={5}
            unit="px"
            onChange={(val) => updateSettings({ dwell_radius_px: val })}
            helperText="Pixel distance tolerance for ocular stability. Default: 35px."
          />
        </SettingsCard>

        {/* Local Storage & Privacy Management */}
        <SettingsCard
          title="Local Privacy & Calibration Reset"
          description="All tracking coordinates and facial vectors stay local on this hardware."
          icon={ShieldCheck}
        >
          <div className="text-xs text-txt-muted space-y-2 leading-relaxed">
            <p>
              MotionEase adheres to a strict zero-cloud architecture. Facial landmarks, voice audio chunks, and gaze coordinates are never stored permanently or uploaded.
            </p>
            <div className="pt-2 flex flex-wrap gap-2">
              <button
                onClick={() => {
                  resetCalibration();
                  addToast('Calibration file deleted and reset', 'info');
                }}
                className="btn-secondary h-8 px-3 text-xs text-red-400 hover:border-red-400"
              >
                Clear Calibration Data
              </button>
            </div>
          </div>
        </SettingsCard>
      </div>
    </div>
  );
};

export default AccessibilitySettingsPage;
