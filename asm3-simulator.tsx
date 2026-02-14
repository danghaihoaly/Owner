import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Play, Pause, RotateCcw, Settings } from 'lucide-react';

const ASM3Simulator = () => {
  // State variables for ASM3 (all in g COD/m³ or g N/m³)
  const [config, setConfig] = useState({
    reactorVolume: 1000, // m³
    flowRate: 100, // m³/h
    srt: 10, // days
    rasRatio: 1.0, // RAS/Q
    mlrRatio: 2.0, // MLR/Q (mixed liquor recycle from aerobic to anoxic)
    anoxicFraction: 0.3, // fraction of reactor volume that is anoxic
    temperature: 20, // °C
    doAerobic: 2.0, // mg/L in aerobic zone
    doAnoxic: 0.2, // mg/L in anoxic zone
  });

  // Influent characteristics
  const [influent, setInfluent] = useState({
    ss: 400, // Readily biodegradable substrate (g COD/m³)
    xs: 100, // Slowly biodegradable substrate (g COD/m³)
    xi: 50, // Inert particulate COD (g COD/m³)
    si: 30, // Inert soluble COD (g COD/m³)
    snh: 40, // Ammonia nitrogen (g N/m³)
    sno: 0, // Nitrate nitrogen (g N/m³)
    salk: 5, // Alkalinity (mol/m³)
  });

  // ASM3 kinetic and stoichiometric parameters (at 20°C)
  const params = {
    // Heterotrophs
    muH: 2.0, // Maximum growth rate on storage (1/d)
    qfe: 3.0, // Rate constant for storage of SS (1/d)
    bH: 0.2, // Endogenous respiration rate (1/d)
    KO2: 0.2, // Oxygen saturation constant (g O2/m³)
    KNO3: 0.5, // Nitrate saturation constant (g N/m³)
    KS: 2.0, // Saturation constant for SS (g COD/m³)
    KSto: 1.0, // Saturation constant for XSTO (g COD/m³)
    KALK: 0.1, // Alkalinity saturation constant (mol/m³)
    KNH4_H: 0.01, // Ammonia saturation for heterotrophs (g N/m³)
    
    // Autotrophs (nitrifiers)
    muA: 1.0, // Maximum growth rate (1/d)
    bA: 0.15, // Endogenous respiration rate (1/d)
    KNH4_A: 1.0, // Ammonia saturation constant (g N/m³)
    KO2_A: 0.5, // Oxygen saturation for autotrophs (g O2/m³)
    KALK_A: 0.5, // Alkalinity saturation for autotrophs (mol/m³)
    
    // Stoichiometry
    YH: 0.63, // Yield of heterotrophs on storage (g COD/g COD)
    YSto: 0.85, // Yield of storage on SS (g COD/g COD)
    YA: 0.24, // Yield of autotrophs (g COD/g N)
    fXI: 0.1, // Fraction of XI in biomass
    iNBM: 0.07, // N content of biomass (g N/g COD)
    iNXI: 0.02, // N content of XI (g N/g COD)
    
    // Hydrolysis
    kh: 3.0, // Maximum hydrolysis rate (1/d)
    KX: 1.0, // Hydrolysis saturation constant (g COD/g COD)
    etaNO3: 0.6, // Reduction factor for anoxic activity
  };

  // State variables (concentrations in reactor)
  const [state, setState] = useState({
    // Anoxic zone
    anoxic: {
      ss: 5, // Readily biodegradable substrate
      xs: 100, // Slowly biodegradable substrate
      xi: 1000, // Inert particulate
      si: 30, // Inert soluble
      xsto: 50, // Storage polymers
      xh: 2000, // Heterotrophic biomass
      xa: 100, // Autotrophic biomass
      snh: 2, // Ammonia
      sno: 5, // Nitrate
      salk: 4, // Alkalinity
      so2: 0.2, // Dissolved oxygen
    },
    // Aerobic zone
    aerobic: {
      ss: 2,
      xs: 80,
      xi: 1000,
      si: 30,
      xsto: 30,
      xh: 2000,
      xa: 100,
      snh: 1,
      sno: 8,
      salk: 3.5,
      so2: 2.0,
    },
  });

  const [effluent, setEffluent] = useState({
    ss: 0, xs: 0, xi: 0, si: 0, xsto: 0, xh: 0, xa: 0,
    snh: 0, sno: 0, salk: 0, so2: 0,
    totalCOD: 0, totalN: 0, tss: 0,
  });

  const [history, setHistory] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [time, setTime] = useState(0);
  const [showSettings, setShowSettings] = useState(false);

  const dt = 0.01; // time step in days (about 15 minutes)
  const maxHistory = 500;

  // Temperature correction
  const tempCorrect = (k, temp) => k * Math.pow(1.07, temp - 20);

  // Monod/switching functions
  const monod = (S, K) => S / (K + S);
  const switchO2 = (SO, KO) => SO / (KO + SO);
  const switchNO3 = (SO, SNO, KO, KNO) => (KO / (KO + SO)) * (SNO / (KNO + SNO));

  // ASM3 process rates
  const calculateRates = (s, so2, temp) => {
    const p = { ...params };
    
    // Temperature corrections
    const muH_T = tempCorrect(p.muH, temp);
    const qfe_T = tempCorrect(p.qfe, temp);
    const bH_T = tempCorrect(p.bH, temp);
    const muA_T = tempCorrect(p.muA, temp);
    const bA_T = tempCorrect(p.bA, temp);
    const kh_T = tempCorrect(p.kh, temp);

    const rates = {};
    
    // 1. Storage of SS (aerobic)
    rates.r1_ae = qfe_T * monod(s.ss, p.KS) * monod(s.salk, p.KALK) * 
                  switchO2(so2, p.KO2) * s.xh;
    
    // 2. Storage of SS (anoxic)
    rates.r1_an = p.etaNO3 * qfe_T * monod(s.ss, p.KS) * monod(s.salk, p.KALK) * 
                  switchNO3(so2, s.sno, p.KO2, p.KNO3) * s.xh;
    
    // 3. Growth on XSTO (aerobic)
    rates.r2_ae = muH_T * monod(s.xsto / s.xh, p.KSto) * monod(s.snh, p.KNH4_H) * 
                  monod(s.salk, p.KALK) * switchO2(so2, p.KO2) * s.xh;
    
    // 4. Growth on XSTO (anoxic)
    rates.r2_an = p.etaNO3 * muH_T * monod(s.xsto / s.xh, p.KSto) * 
                  monod(s.snh, p.KNH4_H) * monod(s.salk, p.KALK) * 
                  switchNO3(so2, s.sno, p.KO2, p.KNO3) * s.xh;
    
    // 5. Endogenous respiration of heterotrophs (aerobic)
    rates.r3_ae = bH_T * monod(s.salk, p.KALK) * switchO2(so2, p.KO2) * s.xh;
    
    // 6. Endogenous respiration of heterotrophs (anoxic)
    rates.r3_an = p.etaNO3 * bH_T * monod(s.salk, p.KALK) * 
                  switchNO3(so2, s.sno, p.KO2, p.KNO3) * s.xh;
    
    // 7. Growth of autotrophs (nitrification)
    rates.r4 = muA_T * monod(s.snh, p.KNH4_A) * monod(s.salk, p.KALK_A) * 
               switchO2(so2, p.KO2_A) * s.xa;
    
    // 8. Endogenous respiration of autotrophs
    rates.r5 = bA_T * monod(s.salk, p.KALK_A) * switchO2(so2, p.KO2_A) * s.xa;
    
    // 9. Hydrolysis (aerobic)
    rates.r6_ae = kh_T * monod(s.xs / s.xh, p.KX) * 
                  monod(s.salk, p.KALK) * switchO2(so2, p.KO2) * s.xh;
    
    // 10. Hydrolysis (anoxic)
    rates.r6_an = p.etaNO3 * kh_T * monod(s.xs / s.xh, p.KX) * 
                  monod(s.salk, p.KALK) * switchNO3(so2, s.sno, p.KO2, p.KNO3) * s.xh;

    return rates;
  };

  // Calculate derivatives
  const derivatives = (s, so2, temp, rates) => {
    const p = params;
    const ds = {};

    // Substrate
    ds.ss = -(1/p.YSto) * (rates.r1_ae + rates.r1_an) + rates.r6_ae + rates.r6_an;
    
    // Storage polymers
    ds.xsto = rates.r1_ae + rates.r1_an - (1/p.YH) * (rates.r2_ae + rates.r2_an);
    
    // Heterotrophs
    ds.xh = rates.r2_ae + rates.r2_an - rates.r3_ae - rates.r3_an;
    
    // Autotrophs
    ds.xa = rates.r4 - rates.r5;
    
    // Slowly biodegradable substrate
    ds.xs = -(rates.r6_ae + rates.r6_an) + 
            (1 - p.fXI) * (rates.r3_ae + rates.r3_an + rates.r5);
    
    // Inert particulate
    ds.xi = p.fXI * (rates.r3_ae + rates.r3_an + rates.r5);
    
    // Ammonia
    ds.snh = -p.iNBM * (rates.r2_ae + rates.r2_an) - 
             (p.iNBM + 1/p.YA) * rates.r4 +
             (p.iNBM - p.fXI * p.iNXI) * (rates.r3_ae + rates.r3_an + rates.r5);
    
    // Nitrate
    ds.sno = (1 - 1/p.YA) * rates.r4 - 
             ((1 - p.YH) / (2.86 * p.YH)) * (rates.r1_an + rates.r2_an) -
             (1 / 2.86) * (rates.r3_an);
    
    // Alkalinity (simplified)
    ds.salk = -(p.iNBM / 14) * (rates.r2_ae + rates.r2_an) -
              (p.iNBM / 14 + 1 / (7 * p.YA)) * rates.r4 +
              (p.iNBM / 14) * (rates.r3_ae + rates.r3_an + rates.r5) +
              (1 / (14 * 2.86)) * (rates.r1_an + rates.r2_an + rates.r3_an);
    
    // Inert soluble
    ds.si = 0;
    
    // Oxygen (will be controlled)
    ds.so2 = 0;

    return ds;
  };

  // Simulation step
  const simulateStep = () => {
    const Q = config.flowRate;
    const V_anoxic = config.reactorVolume * config.anoxicFraction;
    const V_aerobic = config.reactorVolume * (1 - config.anoxicFraction);
    const Qr = Q * config.rasRatio;
    const Qmlr = Q * config.mlrRatio;

    // Calculate rates for both zones
    const rates_anoxic = calculateRates(state.anoxic, config.doAnoxic, config.temperature);
    const rates_aerobic = calculateRates(state.aerobic, config.doAerobic, config.temperature);

    // Calculate derivatives
    const ds_anoxic = derivatives(state.anoxic, config.doAnoxic, config.temperature, rates_anoxic);
    const ds_aerobic = derivatives(state.aerobic, config.doAerobic, config.temperature, rates_aerobic);

    // Calculate waste sludge flow (from SRT)
    const HRT = config.reactorVolume / Q; // hours
    const SRT_days = config.srt;
    const Qw = config.reactorVolume / SRT_days / 24; // m³/h

    // Mass balance - Anoxic zone (receives influent + MLR)
    const newAnoxic = { ...state.anoxic };
    Object.keys(newAnoxic).forEach(key => {
      if (key === 'so2') {
        newAnoxic[key] = config.doAnoxic; // Controlled
      } else {
        const biological = ds_anoxic[key] || 0;
        const inflow = (Q * (influent[key] || 0) + Qmlr * state.aerobic[key]) / V_anoxic;
        const outflow = (Q + Qmlr) * state.anoxic[key] / V_anoxic;
        newAnoxic[key] = Math.max(0, state.anoxic[key] + dt * (biological + inflow - outflow));
      }
    });

    // Mass balance - Aerobic zone (receives anoxic effluent + RAS)
    const newAerobic = { ...state.aerobic };
    
    // Underflow concentration from settler (approximation)
    const TSS_aerobic = state.aerobic.xh + state.aerobic.xa + state.aerobic.xi + state.aerobic.xs;
    const concentrationFactor = 2.0; // Settler concentrates sludge by factor of 2
    
    Object.keys(newAerobic).forEach(key => {
      if (key === 'so2') {
        newAerobic[key] = config.doAerobic; // Controlled
      } else {
        const biological = ds_aerobic[key] || 0;
        const particulate = ['xh', 'xa', 'xi', 'xs', 'xsto'].includes(key);
        const rasConc = particulate ? state.aerobic[key] * concentrationFactor : state.aerobic[key];
        const inflow = ((Q + Qmlr) * state.anoxic[key] + Qr * rasConc) / V_aerobic;
        const outflow = (Q + Qmlr + Qr) * state.aerobic[key] / V_aerobic;
        newAerobic[key] = Math.max(0, state.aerobic[key] + dt * (biological + inflow - outflow));
      }
    });

    setState({
      anoxic: newAnoxic,
      aerobic: newAerobic,
    });

    // Calculate effluent (from aerobic zone after settling)
    const newEffluent = { ...state.aerobic };
    
    // Settling removes most particulate matter
    const settlingEfficiency = 0.98;
    newEffluent.xh *= (1 - settlingEfficiency);
    newEffluent.xa *= (1 - settlingEfficiency);
    newEffluent.xi *= (1 - settlingEfficiency);
    newEffluent.xs *= (1 - settlingEfficiency);
    newEffluent.xsto *= (1 - settlingEfficiency);
    
    newEffluent.totalCOD = newEffluent.ss + newEffluent.xs + newEffluent.xi + newEffluent.si + 
                          newEffluent.xsto + newEffluent.xh + newEffluent.xa;
    newEffluent.totalN = newEffluent.snh + newEffluent.sno + 
                        params.iNBM * (newEffluent.xh + newEffluent.xa) +
                        params.iNXI * newEffluent.xi;
    newEffluent.tss = 0.75 * (newEffluent.xh + newEffluent.xa + newEffluent.xi + newEffluent.xs);

    setEffluent(newEffluent);

    // Update history
    setHistory(prev => {
      const newHistory = [...prev, {
        time: time,
        // Effluent quality
        effCOD: newEffluent.totalCOD,
        effNH4: newEffluent.snh,
        effNO3: newEffluent.sno,
        effTN: newEffluent.totalN,
        effTSS: newEffluent.tss,
        // Anoxic zone
        anoxicSS: state.anoxic.ss,
        anoxicSTO: state.anoxic.xsto,
        anoxicXH: state.anoxic.xh,
        anoxicNO3: state.anoxic.sno,
        // Aerobic zone
        aerobicSS: state.aerobic.ss,
        aerobicSTO: state.aerobic.xsto,
        aerobicXH: state.aerobic.xh,
        aerobicXA: state.aerobic.xa,
        aerobicNH4: state.aerobic.snh,
        aerobicNO3: state.aerobic.sno,
      }];
      return newHistory.slice(-maxHistory);
    });

    setTime(t => t + dt);
  };

  useEffect(() => {
    let interval;
    if (isRunning) {
      interval = setInterval(simulateStep, 50);
    }
    return () => clearInterval(interval);
  }, [isRunning, state, config, influent, time]);

  const reset = () => {
    setState({
      anoxic: {
        ss: 5, xs: 100, xi: 1000, si: 30, xsto: 50, xh: 2000, xa: 100,
        snh: 2, sno: 5, salk: 4, so2: 0.2,
      },
      aerobic: {
        ss: 2, xs: 80, xi: 1000, si: 30, xsto: 30, xh: 2000, xa: 100,
        snh: 1, sno: 8, salk: 3.5, so2: 2.0,
      },
    });
    setHistory([]);
    setTime(0);
    setIsRunning(false);
  };

  return (
    <div className="w-full h-screen bg-gray-50 p-4 overflow-auto">
      <div className="max-w-7xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-4">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h1 className="text-3xl font-bold text-blue-900">ASM3 Wastewater Treatment Simulator</h1>
              <p className="text-gray-600">Time: {time.toFixed(2)} days ({(time * 24).toFixed(1)} hours)</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setIsRunning(!isRunning)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                {isRunning ? <><Pause size={20} /> Pause</> : <><Play size={20} /> Run</>}
              </button>
              <button
                onClick={reset}
                className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
              >
                <RotateCcw size={20} /> Reset
              </button>
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
              >
                <Settings size={20} /> Settings
              </button>
            </div>
          </div>

          {/* Settings Panel */}
          {showSettings && (
            <div className="grid grid-cols-3 gap-4 mb-6 p-4 bg-gray-100 rounded-lg">
              <div>
                <h3 className="font-bold mb-2">Reactor Configuration</h3>
                <label className="block text-sm mb-1">
                  Volume (m³): {config.reactorVolume}
                  <input
                    type="range"
                    min="500"
                    max="3000"
                    value={config.reactorVolume}
                    onChange={(e) => setConfig({...config, reactorVolume: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
                <label className="block text-sm mb-1">
                  Flow Rate (m³/h): {config.flowRate}
                  <input
                    type="range"
                    min="50"
                    max="300"
                    value={config.flowRate}
                    onChange={(e) => setConfig({...config, flowRate: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
                <label className="block text-sm mb-1">
                  Anoxic Fraction: {config.anoxicFraction.toFixed(2)}
                  <input
                    type="range"
                    min="0"
                    max="0.5"
                    step="0.05"
                    value={config.anoxicFraction}
                    onChange={(e) => setConfig({...config, anoxicFraction: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
              </div>

              <div>
                <h3 className="font-bold mb-2">Operating Conditions</h3>
                <label className="block text-sm mb-1">
                  SRT (days): {config.srt}
                  <input
                    type="range"
                    min="3"
                    max="30"
                    value={config.srt}
                    onChange={(e) => setConfig({...config, srt: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
                <label className="block text-sm mb-1">
                  RAS Ratio: {config.rasRatio.toFixed(1)}
                  <input
                    type="range"
                    min="0.5"
                    max="2"
                    step="0.1"
                    value={config.rasRatio}
                    onChange={(e) => setConfig({...config, rasRatio: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
                <label className="block text-sm mb-1">
                  MLR Ratio: {config.mlrRatio.toFixed(1)}
                  <input
                    type="range"
                    min="0"
                    max="5"
                    step="0.5"
                    value={config.mlrRatio}
                    onChange={(e) => setConfig({...config, mlrRatio: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
                <label className="block text-sm mb-1">
                  Temperature (°C): {config.temperature}
                  <input
                    type="range"
                    min="10"
                    max="30"
                    value={config.temperature}
                    onChange={(e) => setConfig({...config, temperature: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
              </div>

              <div>
                <h3 className="font-bold mb-2">Influent (g/m³)</h3>
                <label className="block text-sm mb-1">
                  SS (COD): {influent.ss}
                  <input
                    type="range"
                    min="100"
                    max="800"
                    value={influent.ss}
                    onChange={(e) => setInfluent({...influent, ss: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
                <label className="block text-sm mb-1">
                  XS (COD): {influent.xs}
                  <input
                    type="range"
                    min="50"
                    max="300"
                    value={influent.xs}
                    onChange={(e) => setInfluent({...influent, xs: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
                <label className="block text-sm mb-1">
                  NH4-N: {influent.snh}
                  <input
                    type="range"
                    min="10"
                    max="80"
                    value={influent.snh}
                    onChange={(e) => setInfluent({...influent, snh: Number(e.target.value)})}
                    className="w-full"
                  />
                </label>
              </div>
            </div>
          )}

          {/* Performance Metrics */}
          <div className="grid grid-cols-5 gap-4 mb-6">
            <div className="bg-blue-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600">Effluent COD</div>
              <div className="text-2xl font-bold text-blue-900">{effluent.totalCOD.toFixed(1)}</div>
              <div className="text-xs text-gray-500">g COD/m³</div>
            </div>
            <div className="bg-green-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600">NH4-N</div>
              <div className="text-2xl font-bold text-green-900">{effluent.snh.toFixed(2)}</div>
              <div className="text-xs text-gray-500">g N/m³</div>
            </div>
            <div className="bg-purple-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600">NO3-N</div>
              <div className="text-2xl font-bold text-purple-900">{effluent.sno.toFixed(2)}</div>
              <div className="text-xs text-gray-500">g N/m³</div>
            </div>
            <div className="bg-orange-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600">Total N</div>
              <div className="text-2xl font-bold text-orange-900">{effluent.totalN.toFixed(2)}</div>
              <div className="text-xs text-gray-500">g N/m³</div>
            </div>
            <div className="bg-red-50 p-4 rounded-lg">
              <div className="text-sm text-gray-600">TSS</div>
              <div className="text-2xl font-bold text-red-900">{effluent.tss.toFixed(1)}</div>
              <div className="text-xs text-gray-500">g/m³</div>
            </div>
          </div>

          {/* Charts */}
          <div className="space-y-6">
            {/* Effluent Quality */}
            <div>
              <h3 className="text-lg font-bold mb-2">Effluent Quality Over Time</h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" label={{ value: 'Time (days)', position: 'insideBottom', offset: -5 }} />
                  <YAxis label={{ value: 'Concentration', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="effCOD" stroke="#2563eb" name="COD" dot={false} />
                  <Line type="monotone" dataKey="effNH4" stroke="#10b981" name="NH4-N" dot={false} />
                  <Line type="monotone" dataKey="effNO3" stroke="#8b5cf6" name="NO3-N" dot={false} />
                  <Line type="monotone" dataKey="effTN" stroke="#f59e0b" name="Total N" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Anoxic Zone */}
            <div>
              <h3 className="text-lg font-bold mb-2">Anoxic Zone Dynamics</h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" label={{ value: 'Time (days)', position: 'insideBottom', offset: -5 }} />
                  <YAxis label={{ value: 'Concentration (g/m³)', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="anoxicSS" stroke="#ef4444" name="SS" dot={false} />
                  <Line type="monotone" dataKey="anoxicSTO" stroke="#f97316" name="Storage" dot={false} />
                  <Line type="monotone" dataKey="anoxicXH" stroke="#3b82f6" name="Heterotrophs" dot={false} />
                  <Line type="monotone" dataKey="anoxicNO3" stroke="#8b5cf6" name="NO3-N" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Aerobic Zone */}
            <div>
              <h3 className="text-lg font-bold mb-2">Aerobic Zone Dynamics</h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" label={{ value: 'Time (days)', position: 'insideBottom', offset: -5 }} />
                  <YAxis label={{ value: 'Concentration (g/m³)', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="aerobicSS" stroke="#ef4444" name="SS" dot={false} />
                  <Line type="monotone" dataKey="aerobicSTO" stroke="#f97316" name="Storage" dot={false} />
                  <Line type="monotone" dataKey="aerobicXH" stroke="#3b82f6" name="Heterotrophs" dot={false} />
                  <Line type="monotone" dataKey="aerobicXA" stroke="#10b981" name="Autotrophs" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Nitrogen Species in Aerobic Zone */}
            <div>
              <h3 className="text-lg font-bold mb-2">Nitrogen Species (Aerobic Zone)</h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" label={{ value: 'Time (days)', position: 'insideBottom', offset: -5 }} />
                  <YAxis label={{ value: 'Concentration (g N/m³)', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="aerobicNH4" stroke="#10b981" name="NH4-N" dot={false} />
                  <Line type="monotone" dataKey="aerobicNO3" stroke="#8b5cf6" name="NO3-N" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Current State Display */}
          <div className="mt-6 grid grid-cols-2 gap-4">
            <div className="bg-gray-50 p-4 rounded-lg">
              <h3 className="font-bold mb-3 text-lg">Anoxic Zone State</h3>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>SS: {state.anoxic.ss.toFixed(2)} g COD/m³</div>
                <div>XS: {state.anoxic.xs.toFixed(1)} g COD/m³</div>
                <div>X_STO: {state.anoxic.xsto.toFixed(1)} g COD/m³</div>
                <div>X_H: {state.anoxic.xh.toFixed(0)} g COD/m³</div>
                <div>X_A: {state.anoxic.xa.toFixed(1)} g COD/m³</div>
                <div>NH4-N: {state.anoxic.snh.toFixed(2)} g N/m³</div>
                <div>NO3-N: {state.anoxic.sno.toFixed(2)} g N/m³</div>
                <div>DO: {state.anoxic.so2.toFixed(2)} mg/L</div>
              </div>
            </div>

            <div className="bg-gray-50 p-4 rounded-lg">
              <h3 className="font-bold mb-3 text-lg">Aerobic Zone State</h3>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>SS: {state.aerobic.ss.toFixed(2)} g COD/m³</div>
                <div>XS: {state.aerobic.xs.toFixed(1)} g COD/m³</div>
                <div>X_STO: {state.aerobic.xsto.toFixed(1)} g COD/m³</div>
                <div>X_H: {state.aerobic.xh.toFixed(0)} g COD/m³</div>
                <div>X_A: {state.aerobic.xa.toFixed(1)} g COD/m³</div>
                <div>NH4-N: {state.aerobic.snh.toFixed(2)} g N/m³</div>
                <div>NO3-N: {state.aerobic.sno.toFixed(2)} g N/m³</div>
                <div>DO: {state.aerobic.so2.toFixed(2)} mg/L</div>
              </div>
            </div>
          </div>

          {/* Process Information */}
          <div className="mt-6 bg-blue-50 p-4 rounded-lg">
            <h3 className="font-bold mb-2">ASM3 Key Features</h3>
            <ul className="text-sm space-y-1">
              <li><strong>Storage Polymers:</strong> Readily biodegradable substrate (SS) is first stored as X_STO before being used for growth</li>
              <li><strong>Nitrification:</strong> Autotrophs (X_A) convert NH4-N to NO3-N in aerobic conditions</li>
              <li><strong>Denitrification:</strong> Heterotrophs use NO3-N as electron acceptor in anoxic zone, producing N2 gas</li>
              <li><strong>Hydrolysis:</strong> Slowly biodegradable substrate (XS) is broken down to SS</li>
              <li><strong>Endogenous Respiration:</strong> Biomass decay produces inert material (XI) and releases nutrients</li>
            </ul>
          </div>

          {/* Operation Tips */}
          <div className="mt-4 bg-green-50 p-4 rounded-lg">
            <h3 className="font-bold mb-2">Operation Tips</h3>
            <ul className="text-sm space-y-1">
              <li><strong>SRT:</strong> Higher SRT improves nitrification but increases oxygen demand (typical: 8-15 days)</li>
              <li><strong>Anoxic Fraction:</strong> Increase for better denitrification (typical: 20-40%)</li>
              <li><strong>MLR:</strong> Higher mixed liquor recycle improves nitrogen removal by returning NO3 to anoxic zone</li>
              <li><strong>RAS:</strong> Maintains desired MLSS concentration (typical: 0.5-1.5)</li>
              <li><strong>Temperature:</strong> Higher temperature increases reaction rates but reduces oxygen solubility</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ASM3Simulator;