import { useEffect, useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const PRIMARY_COLOR = "#4ade80";
const COMPARE_COLOR = "#60a5fa";

const RANGES = [
  { label: "1Y", days: 365 },
  { label: "5Y", days: 365 * 5 },
  { label: "10Y", days: 365 * 10 },
  { label: "All", days: 365 * 50 },
];

function titleCase(s) {
  return s
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/Padd/g, "PADD")
    .replace(/U\.s\./, "U.S.");
}

function App() {
  const [prices, setPrices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [range, setRange] = useState(RANGES[0]);
  const [areas, setAreas] = useState([]);
  const [area, setArea] = useState("U.S.");
  const [compareArea, setCompareArea] = useState("");
  const [compareData, setCompareData] = useState([]);

  useEffect(() => {
    fetch(`${API_URL}/api/areas`)
      .then((res) => res.json())
      .then(setAreas)
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      area_name: area,
      grade: "regular",
      days: String(range.days),
    });
    fetch(`${API_URL}/api/prices?${params}`)
      .then((res) => res.json())
      .then((data) => {
        const clean = (data || []).filter(
          (p) => typeof p.price === "number" && Number.isFinite(p.price),
        );
        setPrices(clean);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [range, area]);

  useEffect(() => {
    if (!compareArea) {
      setCompareData([]);
      return;
    }
    const params = new URLSearchParams({
      area_name: compareArea,
      grade: "regular",
      days: String(range.days),
    });
    fetch(`${API_URL}/api/prices?${params}`)
      .then((res) => res.json())
      .then((data) => {
        const clean = (data || []).filter(
          (p) => typeof p.price === "number" && Number.isFinite(p.price),
        );
        setCompareData(clean);
      })
      .catch(() => setCompareData([]));
  }, [range, compareArea]);

  const chartData = useMemo(() => {
    const map = new Map();
    prices.forEach((p) => {
      map.set(p.date, { date: p.date, primary: p.price });
    });
    compareData.forEach((p) => {
      const existing = map.get(p.date) || { date: p.date };
      existing.compare = p.price;
      map.set(p.date, existing);
    });
    return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [prices, compareData]);

  const stats = useMemo(() => computeStats(prices), [prices]);
  const compareStats = useMemo(() => computeStats(compareData), [compareData]);

  const diffStats = useMemo(() => {
    if (!compareArea || !chartData.length) return null;
    const both = chartData.filter(
      (d) => typeof d.primary === "number" && typeof d.compare === "number",
    );
    if (!both.length) return null;
    const avg = both.reduce((s, d) => s + (d.primary - d.compare), 0) / both.length;
    const last = both[both.length - 1];
    const current = last.primary - last.compare;
    return { avg, current };
  }, [chartData, compareArea]);

  const formatDate = (d) => {
    const date = new Date(d);
    if (range.days > 365 * 3) return String(date.getFullYear());
    return date.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  };

  return (
    <div
      style={{
        padding: 24,
        fontFamily: "system-ui, sans-serif",
        color: "#e5e7eb",
        maxWidth: 1100,
        margin: "0 auto",
      }}
    >
      <header
        style={{
          marginBottom: 24,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 28 }}>
            {compareArea
              ? `${titleCase(area)} vs. ${titleCase(compareArea)}`
              : area === "U.S."
                ? "U.S. Gas Prices"
                : `${titleCase(area)} Gas Prices`}
          </h1>
          <p style={{ margin: "4px 0 0", color: "#9ca3af" }}>
            Regular unleaded · weekly EIA data
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 220 }}>
          <PickerRow label="Area" color={PRIMARY_COLOR}>
            <select
              value={area}
              onChange={(e) => {
                setArea(e.target.value);
                if (e.target.value === compareArea) setCompareArea("");
              }}
              style={selectStyle}
            >
              {areas.length === 0 && <option>{area}</option>}
              {areas.map((a) => (
                <option key={a} value={a}>
                  {titleCase(a)}
                </option>
              ))}
            </select>
          </PickerRow>
          <PickerRow label="Compare with" color={compareArea ? COMPARE_COLOR : "#374151"}>
            <select
              value={compareArea}
              onChange={(e) => setCompareArea(e.target.value)}
              style={selectStyle}
            >
              <option value="">None</option>
              {areas
                .filter((a) => a !== area)
                .map((a) => (
                  <option key={a} value={a}>
                    {titleCase(a)}
                  </option>
                ))}
            </select>
          </PickerRow>
        </div>
      </header>

      {error && <p style={{ color: "#f87171" }}>Error: {error}</p>}

      {stats && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 12,
            marginBottom: 24,
          }}
        >
          <StatCard
            label="Current"
            primary={priceRow(stats.current, area, PRIMARY_COLOR)}
            compare={compareStats && priceRow(compareStats.current, compareArea, COMPARE_COLOR)}
          />
          <StatCard
            label={`${range.label} change`}
            primary={changeRow(stats.periodChange, stats.first?.date, area, PRIMARY_COLOR)}
            compare={
              compareStats &&
              changeRow(compareStats.periodChange, compareStats.first?.date, compareArea, COMPARE_COLOR)
            }
          />
          <StatCard
            label="Range high"
            primary={priceRow(stats.high, area, PRIMARY_COLOR)}
            compare={compareStats && priceRow(compareStats.high, compareArea, COMPARE_COLOR)}
          />
          <StatCard
            label="Range low"
            primary={priceRow(stats.low, area, PRIMARY_COLOR)}
            compare={compareStats && priceRow(compareStats.low, compareArea, COMPARE_COLOR)}
          />
          {diffStats && (
            <StatCard
              label="Difference"
              primary={{
                value: `$${Math.abs(diffStats.avg).toFixed(3)}`,
                sub: `${titleCase(diffStats.avg >= 0 ? area : compareArea)} higher · Avg.`,
                color: PRIMARY_COLOR,
                secondColor: COMPARE_COLOR,
              }}
              compare={{
                value: `$${Math.abs(diffStats.current).toFixed(3)}`,
                sub: `${titleCase(diffStats.current >= 0 ? area : compareArea)} higher · Now`,
                color: PRIMARY_COLOR,
                secondColor: COMPARE_COLOR,
              }}
            />
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {RANGES.map((r) => (
          <button
            key={r.label}
            onClick={() => setRange(r)}
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              border: "1px solid #374151",
              background: range.label === r.label ? "#4ade80" : "transparent",
              color: range.label === r.label ? "#0a0a0a" : "#e5e7eb",
              cursor: "pointer",
              fontWeight: 500,
            }}
          >
            {r.label}
          </button>
        ))}
      </div>

      <div
        style={{
          width: "100%",
          height: 420,
          background: "#111827",
          borderRadius: 8,
          padding: 16,
          boxSizing: "border-box",
        }}
      >
        {loading ? (
          <p style={{ color: "#9ca3af" }}>Loading...</p>
        ) : (
          <ResponsiveContainer>
            <LineChart data={chartData} margin={{ top: 20, right: 24, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="date"
                tickFormatter={formatDate}
                stroke="#9ca3af"
                minTickGap={40}
              />
              <YAxis
                domain={["auto", "auto"]}
                tickFormatter={(v) => `$${v.toFixed(2)}`}
                stroke="#9ca3af"
              />
              <Tooltip
                contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 6 }}
                labelStyle={{ color: "#9ca3af" }}
                formatter={(v) => (typeof v === "number" ? `$${v.toFixed(3)}` : v)}
              />
              {compareArea && (
                <Legend
                  wrapperStyle={{ paddingTop: 8 }}
                  iconType="plainline"
                />
              )}
              {stats && !compareArea && (
                <ReferenceLine
                  y={stats.avg}
                  stroke="#9ca3af"
                  strokeDasharray="4 4"
                  label={{
                    value: `Avg  $${stats.avg.toFixed(2)}`,
                    fill: "#e5e7eb",
                    fontSize: 12,
                    fontWeight: 500,
                    position: "insideTopLeft",
                    offset: 8,
                  }}
                />
              )}
              <Line
                type="monotone"
                dataKey="primary"
                name={titleCase(area)}
                stroke={PRIMARY_COLOR}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
              {compareArea && (
                <Line
                  type="monotone"
                  dataKey="compare"
                  name={titleCase(compareArea)}
                  stroke={COMPARE_COLOR}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <p style={{ marginTop: 16, color: "#6b7280", fontSize: 12 }}>
        {prices.length} records · source: U.S. Energy Information Administration
      </p>
    </div>
  );
}

const selectStyle = {
  background: "#111827",
  color: "#e5e7eb",
  border: "1px solid #374151",
  borderRadius: 6,
  padding: "8px 12px",
  fontSize: 14,
  cursor: "pointer",
  width: "100%",
};

function PickerRow({ label, color, children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          minWidth: 110,
          color: "#9ca3af",
          fontSize: 12,
          textTransform: "uppercase",
          letterSpacing: 0.5,
        }}
      >
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: color,
            display: "inline-block",
          }}
        />
        {label}
      </div>
      <div style={{ flex: 1 }}>{children}</div>
    </div>
  );
}

