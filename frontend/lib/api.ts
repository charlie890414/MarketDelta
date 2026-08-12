import createClient from "openapi-fetch";
import type { paths } from "./generated/api";

const base = typeof window === "undefined"
  ? process.env.API_INTERNAL_URL ?? "http://localhost:8000"
  : process.env.NEXT_PUBLIC_API_URL ?? "/api";
const client = createClient<paths>({ baseUrl: base });
export type Change = paths["/changes"]["get"]["responses"][200]["content"]["application/json"][number];

export async function getChanges(
  filters: {
    market?: string;
    category?: string;
    severity?: string;
    minScore?: number;
    hours?: number;
    watchlistId?: number;
  } = {},
): Promise<Change[]> {
  const { data, error } = await client.GET("/changes", {
    params: {
      query: {
        min_score: filters.minScore ?? 50,
        hours: filters.hours ?? 24,
        limit: 100,
        market: filters.market,
        category: filters.category,
        severity: filters.severity,
        watchlist_id: filters.watchlistId,
      },
    },
  });
  if (error || !data) throw new Error("Change feed unavailable");
  return data;
}

export async function getChange(changeId: number): Promise<Change> {
  const { data, error } = await client.GET("/changes/{change_id}", {
    params: { path: { change_id: changeId } },
  });
  if (error || !data) throw new Error("Change unavailable");
  return data;
}

export async function getCompany(symbol: string) {
  const { data, error } = await client.GET("/companies/{symbol}", { params: { path: { symbol } } });
  if (error || !data) throw new Error("Company unavailable");
  return data;
}

export async function createCompany(body: {
  symbol: string;
  market: "TW" | "US";
  exchange?: string;
  company_name?: string;
}) {
  const { data, error } = await client.POST("/companies", { body });
  if (error || !data) throw new Error("Company creation failed");
  return data;
}

export async function getCompanyChanges(symbol: string): Promise<Change[]> {
  const { data, error } = await client.GET("/companies/{symbol}/changes", { params: { path: { symbol } } });
  if (error || !data) throw new Error("Company changes unavailable");
  return data;
}

export async function getCompanyHistory(symbol: string) {
  const { data, error } = await client.GET("/companies/{symbol}/history", { params: { path: { symbol } } });
  if (error || !data) throw new Error("Company history unavailable");
  return data;
}

export async function getCompanyEvents(symbol: string) {
  const { data, error } = await client.GET("/companies/{symbol}/events", { params: { path: { symbol } } });
  if (error || !data) throw new Error("Company events unavailable");
  return data;
}

export async function getWatchlists() {
  const { data, error } = await client.GET("/watchlists");
  if (error || !data) throw new Error("Watchlists unavailable");
  return data;
}

export async function getWatchlistItems(watchlistId: number) {
  const { data, error } = await client.GET("/watchlists/{watchlist_id}/items", { params: { path: { watchlist_id: watchlistId } } });
  if (error || !data) throw new Error("Watchlist items unavailable");
  return data;
}

export async function getJobs() {
  const { data, error } = await client.GET("/jobs");
  if (error || !data) throw new Error("Jobs unavailable");
  return data;
}

export async function getEvents() {
  const { data, error } = await client.GET("/events", { params: { query: { days: 30 } } });
  if (error || !data) throw new Error("Events unavailable");
  return data;
}

export async function searchCompanies(q: string) {
  const { data, error } = await client.GET("/companies/search", { params: { query: { q, limit: 20 } } });
  if (error || !data) throw new Error("Company search unavailable");
  return data;
}

export async function getDailyReports(reportType?: string) {
  const { data, error } = await client.GET("/reports/daily", {
    params: { query: { report_type: reportType, limit: 30 } },
  });
  if (error || !data) throw new Error("Daily reports unavailable");
  return data;
}

export async function getAlertDeliveries() {
  const { data, error } = await client.GET("/alerts/deliveries", {
    params: { query: { limit: 50 } },
  });
  if (error || !data) throw new Error("Alert deliveries unavailable");
  return data;
}

export async function getAlerts() {
  const { data, error } = await client.GET("/alerts");
  if (error || !data) throw new Error("Alerts unavailable");
  return data;
}

export async function updateAlert(alertId: number, body: {
  name?: string;
  min_score?: number;
  category?: string | null;
  market?: string | null;
  is_enabled?: boolean;
}) {
  const { data, error } = await client.PATCH("/alerts/{alert_id}", {
    params: { path: { alert_id: alertId } },
    body,
  });
  if (error || !data) throw new Error("Alert update failed");
  return data;
}

export async function deleteAlert(alertId: number) {
  const { error } = await client.DELETE("/alerts/{alert_id}", {
    params: { path: { alert_id: alertId } },
  });
  if (error) throw new Error("Alert deletion failed");
}

export async function createWatchlist(name: string, description?: string) {
  const { data, error } = await client.POST("/watchlists", {
    body: { name, description },
  });
  if (error || !data) throw new Error("Watchlist creation failed");
  return data;
}

export async function updateWatchlist(watchlistId: number, body: { name?: string; description?: string }) {
  const { data, error } = await client.PATCH("/watchlists/{watchlist_id}", {
    params: { path: { watchlist_id: watchlistId } },
    body,
  });
  if (error || !data) throw new Error("Watchlist update failed");
  return data;
}

export async function deleteWatchlist(watchlistId: number) {
  const { error } = await client.DELETE("/watchlists/{watchlist_id}", {
    params: { path: { watchlist_id: watchlistId } },
  });
  if (error) throw new Error("Watchlist deletion failed");
}

export async function addWatchlistItem(watchlistId: number, symbol: string, priority = 0) {
  const { data, error } = await client.POST("/watchlists/{watchlist_id}/items", {
    params: { path: { watchlist_id: watchlistId } },
    body: { symbol, priority },
  });
  if (error || !data) throw new Error("Watchlist item creation failed");
  return data;
}

export async function removeWatchlistItem(watchlistId: number, instrumentId: number) {
  const { error } = await client.DELETE("/watchlists/{watchlist_id}/items/{instrument_id}", {
    params: { path: { watchlist_id: watchlistId, instrument_id: instrumentId } },
  });
  if (error) throw new Error("Watchlist item removal failed");
}

export async function getNews(category?: string) {
  const { data, error } = await client.GET("/news", {
    params: { query: { days: 7, category, limit: 100 } },
  });
  if (error || !data) throw new Error("News unavailable");
  return data;
}

export async function getCompanyInterpretations(symbol: string) {
  const { data, error } = await client.GET("/companies/{symbol}/interpretations", {
    params: { path: { symbol } },
  });
  if (error || !data) throw new Error("Interpretations unavailable");
  return data;
}

export async function getCompanyNews(symbol: string) {
  const { data, error } = await client.GET("/companies/{symbol}/news", {
    params: { path: { symbol } },
  });
  if (error || !data) throw new Error("Company news unavailable");
  return data;
}

export async function getCompanyOwnership(symbol: string) {
  const { data, error } = await client.GET("/companies/{symbol}/ownership", {
    params: { path: { symbol } },
  });
  if (error || !data) throw new Error("Ownership unavailable");
  return data;
}

export async function generateCompanyInterpretation(symbol: string) {
  const { data, error } = await client.POST("/companies/{symbol}/interpretations/generate", {
    params: { path: { symbol } },
  });
  if (error || !data) throw new Error("Interpretation generation failed");
  return data;
}
