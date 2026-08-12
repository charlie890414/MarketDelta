"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  addWatchlistItem,
  createWatchlist,
  deleteWatchlist,
  getWatchlists,
  getWatchlistItems,
  removeWatchlistItem,
  searchCompanies,
} from "../../lib/api";

type Watchlist = Awaited<ReturnType<typeof getWatchlists>>[number];

export default function WatchlistManager() {
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("");
  const [selectedList, setSelectedList] = useState<number>();
  const [matches, setMatches] = useState<Awaited<ReturnType<typeof searchCompanies>>>([]);
  const [message, setMessage] = useState("");
  const [items, setItems] = useState<Record<number, Awaited<ReturnType<typeof getWatchlistItems>>>>({});

  async function refresh() {
    const nextLists = await getWatchlists();
    setLists(nextLists);
    const entries = await Promise.all(nextLists.map(async (list) => [list.id, await getWatchlistItems(list.id)] as const));
    setItems(Object.fromEntries(entries));
  }

  useEffect(() => {
    refresh().catch(() => setMessage("Watchlist service unavailable."));
  }, []);

  async function submitList(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      await createWatchlist(name.trim());
      setName("");
      setMessage("Watchlist created.");
      await refresh();
    } catch {
      setMessage("Could not create watchlist.");
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    if (!symbol.trim()) return;
    try {
      setMatches(await searchCompanies(symbol.trim()));
    } catch {
      setMessage("Search unavailable.");
    }
  }

  async function add(symbolToAdd: string) {
    if (!selectedList) {
      setMessage("Choose a watchlist first.");
      return;
    }
    try {
      await addWatchlistItem(selectedList, symbolToAdd);
      setMessage(`${symbolToAdd} added.`);
      setMatches([]);
      setSymbol("");
      await refresh();
    } catch {
      setMessage("Could not add instrument.");
    }
  }

  async function removeItem(watchlistId: number, instrumentId: number) {
    try {
      await removeWatchlistItem(watchlistId, instrumentId);
      setItems((current) => ({ ...current, [watchlistId]: (current[watchlistId] ?? []).filter((item) => item.instrument_id !== instrumentId) }));
    } catch {
      setMessage("Could not remove instrument.");
    }
  }

  async function remove(id: number) {
    try {
      await deleteWatchlist(id);
      setMessage("Watchlist deleted.");
      await refresh();
    } catch {
      setMessage("Could not delete watchlist.");
    }
  }

  return (
    <section className="history-block">
      <div className="eyebrow">Manage tracked universe</div>
      <form className="toolbar" onSubmit={submitList}>
        <input aria-label="Watchlist name" value={name} onChange={(event) => setName(event.target.value)} placeholder="New watchlist" />
        <button className="pill selected" type="submit">CREATE</button>
      </form>
      <form className="toolbar" onSubmit={search}>
        <select aria-label="Target watchlist" value={selectedList ?? ""} onChange={(event) => setSelectedList(Number(event.target.value))}>
          <option value="">Choose list</option>
          {lists.map((list) => <option key={list.id} value={list.id}>{list.name}</option>)}
        </select>
        <input aria-label="Company search" value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="Ticker or company" />
        <button className="pill" type="submit">SEARCH</button>
      </form>
      {matches.map((match) => <div className="change" key={match.id}>
        <div className="ticker">{match.symbol}</div>
        <div className="metric">{match.company_name}<span>{match.market} / {match.exchange ?? "market"}</span></div>
        <button className="pill selected" onClick={() => add(match.symbol)}>ADD</button>
      </div>)}
      {lists.map((list) => <div className="change" key={list.id}>
        <div className="ticker">{list.name}</div>
        <div className="metric">{list.description ?? "No description"}</div>
        <button className="pill" onClick={() => remove(list.id)}>DELETE</button>
        <div className="history-list">{(items[list.id] ?? []).map((item) => <div className="history-row" key={item.instrument_id}><span className="history-metric">{item.symbol}</span><span>{item.company_name}</span><button className="pill" onClick={() => removeItem(list.id, item.instrument_id)}>REMOVE</button></div>)}</div>
      </div>)}
      {message && <div className="empty">{message}</div>}
    </section>
  );
}