function computeStats(data) {
  if (!data || !data.length) return null;
  const first = data[0];
  const current = data[data.length - 1];
  const high = data.reduce((m, p) => (p.price > m.price ? p : m), data[0]);
  const low = data.reduce((m, p) => (p.price < m.price ? p : m), data[0]);
  const periodChange =
    first.price > 0 ? ((current.price - first.price) / first.price) * 100 : null;
  const avg = data.reduce((s, p) => s + p.price, 0) / data.length;
  return { first, current, high, low, periodChange, avg };
}

function priceRow(point, areaName, color) {
  if (!point) return null;
  return {
    color,
    name: titleCase(areaName),
    value: `$${point.price.toFixed(3)}`,
    sub: point.date,
  };
}

function changeRow(pct, sinceDate, areaName, color) {
  if (pct == null) return null;
  return {
    color,
    name: titleCase(areaName),
    value: `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`,
    sub: sinceDate ? `since ${sinceDate}` : null,
    valueColor: pct >= 0 ? "#f87171" : "#4ade80",
  };
}

function StatCard({ label, primary, compare }) {
  const hasCompare = !!compare;
  return (
    <div
      style={{
        background: "#111827",
        borderRadius: 8,
        padding: "14px 16px",
        border: "1px solid #1f2937",
      }}
    >
      <div
        style={{
          color: "#9ca3af",
          fontSize: 12,
          textTransform: "uppercase",
          letterSpacing: 0.5,
          marginBottom: 8,
        }}
      >
        {label}
      </div>
      <StatRow row={primary} showDot={hasCompare} />
      {hasCompare && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid #1f2937" }}>
          <StatRow row={compare} showDot />
        </div>
      )}
    </div>
  );
}

function StatRow({ row, showDot }) {
  if (!row) return <div style={{ color: "#6b7280", fontSize: 18 }}>—</div>;
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        {showDot && (
          <span style={{ display: "flex", gap: 3, alignSelf: "center", flexShrink: 0 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: row.color,
              }}
            />
            {row.secondColor && (
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: row.secondColor,
                }}
              />
            )}
          </span>
        )}
        <span
          style={{
            color: row.valueColor || "#e5e7eb",
            fontSize: showDot ? 18 : 22,
            fontWeight: 600,
          }}
        >
          {row.value}
        </span>
      </div>
      {row.sub && (
        <div
          style={{
            color: "#6b7280",
            fontSize: 11,
            marginTop: 2,
            marginLeft: showDot ? (row.secondColor ? 27 : 16) : 0,
          }}
        >
          {row.sub}
        </div>
      )}
    </div>
  );
}

export default App;
