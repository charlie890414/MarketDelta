import createClient from "openapi-fetch";
import type { paths } from "./generated/api";

const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const client = createClient<paths>({ baseUrl: base });
export type Change = paths["/changes"]["get"]["responses"][200]["content"]["application/json"][number];

export async function getChanges(filters: { market?: string; category?: string } = {}): Promise<Change[]> {
  const { data, error } = await client.GET("/changes", { params: { query: { min_score: 0, hours: 8760, limit: 100, market: filters.market, category: filters.category } } });
  if (error || !data) throw new Error("Change feed unavailable");
  return data;
}

export async function getCompany(symbol: string) {
  const { data, error } = await client.GET("/companies/{symbol}", { params: { path: { symbol } } });
  if (error || !data) throw new Error("Company unavailable");
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
